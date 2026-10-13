import unittest
import uuid
from unittest import mock

from fastapi.testclient import TestClient

import db
import main
import paypal

client = TestClient(main.app)


class FakeDb:
    """An in-memory stand-in for the four calls in db.py."""

    def __init__(self):
        self.tables = {}
        self.clock = 0

    def select(self, table, order="created_at", **filters):
        def matches(row):
            return all(
                row[column] in value if isinstance(value, list) else row[column] == value
                for column, value in filters.items()
            )

        return sorted(
            (dict(row) for row in self.tables.get(table, []) if matches(row)),
            key=lambda row: row[order],
        )

    def insert(self, table, rows):
        defaults = {
            "lists": {"finished_at": None},
            "members": {"email": None},
            "items": {
                "price_cents": None,
                "claimed_by": None,
                "bought_by": None,
                "checked_at": None,
                "receipt_id": None,
                "order_id": None,
            },
            "orders": {"status": "CREATED", "captured_at": None},
            "receipts": {"extras": [], "total_cents": None},
        }.get(table, {})
        added = []
        for row in rows:
            self.clock += 1
            added.append({"id": str(uuid.uuid4()), "created_at": self.clock, **defaults, **row})
        self.tables.setdefault(table, []).extend(added)
        return [dict(row) for row in added]

    def update(self, table, values, **filters):
        ids = [row["id"] for row in self.select(table, **filters)]
        changed = [row for row in self.tables.get(table, []) if row["id"] in ids]
        for row in changed:
            row.update(values)
        return [dict(row) for row in changed]

    def delete(self, table, **filters):
        ids = [row["id"] for row in self.select(table, **filters)]
        self.tables[table] = [row for row in self.tables.get(table, []) if row["id"] not in ids]


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        for name in ("select", "insert", "update", "delete"):
            patch = mock.patch.object(db, name, getattr(self.db, name))
            patch.start()
            self.addCleanup(patch.stop)

    def make_list(self, **extra):
        body = {
            "title": "Move-in",
            "kind": "home",
            "budgetCents": 30000,
            "items": [{"name": "Kettle", "estPriceCents": 2500}, {"name": "Mop", "estPriceCents": 1200}],
            **extra,
        }
        response = client.post("/api/lists", json=body)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def join(self, list_id, name="Ana", **extra):
        response = client.post(f"/api/lists/{list_id}/members", json={"name": name, **extra})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json(), {"error": code})


class ListsTest(ApiTest):
    def test_create_then_fetch_by_its_share_id(self):
        created = self.make_list()
        fetched = client.get(f"/api/lists/{created['id']}").json()
        self.assertEqual(fetched, created)
        self.assertEqual(fetched["title"], "Move-in")
        self.assertEqual(fetched["budgetCents"], 30000)
        self.assertEqual([item["name"] for item in fetched["items"]], ["Kettle", "Mop"])
        self.assertEqual(fetched["items"][0]["estPriceCents"], 2500)
        self.assertEqual(fetched["orders"], [])

    def test_bad_bodies_are_400_and_store_nothing(self):
        for body in [
            "not json",
            "[]",
            "{}",
            '{"title": ""}',
            '{"title": "x", "kind": "spaceship"}',
            '{"title": "x", "budgetCents": -1}',
            '{"title": "x", "budgetCents": true}',
            '{"title": "x", "budgetCents": 12.5}',
            '{"title": "x", "items": [{"name": ""}]}',
            '{"title": "x", "items": ["kettle"]}',
        ]:
            with self.subTest(body=body):
                response = client.post(
                    "/api/lists", content=body, headers={"Content-Type": "application/json"}
                )
                self.assert_error(response, 400, "INVALID_BODY")
        self.assertEqual(self.db.tables, {})

    def test_unknown_or_malformed_list_id_is_404(self):
        for list_id in (str(uuid.uuid4()), "nope"):
            with self.subTest(list_id=list_id):
                self.assert_error(client.get(f"/api/lists/{list_id}"), 404, "LIST_NOT_FOUND")
                self.assert_error(
                    client.patch(f"/api/lists/{list_id}", json={"title": "x"}), 404, "LIST_NOT_FOUND"
                )

    def test_update_title_budget_and_finished(self):
        list_id = self.make_list()["id"]
        updated = client.patch(
            f"/api/lists/{list_id}", json={"title": "New flat", "budgetCents": 5000, "finished": True}
        ).json()
        self.assertEqual((updated["title"], updated["budgetCents"]), ("New flat", 5000))
        self.assertTrue(updated["finishedAt"])
        reopened = client.patch(f"/api/lists/{list_id}", json={"finished": False}).json()
        self.assertIsNone(reopened["finishedAt"])
        self.assert_error(client.patch(f"/api/lists/{list_id}", json={}), 400, "INVALID_BODY")


