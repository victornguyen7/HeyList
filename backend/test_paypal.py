import json
import os
import unittest
from unittest import mock

import requests
from requests.adapters import HTTPAdapter

import paypal


class FakePayPal(HTTPAdapter):
    """Answers the token request itself and order requests with the given (status, body) replies, in turn."""

    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        if request.path_url == "/v1/oauth2/token":
            status, body = 200, {"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600}
        else:
            status, body = next(self.replies)
        response = requests.Response()
        response.status_code = status
        response._content = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        response.headers["Content-Type"] = "text/html" if isinstance(body, str) else "application/json"
        response.url = request.url
        response.request = request
        return response


def captured(capture_status):
    return {
        "id": "ORDER1",
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [{"id": "CAP1", "status": capture_status}]}}],
    }


class PayPalTest(unittest.TestCase):
    def fake_paypal(self, *replies):
        self.fake = FakePayPal(replies)
        session = requests.Session()
        session.mount("https://", self.fake)
        for patch in (
            mock.patch.object(paypal, "session", session),
            mock.patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "secret"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        paypal._client.cache_clear()
        self.addCleanup(paypal._client.cache_clear)

    def paths(self):
        return [request.path_url for request in self.fake.requests]

    def test_create_order_sends_price_times_quantity_and_the_return_url(self):
        approve = "https://www.sandbox.paypal.com/checkoutnow?token=ORDER1"
        self.fake_paypal((201, {"id": "ORDER1", "links": [{"rel": "payer-action", "href": approve}]}))

        items = [{"name": "Sunscreen", "priceCents": 899, "quantity": 2}, {"name": "Adapter", "priceCents": 1499, "quantity": 1}]
        self.assertEqual(paypal.create_order(items, "http://app/?list=L1"), {"orderId": "ORDER1", "approveUrl": approve})

        self.assertEqual(self.paths(), ["/v1/oauth2/token", "/v2/checkout/orders"])
        order = self.fake.requests[1]
        self.assertEqual(order.headers["authorization"], "Bearer token-1")
        self.assertTrue(order.headers["paypal-request-id"])
        body = json.loads(order.body)
        unit = body["purchase_units"][0]
        self.assertEqual(unit["amount"]["value"], "32.97")
        self.assertEqual(unit["amount"]["breakdown"]["item_total"]["value"], "32.97")
        self.assertEqual([item["unit_amount"]["value"] for item in unit["items"]], ["8.99", "14.99"])
        self.assertEqual([item["quantity"] for item in unit["items"]], ["2", "1"])
        self.assertEqual(body["payment_source"]["paypal"]["experience_context"]["return_url"], "http://app/?list=L1")

    def test_capture_reports_the_payment_status(self):
        self.fake_paypal((201, captured("COMPLETED")))

        self.assertEqual(paypal.capture_order("ORDER1"), {"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        capture = self.fake.requests[1]
        self.assertEqual(capture.path_url, "/v2/checkout/orders/ORDER1/capture")
        self.assertEqual(capture.headers["paypal-request-id"], "ORDER1")
        self.assertEqual(capture.headers["prefer"], "return=representation")

    def test_a_completed_order_with_a_pending_payment_is_reported_as_pending(self):
        self.fake_paypal((201, captured("PENDING")))

        self.assertEqual(paypal.capture_order("ORDER1")["status"], "PENDING")

    def test_get_order_reads_the_capture_status_without_capturing_again(self):
        self.fake_paypal((200, captured("COMPLETED")), (200, {"id": "ORDER1", "status": "APPROVED", "purchase_units": [{}]}))

        self.assertEqual(paypal.get_order("ORDER1"), {"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})
        self.assertEqual(paypal.get_order("ORDER1")["status"], "NOT_CAPTURED")
        self.assertEqual([r.method for r in self.fake.requests[1:]], ["GET", "GET"])
        self.assertEqual(self.fake.requests[1].path_url, "/v2/checkout/orders/ORDER1")

    def test_refund_returns_part_of_a_capture_once(self):
        self.fake_paypal((201, {"id": "REF1", "status": "COMPLETED"}))

        self.assertEqual(paypal.refund("CAP1", 1499, "ORDER1-item"), {"refundId": "REF1", "status": "COMPLETED"})

        request = self.fake.requests[1]
        self.assertEqual(request.path_url, "/v2/payments/captures/CAP1/refund")
        self.assertEqual(request.headers["paypal-request-id"], "ORDER1-item")
        self.assertEqual(json.loads(request.body)["amount"], {"currency_code": "USD", "value": "14.99"})

    def test_one_429_is_retried(self):
        self.fake_paypal((429, {"name": "RATE_LIMIT_REACHED"}), (201, captured("COMPLETED")))

        with mock.patch.object(paypal.time, "sleep") as sleep:
            self.assertEqual(paypal.capture_order("ORDER1")["status"], "COMPLETED")
        sleep.assert_called_once_with(1)

    def test_a_paypal_failure_carries_the_issue_and_logs_the_debug_id(self):
        self.fake_paypal(
            (
                422,
                {
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "INSTRUMENT_DECLINED"}],
                    "debug_id": "abc123",
                },
            )
        )

        with self.assertLogs(paypal.log, "ERROR") as logs, self.assertRaises(paypal.PayPalError) as raised:
            paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 422)
        self.assertEqual(raised.exception.issue, "INSTRUMENT_DECLINED")
        self.assertIn("abc123", logs.output[0])

    def test_a_non_json_error_body_is_still_a_paypal_error(self):
        self.fake_paypal((503, "<html>down</html>"))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 503)
        self.assertIsNone(raised.exception.issue)

    def test_missing_credentials_fail_before_any_request(self):
        paypal._client.cache_clear()
        self.addCleanup(paypal._client.cache_clear)
        with mock.patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": ""}):
            with self.assertRaisesRegex(RuntimeError, "must be set"):
                paypal.capture_order("ORDER1")
