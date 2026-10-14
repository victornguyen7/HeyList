import logging
import os
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
from paypalserversdk.models.payment_source import PaymentSource
from paypalserversdk.models.paypal_wallet import PaypalWallet
from paypalserversdk.models.paypal_wallet_experience_context import PaypalWalletExperienceContext
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient

from sample_list import ITEMS, total_cents

log = logging.getLogger(__name__)

APP_URL = os.environ.get("APP_URL", "http://localhost:3000")


class PayPalError(Exception):
    def __init__(self, status: int, issue: str | None):
        super().__init__(f"PayPal request failed: {status} {issue or ''}")
        self.status = status
        self.issue = issue


@cache
def _client() -> PaypalServersdkClient:
    """Built on first use, so importing this module doesn't need credentials. The SDK caches the token."""
    client_id = os.environ.get("PAYPAL_CLIENT_ID")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")
    return PaypalServersdkClient(
        environment=Environment.SANDBOX,
        client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
            o_auth_client_id=client_id, o_auth_client_secret=client_secret
        ),
        timeout=30,
        # Every POST here carries a PayPal-Request-Id, so retrying one cannot charge twice.
        max_retries=1,
        retry_statuses=[429],
        retry_methods=["GET", "PUT", "POST"],
    )


def _call(operation, options: dict):
    """Runs an SDK operation; logs the debug_id PayPal support asks for and raises an error the routes can map."""
    try:
        return operation(options).body
    except ApiException as error:
        details = getattr(error, "details", None) or [None]
        issue = getattr(details[0], "issue", None) or getattr(error, "name", None)
        log.error(
            "PayPal error status=%s issue=%s debug_id=%s",
            error.response_code,
            issue,
            getattr(error, "debug_id", None) or error.response.headers.get("paypal-debug-id"),
        )
        raise PayPalError(error.response_code, issue) from error


def _usd(cents: int) -> Money:
    return Money(currency_code="USD", value=f"{cents // 100}.{cents % 100:02d}")


def create_order(item_ids: list[str]) -> dict:
    """Returns the order ID and the PayPal page to send the buyer to."""
    total = _usd(total_cents(item_ids))
    body = OrderRequest(
        intent=CheckoutPaymentIntent.CAPTURE,
        purchase_units=[
            PurchaseUnitRequest(
                amount=AmountWithBreakdown(
                    currency_code=total.currency_code,
                    value=total.value,
                    breakdown=AmountBreakdown(item_total=total), # pyright: ignore[reportArgumentType]
                ),
                items=[  # pyright: ignore[reportArgumentType]  (SDK params are unannotated; SKIP default is a str)
                    # sku carries our item ID, so the capture response says which items were bought.
                    ItemRequest(name=item["name"], unit_amount=_usd(item["priceCents"]), quantity="1", sku=item["id"])
                    for item in ITEMS
                    if item["id"] in item_ids
                ],
            )
        ],
        # Where PayPal sends the buyer after the hosted checkout page; it adds ?token=<order id>&PayerID=...
        # The JS SDK popup ignores these and calls onApprove instead.
        payment_source=PaymentSource(  # pyright: ignore[reportArgumentType]
            paypal=PaypalWallet(  # pyright: ignore[reportArgumentType]
                experience_context=PaypalWalletExperienceContext(  # pyright: ignore[reportArgumentType]
                    return_url=APP_URL, cancel_url=APP_URL
                )
            )
        ),
    )
    order = _call(_client().orders.create_order, {"body": body, "paypal_request_id": str(uuid.uuid4())})  # pyright: ignore[reportOptionalMemberAccess]
    # With payment_source.paypal, PayPal names the approval link "payer-action" rather than "approve".
    approve_url = next(link.href for link in order.links if link.rel == "payer-action")
    return {"orderId": order.id, "approveUrl": approve_url}


def capture_order(order_id: str) -> dict:
    """Check items off only when status is COMPLETED: the order can complete while the payment is PENDING or DECLINED."""
    order = _call(
        _client().orders.capture_order, # pyright: ignore[reportOptionalMemberAccess]
        # The order ID is the idempotency key, so a repeated capture returns the first result.
        # return=representation includes the items, which the default minimal response leaves out.
        {"id": order_id, "paypal_request_id": order_id, "prefer": "return=representation"},
    )
    unit = order.purchase_units[0]
    return {
        "orderId": order.id,
        "status": unit.payments.captures[0].status,
        "itemIds": [item.sku for item in getattr(unit, "items", []) if hasattr(item, "sku")],
    }
