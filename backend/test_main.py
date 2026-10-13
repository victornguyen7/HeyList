import unittest
import uuid
from unittest import mock

from fastapi.testclient import TestClient

import db
import llm
import main
import paypal

client = TestClient(main.app)


class FakeDb:
    """An in-memory stand-in for the four calls in db.py."""

    def __init__(self):
        self.tables = {}
        self.files = {}
        self.clock = 0

    def upload(self, path, data, content_type):
        self.files[path] = data

    def download(self, path):
        return self.files[path]

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
            added.append({"id": str(uuid.uuid4()), "created_at": f"2026-10-13T00:00:00.{self.clock:06d}", **defaults, **row})
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
        for name in ("select", "insert", "update", "delete", "upload", "download"):
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

    def test_the_state_carries_the_money_summary(self):
        created = self.make_list()
        ana, ben = self.join(created["id"], "Ana"), self.join(created["id"], "Ben")
        client.patch(
            f"/api/items/{created['items'][0]['id']}",
            json={"checked": True, "memberId": ana["id"], "priceCents": 2000},
        )
        state_money = client.get(f"/api/lists/{created['id']}").json()["money"]
        self.assertEqual(state_money["spentCents"], 2000)
        self.assertEqual(state_money["owes"], [{"from": ben["id"], "to": ana["id"], "amountCents": 1000}])

    def test_assign_shares_out_the_unclaimed_items(self):
        created = self.make_list()
        ana, ben = self.join(created["id"], "Ana"), self.join(created["id"], "Ben")
        state = client.post(f"/api/lists/{created['id']}/assign").json()
        self.assertEqual([item["claimedBy"] for item in state["items"]], [ana["id"], ben["id"]])
        self.assert_error(client.post(f"/api/lists/{uuid.uuid4()}/assign"), 404, "LIST_NOT_FOUND")

    def test_reuse_copies_the_list_unchecked_at_the_last_price_paid(self):
        created = self.make_list()
        client.patch(f"/api/items/{created['items'][0]['id']}", json={"checked": True, "priceCents": 2199})
        copy = client.post(f"/api/lists/{created['id']}/reuse").json()
        self.assertNotEqual(copy["id"], created["id"])
        self.assertEqual((copy["title"], copy["kind"], copy["budgetCents"]), ("Move-in", "home", 30000))
        self.assertEqual(
            [(item["name"], item["estPriceCents"], item["checkedAt"]) for item in copy["items"]],
            [("Kettle", 2199, None), ("Mop", 1200, None)],
        )
        self.assert_error(client.post(f"/api/lists/{uuid.uuid4()}/reuse"), 404, "LIST_NOT_FOUND")

    def test_history_covers_the_lists_asked_for_and_skips_unknown_ids(self):
        first, second = self.make_list(), self.make_list(title="Groceries", kind="groceries")
        self.make_list(title="Someone else's")
        client.patch(f"/api/items/{first['items'][0]['id']}", json={"checked": True, "priceCents": 2199})
        ids = ",".join([first["id"], second["id"], str(uuid.uuid4()), "nope"])
        result = client.get(f"/api/history?ids={ids}").json()
        self.assertEqual(sorted(row["title"] for row in result["lists"]), ["Groceries", "Move-in"])
        self.assertEqual(result["byKind"], {"home": 2199, "groceries": 0})
        self.assertEqual(result["lastPaidCents"], {"kettle": 2199})
        self.assertEqual(client.get("/api/history").json()["lists"], [])


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


class AiTest(ApiTest):
    def test_a_starting_list_is_suggested_and_not_saved(self):
        suggestion = {"title": "Move-in", "kind": "home", "budgetCents": 30000, "items": []}
        with mock.patch.object(llm, "starting_list", return_value=suggestion) as starting_list:
            response = client.post("/api/ai/list", json={"sentence": " move-in for 3, $300 "})
        self.assertEqual(response.json(), suggestion)
        starting_list.assert_called_once_with("move-in for 3, $300")
        self.assertEqual(self.db.tables, {})

    def test_spoken_text_is_split_into_items_and_not_saved(self):
        items = [{"name": "eggs", "estPriceCents": 350}]
        with mock.patch.object(llm, "split_items", return_value=items) as split_items:
            response = client.post("/api/ai/items", json={"text": "groceries eggs"})
        self.assertEqual(response.json(), {"items": items})
        split_items.assert_called_once_with("groceries eggs")
        self.assertEqual(self.db.tables, {})

    def test_bad_input_never_reaches_the_llm(self):
        with mock.patch.object(llm, "_ask") as ask:
            for url, body in (
                ("/api/ai/list", {}),
                ("/api/ai/list", {"sentence": ""}),
                ("/api/ai/list", {"sentence": "x" * 301}),
                ("/api/ai/items", {"text": 5}),
            ):
                with self.subTest(url=url, body=body):
                    self.assert_error(client.post(url, json=body), 400, "INVALID_BODY")
        ask.assert_not_called()

    def test_an_llm_failure_is_a_502(self):
        with mock.patch.object(llm, "_ask", side_effect=llm.LlmError()):
            self.assert_error(client.post("/api/ai/list", json={"sentence": "camping"}), 502, "LLM_ERROR")
            self.assert_error(client.post("/api/ai/items", json={"text": "eggs"}), 502, "LLM_ERROR")


