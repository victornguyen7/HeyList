import re
import unittest
import uuid
from pathlib import Path
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import db
import kroger
import llm
import main
import market
import paypal
import receipts

# Every table's columns, read from the schema so the fake can't drift from it. Unset columns are None.
SCHEMA = (Path(__file__).parent.parent / "supabase" / "schema.sql").read_text()
COLUMNS = {
    table: re.findall(r"^  (?!constraint|unique)(\w+) ", body, re.M)
    for table, body in re.findall(r"create table if not exists (\w+) \((.*?)\n\);", SCHEMA, re.S)
}
# Column defaults the routes read back.
DEFAULTS = {
    "lists": {"kind": "other"},
    "items": {"position": 0, "quantity": 1, "price_typed": False, "owned": False},
    "orders": {"status": "CREATED", "prices": {}, "taxes": {}, "refunds": {}, "products": {}},
    "settlements": {"status": "CREATED"},
    "receipts": {"lines": [], "fees": [], "extras": []},
}


def generate(table, row):
    """The generated columns Postgres keeps up to date."""
    if table == "items":
        row["name_key"] = row["name"].strip().lower()


class FakeDB:
    """The four db calls over in-memory tables."""

    def __init__(self):
        self.tables = {}
        self.files = {}

    def upload(self, path, data, content_type):
        self.files[path] = data

    def download(self, path):
        return self.files[path]

    def rows(self, table, filters):
        def matches(row, column, value):
            return row.get(column) in value if isinstance(value, list) else row.get(column) == value

        return [row for row in self.tables.get(table, []) if all(matches(row, c, v) for c, v in filters.items())]

    def select(self, table, order="created_at", **filters):
        return sorted((dict(row) for row in self.rows(table, filters)), key=lambda row: row.get(order) or 0)

    def insert(self, table, rows):
        # PostgREST fills a key some rows leave out with null rather than the default, so rows must agree.
        if len({frozenset(row) for row in rows}) > 1:
            raise AssertionError(f"rows inserted into {table} have different keys")
        added = []
        for row in rows:
            added.append({
                    **dict.fromkeys(COLUMNS[table]),
                    "id": str(uuid.uuid4()),
                    "created_at": len(self.tables.get(table, [])),
                    **DEFAULTS.get(table, {}),
                    **row,
                })
            generate(table, added[-1])
            self.tables.setdefault(table, []).append(added[-1])
        return [dict(row) for row in added]

    def update(self, table, values, **filters):
        # The rows it changed, like Postgres: matched before the write, so a filter on a column it sets still counts.
        changed = self.rows(table, filters)
        for row in changed:
            row.update(values)
            generate(table, row)
        return [dict(row) for row in changed]

    def delete(self, table, **filters):
        doomed = self.rows(table, filters)
        self.tables[table] = [row for row in self.tables[table] if row not in doomed]


def stale_reads(fake, table, **columns):
    """Selects from table show columns as given, as if another request changed the rows after they were read."""
    select = fake.select
    return mock.patch.object(
        db, "select", lambda t, *args, **filters: [row | columns if t == table else row for row in select(t, *args, **filters)]
    )


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        for name in ("select", "insert", "update", "delete", "upload", "download"):
            patch = mock.patch.object(db, name, getattr(self.db, name))
            patch.start()
            self.addCleanup(patch.stop)
        main._calls.clear()
        # No store searches in tests unless a test asks for them: nothing reaches Channel3.
        search = mock.patch.object(market, "search", return_value=[])
        self.market_search = search.start()
        self.addCleanup(search.stop)
        # Kroger is off unless a test turns it on.
        krog = mock.patch.object(kroger, "enabled", return_value=False)
        self.kroger_on = krog.start()
        self.addCleanup(krog.stop)
        # No AI price guesses in tests unless a test asks for them.
        estimate = mock.patch.object(llm, "estimate_prices", side_effect=lambda names, context=None: [None] * len(names))
        self.estimate = estimate.start()
        self.addCleanup(estimate.stop)
        self.client = TestClient(main.app)

    def new_list(self, items):
        response = self.client.post("/api/lists", json={"title": "Trip", "kind": "trip", "items": items})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def mock_paypal(self, name, **kwargs):
        patch = mock.patch.object(paypal, name, **kwargs)
        self.addCleanup(patch.stop)
        return patch.start()


class HealthTest(RoutesTest):
    def test_health_answers_without_touching_the_database(self):
        with mock.patch.object(db, "select", side_effect=AssertionError("no db call")):
            self.assertEqual(self.client.get("/api/health").json(), {"ok": True})


class OwnedItemsTest(RoutesTest):
    def test_an_item_already_had_is_checked_off_at_no_cost(self):
        state = self.new_list([{"name": "Tent", "estPriceCents": 9000, "owned": True}, {"name": "Firewood", "estPriceCents": 1200}])
        tent, firewood = state["items"]
        self.assertTrue(tent["owned"])
        self.assertIsNotNone(tent["checkedAt"])
        self.assertIsNone(tent["priceCents"])
        self.assertIsNone(tent["boughtBy"])
        self.assertFalse(firewood["owned"])
        self.assertIsNone(firewood["checkedAt"])

    def test_a_list_whose_items_fail_to_save_is_taken_back(self):
        with mock.patch.object(db, "insert", side_effect=[[{"id": "list-1"}], RuntimeError("boom")]), mock.patch.object(db, "delete") as delete:
            with self.assertRaises(RuntimeError):
                self.client.post("/api/lists", json={"title": "Trip", "items": [{"name": "Tent"}]})
        delete.assert_called_once_with("lists", id="list-1")

    def test_unticking_an_item_already_had_means_it_is_needed(self):
        tent = self.new_list([{"name": "Tent", "owned": True}])["items"][0]
        saved = self.client.patch(f"/api/items/{tent['id']}", json={"checked": False}).json()
        self.assertFalse(saved["owned"])
        self.assertIsNone(saved["checkedAt"])


class PricesTest(RoutesTest):
    def test_an_item_added_without_a_price_gets_one(self):
        the_list = self.new_list([{"name": "Tent", "estPriceCents": 9000}])
        self.estimate.side_effect = lambda names, context=None: [450] * len(names)

        added = self.client.post(f"/api/lists/{the_list['id']}/items", json={"items": [{"name": "Milk"}, {"name": "Rope", "estPriceCents": 700}]}).json()

        self.assertEqual([(i["name"], i["estPriceCents"]) for i in added], [("Milk", 450), ("Rope", 700)])
        # Only the unpriced one was asked about, with the list's name.
        self.estimate.assert_called_once_with(["Milk"], "Trip")

    def test_price_memory_comes_before_the_ai(self):
        the_list = self.new_list([{"name": "Milk", "estPriceCents": 400}])
        milk = the_list["items"][0]
        self.db.update("items", {"checked_at": "earlier", "price_cents": 459, "order_id": None, "receipt_id": None}, id=milk["id"])
        self.db.update("items", {"product": {"priceCents": 389}}, id=milk["id"])
        self.estimate.side_effect = lambda names, context=None: [999] * len(names)

        reply = self.client.post("/api/prices", json={"names": ["milk", "Bread"], "context": "Groceries"}).json()

        self.assertEqual(reply["items"], [{"name": "milk", "estPriceCents": 389, "priceSource": "store"}, {"name": "Bread", "estPriceCents": 999, "priceSource": "estimate"}])
        self.estimate.assert_called_once_with(["Bread"], "Groceries")

    def test_a_failed_guess_still_adds_the_item(self):
        the_list = self.new_list([{"name": "Tent", "estPriceCents": 9000}])
        self.estimate.side_effect = RuntimeError("down")
        with self.assertLogs(main.log):
            added = self.client.post(f"/api/lists/{the_list['id']}/items", json={"items": [{"name": "Milk"}]})
        self.assertEqual((added.status_code, added.json()[0]["estPriceCents"]), (200, None))
        self.assertEqual(self.client.post("/api/prices", json={"names": []}).status_code, 400)


class PriceStoreTest(RoutesTest):
    def test_the_store_a_price_came_from_is_kept_and_cleared_when_the_price_changes(self):
        items = self.new_list([
            {"name": "Charcoal", "estPriceCents": 1029, "priceSource": "market", "priceStore": "walmart.com"},
            {"name": "Ketchup", "estPriceCents": 369, "priceSource": "market", "priceStore": "kroger.com"},
            {"name": "Rope", "estPriceCents": 800, "priceSource": "made-up", "priceStore": "evil.example"},  # unknown source and store
            {"name": "Tent", "priceSource": "estimate", "priceStore": "target.com"},  # no price, so neither
            {"name": "Sunscreen", "estPriceCents": 899, "priceSource": "paid", "priceStore": "target.com"},  # paid before: no store
            {"name": "Towel", "estPriceCents": 1200, "priceSource": "estimate"},
        ])["items"]
        self.assertEqual([(i["priceSource"], i["priceStore"]) for i in items],
                         [("market", "walmart.com"), ("market", "kroger.com"), (None, None), (None, None), ("paid", None), ("estimate", None)])

        saved = self.client.patch(f"/api/items/{items[0]['id']}", json={"estPriceCents": 1500}).json()
        self.assertEqual((saved["estPriceCents"], saved["priceSource"], saved["priceStore"]), (1500, None, None))
        # A quantity change keeps it: still that store's price for one.
        self.assertEqual(self.client.patch(f"/api/items/{items[1]['id']}", json={"quantity": 3}).json()["priceStore"], "kroger.com")

    def test_an_item_added_on_progress_keeps_its_store(self):
        the_list = self.new_list([{"name": "Tent", "estPriceCents": 9000}])
        self.market_search.side_effect = lambda name, stores=None: [ProductRoutesTest.PRODUCT | {"title": "Paper plates", "priceCents": 300, "store": "target.com"}]
        mock.patch.object(llm, "market_matches", side_effect=lambda items, title: ([i["products"] for i in items], [False] * len(items))).start()
        self.addCleanup(mock.patch.stopall)

        added = self.client.post(f"/api/lists/{the_list['id']}/items", json={"items": [{"name": "Paper plates"}]}).json()

        self.assertEqual((added[0]["estPriceCents"], added[0]["priceSource"], added[0]["priceStore"]), (300, "market", "target.com"))


