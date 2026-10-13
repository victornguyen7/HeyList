import unittest
from unittest import mock

from fastapi.testclient import TestClient

import paypal
from main import app
from sample_list import ITEMS

client = TestClient(app)


class ItemsTest(unittest.TestCase):
    def test_lists_the_items(self):
        response = client.get("/api/items")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ITEMS)


class CreateOrderTest(unittest.TestCase):
    def test_bad_input_is_400_and_never_reaches_paypal(self):
        bodies = [
            '{"itemIds": []}',
            '{"itemIds": ["sunscreen", "nope"]}',
            '{"itemIds": ["sunscreen", "sunscreen"]}',
            '{"itemIds": "sunscreen"}',
            '{"itemIds": [["sunscreen"]]}',
            "{}",
            "[]",
            "null",
            "not json",
            "",
        ]
        with mock.patch.object(paypal, "create_order") as create_order:
            for body in bodies:
                with self.subTest(body=body):
                    response = client.post(
                        "/api/orders", content=body, headers={"Content-Type": "application/json"}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"error": "INVALID_ITEMS"})
        create_order.assert_not_called()

    def test_returns_the_order_id(self):
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(return_value="ORDER1")) as create_order:
            response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"orderId": "ORDER1"})
        create_order.assert_awaited_once_with(["sunscreen"])

    def test_a_paypal_failure_is_a_generic_502(self):
        failure = paypal.PayPalError(500, "INTERNAL_SERVER_ERROR")
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(side_effect=failure)):
            response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        failure = RuntimeError("no credentials")
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(side_effect=failure)):
            with self.assertLogs("main", "ERROR"):
                response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})


class CaptureOrderTest(unittest.TestCase):
    def test_malformed_order_id_is_400_and_never_reaches_paypal(self):
        with mock.patch.object(paypal, "capture_order") as capture_order:
            for order_id in ("abc", "ORDER-1", "A" * 37):
                with self.subTest(order_id=order_id):
                    response = client.post(f"/api/orders/{order_id}/capture")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"error": "INVALID_ORDER_ID"})
        capture_order.assert_not_called()

    def test_returns_the_capture_result(self):
        result = {"orderId": "ORDER1", "status": "COMPLETED"}
        with mock.patch.object(paypal, "capture_order", mock.AsyncMock(return_value=result)):
            response = client.post("/api/orders/ORDER1/capture")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

    def test_maps_paypal_failures_to_the_error_contract(self):
        for issue, status, code in [
            ("INSTRUMENT_DECLINED", 422, "INSTRUMENT_DECLINED"),
            ("ORDER_NOT_APPROVED", 502, "PAYPAL_ERROR"),
        ]:
            with self.subTest(issue=issue):
                failure = paypal.PayPalError(422, issue)
                with mock.patch.object(paypal, "capture_order", mock.AsyncMock(side_effect=failure)):
                    response = client.post("/api/orders/ORDER1/capture")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"error": code})

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        failure = RuntimeError("no credentials")
        with mock.patch.object(paypal, "capture_order", mock.AsyncMock(side_effect=failure)):
            with self.assertLogs("main", "ERROR"):
                response = client.post("/api/orders/ORDER1/capture")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})
