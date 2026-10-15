import re
import unittest
import uuid
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

import db
import main
import paypal

# Every table's columns, read from the schema so the fake can't drift from it. Unset columns are None.
SCHEMA = (Path(__file__).parent.parent / "supabase" / "schema.sql").read_text()
COLUMNS = {
    table: re.findall(r"^  (?!constraint|unique)(\w+) ", body, re.M)
    for table, body in re.findall(r"create table if not exists (\w+) \((.*?)\n\);", SCHEMA, re.S)
}
# Column defaults the routes read back.
DEFAULTS = {"lists": {"kind": "other"}, "items": {"position": 0, "quantity": 1}, "orders": {"status": "CREATED"}}


class FakeDB:
    """The four db calls over in-memory tables."""

    def __init__(self):
        self.tables = {}

    def rows(self, table, filters):
        def matches(row, column, value):
            return row.get(column) in value if isinstance(value, list) else row.get(column) == value

        return [row for row in self.tables.get(table, []) if all(matches(row, c, v) for c, v in filters.items())]

    def select(self, table, order="created_at", **filters):
        return sorted((dict(row) for row in self.rows(table, filters)), key=lambda row: row.get(order) or 0)

    def insert(self, table, rows):
        added = []
        for row in rows:
            added.append({
                    **dict.fromkeys(COLUMNS[table]),
                    "id": str(uuid.uuid4()),
                    "created_at": len(self.tables.get(table, [])),
                    **DEFAULTS.get(table, {}),
                    **row,
                })
            self.tables.setdefault(table, []).append(added[-1])
        return [dict(row) for row in added]

    def update(self, table, values, **filters):
        for row in self.rows(table, filters):
            row.update(values)
        return [dict(row) for row in self.rows(table, filters)]

    def delete(self, table, **filters):
        doomed = self.rows(table, filters)
        self.tables[table] = [row for row in self.tables[table] if row not in doomed]


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        for name in ("select", "insert", "update", "delete"):
            patch = mock.patch.object(db, name, getattr(self.db, name))
            patch.start()
            self.addCleanup(patch.stop)
        self.client = TestClient(main.app)

    def new_list(self, items):
        response = self.client.post("/api/lists", json={"title": "Trip", "kind": "trip", "items": items})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def mock_paypal(self, name, **kwargs):
        patch = mock.patch.object(paypal, name, **kwargs)
        self.addCleanup(patch.stop)
        return patch.start()


class ListRoutesTest(RoutesTest):
    def test_a_new_list_comes_back_with_its_items_in_order(self):
        state = self.new_list([{"name": "Sunscreen", "estPriceCents": 899, "quantity": 2}, {"name": "Adapter"}])

        self.assertEqual(state["title"], "Trip")
        self.assertEqual([(i["name"], i["quantity"], i["position"]) for i in state["items"]], [("Sunscreen", 2, 0), ("Adapter", 1, 1)])
        self.assertEqual(self.client.get(f"/api/lists/{state['id']}").json(), state)

    def test_bad_input_is_400_and_saves_nothing(self):
        for body in (
            {"title": ""},
            {"title": "x", "kind": "bogus"},
            {"title": "x", "items": [{"name": "a", "estPriceCents": -1}]},
            {"title": "x", "items": [{"name": "a", "estPriceCents": True}]},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/lists", json=body).status_code, 400)
        self.assertEqual(self.db.tables, {})

    def test_an_unknown_or_malformed_list_is_404(self):
        for list_id in (str(uuid.uuid4()), "not-a-uuid"):
            self.assertEqual(self.client.get(f"/api/lists/{list_id}").status_code, 404)

    def test_a_quantity_must_be_a_whole_number_from_1_to_99(self):
        item = self.new_list([{"name": "Sunscreen"}])["items"][0]
        for bad in (0, 100, 2.5, "2", True):
            with self.subTest(quantity=bad):
                self.assertEqual(self.client.patch(f"/api/items/{item['id']}", json={"quantity": bad}).status_code, 400)

        self.assertEqual(self.client.patch(f"/api/items/{item['id']}", json={"quantity": 3}).json()["quantity"], 3)


class CheckoutTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list(
            [{"name": "Sunscreen", "estPriceCents": 899, "quantity": 2}, {"name": "Adapter", "estPriceCents": 1499}, {"name": "Map"}]
        )
        self.sunscreen, self.adapter, self.map = self.list["items"]

    def order(self, *items):
        return self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [item["id"] for item in items]})

    def test_the_order_uses_database_prices_and_quantities(self):
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        self.assertEqual(self.order(self.sunscreen, self.adapter).json(), {"orderId": "ORDER1", "approveUrl": "https://pay"})

        items, return_url = create.call_args.args
        self.assertEqual(
            items,
            [{"name": "Sunscreen", "priceCents": 899, "quantity": 2}, {"name": "Adapter", "priceCents": 1499, "quantity": 1}],
        )
        self.assertEqual(return_url, f"{main.APP_URL}/?list={self.list['id']}")
        self.assertEqual(self.db.tables["orders"][0]["total_cents"], 899 * 2 + 1499)

    def test_items_without_a_price_or_from_another_list_cannot_be_ordered(self):
        create = self.mock_paypal("create_order")
        other = self.new_list([{"name": "Tent", "estPriceCents": 100}])["items"][0]

        for items in ((self.map,), (other,), (self.adapter, self.adapter), ()):
            with self.subTest(items=items):
                self.assertEqual(self.order(*items).status_code, 400)
        create.assert_not_called()

    def capture(self, status):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.sunscreen, self.adapter)
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": status})
        response = self.client.post("/api/orders/ORDER1/capture")
        return response, {item["name"]: item for item in self.client.get(f"/api/lists/{self.list['id']}").json()["items"]}

    def test_a_completed_capture_checks_the_items_off_at_price_times_quantity(self):
        response, items = self.capture("COMPLETED")

        self.assertEqual(response.json(), {"orderId": "ORDER1", "status": "COMPLETED"})
        self.assertEqual(items["Sunscreen"]["priceCents"], 899 * 2)
        self.assertEqual(items["Adapter"]["orderId"], "ORDER1")
        self.assertIsNone(items["Map"]["checkedAt"])
        # A paid item cannot be unticked or re-priced.
        self.assertEqual(self.client.patch(f"/api/items/{self.adapter['id']}", json={"quantity": 2}).status_code, 409)

    def test_a_pending_payment_checks_nothing_off(self):
        response, items = self.capture("PENDING")

        self.assertEqual(response.json()["status"], "PENDING")
        self.assertTrue(all(item["checkedAt"] is None for item in items.values()))
        self.assertEqual(self.db.tables["orders"][0]["status"], "CREATED")

    def test_paypal_errors_map_to_status_codes(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.adapter)
        for error, status in (
            (paypal.PayPalError(422, "INSTRUMENT_DECLINED"), 422),
            (paypal.PayPalError(500, None), 502),
            (ConnectionError(), 502),
        ):
            with self.subTest(error=error):
                self.mock_paypal("capture_order", side_effect=error)
                with self.assertNoLogs(main.log) if isinstance(error, paypal.PayPalError) else self.assertLogs(main.log):
                    self.assertEqual(self.client.post("/api/orders/ORDER1/capture").status_code, status)

    def test_an_unknown_order_is_404_and_a_malformed_one_400(self):
        self.assertEqual(self.client.post("/api/orders/NOPE1/capture").status_code, 404)
        self.assertEqual(self.client.post("/api/orders/bad-id/capture").status_code, 400)


if __name__ == "__main__":
    unittest.main()
