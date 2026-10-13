import json
import os
import unittest
from unittest import mock

import requests
from requests.adapters import HTTPAdapter

import paypal

TWO_ITEMS = [{"name": "Sunscreen", "priceCents": 899}, {"name": "Travel adapter", "priceCents": 1499}]
ONE_ITEM = [{"name": "Toothbrush", "priceCents": 349}]


class FakePayPal(HTTPAdapter):
    """Answers the token request itself and order POSTs with the given responses, in turn."""

    def __init__(self, replies):
        super().__init__()
        self.requests = []
        self.replies = iter(replies)

    def send(self, request, **kwargs):
        self.requests.append(request)
        if request.path_url == "/v1/oauth2/token":
            status, body, headers = 200, {"access_token": "token-1", "expires_in": 3600}, {}
        else:
            status, body, headers = next(self.replies)
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response._content = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        response.request = request
        return response


class PayPalTest(unittest.TestCase):
    def fake_paypal(self, *order_responses):
        """Points the SDK at a fake PayPal. Each response is (status, body, headers)."""
        fake = FakePayPal(order_responses)
        self.requests = fake.requests
        session = requests.Session()
        session.mount("https://", fake)
        for patch in (
            mock.patch.object(paypal, "session", session),
            mock.patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "secret"}),
            mock.patch.object(paypal.time, "sleep"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        # The client is cached, so each test builds its own around its fake.
        paypal._client.cache_clear()
        self.addCleanup(paypal._client.cache_clear)

    def paths(self):
        return [request.path_url for request in self.requests]

    def test_create_order_sends_the_server_side_total_and_reuses_the_token(self):
        self.fake_paypal((201, {"id": "ORDER1"}, {}), (201, {"id": "ORDER2"}, {}))

        self.assertEqual(paypal.create_order(TWO_ITEMS), "ORDER1")
        self.assertEqual(paypal.create_order(ONE_ITEM), "ORDER2")

        self.assertEqual(
            self.paths(), ["/v1/oauth2/token", "/v2/checkout/orders", "/v2/checkout/orders"]
        )
        order = self.requests[1]
        self.assertTrue(order.url.startswith("https://api-m.sandbox.paypal.com/"))
        self.assertEqual(order.headers["authorization"], "Bearer token-1")
        self.assertTrue(order.headers["paypal-request-id"])
        body = json.loads(order.body)
        self.assertEqual(body["intent"], "CAPTURE")
        unit = body["purchase_units"][0]
        self.assertEqual(unit["amount"]["value"], "23.98")
        self.assertEqual(unit["amount"]["breakdown"]["item_total"]["value"], "23.98")
        self.assertEqual([item["unit_amount"]["value"] for item in unit["items"]], ["8.99", "14.99"])

    def test_capture_retries_once_on_429_with_the_same_request_id(self):
        self.fake_paypal(
            (429, "", {"retry-after": "60"}),
            (201, {"id": "ORDER1", "status": "COMPLETED"}, {}),
        )

        self.assertEqual(
            paypal.capture_order("ORDER1"), {"orderId": "ORDER1", "status": "COMPLETED"}
        )

        paypal.time.sleep.assert_called_once_with(5)
        self.assertEqual(self.paths()[1:], ["/v2/checkout/orders/ORDER1/capture"] * 2)
        self.assertEqual(
            [request.headers["paypal-request-id"] for request in self.requests[1:]],
            ["ORDER1", "ORDER1"],
        )

    def test_a_second_429_is_an_error_not_another_retry(self):
        self.fake_paypal((429, "", {}), (429, "", {}))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(len(self.requests), 3)

    def test_a_paypal_failure_carries_the_issue_and_logs_the_debug_id(self):
        self.fake_paypal(
            (
                422,
                {
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "INSTRUMENT_DECLINED"}],
                    "debug_id": "abc123",
                },
                {},
            )
        )

        with self.assertLogs(paypal.log, "ERROR") as logs, self.assertRaises(paypal.PayPalError) as raised:
            paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.issue, "INSTRUMENT_DECLINED")
        self.assertIn("abc123", logs.output[0])

    def test_a_non_json_error_body_is_still_a_paypal_error(self):
        self.fake_paypal((503, "<html>down</html>", {}))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 503)
        self.assertIsNone(raised.exception.issue)

    def test_missing_credentials_fail_before_any_request(self):
        self.fake_paypal()
        with mock.patch.dict(os.environ, {"PAYPAL_CLIENT_SECRET": ""}):
            with self.assertRaisesRegex(RuntimeError, "must be set"):
                paypal.create_order(ONE_ITEM)
        self.assertEqual(self.requests, [])
