import asyncio
import logging
import os
import time
import uuid
from urllib.parse import quote

import httpx

from sample_list import ITEMS, total_cents

BASE_URL = "https://api-m.sandbox.paypal.com"

log = logging.getLogger(__name__)
# httpx defaults to a 5 second timeout, which a slow capture can exceed.
client = httpx.AsyncClient(base_url=BASE_URL, timeout=30)


class PayPalError(Exception):
    def __init__(self, status: int, issue: str | None):
        super().__init__(f"PayPal request failed: {status} {issue or ''}")
        self.status = status
        self.issue = issue


def _to_error(response: httpx.Response) -> PayPalError:
    """Logs the debug_id PayPal support asks for, then returns an error the routes can map."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    details = body.get("details") or [{}]
    issue = details[0].get("issue") or body.get("name") or body.get("error")
    log.error(
        "PayPal error status=%s issue=%s debug_id=%s",
        response.status_code,
        issue,
        body.get("debug_id") or response.headers.get("paypal-debug-id"),
    )
    return PayPalError(response.status_code, issue)


_token: tuple[str, float] | None = None  # (value, expires at, on the monotonic clock)


async def _access_token() -> str:
    global _token
    if _token and time.monotonic() < _token[1]:
        return _token[0]

    client_id = os.environ.get("PAYPAL_CLIENT_ID")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

    response = await client.post(
        "/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
    )
    if not response.is_success:
        raise _to_error(response)

    data = response.json()
    # Refresh two minutes early so a token never expires mid-request.
    _token = (data["access_token"], time.monotonic() + data["expires_in"] - 120)
    return _token[0]


async def _post(path: str, request_id: str, body: dict, retried: bool = False) -> dict:
    response = await client.post(
        path,
        json=body,
        headers={
            "Authorization": f"Bearer {await _access_token()}",
            "PayPal-Request-Id": request_id,
        },
    )

    if response.status_code == 429 and not retried:
        try:
            seconds = int(response.headers.get("retry-after", ""))
        except ValueError:
            seconds = 1
        await asyncio.sleep(min(seconds or 1, 5))
        return await _post(path, request_id, body, True)
    if not response.is_success:
        raise _to_error(response)
    return response.json()


def _usd(cents: int) -> dict:
    return {"currency_code": "USD", "value": f"{cents // 100}.{cents % 100:02d}"}


async def create_order(item_ids: list[str]) -> str:
    total = total_cents(item_ids)
    items = [item for item in ITEMS if item["id"] in item_ids]

    order = await _post(
        "/v2/checkout/orders",
        str(uuid.uuid4()),
        {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {**_usd(total), "breakdown": {"item_total": _usd(total)}},
                    "items": [
                        {
                            "name": item["name"],
                            "quantity": "1",
                            "unit_amount": _usd(item["priceCents"]),
                        }
                        for item in items
                    ],
                }
            ],
        },
    )
    return order["id"]


async def capture_order(order_id: str) -> dict:
    # The order ID is the idempotency key, so a repeated capture returns the first result.
    order = await _post(f"/v2/checkout/orders/{quote(order_id, safe='')}/capture", order_id, {})
    return {"orderId": order["id"], "status": order["status"]}
