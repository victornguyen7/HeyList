import logging
import os
import time
import uuid
from functools import cache

from paypalserversdk.configuration import Environment
from paypalserversdk.exceptions.api_exception import ApiException
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.models.amount_breakdown import AmountBreakdown
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.item_request import ItemRequest
from paypalserversdk.models.money import Money
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
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
        # Sandbox only (decision 41). The SDK also has PRODUCTION; it is never selected here.
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


def _call(operation: str, options: dict):
    """Runs one Orders operation and returns its body. The SDK is synchronous, so the routes are too."""
    method = getattr(_client().orders, operation)
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


def create_order(items: list[dict]) -> str:
    """Creates an order for [{"name", "priceCents"}, ...]. The caller looked the prices up; none came from the browser."""
    total = sum(item["priceCents"] for item in items)

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
                    ItemRequest(name=item["name"][:127], quantity="1", unit_amount=_usd(item["priceCents"]))
                    for item in items
                ],
            )
        ],
    )
    order = _call("create_order", {"body": body, "paypal_request_id": str(uuid.uuid4())})
    return order.id


def capture_order(order_id: str) -> dict:
    # The order ID is the idempotency key, so a repeated capture returns the first result.
    order = _call("capture_order", {"id": order_id, "paypal_request_id": order_id})
    return {"orderId": order.id, "status": order.status}