class ListRoutesTest(RoutesTest):
    def test_a_new_list_comes_back_with_its_items_in_order(self):
        state = self.new_list([{"name": "Sunscreen", "estPriceCents": 899, "quantity": 2}, {"name": "Adapter"}])

        self.assertEqual(state["title"], "Trip")
        self.assertEqual([(i["name"], i["quantity"], i["position"]) for i in state["items"]], [("Sunscreen", 2, 0), ("Adapter", 1, 1)])
        self.assertEqual(self.client.get(f"/api/lists/{state['id']}").json(), state)

    def test_an_item_keeps_its_note(self):
        items = self.new_list([{"name": "Flashlight", "note": "only if nobody has one"}, {"name": "Tent", "note": None}])["items"]

        self.assertEqual([item["note"] for item in items], ["only if nobody has one", None])
        response = self.client.post("/api/lists", json={"title": "Trip", "items": [{"name": "Tent", "note": "x" * 201}]})
        self.assertEqual(response.status_code, 400)

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

    def test_many_lists_load_in_one_request_each_with_only_its_own_rows(self):
        one, two = self.new_list([{"name": "Tent"}]), self.new_list([{"name": "Milk"}, {"name": "Eggs"}])
        ids = ",".join([two["id"], "not-a-uuid", str(uuid.uuid4()), one["id"]])

        lists = self.client.get(f"/api/lists?ids={ids}").json()["lists"]

        self.assertEqual(sorted(lists, key=lambda state: state["id"]), sorted([one, two], key=lambda state: state["id"]))
        self.assertEqual(self.client.get("/api/lists").json(), {"lists": []})

    def test_a_quantity_must_be_a_whole_number_from_1_to_99(self):
        item = self.new_list([{"name": "Sunscreen"}])["items"][0]
        for bad in (0, 100, 2.5, "2", True):
            with self.subTest(quantity=bad):
                self.assertEqual(self.client.patch(f"/api/items/{item['id']}", json={"quantity": bad}).status_code, 400)

        self.assertEqual(self.client.patch(f"/api/items/{item['id']}", json={"quantity": 3}).json()["quantity"], 3)


class AccountTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([])
        # Two accounts by token; db.user stands in for Supabase Auth.
        users = {"ann-token": {"id": str(uuid.uuid4()), "name": "Ann"}, "new-token": {"id": str(uuid.uuid4()), "name": None}}
        patch = mock.patch.object(db, "user", users.get)
        patch.start()
        self.addCleanup(patch.stop)

    def join(self, token=None, **body):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post(f"/api/lists/{self.list['id']}/members", json=body, headers=headers)


class MyListsTest(AccountTest):
    def test_every_list_the_account_joined_comes_back_newest_join_first(self):
        first = self.list
        self.join("ann-token")
        self.list = second = self.new_list([{"name": "Tent"}])
        self.join("ann-token")
        self.list = self.new_list([])
        self.join(name="Guest Ann")  # joined as a guest: not the account's
        self.join("new-token", name="Bob")  # someone else's account

        found = self.client.get("/api/me/lists", headers={"Authorization": "Bearer ann-token"}).json()["lists"]

        self.assertEqual([l["id"] for l in found], [second["id"], first["id"]])
        self.assertEqual(found[0]["items"][0]["name"], "Tent")

    def test_a_guest_or_a_bad_token_is_401(self):
        self.assertEqual(self.client.get("/api/me/lists").status_code, 401)
        self.assertEqual(self.client.get("/api/me/lists", headers={"Authorization": "Bearer nope"}).status_code, 401)

    def test_a_deleted_list_is_left_out(self):
        self.join("ann-token")
        self.db.delete("lists", id=self.list["id"])
        self.assertEqual(self.client.get("/api/me/lists", headers={"Authorization": "Bearer ann-token"}).json(), {"lists": []})


class JoinTest(AccountTest):
    def test_logged_in_joins_without_a_name_and_gets_the_same_member_back(self):
        first = self.join("ann-token").json()

        self.assertEqual(first["name"], "Ann")
        self.assertEqual(self.join("ann-token", name="Annie").json()["id"], first["id"])

    def test_an_account_without_a_name_gives_one_the_first_time(self):
        self.assertEqual(self.join("new-token").status_code, 400)
        self.assertEqual(self.join("new-token", name="Bob").json()["name"], "Bob")

    def test_an_account_without_a_saved_name_reuses_the_one_it_joined_with_before(self):
        self.join("new-token", name="Bob")
        self.list = self.new_list([])

        self.assertEqual(self.join("new-token").json()["name"], "Bob")

    def test_a_guest_cannot_take_an_accounts_name_but_an_account_can_claim_a_guests(self):
        self.join("ann-token")
        guest = self.join(name="Bob").json()

        self.assertEqual(self.join(name="Ann").status_code, 409)
        self.assertEqual(self.join(name="Ann").json(), {"error": "NAME_TAKEN"})
        self.assertEqual(self.join("new-token", name="Bob").json()["id"], guest["id"])

    def test_a_bad_token_is_a_guest(self):
        self.assertEqual(self.join("expired", name="Cat").json()["userId"], None)


class LockTest(AccountTest):
    """Acting as a member who joined logged in needs that login; a guest member stays open to anyone (decision 53)."""

    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Tent", "estPriceCents": 9000}, {"name": "Map", "estPriceCents": 500}])
        self.tent, self.map = (item["id"] for item in self.list["items"])
        self.ann = self.join("ann-token").json()["id"]
        self.bob = self.join(name="Bob").json()["id"]

    def tick(self, item, member, token=None, checked=True):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.patch(f"/api/items/{item}", json={"checked": checked, "memberId": member}, headers=headers)

    def test_only_ann_can_tick_off_or_untick_as_ann(self):
        self.assertEqual(self.tick(self.tent, self.ann).json(), {"error": "NOT_YOURS"})
        self.assertEqual(self.tick(self.tent, self.ann, "new-token").status_code, 403)
        self.assertEqual(self.tick(self.tent, self.ann, "ann-token").status_code, 200)

        self.assertEqual(self.tick(self.tent, None, checked=False).status_code, 403)
        self.assertEqual(self.tick(self.tent, None, "ann-token", checked=False).status_code, 200)

    def test_a_guest_member_is_open_to_anyone(self):
        self.assertEqual(self.tick(self.map, self.bob).status_code, 200)
        self.assertEqual(self.tick(self.map, None, checked=False).status_code, 200)

    def test_only_ann_can_pay_as_ann(self):
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        order = lambda **headers: self.client.post(
            f"/api/lists/{self.list['id']}/orders", json={"itemIds": [self.tent], "memberId": self.ann}, headers=headers
        )

        self.assertEqual(order().status_code, 403)
        create.assert_not_called()
        self.assertEqual(order(Authorization="Bearer ann-token").status_code, 200)

    def test_only_ann_can_scan_or_confirm_a_receipt_as_ann(self):
        scan = self.client.post(f"/api/lists/{self.list['id']}/receipts?memberId={self.ann}", content=b"photo", headers={"Content-Type": "image/jpeg"})
        self.assertEqual(scan.status_code, 403)

        receipt = self.db.insert("receipts", [{"list_id": self.list["id"], "member_id": self.ann, "lines": [], "image_path": "x"}])[0]
        confirm = lambda **headers: self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": []}, headers=headers)
        self.assertEqual(confirm().status_code, 403)
        self.assertEqual(confirm(Authorization="Bearer ann-token").status_code, 200)


class CheckoutTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list(
            [{"name": "Sunscreen", "estPriceCents": 899, "quantity": 2}, {"name": "Adapter", "estPriceCents": 1499}, {"name": "Map"}]
        )
        self.sunscreen, self.adapter, self.map = self.list["items"]
        self.refund = self.mock_paypal("refund", return_value={"refundId": "REF1", "status": "COMPLETED"})

    def order(self, *items, **body):
        return self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [item["id"] for item in items], **body})

    def join(self, name):
        return self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": name}).json()["id"]

    def test_the_order_uses_database_prices_and_quantities(self):
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        self.assertEqual(self.order(self.sunscreen, self.adapter).json(), {"orderId": "ORDER1", "approveUrl": "https://pay"})

        items, return_url = create.call_args.args
        self.assertEqual(
            items,
            [{"name": "Sunscreen", "priceCents": 899, "quantity": 2, "taxCents": 0}, {"name": "Adapter", "priceCents": 1499, "quantity": 1, "taxCents": 0}],
        )
        self.assertEqual(return_url, f"{main.APP_URL}/lists/{self.list['id']}")
        self.assertEqual(self.db.tables["orders"][0]["total_cents"], 899 * 2 + 1499)

    def test_the_venmo_button_asks_for_a_venmo_order_and_other_methods_are_refused(self):
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": None})
        ids = [self.sunscreen["id"]]

        self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": ids, "method": "venmo"})
        self.assertEqual(create.call_args.kwargs, {"venmo": True})
        self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": ids})
        self.assertEqual(create.call_args.kwargs, {"venmo": False})
        self.assertEqual(self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": ids, "method": "card"}).status_code, 400)

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
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": status, "captureId": "CAP1"})
        response = self.client.post("/api/orders/ORDER1/capture")
        return response, {item["name"]: item for item in self.client.get(f"/api/lists/{self.list['id']}").json()["items"]}

    def test_a_completed_capture_checks_the_items_off_at_price_times_quantity(self):
        response, items = self.capture("COMPLETED")

        self.assertEqual(response.json(), {"orderId": "ORDER1", "status": "COMPLETED", "refundedCents": 0})
        self.assertEqual(items["Sunscreen"]["priceCents"], 899 * 2)
        self.assertEqual(items["Adapter"]["orderId"], "ORDER1")
        self.assertIsNone(items["Map"]["checkedAt"])
        # A paid item cannot be unticked or re-priced.
        self.assertEqual(self.client.patch(f"/api/items/{self.adapter['id']}", json={"quantity": 2}).status_code, 409)

    def test_capture_records_the_price_paypal_charged_even_if_the_item_changed_since(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.sunscreen)
        self.client.patch(f"/api/items/{self.sunscreen['id']}", json={"quantity": 5, "estPriceCents": 1})
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})
        self.client.post("/api/orders/ORDER1/capture")

        self.assertEqual(self.db.select("items", id=self.sunscreen["id"])[0]["price_cents"], 899 * 2)

    def test_a_single_item_already_checked_off_is_refunded_to_the_paypal_buyer(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.sunscreen, self.adapter)
        self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 500}, id=self.adapter["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        response = self.client.post("/api/orders/ORDER1/capture").json()
        # A repeated capture (refresh, Strict Mode) doesn't refund again.
        self.client.post("/api/orders/ORDER1/capture")

        self.assertEqual(response, {"orderId": "ORDER1", "status": "COMPLETED", "refundedCents": 1499})
        self.refund.assert_called_once_with("CAP1", 1499, f"ORDER1-{self.adapter['id']}")
        adapter = self.db.select("items", id=self.adapter["id"])[0]
        self.assertEqual((adapter["receipt_id"], adapter["order_id"], adapter["price_cents"]), ("R1", None, 500))
        self.assertEqual(self.db.select("items", id=self.sunscreen["id"])[0]["order_id"], "ORDER1")
        self.assertEqual(self.db.tables["orders"][0]["refunds"][self.adapter["id"]]["refundId"], "REF1")
        # The refunded charge isn't money the buyer spent (decision 39).
        split = self.client.get(f"/api/lists/{self.list['id']}/split").json()
        self.assertEqual((split["unattributedCents"], split["boughtTwice"]), (899 * 2 + 500, []))

    def test_the_lists_sales_tax_is_charged_per_unit_and_counted_in_the_split(self):
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.assertEqual(self.client.patch(f"/api/lists/{self.list['id']}", json={"taxRateBp": 825}).json()["tax"], {"rateBp": 825, "source": "set"})

        self.order(self.sunscreen, self.adapter, memberId=self.join("Ann"))

        # 8.25% of 8.99 is 0.74 a unit, of 14.99 is 1.24.
        self.assertEqual([item["taxCents"] for item in create.call_args.args[0]], [74, 124])
        order = self.db.tables["orders"][0]
        self.assertEqual(order["taxes"], {self.sunscreen["id"]: 148, self.adapter["id"]: 124})
        self.assertEqual(order["total_cents"], 899 * 2 + 1499 + 148 + 124)
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})
        self.client.post("/api/orders/ORDER1/capture")
        # The items keep their price before tax, as from a receipt; the tax is its own line in the split.
        self.assertEqual(self.db.select("items", id=self.sunscreen["id"])[0]["price_cents"], 899 * 2)
        split = self.client.get(f"/api/lists/{self.list['id']}/split").json()
        self.assertEqual((split["itemsCents"], split["taxCents"], split["totalCents"]), (899 * 2 + 1499, 272, 899 * 2 + 1499 + 272))

    def test_an_item_refunded_at_capture_gets_its_tax_back_too(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.client.patch(f"/api/lists/{self.list['id']}", json={"taxRateBp": 1000})
        self.order(self.sunscreen, self.adapter, memberId=self.join("Ann"))
        self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 500}, id=self.adapter["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        self.assertEqual(self.client.post("/api/orders/ORDER1/capture").json()["refundedCents"], 1499 + 150)
        self.refund.assert_called_once_with("CAP1", 1499 + 150, f"ORDER1-{self.adapter['id']}")
        # Only the sunscreen's tax is still money spent.
        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}/split").json()["taxCents"], 180)

    def test_a_tax_rate_must_be_a_whole_number_of_basis_points_up_to_25_percent(self):
        for rate in (2501, -1, 8.25, "825", True):
            with self.subTest(rate=rate):
                self.assertEqual(self.client.patch(f"/api/lists/{self.list['id']}", json={"taxRateBp": rate}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/lists/{self.list['id']}", json={"taxRateBp": None}).json()["tax"], {"rateBp": 0, "source": None})

    def test_every_unit_of_an_item_already_checked_off_is_refunded(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.sunscreen)
        self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 900}, id=self.sunscreen["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        # Both units were already bought, so both units PayPal charged for go back.
        self.assertEqual(self.client.post("/api/orders/ORDER1/capture").json()["refundedCents"], 899 * 2)
        self.refund.assert_called_once_with("CAP1", 899 * 2, f"ORDER1-{self.sunscreen['id']}")
        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}/split").json()["boughtTwice"], [])

    def test_a_failed_refund_still_counts_the_charge(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.adapter)
        self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 500}, id=self.adapter["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})
        self.refund.side_effect = paypal.PayPalError(422, "CAPTURE_FULLY_REFUNDED")

        with self.assertLogs(main.log, "ERROR"):
            self.assertEqual(self.client.post("/api/orders/ORDER1/capture").json()["refundedCents"], 0)
        split = self.client.get(f"/api/lists/{self.list['id']}/split").json()
        self.assertEqual([b["cents"] for b in split["boughtTwice"]], [1499])

    def test_a_refund_recorded_by_a_capture_at_the_same_moment_is_kept(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.sunscreen, self.adapter)
        for item in (self.sunscreen, self.adapter):
            self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 500}, id=item["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        def refund(capture_id, cents, request_id):
            if request_id.endswith(self.sunscreen["id"]):
                return {"refundId": "REF1", "status": "COMPLETED"}
            # The other capture refunded the adapter and saved it; this one's call was still in progress.
            other = {self.adapter["id"]: {"refundId": "REF2", "status": "COMPLETED", "cents": 1499}}
            self.db.update("orders", {"refunds": other}, id="ORDER1")
            raise paypal.PayPalError(409, "PREVIOUS_REQUEST_IN_PROGRESS")

        self.refund.side_effect = refund
        with self.assertLogs(main.log, "ERROR"):
            response = self.client.post("/api/orders/ORDER1/capture").json()

        refunds = self.db.tables["orders"][0]["refunds"]
        self.assertEqual({key: value["refundId"] for key, value in refunds.items()}, {self.sunscreen["id"]: "REF1", self.adapter["id"]: "REF2"})
        self.assertEqual(response["refundedCents"], 899 * 2 + 1499)

    def test_a_receipt_confirmed_while_capture_runs_keeps_its_item(self):
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.order(self.adapter)
        self.db.update("items", {"checked_at": "earlier", "receipt_id": "R1", "price_cents": 500}, id=self.adapter["id"])
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        with stale_reads(self.db, "items", checked_at=None):
            self.client.post("/api/orders/ORDER1/capture")
        adapter = self.db.select("items", id=self.adapter["id"])[0]
        self.assertEqual((adapter["receipt_id"], adapter["order_id"], adapter["price_cents"]), ("R1", None, 500))
        self.refund.assert_called_once()

    def test_checking_off_by_hand_never_overwrites_a_purchase_that_just_landed(self):
        self.db.update("items", {"checked_at": "earlier", "order_id": "ORDER1", "price_cents": 1499}, id=self.adapter["id"])
        url = f"/api/items/{self.adapter['id']}"

        with stale_reads(self.db, "items", checked_at=None, order_id=None):
            self.assertEqual(self.client.patch(url, json={"checked": True, "priceCents": 1}).json(), {"error": "ITEM_CHECKED"})
            self.assertEqual(self.client.patch(url, json={"checked": False}).json(), {"error": "ITEM_PAID"})
            self.assertEqual(self.client.patch(url, json={"name": "Plug"}).status_code, 200)
        adapter = self.db.select("items", id=self.adapter["id"])[0]
        self.assertEqual((adapter["order_id"], adapter["price_cents"], adapter["name"]), ("ORDER1", 1499, "Plug"))

    def test_a_pending_payment_checks_nothing_off(self):
        response, items = self.capture("PENDING")

        self.assertEqual(response.json()["status"], "PENDING")
        self.assertTrue(all(item["checkedAt"] is None for item in items.values()))
        self.assertEqual(self.db.tables["orders"][0]["status"], "PENDING")
        # The list shows it as pending, and its items can't be paid for again until PayPal decides.
        orders = self.client.get(f"/api/lists/{self.list['id']}").json()["orders"]
        self.assertEqual([(o["id"], o["status"]) for o in orders], [("ORDER1", "PENDING")])
        create = self.mock_paypal("create_order")
        self.assertEqual(self.order(self.adapter).json(), {"error": "PAYMENT_PENDING"})
        create.assert_not_called()

    def test_a_pending_payment_that_completes_later_checks_the_items_off(self):
        self.capture("PENDING")
        self.mock_paypal("get_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})

        self.assertEqual(self.client.post("/api/orders/ORDER1/refresh").json()["status"], "COMPLETED")
        items = self.db.select("items", order_id="ORDER1")
        self.assertEqual(sorted(i["name"] for i in items), ["Adapter", "Sunscreen"])
        # Only a pending order is asked about again.
        self.assertEqual(self.client.post("/api/orders/ORDER1/refresh").json(), {"error": "ORDER_NOT_PENDING"})
        self.assertEqual(self.client.post("/api/orders/NOPE1/refresh").status_code, 404)

    def test_a_pending_payment_that_is_declined_releases_its_items(self):
        self.capture("PENDING")
        self.mock_paypal("get_order", return_value={"orderId": "ORDER1", "status": "DECLINED", "captureId": "CAP1"})
        self.client.post("/api/orders/ORDER1/refresh")

        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}").json()["orders"], [])
        self.mock_paypal("create_order", return_value={"orderId": "ORDER2", "approveUrl": "https://pay"})
        self.assertEqual(self.order(self.adapter).status_code, 200)

    def sweep(self, secret="s3cret"):
        return self.client.post("/api/cron/sweep", headers={"Authorization": f"Bearer {secret}"})

    def test_the_cron_sweep_finishes_a_pending_payment(self):
        self.capture("PENDING")
        get = self.mock_paypal("get_order", return_value={"orderId": "ORDER1", "status": "COMPLETED", "captureId": "CAP1"})
        with mock.patch.dict(main.os.environ, {"CRON_SECRET": "s3cret"}):
            self.assertEqual(self.sweep().json(), {"pending": 1, "checked": 1, "completed": 1, "failed": 0})
            # Nothing pending is left, so the next run asks PayPal nothing.
            self.assertEqual(self.sweep().json(), {"pending": 0, "checked": 0, "completed": 0, "failed": 0})
        get.assert_called_once_with("ORDER1")
        self.assertEqual(sorted(i["name"] for i in self.db.select("items", order_id="ORDER1")), ["Adapter", "Sunscreen"])

    def test_the_cron_sweep_leaves_a_still_pending_payment_and_counts_failures(self):
        self.capture("PENDING")
        with mock.patch.dict(main.os.environ, {"CRON_SECRET": "s3cret"}):
            self.mock_paypal("get_order", return_value={"orderId": "ORDER1", "status": "PENDING", "captureId": "CAP1"})
            self.assertEqual(self.sweep().json()["completed"], 0)
            self.mock_paypal("get_order", side_effect=paypal.PayPalError(500, "INTERNAL_SERVER_ERROR"))
            self.assertEqual(self.sweep().json()["failed"], 1)
        self.assertEqual(self.db.tables["orders"][0]["status"], "PENDING")

    def test_the_cron_sweep_needs_its_secret(self):
        get = self.mock_paypal("get_order")
        self.assertEqual(self.sweep().status_code, 404)  # CRON_SECRET unset: off
        with mock.patch.dict(main.os.environ, {"CRON_SECRET": "s3cret"}):
            self.assertEqual(self.sweep("wrong").status_code, 404)
            self.assertEqual(self.client.post("/api/cron/sweep").status_code, 404)
        get.assert_not_called()

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


class ProductRoutesTest(RoutesTest):
    PRODUCT = {"productId": "P1", "title": "SPF 50", "store": "shop.example", "url": "https://shop.example/p", "imageUrl": None, "priceCents": 950}

    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Sunscreen", "estPriceCents": 500, "quantity": 2}])
        self.item = self.list["items"][0]

    def mock_market(self, name, **kwargs):
        patch = mock.patch.object(market, name, **kwargs)
        self.addCleanup(patch.stop)
        return patch.start()

    def choose(self, body):
        return self.client.post(f"/api/items/{self.item['id']}/product", json=body)

    def test_search_uses_the_item_name_shows_only_checked_matches_and_saves_nothing(self):
        found = [self.PRODUCT | {"productId": f"P{n}"} for n in range(7)]
        search = self.mock_market("search", return_value=found)
        check = mock.patch.object(llm, "store_matches", return_value=found[1:]).start()
        self.addCleanup(mock.patch.stopall)

        self.assertEqual(self.client.get(f"/api/items/{self.item['id']}/products").json(), {"products": found[1:6]})
        search.assert_called_once_with("Sunscreen")
        check.assert_called_once_with("Sunscreen", None, "Trip", found)
        self.assertIsNone(self.db.tables["items"][0]["product"])

    def test_a_failed_match_check_shows_nothing_unchecked(self):
        self.mock_market("search", return_value=[self.PRODUCT])
        mock.patch.object(llm, "store_matches", side_effect=ValueError("bad reply")).start()
        self.addCleanup(mock.patch.stopall)
        with self.assertLogs(main.log):
            self.assertEqual(self.client.get(f"/api/items/{self.item['id']}/products").json(), {"error": "MARKET_UNAVAILABLE"})

    def test_the_price_comes_from_channel3_not_the_request_and_paypal_charges_it(self):
        lookup = self.mock_market("get", return_value=self.PRODUCT)

        item = self.choose({"productId": "P1", "priceCents": 1}).json()

        lookup.assert_called_once_with("P1")
        self.assertEqual((item["estPriceCents"], item["product"]["store"]), (950, "shop.example"))
        self.assertIn("fetchedAt", item["product"])
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [self.item["id"]]})
        self.assertEqual(create.call_args.args[0], [{"name": "Sunscreen", "priceCents": 950, "quantity": 2, "taxCents": 0}])

    def chosen_long_ago(self):
        """The item has the product, chosen at 950 more than 10 minutes ago."""
        self.mock_market("get", return_value=self.PRODUCT)
        self.choose({"productId": "P1"})
        product = self.db.tables["items"][0]["product"] | {"fetchedAt": "2026-01-01T00:00:00+00:00"}
        self.db.update("items", {"product": product}, id=self.item["id"])

    def pay(self):
        return self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [self.item["id"]]})

    def test_a_store_price_changed_since_it_was_chosen_is_shown_before_paypal_charges_it(self):
        self.chosen_long_ago()
        lookup = self.mock_market("get", return_value=self.PRODUCT | {"priceCents": 1200})
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        self.assertEqual(self.pay().json(), {"error": "PRICE_CHANGED"})
        create.assert_not_called()
        self.assertEqual(self.db.tables["items"][0]["est_price_cents"], 1200)
        # Paying again charges the new price, without asking Channel3 a second time.
        self.pay()
        self.assertEqual(create.call_args.args[0], [{"name": "Sunscreen", "priceCents": 1200, "quantity": 2, "taxCents": 0}])
        lookup.assert_called_once_with("P1")

    def test_an_unchanged_store_price_goes_straight_to_paypal(self):
        self.chosen_long_ago()
        lookup = self.mock_market("get", return_value=self.PRODUCT)
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        self.assertEqual(self.pay().json()["orderId"], "ORDER1")
        lookup.assert_called_once()
        self.assertNotEqual(self.db.tables["items"][0]["product"]["fetchedAt"], "2026-01-01T00:00:00+00:00")

    def test_a_product_the_store_stopped_selling_loses_its_store_label(self):
        self.chosen_long_ago()
        self.mock_market("get", return_value=None)
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        self.assertEqual(self.pay().json(), {"error": "PRICE_CHANGED"})
        item = self.db.tables["items"][0]
        self.assertEqual((item["product"], item["est_price_cents"]), (None, 950))

    def test_checkout_still_works_at_the_saved_price_when_channel3_is_down(self):
        self.chosen_long_ago()
        self.mock_market("get", side_effect=httpx.ConnectError("down"))
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        with self.assertLogs(main.log):
            self.assertEqual(self.pay().json()["orderId"], "ORDER1")
        self.assertEqual(create.call_args.args[0][0]["priceCents"], 950)

    def test_renaming_or_repricing_drops_the_product(self):
        self.mock_market("get", return_value=self.PRODUCT)
        for change in ({"name": "Sun cream"}, {"estPriceCents": 700}):
            with self.subTest(change=change):
                self.choose({"productId": "P1"})
                self.assertIsNone(self.client.patch(f"/api/items/{self.item['id']}", json=change).json()["product"])

    def test_a_bought_or_held_item_and_bad_input_are_refused(self):
        lookup = self.mock_market("get", return_value=None)
        self.assertEqual(self.choose({"productId": "../lists"}).status_code, 400)
        self.assertEqual(self.choose({"productId": "P9"}).status_code, 404)
        self.db.insert("orders", [{"id": "ORDER1", "list_id": self.list["id"], "item_ids": [self.item["id"]], "status": "PENDING"}])
        self.assertEqual(self.choose({"productId": "P1"}).json(), {"error": "PAYMENT_PENDING"})
        self.db.update("items", {"checked_at": "earlier"}, id=self.item["id"])
        self.assertEqual(self.choose({"productId": "P1"}).json(), {"error": "ITEM_CHECKED"})
        self.assertEqual(lookup.call_count, 1)

    def test_channel3_failures_are_502_and_searches_capped(self):
        self.mock_market("search", side_effect=httpx.ConnectError("down"))
        with self.assertLogs(main.log):
            self.assertEqual(self.client.get(f"/api/items/{self.item['id']}/products").json(), {"error": "MARKET_UNAVAILABLE"})
        self.mock_market("search", return_value=[])
        statuses = [self.client.get(f"/api/items/{self.item['id']}/products").status_code for _ in range(100)]
        self.assertEqual(statuses[-2:], [200, 429])