class ReceiptsTest(ApiTest):
    def setUp(self):
        super().setUp()
        self.list = self.make_list()
        self.member = self.join(self.list["id"])
        self.kettle, self.mop = (item["id"] for item in self.list["items"])
        self.url = f"/api/lists/{self.list['id']}/receipts"

    def scan(self, reading=None, content_type="image/jpeg", image=b"photo"):
        reading = reading or {
            "totalCents": 3099,
            "matches": [{"itemId": self.kettle, "line": "KETTLE 1.7L", "priceCents": 2399}],
            "extras": [{"name": "GUM", "priceCents": 700}],
        }
        with mock.patch.object(llm, "read_receipt", return_value=reading) as self.read_receipt:
            return client.post(f"{self.url}/scan", content=image, headers={"Content-Type": content_type})

    def test_a_scan_proposes_matches_and_checks_nothing_off(self):
        client.patch(f"/api/items/{self.mop}", json={"checked": True})
        response = self.scan()
        self.assertEqual(response.status_code, 200)
        proposal = response.json()
        self.assertEqual(proposal["matches"][0]["itemId"], self.kettle)
        self.assertEqual(proposal["extras"], [{"name": "GUM", "priceCents": 700}])
        # Only the open items are offered to the model for matching.
        self.read_receipt.assert_called_once_with(b"photo", [{"id": self.kettle, "name": "Kettle"}])
        self.assertEqual(self.db.files, {proposal["imagePath"]: b"photo"})
        self.assertTrue(proposal["imagePath"].startswith(self.list["id"] + "/"))
        state = client.get(f"/api/lists/{self.list['id']}").json()
        self.assertIsNone(state["items"][0]["checkedAt"])
        self.assertEqual(state["receipts"], [])

    def test_bad_scans(self):
        self.assert_error(self.scan(content_type="application/pdf"), 400, "INVALID_IMAGE")
        self.assert_error(self.scan(image=b""), 400, "INVALID_IMAGE")
        self.assert_error(self.scan(image=b"x" * (main.MAX_IMAGE_BYTES + 1)), 400, "INVALID_IMAGE")
        self.read_receipt.assert_not_called()
        response = client.post(
            f"/api/lists/{uuid.uuid4()}/receipts/scan", content=b"p", headers={"Content-Type": "image/png"}
        )
        self.assert_error(response, 404, "LIST_NOT_FOUND")
        with mock.patch.object(llm, "_ask", side_effect=llm.LlmError()):
            response = client.post(f"{self.url}/scan", content=b"p", headers={"Content-Type": "image/png"})
        self.assert_error(response, 502, "LLM_ERROR")
        self.assertEqual(self.db.files, {})

    def test_confirming_checks_the_items_off_with_the_receipt_as_proof(self):
        proposal = self.scan().json()
        body = {
            "imagePath": proposal["imagePath"],
            "memberId": self.member["id"],
            "totalCents": proposal["totalCents"],
            "matches": [{"itemId": self.kettle, "priceCents": 2399}],
            "extras": proposal["extras"],
        }
        response = client.post(self.url, json=body)
        self.assertEqual(response.status_code, 200)
        state = response.json()
        receipt = state["receipts"][0]
        self.assertEqual((receipt["totalCents"], receipt["memberId"]), (3099, self.member["id"]))
        self.assertEqual(receipt["extras"], [{"name": "GUM", "priceCents": 700}])
        kettle, mop = state["items"]
        self.assertTrue(kettle["checkedAt"])
        self.assertEqual(
            (kettle["priceCents"], kettle["receiptId"], kettle["boughtBy"]),
            (2399, receipt["id"], self.member["id"]),
        )
        self.assertIsNone(mop["checkedAt"])

        image = client.get(f"/api/receipts/{receipt['id']}/image")
        self.assertEqual((image.status_code, image.content), (200, b"photo"))
        self.assertEqual(image.headers["content-type"], "image/jpeg")
        # The same scan cannot be saved twice.
        self.assert_error(client.post(self.url, json={**body, "matches": []}), 400, "INVALID_BODY")

    def test_bad_confirmations_store_nothing(self):
        path = self.scan().json()["imagePath"]
        other_list = self.make_list()
        good = {"imagePath": path, "matches": [{"itemId": self.kettle, "priceCents": 1}], "extras": []}
        client.patch(f"/api/items/{self.mop}", json={"checked": True})
        for change in (
            {"imagePath": f"{other_list['id']}/{uuid.uuid4()}.jpg"},
            {"imagePath": "../secrets.jpg"},
            {"matches": [{"itemId": other_list["items"][0]["id"]}]},
            {"matches": [{"itemId": self.mop}]},  # already checked off
            {"matches": [{"itemId": self.kettle}, {"itemId": self.kettle}]},
            {"matches": [{"itemId": self.kettle, "priceCents": -5}]},
            {"extras": [{"name": ""}]},
            {"memberId": str(uuid.uuid4())},
            {"matches": None},
        ):
            with self.subTest(change=change):
                self.assert_error(client.post(self.url, json={**good, **change}), 400, "INVALID_BODY")
        self.assert_error(client.post(self.url, json=None), 400, "INVALID_BODY")
        self.assertNotIn("receipts", self.db.tables)

    def test_unknown_receipt_image_is_404(self):
        self.assert_error(client.get(f"/api/receipts/{uuid.uuid4()}/image"), 404, "RECEIPT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
