import logging

import requests
from apimatic_core.exceptions.auth_validation_exception import AuthValidationException
from fastapi import FastAPI, HTTPException

import paypal

logging.basicConfig(level=logging.INFO)
app = FastAPI()


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
