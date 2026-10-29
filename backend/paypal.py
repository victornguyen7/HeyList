# pyright: reportArgumentType=false
# The SDK's model parameters are unannotated with string defaults, so Pylance types them all as str.
import logging
import os
import time
import uuid
from functools import cache
from typing import Any

import requests

from paypalserversdk.configuration import Environment
from paypalserversdk.exceptions.api_exception import ApiException
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.models.amount_breakdown import AmountBreakdown
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.item_request import ItemRequest
from paypalserversdk.models.money import Money
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.payee_base import PayeeBase
from paypalserversdk.models.payment_source import PaymentSource
from paypalserversdk.models.paypal_wallet import PaypalWallet
from paypalserversdk.models.paypal_wallet_experience_context import PaypalWalletExperienceContext
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.models.refund_request import RefundRequest
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient

log = logging.getLogger(__name__)

# The requests.Session the SDK sends through. None means the SDK's own; the tests put a fake here.
session = None


class PayPalError(Exception):
    def __init__(self, status: int, issue: str | None):
        super().__init__(f"PayPal request failed: {status} {issue or ''}")
        self.status = status
        self.issue = issue


@cache
def _client() -> PaypalServersdkClient:
    client_id = os.environ.get("PAYPAL_CLIENT_ID")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")
    return PaypalServersdkClient(
        # Sandbox only (decision 17). The SDK also has PRODUCTION; it is never selected here.
        environment=Environment.SANDBOX,
        client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
            o_auth_client_id=client_id,
            o_auth_client_secret=client_secret,
            # The SDK caches the token; this refreshes it two minutes early.
            o_auth_clock_skew=120,
        ),
        http_client_instance=session,
        timeout=30,
        # The one 429 retry is done in _call, where the wait can be capped.
        max_retries=0,
    )


def _to_error(exc: ApiException) -> PayPalError:
    """Logs the debug_id PayPal support asks for, then returns an error the routes can map."""
    # The typed fields are only set when the body was a JSON object, so every read has a default.
    details = getattr(exc, "details", None) or []
    issue = (details[0].issue if details else None) or getattr(exc, "name", None)
    log.error(
        "PayPal error status=%s issue=%s debug_id=%s",
        exc.response_code,
        issue,
        getattr(exc, "debug_id", None) or exc.response.headers.get("paypal-debug-id"),
    )
    return PayPalError(exc.response_code, issue)


def _call(operation: str, options: dict, controller: str = "orders") -> Any:
    """Runs one Orders (or Payments) operation and returns its body. The SDK is synchronous, so the routes are too."""
    method = getattr(getattr(_client(), controller), operation)
    for retried in (False, True):
        try:
            return method(options).body
        except ApiException as exc:
            if exc.response_code == 429 and not retried:
                try:
                    seconds = int(exc.response.headers.get("retry-after", ""))
                except ValueError:
                    seconds = 1
                time.sleep(min(seconds or 1, 5))
                continue
            raise _to_error(exc) from None


def _usd(cents: int) -> Money:
    return Money(currency_code="USD", value=f"{cents // 100}.{cents % 100:02d}")


def create_order(items: list[dict], return_url: str, payee_email: str | None = None, venmo: bool = False) -> dict:
    """Creates an order for [{"name", "priceCents", "quantity"}, ...] and returns its ID and the PayPal page to send
    the buyer to. The caller looked the prices up; none came from the browser. With payee_email the money goes to
    that PayPal account instead of HeyList's (settle up, decision 60). A Venmo order (JS SDK v6 button, decision 67)
    names no payment source, as PayPal's v6 sample does; it is approved in Venmo's own flow, so it has no return page."""
    total = sum(item["priceCents"] * item["quantity"] for item in items)

    body = OrderRequest(
        intent=CheckoutPaymentIntent.CAPTURE,
        purchase_units=[
            PurchaseUnitRequest(
                amount=AmountWithBreakdown(
                    currency_code="USD",
                    value=_usd(total).value,
                    breakdown=AmountBreakdown(item_total=_usd(total)),
                ),
                items=[
                    # PayPal allows 127 characters for an item name.
                    ItemRequest(name=item["name"][:127], quantity=str(item["quantity"]), unit_amount=_usd(item["priceCents"]))
                    for item in items
                ],
                **({"payee": PayeeBase(email_address=payee_email)} if payee_email else {}),
            )
        ],
        # Where PayPal's hosted page sends the buyer back; it adds ?token=<order id>&PayerID=... after approval.
        # The v6 PayPal button uses the same order: when a pop-up can't open, it falls back to this redirect.
        **(
            {}
            if venmo
            else {
                "payment_source": PaymentSource(
                    paypal=PaypalWallet(experience_context=PaypalWalletExperienceContext(return_url=return_url, cancel_url=return_url))
                )
            }
        ),
    )
    order = _call("create_order", {"body": body, "paypal_request_id": str(uuid.uuid4())})
    # With payment_source.paypal, PayPal names the approval link "payer-action"; without one, "approve".
    approve_url = next((link.href for link in order.links or [] if link.rel in ("payer-action", "approve")), None)
    return {"orderId": order.id, "approveUrl": approve_url}