class MembersTest(ApiTest):
    def test_joining_twice_with_one_name_is_one_member_and_an_email_is_kept(self):
        list_id = self.make_list()["id"]
        first = self.join(list_id)
        again = self.join(list_id, email="ana@example.com")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(again["email"], "ana@example.com")
        self.assertEqual(self.join(list_id)["email"], "ana@example.com")
        self.assertEqual(len(client.get(f"/api/lists/{list_id}").json()["members"]), 1)

    def test_bad_input(self):
        list_id = self.make_list()["id"]
        for body in ({}, {"name": " "}, {"name": "Ana", "email": "not-an-email"}):
            with self.subTest(body=body):
                self.assert_error(
                    client.post(f"/api/lists/{list_id}/members", json=body), 400, "INVALID_BODY"
                )
        self.assert_error(
            client.post(f"/api/lists/{uuid.uuid4()}/members", json={"name": "Ana"}), 404, "LIST_NOT_FOUND"
        )


class ItemsTest(ApiTest):
    def test_add_items_go_after_the_existing_ones(self):
        list_id = self.make_list()["id"]
        response = client.post(f"/api/lists/{list_id}/items", json={"items": [{"name": "Bin"}]})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()[0]["estPriceCents"])
        names = [item["name"] for item in client.get(f"/api/lists/{list_id}").json()["items"]]
        self.assertEqual(names, ["Kettle", "Mop", "Bin"])
        self.assert_error(client.post(f"/api/lists/{list_id}/items", json={}), 400, "INVALID_BODY")
        self.assert_error(
            client.post(f"/api/lists/{uuid.uuid4()}/items", json={"items": []}), 404, "LIST_NOT_FOUND"
        )

    def test_claim_check_and_uncheck(self):
        created = self.make_list()
        member = self.join(created["id"])
        item_id = created["items"][0]["id"]

        claimed = client.patch(f"/api/items/{item_id}", json={"claimedBy": member["id"]}).json()
        self.assertEqual(claimed["claimedBy"], member["id"])

        checked = client.patch(
            f"/api/items/{item_id}", json={"checked": True, "memberId": member["id"], "priceCents": 2399}
        ).json()
        self.assertTrue(checked["checkedAt"])
        self.assertEqual((checked["boughtBy"], checked["priceCents"]), (member["id"], 2399))

        unchecked = client.patch(f"/api/items/{item_id}", json={"checked": False}).json()
        self.assertEqual(
            (unchecked["checkedAt"], unchecked["boughtBy"], unchecked["priceCents"]), (None, None, None)
        )

    def test_bad_updates(self):
        created = self.make_list()
        item_id = created["items"][0]["id"]
        stranger = self.join(self.make_list()["id"], "Stranger")
        for body in (
            {},
            {"name": ""},
            {"estPriceCents": "12"},
            {"claimedBy": stranger["id"]},
            {"checked": True, "memberId": "nope"},
        ):
            with self.subTest(body=body):
                self.assert_error(client.patch(f"/api/items/{item_id}", json=body), 400, "INVALID_BODY")
        self.assert_error(client.patch("/api/items/nope", json={"name": "x"}), 404, "ITEM_NOT_FOUND")

    def test_delete(self):
        created = self.make_list()
        item_id = created["items"][0]["id"]
        self.assertEqual(client.delete(f"/api/items/{item_id}").status_code, 204)
        self.assertEqual(len(client.get(f"/api/lists/{created['id']}").json()["items"]), 1)
        self.assert_error(client.delete(f"/api/items/{item_id}"), 404, "ITEM_NOT_FOUND")


