import re
import unittest
import uuid
from pathlib import Path
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import db
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
    "items": {"position": 0, "quantity": 1, "price_typed": False},
    "orders": {"status": "CREATED", "prices": {}, "refunds": {}},
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


class JoinTest(AccountTest):
    def test_logged_in_joins_without_a_name_and_gets_the_same_member_back(self):
        first = self.join("ann-token").json()

        self.assertEqual(first["name"], "Ann")
        self.assertEqual(self.join("ann-token", name="Annie").json()["id"], first["id"])

    def test_an_account_without_a_name_gives_one_the_first_time(self):
        self.assertEqual(self.join("new-token").status_code, 400)
        self.assertEqual(self.join("new-token", name="Bob").json()["name"], "Bob")

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
        self.assertEqual(return_url, f"{main.APP_URL}/lists/{self.list['id']}")
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
        self.assertEqual(create.call_args.args[0], [{"name": "Sunscreen", "priceCents": 950, "quantity": 2}])

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
        self.assertEqual(create.call_args.args[0], [{"name": "Sunscreen", "priceCents": 1200, "quantity": 2}])
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
        self.assertEqual(ann["purchases"][-1], {"itemId": None, "cents": 61, "boughtTwice": False, "feesOf": receipt["id"]})
        self.assertEqual(state["split"]["totalCents"], 858 + 61)
        self.assertEqual([m["shareCents"] for m in state["split"]["members"] if m["memberId"] in (self.member, bob)], [460, 459])

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
