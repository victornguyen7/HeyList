import logging
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import paypal
from sample_list import ITEMS, total_cents

log = logging.getLogger(__name__)
app = FastAPI()


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


@app.get("/api/items")
def list_items():
    return ITEMS


@app.post("/api/orders")
async def create_order(request: Request):
    # The body is read by hand: a Pydantic model would answer bad input with 422, not 400 INVALID_ITEMS.
    try:
        item_ids = (await request.json())["itemIds"]
        total_cents(item_ids)
    except (ValueError, KeyError, TypeError):
        return error("INVALID_ITEMS", 400)

    try:
        return {"orderId": await paypal.create_order(item_ids)}
    except Exception as exc:
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Create order failed")
        return error("PAYPAL_ERROR", 502)


@app.post("/api/orders/{order_id}/capture")
async def capture_order(order_id: str):
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)

    try:
        return await paypal.capture_order(order_id)
    except Exception as exc:
        if isinstance(exc, paypal.PayPalError) and exc.issue == "INSTRUMENT_DECLINED":
            return error("INSTRUMENT_DECLINED", 422)
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Capture order failed")
        return error("PAYPAL_ERROR", 502)