class StartingListTest(RoutesTest):
    def test_a_suggestion_is_returned_not_saved(self):
        suggestion = {"title": "Trip", "kind": "trip", "items": [{"name": "Tent", "quantity": 1, "estPriceCents": None}]}
        starting = self.mock_llm(return_value=suggestion)

        response = self.client.post("/api/lists/suggest", json={"description": "Camping", "budgetCents": 5000})

        self.assertEqual(response.json(), suggestion)
        starting.assert_called_once_with("Camping", 5000)
        self.assertEqual(self.db.tables, {})
        # The edited suggestion is what POST /api/lists takes.
        self.assertEqual(self.new_list(suggestion["items"])["items"][0]["name"], "Tent")

    def test_bad_input_is_400_and_an_ai_failure_502(self):
        self.mock_llm(side_effect=ValueError("not JSON"))
        for body, status in (({"description": ""}, 400), ({"description": "x", "budgetCents": -1}, 400), ({"description": "x"}, 502)):
            with self.subTest(body=body), self.assertLogs(main.log) if status == 502 else self.assertNoLogs(main.log):
                self.assertEqual(self.client.post("/api/lists/suggest", json=body).status_code, status)

    def test_suggestions_are_capped(self):
        self.mock_llm(return_value={"title": "x", "kind": "other", "items": []})
        statuses = [self.client.post("/api/lists/suggest", json={"description": "x"}).status_code for _ in range(21)]
        self.assertEqual(statuses[-2:], [200, 429])

    def test_prices_come_from_proven_purchases_then_store_products_then_the_ai(self):
        old = self.new_list([{"name": "Sunscreen", "quantity": 2}, {"name": "Sunscreen"}, {"name": "sunscreen"},
                             {"name": "Tent"}, {"name": "Rope"}, {"name": "Lamp"}])["items"]
        proof = [{"order_id": "ORDER1", "price_cents": 1800}, {"receipt_id": "R1", "price_cents": 1000}, {"price_cents": 100}]
        for item, values in zip(old, proof):  # 900 a unit, 1000, and a hand tick that doesn't count
            self.db.update("items", {"checked_at": "earlier", **values}, id=item["id"])
        self.db.update("items", {"product": {"priceCents": 4999}}, id=old[3]["id"])
        self.db.update("items", {"checked_at": "earlier", "price_cents": 700}, id=old[4]["id"])  # hand tick only
        self.mock_llm(return_value={"title": "Beach", "kind": "trip", "items": [
            {"name": "SUNSCREEN ", "quantity": 1, "estPriceCents": 500},
            {"name": "Tent", "quantity": 1, "estPriceCents": 9000},
            {"name": "Rope", "quantity": 1, "estPriceCents": 800},
            {"name": "Towel", "quantity": 1, "estPriceCents": None},
        ]})

        items = self.client.post("/api/lists/suggest", json={"description": "Beach"}).json()["items"]

        self.assertEqual([(i["estPriceCents"], i["priceSource"]) for i in items], [(950, "paid"), (4999, "store"), (800, "estimate"), (None, None)])

    def test_guesses_are_replaced_by_todays_big_store_price(self):
        self.mock_llm(return_value={"title": "Beach", "kind": "trip", "items": [
            {"name": "Sunscreen", "quantity": 1, "estPriceCents": 500},
            {"name": "Unicorn saddle", "quantity": 1, "estPriceCents": 4000},
            {"name": "Towel", "quantity": 1, "estPriceCents": None},
        ]})
        found = {
            "Sunscreen": [ProductRoutesTest.PRODUCT | {"title": t, "priceCents": c, "store": s} for t, c, s in
                          (("SPF 50 lotion", 1098, "target.com"), ("Milk cleanser", 300, "walmart.com"), ("SPF 30 spray", 897, "walmart.com"), ("SPF 50 stick", 1297, "target.com"))],
            "Unicorn saddle": [],
            "Towel": [ProductRoutesTest.PRODUCT | {"title": "Beach towel", "priceCents": 1500, "store": "walmart.com"}],
        }
        self.market_search.side_effect = lambda name, stores=None: found[name]
        # The AI keeps the three real sunscreens and the towel; the cleanser only shares a word.
        matches = mock.patch.object(llm, "market_matches", side_effect=lambda items, title: ([[p for p in i["products"] if "cleanser" not in p["title"]] for i in items], [None] * len(items))).start()
        self.addCleanup(mock.patch.stopall)

        items = self.client.post("/api/lists/suggest", json={"description": "Beach"}).json()["items"]

        # Sunscreen: the middle of 8.97, 10.98 and 12.97. The saddle no big store sells keeps the AI's guess.
        self.assertEqual([(i["estPriceCents"], i["priceSource"], i.get("priceStore")) for i in items],
                         [(1098, "market", "target.com"), (4000, "estimate", None), (1500, "market", "walmart.com")])
        self.assertTrue(all(call.args[1] == ("walmart.com", "target.com") for call in self.market_search.call_args_list))
        # One AI check for the whole list, only for the items with results.
        self.assertEqual([i["name"] for i in matches.call_args.args[0]], ["Sunscreen", "Towel"])

    def test_what_people_paid_beats_the_market_and_a_market_failure_keeps_the_guess(self):
        old = self.new_list([{"name": "Tent"}])["items"][0]
        self.db.update("items", {"checked_at": "earlier", "order_id": "ORDER1", "price_cents": 12000}, id=old["id"])
        self.mock_llm(return_value={"title": "Trip", "kind": "trip", "items": [
            {"name": "Tent", "quantity": 1, "estPriceCents": 9000}, {"name": "Rope", "quantity": 1, "estPriceCents": 800}]})
        self.market_search.side_effect = RuntimeError("Channel3 down")

        with self.assertLogs(main.log):
            items = self.client.post("/api/lists/suggest", json={"description": "Trip"}).json()["items"]

        self.assertEqual([(i["estPriceCents"], i["priceSource"]) for i in items], [(12000, "paid"), (800, "estimate")])
        self.assertEqual([call.args[0] for call in self.market_search.call_args_list], ["Rope"])

    def test_food_is_priced_at_kroger_and_everything_else_at_walmart_or_target(self):
        self.kroger_on.return_value = True
        self.mock_llm(return_value={"title": "BBQ", "kind": "groceries", "items": [
            {"name": "Ketchup", "quantity": 1, "estPriceCents": 350},
            {"name": "Charcoal", "quantity": 1, "estPriceCents": 1200},
            {"name": "ketchup", "quantity": 2, "estPriceCents": 350},
            {"name": "Paper plates", "quantity": 1, "estPriceCents": 400},
            {"name": "Tent", "quantity": 1, "estPriceCents": 9000},
        ]})
        k = lambda title, cents: {"productId": title, "title": title, "store": "kroger.com", "priceCents": cents, "category": "x"}
        at_kroger = {"Ketchup": [k("Heinz Tomato Ketchup (20 oz)", 279), k("Kroger Ketchup (24 oz)", 199), k("Ketchup costume", 2999)],
                     "Charcoal": [k("Kroger Charcoal (15 lb)", 899)], "Paper plates": [k("Kroger Paper Plates (50 ct)", 599)], "Tent": []}
        search_kroger = mock.patch.object(kroger, "search", side_effect=lambda name: at_kroger[name]).start()
        at_big = {"Charcoal": [ProductRoutesTest.PRODUCT | {"title": "Kingsford Charcoal", "priceCents": 1497, "store": "walmart.com"}], "Paper plates": [],
                  "Tent": [ProductRoutesTest.PRODUCT | {"title": "Ozark Trail 4-Person Tent", "priceCents": 6997, "store": "walmart.com"}]}
        self.market_search.side_effect = lambda name, stores=None: at_big[name]
        food = {"Ketchup": True, "Charcoal": False, "Paper plates": False, "Tent": False}
        matches = mock.patch.object(llm, "market_matches", side_effect=lambda items, title: (
            [[p for p in i["products"] if "costume" not in p["title"]] for i in items], [food[i["name"]] for i in items])).start()
        self.addCleanup(mock.patch.stopall)

        items = self.client.post("/api/lists/suggest", json={"description": "BBQ"}).json()["items"]

        # Ketchup (food): Kroger. Charcoal and the tent: Walmart. Plates: Walmart and Target have none, so Kroger's.
        self.assertEqual([(i["estPriceCents"], i["priceStore"]) for i in items],
                         [(199, "kroger.com"), (1497, "walmart.com"), (199, "kroger.com"), (599, "kroger.com"), (6997, "walmart.com")])
        # Searched at the same time, so in any order.
        self.assertEqual(sorted(c.args[0] for c in search_kroger.call_args_list), ["Charcoal", "Ketchup", "Paper plates", "Tent"])
        # Walmart and Target only for what isn't food or wasn't at Kroger; never for the ketchup.
        self.assertEqual(sorted(c.args[0] for c in self.market_search.call_args_list), ["Charcoal", "Paper plates", "Tent"])
        self.assertEqual(matches.call_count, 2)

    def test_a_kroger_failure_falls_back_to_the_big_stores(self):
        self.kroger_on.return_value = True
        self.mock_llm(return_value={"title": "x", "kind": "other", "items": [{"name": "Rope", "quantity": 1, "estPriceCents": 800}]})
        mock.patch.object(kroger, "search", side_effect=RuntimeError("401")).start()
        self.market_search.side_effect = lambda name, stores=None: [ProductRoutesTest.PRODUCT | {"title": "Rope", "priceCents": 999, "store": "target.com"}]
        mock.patch.object(llm, "market_matches", side_effect=lambda items, title: ([i["products"] for i in items], [None] * len(items))).start()
        self.addCleanup(mock.patch.stopall)

        with self.assertLogs(main.log):
            items = self.client.post("/api/lists/suggest", json={"description": "x"}).json()["items"]

        self.assertEqual((items[0]["estPriceCents"], items[0]["priceStore"]), (999, "target.com"))

    def test_a_price_memory_failure_still_returns_the_suggestion(self):
        self.mock_llm(return_value={"title": "x", "kind": "other", "items": [{"name": "Tent", "quantity": 1, "estPriceCents": 9000}]})
        with mock.patch.object(db, "select", side_effect=RuntimeError("no name_key column")), self.assertLogs(main.log):
            response = self.client.post("/api/lists/suggest", json={"description": "x"})
        self.assertEqual(response.json()["items"][0]["estPriceCents"], 9000)

    def mock_llm(self, **kwargs):
        patch = mock.patch.object(llm, "starting_list", **kwargs)
        self.addCleanup(patch.stop)
        return patch.start()


class SplitTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Tent", "estPriceCents": 9000}, {"name": "Food", "estPriceCents": 3000}, {"name": "Map", "estPriceCents": 500}])
        self.ann, self.bob = (self.join(name) for name in ("Ann", "Bob"))

    def join(self, name):
        return self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": name}).json()["id"]

    def test_assign_gives_every_open_item_to_someone_and_evens_the_cost(self):
        tent = self.list["items"][0]["id"]
        self.client.patch(f"/api/items/{tent}", json={"claimedBy": self.ann})

        items = self.client.post(f"/api/lists/{self.list['id']}/assign").json()["items"]

        self.assertEqual({i["name"]: i["claimedBy"] for i in items}, {"Tent": self.ann, "Food": self.bob, "Map": self.bob})

    def test_assign_needs_members(self):
        empty = self.new_list([{"name": "x"}])
        self.assertEqual(self.client.post(f"/api/lists/{empty['id']}/assign").status_code, 409)

    def test_split_settles_what_people_paid(self):
        tent, food, _ = (i["id"] for i in self.list["items"])
        self.client.patch(f"/api/items/{tent}", json={"checked": True, "memberId": self.ann, "priceCents": 9000})
        self.client.patch(f"/api/items/{food}", json={"checked": True, "memberId": self.bob, "priceCents": 3000})

        split = self.client.get(f"/api/lists/{self.list['id']}/split").json()

        self.assertEqual(split["totalCents"], 12000)
        self.assertEqual(split["transfers"], [{"from": self.bob, "to": self.ann, "amountCents": 3000}])


