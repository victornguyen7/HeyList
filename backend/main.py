import logging

import requests
from apimatic_core.exceptions.auth_validation_exception import AuthValidationException
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt

import paypal
from sample_list import ITEMS

logging.basicConfig(level=logging.INFO)
app = FastAPI()


@app.get("/api/items")
def items() -> list[dict]:
    return ITEMS


class OrderIn(BaseModel):
    items: dict[str, StrictInt]  # item ID -> quantity; total_cents checks the range


@app.post("/api/orders")
def create(order: OrderIn) -> dict:
    try:
        return paypal.create_order(order.items)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except paypal.PayPalError as error:
        raise HTTPException(502, error.issue or "PAYPAL_ERROR") from error
    except (requests.ConnectionError, requests.Timeout, AuthValidationException) as error:
        raise HTTPException(502, "PAYPAL_UNREACHABLE") from error


@app.post("/api/orders/{order_id}/capture")
def capture(order_id: str) -> dict:
    try:
        return paypal.capture_order(order_id)
    except paypal.PayPalError as error:
        # 404/422 are about this order (not approved, already captured, unknown); anything else is our side.
        status = error.status if error.status in (404, 422) else 502
        raise HTTPException(status, error.issue or "PAYPAL_ERROR") from error
    except (requests.ConnectionError, requests.Timeout, AuthValidationException) as error:
        raise HTTPException(502, "PAYPAL_UNREACHABLE") from error
