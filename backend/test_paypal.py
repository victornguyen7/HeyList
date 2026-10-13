import json
import os
import unittest
from unittest import mock

import httpx
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


class InvoicingTest(unittest.TestCase):
    def fake_paypal(self, *responses):
        self.requests = []
        replies = iter(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return next(replies)

        for patch in (
            mock.patch.object(paypal, "http", httpx.Client(transport=httpx.MockTransport(handler))),
            mock.patch.object(paypal, "_access_token", return_value="token-1"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_create_sends_the_amount_in_dollars_and_reads_the_id_from_the_link(self):
        href = "https://api-m.sandbox.paypal.com/v2/invoicing/invoices/INV2-AAAA-BBBB"
        self.fake_paypal(httpx.Response(201, json={"rel": "self", "href": href, "method": "GET"}))

        invoice_id = paypal.create_invoice("ben@example.com", 1005, "Your share of Move-in", "Ben owes Ana.")

        self.assertEqual(invoice_id, "INV2-AAAA-BBBB")
        request = self.requests[0]
        self.assertEqual((request.method, str(request.url)), ("POST", paypal.INVOICING_URL))
        self.assertTrue(str(request.url).startswith("https://api-m.sandbox.paypal.com/"))
        self.assertEqual(request.headers["authorization"], "Bearer token-1")
        body = json.loads(request.content)
        self.assertEqual(body["primary_recipients"][0]["billing_info"]["email_address"], "ben@example.com")
        self.assertEqual(body["items"][0]["unit_amount"], {"currency_code": "USD", "value": "10.05"})
        self.assertEqual(body["detail"]["note"], "Ben owes Ana.")

    def test_send_then_get_status_and_pay_link(self):
        self.fake_paypal(
            httpx.Response(202, json={}),
            httpx.Response(
                200,
                json={"status": "SENT", "detail": {"metadata": {"recipient_view_url": "https://pay.example/i"}}},
            ),
        )
        paypal.send_invoice("INV2-AAAA")
        self.assertEqual(paypal.get_invoice("INV2-AAAA"), {"status": "SENT", "payUrl": "https://pay.example/i"})
        self.assertEqual(
            [(request.method, request.url.path) for request in self.requests],
            [("POST", "/v2/invoicing/invoices/INV2-AAAA/send"), ("GET", "/v2/invoicing/invoices/INV2-AAAA")],
        )
        self.assertEqual(json.loads(self.requests[0].content), {"send_to_recipient": True})

    def test_a_failure_carries_the_issue_and_logs_the_debug_id(self):
        self.fake_paypal(
            httpx.Response(
                422,
                json={"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "INVALID_EMAIL"}], "debug_id": "d1"},
            ),
            httpx.Response(503, text="<html>down</html>"),
        )
        with self.assertLogs(paypal.log, "ERROR") as logs, self.assertRaises(paypal.PayPalError) as raised:
            paypal.send_invoice("INV2-AAAA")
        self.assertEqual(raised.exception.issue, "INVALID_EMAIL")
        self.assertIn("d1", logs.output[0])
        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            paypal.get_invoice("INV2-AAAA")
        self.assertEqual((raised.exception.status, raised.exception.issue), (503, None))