class CreateOrderTest(ApiTest):
    def setUp(self):
        super().setUp()
        self.list = self.make_list()
        self.ids = [item["id"] for item in self.list["items"]]
        self.url = f"/api/lists/{self.list['id']}/orders"

    def test_the_server_looks_up_the_prices_and_stores_the_order(self):
        member = self.join(self.list["id"])
        with mock.patch.object(paypal, "create_order", return_value="ORDER1") as create_order:
            # An amount sent by the browser is ignored.
            response = client.post(
                self.url, json={"itemIds": self.ids, "memberId": member["id"], "totalCents": 1}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"orderId": "ORDER1"})
        create_order.assert_called_once_with(
            [{"name": "Kettle", "priceCents": 2500}, {"name": "Mop", "priceCents": 1200}]
        )
        order = self.db.tables["orders"][0]
        self.assertEqual(
            (order["id"], order["total_cents"], order["item_ids"], order["member_id"], order["status"]),
            ("ORDER1", 3700, self.ids, member["id"], "CREATED"),
        )

    def test_bad_input_is_400_and_never_reaches_paypal(self):
        other = self.make_list()["items"][0]["id"]
        unpriced = client.post(
            f"/api/lists/{self.list['id']}/items", json={"items": [{"name": "Bin"}]}
        ).json()[0]["id"]
        client.patch(f"/api/items/{self.ids[1]}", json={"checked": True})
        bodies = [
            {"itemIds": []},
            {"itemIds": [self.ids[0], self.ids[0]]},
            {"itemIds": self.ids[0]},
            {"itemIds": [[self.ids[0]]]},
            {"itemIds": ["nope"]},
            {"itemIds": [other]},  # on another list
            {"itemIds": [unpriced]},  # no price to charge
            {"itemIds": [self.ids[1]]},  # already checked off
            {"itemIds": [self.ids[0]], "memberId": str(uuid.uuid4())},
            {},
        ]
        with mock.patch.object(paypal, "create_order") as create_order:
            for body in bodies:
                with self.subTest(body=body):
                    self.assert_error(client.post(self.url, json=body), 400, "INVALID_ITEMS")
            for raw in ("[]", "null", "not json", ""):
                with self.subTest(raw=raw):
                    response = client.post(
                        self.url, content=raw, headers={"Content-Type": "application/json"}
                    )
                    self.assert_error(response, 400, "INVALID_ITEMS")
        create_order.assert_not_called()
        self.assertNotIn("orders", self.db.tables)

    def test_unknown_list_is_404(self):
        response = client.post(f"/api/lists/{uuid.uuid4()}/orders", json={"itemIds": self.ids})
        self.assert_error(response, 404, "LIST_NOT_FOUND")

    def test_a_paypal_failure_is_a_generic_502_and_stores_nothing(self):
        failure = paypal.PayPalError(500, "INTERNAL_SERVER_ERROR")
        with mock.patch.object(paypal, "create_order", side_effect=failure):
            self.assert_error(client.post(self.url, json={"itemIds": self.ids}), 502, "PAYPAL_ERROR")
        self.assertNotIn("orders", self.db.tables)

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        with mock.patch.object(paypal, "create_order", side_effect=RuntimeError("no credentials")):
            with self.assertLogs("main", "ERROR"):
                self.assert_error(client.post(self.url, json={"itemIds": self.ids}), 502, "PAYPAL_ERROR")