def capture_order(order_id: str) -> dict:
    """status is the capture's, not the order's: an order can be COMPLETED while its payment is PENDING or DECLINED
    (decision 25). Check items off only when it is COMPLETED."""
    order = _call(
        "capture_order",
        # The order ID is the idempotency key, so a repeated capture returns the first result.
        # return=representation includes the payments, which the default minimal response may leave out.
        {"id": order_id, "paypal_request_id": order_id, "prefer": "return=representation"},
    )
    capture = order.purchase_units[0].payments.captures[0]
    return {"orderId": order.id, "status": capture.status, "captureId": capture.id}


def get_order(order_id: str) -> dict:
    """The capture's current status, for an order whose capture came back PENDING. Capturing again would only
    replay the first answer (same PayPal-Request-Id), so this reads the order instead."""
    order = _call("get_order", {"id": order_id})
    # The SDK leaves absent fields off the model rather than setting them to None.
    captures = getattr(getattr(order.purchase_units[0], "payments", None), "captures", None)
    # No capture yet means nothing was paid, whatever the order's own status says.
    if not captures:
        return {"orderId": order.id, "status": "NOT_CAPTURED", "captureId": None}
    return {"orderId": order.id, "status": captures[0].status, "captureId": captures[0].id}


# Set as custom_id on HeyList's own refunds, so the refund webhook can tell them from one made in PayPal's dashboard.
REFUND_MARK = "heylist"


def refund(capture_id: str, cents: int, request_id: str) -> dict:
    """Refunds part of a capture to the buyer. request_id is the idempotency key, so a repeated call (a retried
    capture) refunds once. A call made while the same refund is still in progress waits for its result, so two
    captures at the same moment both see it (issue 45)."""
    body = RefundRequest(amount=_usd(cents), custom_id=REFUND_MARK, note_to_payer="Someone on your list had already bought this item.")
    for wait in (0.5, 1, 2, None):
        try:
            result = _call(
                "refund_captured_payment",
                {"capture_id": capture_id, "body": body, "paypal_request_id": request_id, "prefer": "return=representation"},
                "payments",
            )
            return {"refundId": result.id, "status": result.status}
        except PayPalError as exc:
            if exc.issue != "PREVIOUS_REQUEST_IN_PROGRESS" or wait is None:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


SANDBOX_API = "https://api-m.sandbox.paypal.com"
# The headers PayPal signs a webhook with, as the verify call names them.
WEBHOOK_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}


def verify_webhook(headers: dict[str, str], event: dict) -> bool:
    """True only if PayPal confirms it sent this event to our webhook (decision 66). The Server SDK has no
    notifications API, so this is two plain REST calls: a token, then verify-webhook-signature."""
    webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID")
    client_id, client_secret = os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_CLIENT_SECRET")
    if not webhook_id or not client_id or not client_secret:
        raise RuntimeError("PAYPAL_WEBHOOK_ID, PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")
    signed = {key: headers.get(name) for key, name in WEBHOOK_HEADERS.items()}
    if not all(signed.values()):
        return False
    http = session or requests.Session()
    token = http.post(f"{SANDBOX_API}/v1/oauth2/token", auth=(client_id, client_secret), data={"grant_type": "client_credentials"}, timeout=30)
    token.raise_for_status()
    answer = http.post(
        f"{SANDBOX_API}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
        json={**signed, "webhook_id": webhook_id, "webhook_event": event},
        timeout=30,
    )
    answer.raise_for_status()
    return answer.json().get("verification_status") == "SUCCESS"

