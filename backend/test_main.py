import unittest
from unittest import mock

import requests
from fastapi.testclient import TestClient

import paypal
from main import app

client = TestClient(app)


class CaptureRouteTest(unittest.TestCase):
    def capture(self, side_effect):
        with mock.patch.object(paypal, "capture_order", side_effect=side_effect):
            return client.post("/api/orders/ORDER1/capture")

    def test_returns_capture_result(self):
        result = {"orderId": "ORDER1", "status": "COMPLETED", "itemIds": ["sunscreen"]}
        response = self.capture(lambda order_id: result)
        self.assertEqual((response.status_code, response.json()), (200, result))

    def test_order_errors_pass_through(self):
        response = self.capture(paypal.PayPalError(422, "ORDER_NOT_APPROVED"))
        self.assertEqual((response.status_code, response.json()["detail"]), (422, "ORDER_NOT_APPROVED"))

    def test_other_paypal_errors_are_502(self):
        response = self.capture(paypal.PayPalError(401, "invalid_client"))
        self.assertEqual(response.status_code, 502)

    def test_network_failure_is_502(self):
        response = self.capture(requests.ConnectionError())
        self.assertEqual((response.status_code, response.json()["detail"]), (502, "PAYPAL_UNREACHABLE"))


class OrderRoutesTest(unittest.TestCase):
    def test_items_lists_the_sample_list(self):
        self.assertEqual(client.get("/api/items").json()[0]["id"], "sunscreen")

    def test_create_returns_the_order_and_approval_link(self):
        result = {"orderId": "ORDER1", "approveUrl": "https://paypal.example/approve"}
        with mock.patch.object(paypal, "create_order", return_value=result) as create:
            response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual((response.status_code, response.json()), (200, result))
        create.assert_called_once_with(["sunscreen"])

    def test_an_invalid_selection_is_400(self):
        response = client.post("/api/orders", json={"itemIds": []})
        self.assertEqual((response.status_code, response.json()["detail"]), (400, "Select at least one item"))


if __name__ == "__main__":
    unittest.main()