class CaptureOrderTest(ApiTest):
    def setUp(self):
        super().setUp()
        self.list = self.make_list()
        self.member = self.join(self.list["id"])
        self.item_id = self.list["items"][0]["id"]
        with mock.patch.object(paypal, "create_order", return_value="ORDER1"):
            client.post(
                f"/api/lists/{self.list['id']}/orders",
                json={"itemIds": [self.item_id], "memberId": self.member["id"]},
            )

    def test_malformed_order_id_is_400_and_never_reaches_paypal(self):
        with mock.patch.object(paypal, "capture_order") as capture_order:
            for order_id in ("abc", "ORDER-1", "A" * 37):
                with self.subTest(order_id=order_id):
                    self.assert_error(
                        client.post(f"/api/orders/{order_id}/capture"), 400, "INVALID_ORDER_ID"
                    )
            # An order this backend did not create is not captured either.
            self.assert_error(client.post("/api/orders/ORDER2/capture"), 404, "ORDER_NOT_FOUND")
        capture_order.assert_not_called()

    def test_a_completed_capture_is_stored_as_the_proof(self):
        result = {"orderId": "ORDER1", "status": "COMPLETED"}
        with mock.patch.object(paypal, "capture_order", return_value=result):
            response = client.post("/api/orders/ORDER1/capture")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

        state = client.get(f"/api/lists/{self.list['id']}").json()
        paid, open_item = state["items"]
        self.assertTrue(paid["checkedAt"])
        self.assertEqual(
            (paid["orderId"], paid["priceCents"], paid["boughtBy"]), ("ORDER1", 2500, self.member["id"])
        )
        self.assertIsNone(open_item["checkedAt"])
        self.assertEqual([order["id"] for order in state["orders"]], ["ORDER1"])
        self.assertTrue(state["orders"][0]["capturedAt"])

        # A paid item cannot be unticked, re-priced, deleted, or paid for again.
        self.assert_error(client.patch(f"/api/items/{self.item_id}", json={"checked": False}), 409, "ITEM_PAID")
        self.assert_error(client.patch(f"/api/items/{self.item_id}", json={"estPriceCents": 1}), 409, "ITEM_PAID")
        self.assert_error(client.delete(f"/api/items/{self.item_id}"), 409, "ITEM_PAID")
        with mock.patch.object(paypal, "create_order") as create_order:
            again = client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [self.item_id]})
        self.assert_error(again, 400, "INVALID_ITEMS")
        create_order.assert_not_called()

    def test_a_capture_that_is_not_completed_checks_nothing_off(self):
        result = {"orderId": "ORDER1", "status": "PENDING"}
        with mock.patch.object(paypal, "capture_order", return_value=result):
            self.assertEqual(client.post("/api/orders/ORDER1/capture").json(), result)
        state = client.get(f"/api/lists/{self.list['id']}").json()
        self.assertIsNone(state["items"][0]["checkedAt"])
        self.assertEqual(state["orders"], [])

    def test_maps_paypal_failures_to_the_error_contract(self):
        for issue, status, code in [
            ("INSTRUMENT_DECLINED", 422, "INSTRUMENT_DECLINED"),
            ("ORDER_NOT_APPROVED", 502, "PAYPAL_ERROR"),
        ]:
            with self.subTest(issue=issue):
                failure = paypal.PayPalError(422, issue)
                with mock.patch.object(paypal, "capture_order", side_effect=failure):
                    self.assert_error(client.post("/api/orders/ORDER1/capture"), status, code)

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        with mock.patch.object(paypal, "capture_order", side_effect=RuntimeError("no credentials")):
            with self.assertLogs("main", "ERROR"):
                self.assert_error(client.post("/api/orders/ORDER1/capture"), 502, "PAYPAL_ERROR")


if __name__ == "__main__":
    unittest.main()
