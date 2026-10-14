import json
import os
import unittest
from unittest import mock

import httpx

import paypal


class PayPalTest(unittest.IsolatedAsyncioTestCase):
    def fake_paypal(self, *order_responses):
        """Points the client at a fake PayPal that answers order POSTs with the given responses, in turn."""
        self.requests = []
        replies = iter(order_responses)

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if request.url.path == "/v1/oauth2/token":
                return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
            return next(replies)

        fake = httpx.AsyncClient(base_url=paypal.BASE_URL, transport=httpx.MockTransport(handler))
        for patch in (
            mock.patch.object(paypal, "client", fake),
            mock.patch.object(paypal, "_token", None),
            mock.patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "secret"}),
            mock.patch("asyncio.sleep", mock.AsyncMock()),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def paths(self):
        return [request.url.path for request in self.requests]

    async def test_create_order_sends_the_server_side_total_and_reuses_the_token(self):
        self.fake_paypal(
            httpx.Response(201, json={"id": "ORDER1"}),
            httpx.Response(201, json={"id": "ORDER2"}),
        )

        self.assertEqual(await paypal.create_order(["sunscreen", "adapter"]), "ORDER1")
        self.assertEqual(await paypal.create_order(["toothbrush"]), "ORDER2")

        self.assertEqual(
            self.paths(), ["/v1/oauth2/token", "/v2/checkout/orders", "/v2/checkout/orders"]
        )
        order = self.requests[1]
        self.assertEqual(order.headers["authorization"], "Bearer token-1")
        self.assertTrue(order.headers["paypal-request-id"])
        unit = json.loads(order.content)["purchase_units"][0]
        self.assertEqual(unit["amount"]["value"], "23.98")
        self.assertEqual(unit["amount"]["breakdown"]["item_total"]["value"], "23.98")
        self.assertEqual([item["unit_amount"]["value"] for item in unit["items"]], ["8.99", "14.99"])

    async def test_capture_retries_once_on_429_with_the_same_request_id(self):
        self.fake_paypal(
            httpx.Response(429, headers={"retry-after": "60"}),
            httpx.Response(201, json={"id": "ORDER1", "status": "COMPLETED"}),
        )

        self.assertEqual(
            await paypal.capture_order("ORDER1"), {"orderId": "ORDER1", "status": "COMPLETED"}
        )

        paypal.asyncio.sleep.assert_awaited_once_with(5)
        self.assertEqual(self.paths()[1:], ["/v2/checkout/orders/ORDER1/capture"] * 2)
        self.assertEqual(
            [request.headers["paypal-request-id"] for request in self.requests[1:]],
            ["ORDER1", "ORDER1"],
        )

    async def test_a_second_429_is_an_error_not_another_retry(self):
        self.fake_paypal(httpx.Response(429), httpx.Response(429))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(len(self.requests), 3)

    async def test_a_paypal_failure_carries_the_issue_and_logs_the_debug_id(self):
        self.fake_paypal(
            httpx.Response(
                422,
                json={
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "INSTRUMENT_DECLINED"}],
                    "debug_id": "abc123",
                },
            )
        )

        with self.assertLogs(paypal.log, "ERROR") as logs, self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.issue, "INSTRUMENT_DECLINED")
        self.assertIn("abc123", logs.output[0])

    async def test_a_non_json_error_body_is_still_a_paypal_error(self):
        self.fake_paypal(httpx.Response(503, text="<html>down</html>"))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 503)
        self.assertIsNone(raised.exception.issue)

    async def test_missing_credentials_fail_before_any_request(self):
        self.fake_paypal()
        with mock.patch.dict(os.environ, {"PAYPAL_CLIENT_SECRET": ""}):
            with self.assertRaisesRegex(RuntimeError, "must be set"):
                await paypal.create_order(["sunscreen"])
        self.assertEqual(self.requests, [])