class ShopTest(RoutesTest):
    def setUp(self):
        super().setUp()
        response = self.client.post(
            "/api/lists",
            json={
                "title": "Trip",
                "budgetCents": 20000,
                "items": [
                    {"name": "Tent", "estPriceCents": 8000},
                    {"name": "Lamp", "estPriceCents": 1000, "quantity": 2},
                    {"name": "Milk", "estPriceCents": 400},
                    {"name": "Gas", "estPriceCents": 3000},
                ],
            },
        )
        self.list = response.json()
        self.tent, self.lamp, self.milk, self.gas = self.list["items"]
        self.ann = self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": "Ann"}).json()["id"]
        self.products = {
            "Tent": [ProductRoutesTest.PRODUCT | {"productId": "T1", "priceCents": 9000}, ProductRoutesTest.PRODUCT | {"productId": "T2", "priceCents": 7000}],
            "Lamp": [ProductRoutesTest.PRODUCT | {"productId": "L1", "priceCents": 1200}],
            "Milk": [],
            "Gas": [ProductRoutesTest.PRODUCT | {"productId": "G1", "priceCents": 2500}],
        }
        self.search = mock.patch.object(market, "search", side_effect=lambda name, stores=None: self.products.get(name, [])).start()
        mock.patch.object(llm, "store_matches", side_effect=lambda name, note, title, found: found).start()
        self.addCleanup(mock.patch.stopall)

    def plan(self, *items):
        items = items or (self.tent, self.lamp, self.milk)
        return self.client.post(f"/api/lists/{self.list['id']}/shop", json={"itemIds": [item["id"] for item in items]}).json()

    def test_each_ticked_item_gets_a_checked_product_and_misses_say_why(self):
        self.client.patch(f"/api/items/{self.gas['id']}", json={"checked": True, "priceCents": 3000})

        plan = self.plan()

        self.assertEqual([(l["itemId"], l["product"]["productId"]) for l in plan["cart"]], [(self.tent["id"], "T1"), (self.lamp["id"], "L1")])
        self.assertEqual(plan["skipped"], [{"itemId": self.milk["id"], "reason": main.NOT_SOLD}])
        self.assertEqual(plan["totalCents"], 9000 + 1200 * 2)
        # 20000 budget, less 3000 spent on gas.
        self.assertEqual(plan["budgetLeftCents"], 17000)
        self.assertEqual(self.search.call_count, 3)
        # Nothing is saved until the person pays.
        self.assertTrue(all(row["product"] is None for row in self.db.tables["items"]))

    def test_the_cart_fits_what_is_left_of_the_budget(self):
        self.client.patch(f"/api/lists/{self.list['id']}", json={"budgetCents": 10000})
        # Only the tent and the lamps are shopped; the milk and gas still need ~3400 of the budget.
        plan = self.plan(self.tent, self.lamp)

        self.assertEqual(plan["budgetLeftCents"], 10000 - 3400)
        self.assertEqual([l["product"]["productId"] for l in plan["cart"]], ["L1"])
        self.assertEqual(plan["skipped"], [{"itemId": self.tent["id"], "reason": "Left out to stay within the budget."}])

    def test_the_budget_left_counts_the_tax_and_the_cart_fits_before_tax(self):
        self.client.patch(f"/api/lists/{self.list['id']}", json={"budgetCents": 10000, "taxRateBp": 1000})
        plan = self.plan(self.tent, self.lamp)

        # The milk and gas still need 3400, and 340 of tax on them.
        self.assertEqual((plan["budgetLeftCents"], plan["taxRateBp"]), (10000 - 3400 - 340, 1000))
        # 6260 with tax leaves 5690 before tax: the lamps (2400, 2640 with tax) fit, the tent doesn't.
        self.assertEqual([l["product"]["productId"] for l in plan["cart"]], ["L1"])

    def test_a_failed_search_skips_only_that_item(self):
        def search(name):
            if name == "Lamp":
                raise RuntimeError("Channel3 down")
            return self.products[name]

        self.search.side_effect = search
        with self.assertLogs(main.log, "ERROR"):
            plan = self.plan(self.tent, self.lamp, self.gas)

        self.assertEqual(len(plan["cart"]), 2)
        self.assertIn("didn't answer", next(s["reason"] for s in plan["skipped"] if s["itemId"] == self.lamp["id"]))

    def test_only_open_items_from_this_list_can_be_shopped_and_any_number_of_them(self):
        self.client.patch(f"/api/items/{self.tent['id']}", json={"checked": True})
        self.db.insert("orders", [{"id": "O1", "list_id": self.list["id"], "item_ids": [self.lamp["id"]], "status": "PENDING"}])
        other = self.new_list([{"name": "Gas"}])["items"][0]
        many = self.client.post(f"/api/lists/{self.list['id']}/items", json={"items": [{"name": "Gas"}] * 11}).json()
        # Pricing the added items looked "Gas" up once at the big stores; the shop requests below must not search.
        self.assertEqual(self.search.call_count, 1)
        self.search.reset_mock()

        for items in ((self.tent,), (self.lamp,), (other,), (self.gas, self.gas), ()):
            with self.subTest(items=[i["name"] for i in items]):
                self.assertEqual(self.client.post(f"/api/lists/{self.list['id']}/shop", json={"itemIds": [i["id"] for i in items]}).status_code, 400)
        self.search.assert_not_called()
        plan = self.plan(*many)
        self.assertEqual(len(plan["cart"]) + len(plan["skipped"]), 11)

    def checkout(self, picks, total, **body):
        picks = [{"itemId": item["id"], "productId": product} for item, product in picks]
        return self.client.post(f"/api/lists/{self.list['id']}/shop/checkout", json={"picks": picks, "totalCents": total, **body})

    def test_checkout_reads_prices_from_channel3_and_opens_one_order(self):
        fresh = {"T2": ProductRoutesTest.PRODUCT | {"productId": "T2", "priceCents": 7000}, "L1": ProductRoutesTest.PRODUCT | {"productId": "L1", "priceCents": 1200}}
        get = mock.patch.object(market, "get", side_effect=fresh.get).start()
        create = self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})

        response = self.checkout([(self.tent, "T2"), (self.lamp, "L1")], 7000 + 2400, memberId=self.ann, priceCents=1)

        self.assertEqual(response.json(), {"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.assertEqual(get.call_count, 2)
        self.assertEqual(create.call_args.args[0], [{"name": "Tent", "priceCents": 7000, "quantity": 1, "taxCents": 0}, {"name": "Lamp", "priceCents": 1200, "quantity": 2, "taxCents": 0}])
        order = self.db.tables["orders"][0]
        self.assertEqual((order["member_id"], order["total_cents"]), (self.ann, 9400))
        self.assertEqual(sorted(p["productId"] for p in order["products"].values()), ["L1", "T2"])
        # Nothing is saved on the items until the payment goes through.
        items = self.client.get(f"/api/lists/{self.list['id']}").json()["items"]
        self.assertEqual([(i["product"], i["estPriceCents"]) for i in items[:2]], [(None, self.tent["estPriceCents"]), (None, self.lamp["estPriceCents"])])

    def test_the_store_product_is_saved_on_its_item_when_the_payment_completes(self):
        fresh = {"T2": ProductRoutesTest.PRODUCT | {"productId": "T2", "priceCents": 7000}}
        mock.patch.object(market, "get", side_effect=fresh.get).start()
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.checkout([(self.tent, "T2")], 7000, memberId=self.ann)
        self.mock_paypal("capture_order", return_value={"status": "COMPLETED", "captureId": "CAP1"})

        self.client.post("/api/orders/ORDER1/capture")

        tent = self.client.get(f"/api/lists/{self.list['id']}").json()["items"][0]
        self.assertEqual((tent["product"]["productId"], tent["estPriceCents"], tent["priceCents"], tent["orderId"]), ("T2", 7000, 7000, "ORDER1"))

    def test_leaving_paypal_without_paying_leaves_the_items_as_they_were(self):
        mock.patch.object(market, "get", return_value=ProductRoutesTest.PRODUCT | {"productId": "T2", "priceCents": 7000}).start()
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        before = self.client.get(f"/api/lists/{self.list['id']}").json()["items"]

        self.checkout([(self.tent, "T2")], 7000, memberId=self.ann)

        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}").json()["items"], before)

    def test_a_price_that_changed_since_the_plan_comes_back_and_no_order_is_made(self):
        mock.patch.object(market, "get", return_value=ProductRoutesTest.PRODUCT | {"productId": "T2", "priceCents": 7500}).start()
        create = self.mock_paypal("create_order")

        self.assertEqual(self.checkout([(self.tent, "T2")], 7000).json(), {"error": "PRICE_CHANGED", "prices": {self.tent["id"]: 7500}})

        create.assert_not_called()
        self.assertEqual(self.db.tables["items"][0]["est_price_cents"], self.tent["estPriceCents"])

    def test_checkout_refuses_bought_items_and_gone_products(self):
        mock.patch.object(market, "get", return_value=None).start()
        create = self.mock_paypal("create_order")
        self.assertEqual(self.checkout([(self.tent, "T2")], 7000).json(), {"error": "PRODUCT_NOT_FOUND"})

        self.client.patch(f"/api/items/{self.tent['id']}", json={"checked": True})
        self.assertEqual(self.checkout([(self.tent, "T2")], 7000).status_code, 400)
        self.assertEqual(self.checkout([(self.lamp, "L1"), (self.lamp, "L2")], 2400).status_code, 400)
        create.assert_not_called()


class ReminderTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Tent", "estPriceCents": 9000}, {"name": "Food", "estPriceCents": 3000}])
        self.ann, self.bob = (self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": n}).json()["id"] for n in ("Ann", "Bob"))
        tent, food = (i["id"] for i in self.list["items"])
        self.client.patch(f"/api/items/{tent}", json={"checked": True, "memberId": self.ann, "priceCents": 9000})
        self.client.patch(f"/api/items/{food}", json={"checked": True, "memberId": self.bob, "priceCents": 3000})
        # Bob owes Ann $30.

    def remind(self, from_id=None, to_id=None):
        return self.client.post(f"/api/lists/{self.list['id']}/reminders", json={"fromId": from_id or self.bob, "toId": to_id or self.ann})

    def test_the_ai_writes_it_from_the_splits_amount_and_the_link_opens_settle_up(self):
        write = mock.patch.object(llm, "reminder", return_value="Hey Bob, just a heads-up: $30.00 for Trip, to Ann 🙂").start()
        self.addCleanup(mock.patch.stopall)

        reply = self.remind().json()

        write.assert_called_once_with("Bob", "Ann", "$30.00", "Trip")
        link = f"{main.APP_URL}/lists/{self.list['id']}/settle?pay={self.bob}"
        self.assertEqual(reply, {"message": f"Hey Bob, just a heads-up: $30.00 for Trip, to Ann 🙂\n{link}", "link": link, "amountCents": 3000, "aiWritten": True})

    def test_a_pair_that_owes_nothing_or_isnt_on_the_list_is_refused(self):
        write = mock.patch.object(llm, "reminder").start()
        self.addCleanup(mock.patch.stopall)
        other = self.new_list([{"name": "x"}])
        stranger = self.client.post(f"/api/lists/{other['id']}/members", json={"name": "Cy"}).json()["id"]

        self.assertEqual(self.remind(self.ann, self.bob).json(), {"error": "SPLIT_CHANGED"})
        self.assertEqual(self.remind(stranger, self.ann).status_code, 400)
        write.assert_not_called()

    def test_a_failed_ai_call_or_the_cap_falls_back_to_the_template(self):
        mock.patch.object(llm, "reminder", side_effect=ValueError("unusable reminder")).start()
        self.addCleanup(mock.patch.stopall)
        with self.assertLogs(main.log, "ERROR"):
            reply = self.remind().json()
        self.assertFalse(reply["aiWritten"])
        self.assertTrue(reply["message"].startswith("Hi Bob! Quick heads-up: your part of Trip comes to $30.00, to Ann."))

        for _ in range(30):
            main.allow("reminder", 30, 3600)
        llm.reminder.reset_mock()
        self.assertFalse(self.remind().json()["aiWritten"])
        llm.reminder.assert_not_called()


class WebhookTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Tent", "estPriceCents": 9000}])
        self.tent = self.list["items"][0]
        self.mock_paypal("create_order", return_value={"orderId": "ORDER1", "approveUrl": "https://pay"})
        self.client.post(f"/api/lists/{self.list['id']}/orders", json={"itemIds": [self.tent["id"]]})
        self.mock_paypal("capture_order", return_value={"orderId": "ORDER1", "status": "PENDING", "captureId": "CAP1"})
        self.client.post("/api/orders/ORDER1/capture")
        self.verify = self.mock_paypal("verify_webhook", return_value=True)

    def event(self, event_type="PAYMENT.CAPTURE.COMPLETED", order_id="ORDER1", event_id="WH-1"):
        body = {"id": event_id, "event_type": event_type, "resource": {"id": "CAP1", "supplementary_data": {"related_ids": {"order_id": order_id}}}}
        return self.client.post("/api/paypal/webhook", json=body, headers={"paypal-transmission-id": "T1"})

    def tent_now(self):
        return next(i for i in self.client.get(f"/api/lists/{self.list['id']}").json()["items"] if i["id"] == self.tent["id"])

    def test_a_pending_payment_completes_without_check_again(self):
        self.assertEqual(self.event().json(), {"handled": True})

        self.assertEqual(self.tent_now()["orderId"], "ORDER1")
        self.assertEqual(self.tent_now()["priceCents"], 9000)
        headers, body = self.verify.call_args.args
        self.assertEqual((headers["paypal-transmission-id"], body["id"]), ("T1", "WH-1"))

    def test_a_denied_payment_releases_its_items(self):
        self.event("PAYMENT.CAPTURE.DENIED")

        self.assertEqual(self.db.tables["orders"][0]["status"], "DENIED")
        self.assertIsNone(self.tent_now()["checkedAt"])
        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}").json()["orders"], [])

    def test_a_bad_signature_changes_nothing(self):
        self.verify.return_value = False
        self.assertEqual(self.event().status_code, 401)
        self.assertEqual(self.db.tables["orders"][0]["status"], "PENDING")

        self.verify.side_effect = RuntimeError("PAYPAL_WEBHOOK_ID must be set")
        with self.assertLogs(main.log, "ERROR"):
            self.assertEqual(self.event().status_code, 503)
        self.assertNotIn("webhook_events", self.db.tables)

    def test_a_repeated_event_is_handled_once_and_a_late_denial_doesnt_undo_a_completion(self):
        self.event()
        self.assertEqual(self.event().json(), {"handled": False})
        self.assertEqual(self.event("PAYMENT.CAPTURE.DENIED", event_id="WH-2").json(), {"handled": False})
        self.assertEqual(self.db.tables["orders"][0]["status"], "COMPLETED")
        # Each distinct event is recorded once; the repeat of WH-1 added nothing.
        self.assertEqual([e["id"] for e in self.db.tables["webhook_events"]], ["WH-1", "WH-2"])

    def test_other_events_and_unknown_orders_are_acknowledged_and_ignored(self):
        self.assertEqual(self.event("PAYMENT.CAPTURE.REVERSED").json(), {"handled": False})
        self.assertEqual(self.event(order_id="NOPE", event_id="WH-3").json(), {"handled": False})
        self.assertEqual(self.db.tables["orders"][0]["status"], "PENDING")

    def refunded(self, event_id="WH-R1", refund_id="REF9", value="20.00", **resource):
        resource = {
            "id": refund_id,
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": value},
            "links": [{"rel": "up", "href": "https://api.sandbox.paypal.com/v2/payments/captures/CAP1", "method": "GET"}],
        } | resource
        body = {"id": event_id, "event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": resource}
        return self.client.post("/api/paypal/webhook", json=body, headers={"paypal-transmission-id": "T1"})

    def test_a_refund_made_in_paypal_is_taken_off_what_the_buyer_paid(self):
        ann = self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": "Ann"}).json()["id"]
        self.db.tables["orders"][0]["member_id"] = ann
        self.event()

        self.assertEqual(self.refunded().json(), {"handled": True})
        self.assertEqual(self.refunded().json(), {"handled": False})  # the same event again
        # A second, separate partial refund counts too.
        self.assertEqual(self.refunded("WH-R2", "REF10", "5.50").json(), {"handled": True})

        split = self.client.get(f"/api/lists/{self.list['id']}").json()["split"]
        self.assertEqual(split["members"][0]["paidCents"], 9000 - 2000 - 550)
        # One line per order, for all its refunds.
        self.assertEqual([(line["refundOf"], line["cents"]) for line in split["members"][0]["purchases"]], [(None, 9000), ("ORDER1", -2550)])
        # The item stays bought at the price PayPal charged.
        self.assertEqual(self.tent_now()["priceCents"], 9000)

    def test_heylists_own_refunds_and_odd_refunds_are_not_counted_again(self):
        self.event()
        self.db.tables["orders"][0]["refunds"] = {"item": {"refundId": "OLD1", "cents": 100, "status": "COMPLETED"}}

        self.assertEqual(self.refunded("WH-R1", custom_id="heylist").json(), {"handled": False})
        self.assertEqual(self.refunded("WH-R2", "OLD1").json(), {"handled": False})  # made before refunds were marked
        self.assertEqual(self.refunded("WH-R3", amount={"currency_code": "EUR", "value": "1.00"}).json(), {"handled": False})
        self.assertEqual(self.refunded("WH-R4", value="0.001").json(), {"handled": False})
        self.assertEqual(self.refunded("WH-R5", links=[]).json(), {"handled": False})
        self.assertEqual(self.db.tables["orders"][0]["refunds"], {"item": {"refundId": "OLD1", "cents": 100, "status": "COMPLETED"}})

    def test_a_refund_before_the_payment_completed_is_ignored(self):
        self.assertEqual(self.refunded().json(), {"handled": False})
        self.assertEqual(self.db.tables["orders"][0]["refunds"], {})

    def test_a_pending_settle_up_payment_completes_too(self):
        ann, bob = (self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": n}).json()["id"] for n in ("Ann", "Bob"))
        self.db.insert("settlements", [{"id": "SETTLE1", "list_id": self.list["id"], "debtor_id": bob, "creditor_id": ann, "amount_cents": 500, "status": "PENDING"}])

        self.assertEqual(self.event(order_id="SETTLE1", event_id="WH-4").json(), {"handled": True})
        self.assertEqual(self.db.tables["settlements"][0]["status"], "COMPLETED")


class SettleUpTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Tent", "estPriceCents": 9000}, {"name": "Food", "estPriceCents": 3000}])
        self.ann, self.bob = (self.join(name) for name in ("Ann", "Bob"))
        tent, food = (i["id"] for i in self.list["items"])
        self.client.patch(f"/api/items/{tent}", json={"checked": True, "memberId": self.ann, "priceCents": 9000})
        self.client.patch(f"/api/items/{food}", json={"checked": True, "memberId": self.bob, "priceCents": 3000})
        # Bob owes Ann $30.
        self.create = self.mock_paypal("create_order", return_value={"orderId": "SETTLE1", "approveUrl": "https://pay"})

    def join(self, name, **body):
        return self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": name, **body}).json()["id"]

    def pay(self, amount=3000, **body):
        body = {"fromId": self.bob, "toId": self.ann, "amountCents": amount, **body}
        return self.client.post(f"/api/lists/{self.list['id']}/settlements", json=body)

    def state(self):
        return self.client.get(f"/api/lists/{self.list['id']}").json()

    def test_the_payment_goes_to_the_paypal_email_of_the_person_owed(self):
        self.assertEqual(self.pay(email="ann@example.com").json(), {"orderId": "SETTLE1", "approveUrl": "https://pay"})

        items, return_url = self.create.call_args.args
        self.assertEqual(self.create.call_args.kwargs, {"payee_email": "ann@example.com", "venmo": False})
        self.assertEqual(items, [{"name": "HeyList: settle up for Trip", "priceCents": 3000, "quantity": 1}])
        self.assertEqual(return_url, f"{main.APP_URL}/lists/{self.list['id']}/settle")
        row = self.db.tables["settlements"][0]
        self.assertEqual((row["debtor_id"], row["creditor_id"], row["amount_cents"], row["status"]), (self.bob, self.ann, 3000, "CREATED"))
        # The email is kept for next time, but never sent to the browser.
        self.assertEqual({m["name"]: m["hasEmail"] for m in self.state()["members"]}, {"Ann": True, "Bob": False})
        self.assertNotIn("email", self.state()["members"][0])

    def test_the_amount_must_be_the_current_splits(self):
        for amount, from_id, to_id in ((2999, self.bob, self.ann), (3000, self.ann, self.bob), (0, self.bob, self.ann)):
            with self.subTest(amount=amount):
                response = self.pay(amount, fromId=from_id, toId=to_id, email="ann@example.com")
                self.assertIn(response.status_code, (400, 409))
        self.assertEqual(self.pay(2999, email="ann@example.com").json(), {"error": "SPLIT_CHANGED"})
        self.create.assert_not_called()

    def test_an_email_is_asked_for_and_kept_only_once_paypal_accepts_it(self):
        self.assertEqual(self.pay().json(), {"error": "EMAIL_NEEDED"})
        self.create.side_effect = paypal.PayPalError(422, "PAYEE_ACCOUNT_INVALID")
        self.assertEqual(self.pay(email="typo@example.com").json(), {"error": "PAYEE_NOT_ACCEPTED"})
        self.assertIsNone(self.db.tables["members"][0]["email"])
        self.assertNotIn("settlements", self.db.tables)

    def test_once_set_the_email_cant_be_changed_by_someone_else_on_the_link(self):
        self.pay(email="ann@example.com")
        self.db.tables["settlements"].clear()

        self.assertEqual(self.pay(email="bob@example.com").status_code, 403)
        # Joining again by name doesn't change it either.
        self.join("Ann", email="bob@example.com")
        self.assertEqual(self.db.tables["members"][0]["email"], "ann@example.com")
        self.assertEqual(self.pay().status_code, 200)
        self.assertEqual(self.create.call_args.kwargs, {"payee_email": "ann@example.com", "venmo": False})

    def test_capturing_twice_records_one_settlement_and_everyone_is_even(self):
        self.pay(email="ann@example.com")
        capture = self.mock_paypal("capture_order", return_value={"orderId": "SETTLE1", "status": "COMPLETED", "captureId": "CAP1"})

        first = self.client.post("/api/orders/SETTLE1/capture").json()
        captured_at = self.db.tables["settlements"][0]["captured_at"]
        self.client.post("/api/orders/SETTLE1/capture")

        self.assertEqual(first, {"orderId": "SETTLE1", "status": "COMPLETED", "refundedCents": 0, "settlement": True})
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(len(self.db.tables["settlements"]), 1)
        self.assertEqual(self.db.tables["settlements"][0]["captured_at"], captured_at)
        split = self.state()["split"]
        self.assertEqual(split["transfers"], [])
        self.assertEqual({m["memberId"]: m["balanceCents"] for m in split["members"]}, {self.ann: 0, self.bob: 0})
        # Nothing on the list was checked off or re-priced by it.
        self.assertEqual(split["totalCents"], 12000)

    def test_a_pending_payment_doesnt_count_yet_and_blocks_another(self):
        self.pay(email="ann@example.com")
        self.mock_paypal("capture_order", return_value={"orderId": "SETTLE1", "status": "PENDING", "captureId": "CAP1"})
        self.client.post("/api/orders/SETTLE1/capture")

        self.assertEqual(self.state()["split"]["transfers"], [{"from": self.bob, "to": self.ann, "amountCents": 3000}])
        self.assertEqual(self.state()["settlements"][0]["status"], "PENDING")
        self.assertEqual(self.pay().json(), {"error": "PAYMENT_PENDING"})

        self.mock_paypal("get_order", return_value={"orderId": "SETTLE1", "status": "COMPLETED", "captureId": "CAP1"})
        self.assertEqual(self.client.post("/api/orders/SETTLE1/refresh").json()["status"], "COMPLETED")
        self.assertEqual(self.state()["split"]["transfers"], [])

    def test_the_cron_sweep_finishes_a_pending_settle_up_payment(self):
        self.pay(email="ann@example.com")
        self.mock_paypal("capture_order", return_value={"orderId": "SETTLE1", "status": "PENDING", "captureId": "CAP1"})
        self.client.post("/api/orders/SETTLE1/capture")
        self.mock_paypal("get_order", return_value={"orderId": "SETTLE1", "status": "COMPLETED", "captureId": "CAP1"})
        with mock.patch.dict(main.os.environ, {"CRON_SECRET": "s3cret"}):
            response = self.client.post("/api/cron/sweep", headers={"Authorization": "Bearer s3cret"})
        self.assertEqual(response.json()["completed"], 1)
        self.assertEqual(self.state()["split"]["transfers"], [])


class ReceiptTest(RoutesTest):
    LINES = [
        {"text": "2% MILK 1GAL", "priceCents": 429, "confidence": 99.0, "lowConfidence": False},
        {"text": "MILK 2%", "priceCents": 429, "confidence": 98.0, "lowConfidence": False},
        {"text": "GUM", "priceCents": 199, "confidence": 75.0, "lowConfidence": True},
    ]
    FEES = [{"kind": "tax", "name": "TAX", "amountCents": 75}]

    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Milk", "estPriceCents": 400}, {"name": "Bread"}])
        self.milk, self.bread = (i["id"] for i in self.list["items"])
        self.member = self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": "Ann"}).json()["id"]

    def scan(self, content_type="image/jpeg", body=b"photo", read=None, matches=None):
        read = read or {"lines": self.LINES, "fees": self.FEES, "totalCents": 1132}
        for name, value in (("read_receipt", read), ("match_lines", matches)):
            patch = mock.patch.object(receipts, name, **({"side_effect": value} if isinstance(value, Exception) else {"return_value": value}))
            patch.start()
            self.addCleanup(patch.stop)
        return self.client.post(
            f"/api/lists/{self.list['id']}/receipts?memberId={self.member}", content=body, headers={"Content-Type": content_type}
        )

    def test_a_scan_stores_the_photo_and_proposals_but_checks_nothing_off(self):
        receipt = self.scan(matches=[self.milk, self.milk, None]).json()

        self.assertEqual([line["itemId"] for line in receipt["lines"]], [self.milk, self.milk, None])
        self.assertIsNone(receipt["confirmedAt"])
        self.assertEqual(self.client.get(f"/api/receipts/{receipt['id']}/image").content, b"photo")
        self.assertIsNone(self.state_of("Milk")["checkedAt"])

    def thumb(self, receipt, body=b"small", content_type="image/jpeg"):
        return self.client.put(f"/api/receipts/{receipt['id']}/thumbnail", content=body, headers={"Content-Type": content_type})

    def test_a_small_copy_is_sent_once_and_served_for_the_receipts_tab(self):
        receipt = self.scan(matches=[None, None, None]).json()
        image = lambda size: self.client.get(f"/api/receipts/{receipt['id']}/image?size={size}")
        # Before it arrives, the small size is the photo.
        self.assertEqual(image("thumb").content, b"photo")

        self.assertEqual(self.thumb(receipt).status_code, 204)
        self.assertEqual(self.thumb(receipt, b"other").status_code, 409)

        self.assertEqual((image("thumb").content, image("full").content), (b"small", b"photo"))
        self.assertEqual(image("thumb").headers["cache-control"], "private, max-age=86400")

    def test_a_small_copy_must_be_small_an_image_and_for_a_real_receipt(self):
        receipt = self.scan(matches=[None, None, None]).json()
        self.assertEqual(self.thumb(receipt, b"x" * (main.MAX_THUMB_BYTES + 1)).status_code, 413)
        self.assertEqual(self.thumb(receipt, content_type="image/gif").status_code, 415)
        self.assertEqual(self.thumb({"id": str(uuid.uuid4())}).status_code, 404)

    def test_a_failed_upload_leaves_no_small_copy(self):
        receipt = self.scan(matches=[None, None, None]).json()
        with mock.patch.object(db, "upload", side_effect=RuntimeError("storage down")), self.assertRaises(RuntimeError):
            self.thumb(receipt)
        self.assertIsNone(self.db.select("receipts", id=receipt["id"])[0]["thumb_path"])
        self.assertEqual(self.thumb(receipt).status_code, 204)

    def test_confirming_checks_items_off_with_receipt_prices_and_keeps_extras(self):
        receipt = self.scan(matches=[self.milk, None, None]).json()

        # The person corrects line 2: it is milk too.
        state = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk, self.milk, None]}).json()

        milk = next(i for i in state["items"] if i["name"] == "Milk")
        self.assertEqual((milk["priceCents"], milk["boughtBy"], milk["receiptId"]), (858, self.member, receipt["id"]))
        self.assertEqual(state["receipts"][0]["extras"], [{"name": "GUM", "priceCents": 199}])
        # Confirming twice would pay twice.
        again = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [None, None, None]})
        self.assertEqual(again.status_code, 409)

    def test_fees_are_kept_and_shared_with_the_items_they_were_charged_on(self):
        bob = self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": "Bob"}).json()["id"]
        receipt = self.scan(matches=[self.milk, self.milk, None]).json()
        self.assertEqual(receipt["fees"], self.FEES)

        state = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk, self.milk, None]}).json()

        # 75 cents of tax on 858 of milk for the list and 199 of gum for Ann: 61 is shared, 14 stays Ann's.
        ann = next(m for m in state["split"]["members"] if m["memberId"] == self.member)
        self.assertEqual(ann["purchases"][-1], {"itemId": None, "cents": 61, "boughtTwice": False, "feesOf": receipt["id"], "refundOf": None, "fee": "tax"})
        self.assertEqual(state["split"]["totalCents"], 858 + 61)
        self.assertEqual([m["shareCents"] for m in state["split"]["members"] if m["memberId"] in (self.member, bob)], [460, 459])

    def test_a_confirmed_receipt_sets_the_lists_tax_rate_over_a_typed_one(self):
        self.client.patch(f"/api/lists/{self.list['id']}", json={"taxRateBp": 825})
        receipt = self.scan(matches=[self.milk, self.milk, None]).json()
        state = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk, self.milk, None]}).json()

        # 75 cents of tax on 858 + 199 of lines is 7.10%.
        self.assertEqual(state["tax"], {"rateBp": 710, "source": "receipts"})
        self.assertEqual(state["taxRateBp"], 825)

    def test_a_price_the_photo_left_blank_is_typed_in_and_marked_typed(self):
        lines = [self.LINES[0] | {"priceCents": None}, self.LINES[2]]
        fees = [{"kind": "tax", "name": "TAX", "amountCents": None}, {"kind": "discount", "name": "COUPON", "amountCents": None}]
        receipt = self.scan(read={"lines": lines, "fees": fees, "totalCents": 700}, matches=[self.milk, None]).json()

        # A price the photo gave (gum) can't be changed from the browser.
        state = self.client.post(
            f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk, None], "prices": [450, 1], "feeAmounts": [60, 9]}
        ).json()

        milk = next(i for i in state["items"] if i["name"] == "Milk")
        self.assertEqual((milk["priceCents"], milk["priceTyped"]), (450, True))
        stored = state["receipts"][0]
        self.assertEqual([(line["priceCents"], line.get("typed")) for line in stored["lines"]], [(450, True), (199, None)])
        self.assertEqual([fee["amountCents"] for fee in stored["fees"]], [60, -9])
        self.assertEqual(stored["extras"], [{"name": "GUM", "priceCents": 199}])
        # A typed price is self-reported: price memory leaves it out.
        self.assertEqual(main.remember_prices([{"name": "Milk", "estPriceCents": 300}])[0]["priceSource"], "estimate")

    def test_a_price_left_blank_checks_the_item_off_without_a_price(self):
        receipt = self.scan(read={"lines": [self.LINES[0] | {"priceCents": None}], "fees": [], "totalCents": None}, matches=[self.milk]).json()

        state = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk], "prices": [None]}).json()

        milk = next(i for i in state["items"] if i["name"] == "Milk")
        self.assertEqual((milk["priceCents"], milk["priceTyped"], milk["receiptId"]), (None, False, receipt["id"]))
        for prices in ([1.5], [-1], [450, 450], "450"):
            with self.subTest(prices=prices):
                other = self.scan(read={"lines": [self.LINES[1] | {"priceCents": None}], "fees": [], "totalCents": None}, matches=[None]).json()
                response = self.client.post(f"/api/receipts/{other['id']}/confirm", json={"itemIds": [None], "prices": prices})
                self.assertEqual(response.status_code, 400)

    def test_confirm_racing_a_capture_or_another_confirm_checks_nothing_off_twice(self):
        receipt = self.scan(matches=[self.milk, None, None]).json()
        # Both happen after the route read the receipt and the items, as when two requests overlap.
        self.db.update("items", {"checked_at": "earlier", "order_id": "ORDER1", "price_cents": 400}, id=self.milk)
        with stale_reads(self.db, "items", checked_at=None):
            state = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [self.milk, None, None]}).json()
        milk = next(i for i in state["items"] if i["name"] == "Milk")
        self.assertEqual((milk["orderId"], milk["receiptId"], milk["priceCents"]), ("ORDER1", None, 400))
        self.assertEqual(len(state["receipts"][0]["extras"]), 3)

        with stale_reads(self.db, "receipts", confirmed_at=None):
            again = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": [None, None, None]})
        self.assertEqual(again.status_code, 409)

    def test_confirm_rejects_items_that_cannot_be_checked_off(self):
        receipt = self.scan(matches=[None, None, None]).json()
        other = self.new_list([{"name": "Tent"}])["items"][0]["id"]
        self.client.patch(f"/api/items/{self.bread}", json={"checked": True})

        for item_ids in ([self.milk], [other, None, None], [self.bread, None, None], ["nope", None, None]):
            with self.subTest(item_ids=item_ids):
                response = self.client.post(f"/api/receipts/{receipt['id']}/confirm", json={"itemIds": item_ids})
                self.assertEqual(response.status_code, 400)

    def test_bad_uploads_and_scan_failures(self):
        self.assertEqual(self.scan(content_type="image/gif").status_code, 415)
        self.assertEqual(self.scan(body=b"x" * (main.MAX_RECEIPT_BYTES + 1)).status_code, 413)
        self.assertEqual(self.scan(read={"lines": [], "fees": [], "totalCents": None}).status_code, 422)
        self.assertEqual(self.scan(read=receipts.ReceiptError("UNREADABLE_IMAGE")).json(), {"error": "UNREADABLE_IMAGE"})
        self.assertEqual(self.scan(read=receipts.ReceiptError("MATCHING_UNAVAILABLE")).status_code, 502)
        self.assertNotIn("receipts", self.db.tables)

    def test_scans_per_list_are_capped(self):
        for _ in range(10):
            self.assertEqual(self.scan(matches=[None, None, None]).status_code, 200)
        self.assertEqual(self.scan().json(), {"error": "TOO_MANY_REQUESTS"})

    def state_of(self, name):
        return next(i for i in self.client.get(f"/api/lists/{self.list['id']}").json()["items"] if i["name"] == name)


if __name__ == "__main__":
    unittest.main()
