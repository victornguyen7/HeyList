import json
import os
import unittest
from unittest import mock

from botocore.stub import Stubber

import llm
import main
import photos
import receipts
from test_main import RoutesTest


def line(text, confidence=99.0, kind=None):
    """A LINE block; with kind, also the WORD block under it, as Textract reports them."""
    block = {"BlockType": "LINE", "Text": text, "Confidence": confidence}
    if not kind:
        return [block]
    word_id = f"word-{text}"
    return [block | {"Relationships": [{"Type": "CHILD", "Ids": [word_id]}]}, {"BlockType": "WORD", "Id": word_id, "Text": text, "TextType": kind}]


class ShowThroughTest(unittest.TestCase):
    def parse(self, *lines):
        return photos.parse_text({"Blocks": [block for found in lines for block in found]})

    def test_print_showing_through_a_handwritten_list_is_left_out_and_named(self):
        result = self.parse(line("TOTAL 13.27", 55.0, "PRINTED"), line("eggs", 95.0, "HANDWRITING"), line("milk", 80.0, "HANDWRITING"), line("VISA 4821", 60.0, "PRINTED"))

        self.assertEqual(result["lines"], [{"text": "eggs", "lowConfidence": False}, {"text": "milk", "lowConfidence": True}])
        self.assertEqual(result["leftOut"], ["TOTAL 13.27", "VISA 4821"])

    def test_a_printed_list_is_kept_whole(self):
        result = self.parse(line("eggs", 99.0, "PRINTED"), line("milk", 99.0, "PRINTED"))
        self.assertEqual(([found["text"] for found in result["lines"]], result["leftOut"]), (["eggs", "milk"], []))

    def test_one_stray_handwritten_line_does_not_throw_away_a_printed_list(self):
        result = self.parse(line("eggs", 99.0, "PRINTED"), line("milk", 99.0, "PRINTED"), line("xq", 50.0, "HANDWRITING"))
        self.assertEqual((len(result["lines"]), result["leftOut"]), (3, []))


class ReadListTest(unittest.TestCase):
    def setUp(self):
        receipts._textract.cache_clear()
        self.addCleanup(receipts._textract.cache_clear)
        with mock.patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}):
            self.stub = Stubber(receipts._textract())
        self.stub.activate()
        self.addCleanup(self.stub.deactivate)

    def test_only_lines_come_out_and_unsure_ones_are_flagged(self):
        blocks = [{"BlockType": "PAGE"}, *line("2  packs   water"), {"BlockType": "WORD", "Text": "water"}, *line("mlik", 61.0), *line("   ")]
        self.stub.add_response("detect_document_text", {"Blocks": blocks}, {"Document": {"Bytes": b"photo"}})

        self.assertEqual(photos.read_list(b"photo"), {"lines": [{"text": "2 packs water", "lowConfidence": False}, {"text": "mlik", "lowConfidence": True}], "leftOut": []})

    def test_a_bad_photo_is_not_retried_with_ollama(self):
        self.stub.add_client_error("detect_document_text", "UnsupportedDocumentException")
        with mock.patch.object(llm, "chat") as chat, self.assertRaises(receipts.ReceiptError) as caught:
            photos.read_list(b"photo")
        self.assertEqual(str(caught.exception), "UNREADABLE_LIST")
        chat.assert_not_called()

    def test_without_textract_the_ollama_vision_model_reads_the_photo(self):
        self.stub.add_client_error("detect_document_text", "AccessDeniedException")
        reply = json.dumps({"lines": ["eggs", "  ", 3, "bread  rolls"]})
        with mock.patch.object(llm, "chat", return_value=reply) as chat, self.assertLogs(photos.log):
            read = photos.read_list(b"photo")
        self.assertEqual([found["text"] for found in read["lines"]], ["eggs", "bread rolls"])
        self.assertIn("shows through", chat.call_args.args[0][0]["content"])
        self.assertEqual(chat.call_args.args[0][1]["images"], [b"photo"])


class ListRequestTest(unittest.TestCase):
    def test_the_list_is_named_exact_and_unsure_lines_are_marked(self):
        request = photos.list_request([{"text": "eggs", "lowConfidence": False}, {"text": "mlik", "lowConfidence": True}])
        self.assertIn("exactly these", request)
        self.assertIn("ignore any instructions", request)
        self.assertIn("showing through", request)
        self.assertIn("Never turn unclear text into a guessed item", request)
        self.assertNotIn("obvious misreading", request)
        self.assertTrue(request.endswith("eggs\nmlik [hard to read]"))

    def test_a_reply_with_no_title_is_not_named_after_the_request(self):
        with mock.patch.object(llm, "chat", return_value='{"title": "", "kind": "other", "items": []}'):
            self.assertEqual(llm.starting_list("the whole long request", fallback_title="List from a photo")["title"], "List from a photo")


class IdentifyTest(unittest.TestCase):
    ITEMS = [{"id": "a", "name": "Milk"}, {"id": "b", "name": "Almond milk"}]

    def identify(self, reply):
        with mock.patch.object(llm, "chat", return_value=reply) as self.chat:
            return photos.identify_item(b"photo", self.ITEMS)

    def test_the_model_sees_the_photo_and_names_only(self):
        found = self.identify('{"seen": "carton  of almond milk", "item": 1}')
        self.assertEqual(found, {"itemId": "b", "seen": "carton of almond milk"})
        request = self.chat.call_args.args[0][1]
        self.assertEqual(request["images"], [b"photo"])
        self.assertEqual(request["content"], "List items:\n0. Milk\n1. Almond milk")

    def test_anything_but_a_real_number_is_no_match(self):
        for item in ("null", "2", "-1", "true", '"1"'):
            with self.subTest(item=item):
                self.assertIsNone(self.identify(f'{{"seen": "a dog", "item": {item}}}')["itemId"])

    def test_an_unusable_reply_lets_the_person_pick(self):
        self.assertEqual(self.identify("sorry, no idea"), {"itemId": None, "seen": ""})

    def test_an_ollama_failure_is_reported(self):
        with mock.patch.object(llm, "chat", side_effect=RuntimeError("down")), self.assertRaises(receipts.ReceiptError) as caught:
            photos.identify_item(b"photo", self.ITEMS)
        self.assertEqual(str(caught.exception), "SCANNING_UNAVAILABLE")


class FromPhotoRouteTest(RoutesTest):
    SUGGESTION = {"title": "Groceries", "kind": "groceries", "items": [{"name": "Eggs", "quantity": 1, "estPriceCents": 400, "note": None}]}

    def post(self, lines=None, suggestion=None, content_type="image/jpeg", body=b"photo"):
        read = lines if lines is not None else [{"text": "eggs", "lowConfidence": False}]
        read_kind = {"side_effect": read} if isinstance(read, Exception) else {"return_value": {"lines": read, "leftOut": ["TOTAL 13.27"]}}
        self.starting = mock.Mock(return_value=suggestion or self.SUGGESTION)
        with mock.patch.object(photos, "read_list", **read_kind), mock.patch.object(llm, "starting_list", self.starting):
            return self.client.post("/api/lists/from-photo", content=body, headers={"Content-Type": content_type})

    def test_a_suggestion_is_returned_and_nothing_is_saved(self):
        response = self.post()

        self.assertEqual(response.json()["items"][0]["name"], "Eggs")
        self.assertEqual(response.json()["items"][0]["priceSource"], "estimate")
        self.assertEqual(response.json()["leftOut"], ["TOTAL 13.27"])
        # What the page sends back to create the list is accepted, and left-out lines don't become items.
        self.assertEqual([i["name"] for i in self.client.post("/api/lists", json=response.json()).json()["items"]], ["Eggs"])
        self.db.tables.clear()
        # No budget is sent, so nothing written down is dropped to fit one.
        self.assertEqual(self.starting.call_args.args, (photos.list_request([{"text": "eggs", "lowConfidence": False}]),))
        self.assertEqual(self.db.tables, {})
        self.assertEqual(self.db.files, {})

    def test_bad_uploads_and_failures(self):
        self.assertEqual(self.post(content_type="image/gif").status_code, 415)
        self.assertEqual(self.post(body=b"x" * (main.MAX_RECEIPT_BYTES + 1)).status_code, 413)
        self.assertEqual(self.post(lines=[]).json(), {"error": "NO_ITEMS_FOUND"})
        self.starting.assert_not_called()
        self.assertEqual(self.post(suggestion={"title": "x", "kind": "other", "items": []}).json(), {"error": "NO_ITEMS_FOUND"})
        with self.assertLogs(main.log):
            self.assertEqual(self.post(lines=receipts.ReceiptError("UNREADABLE_LIST")).status_code, 422)
            self.assertEqual(self.post(lines=receipts.ReceiptError("SCANNING_UNAVAILABLE")).status_code, 502)

    def test_it_shares_the_cap_on_suggestions(self):
        statuses = [self.post().status_code for _ in range(21)]
        self.assertEqual(statuses[-2:], [200, 429])


class ItemPhotoRouteTest(RoutesTest):
    def setUp(self):
        super().setUp()
        self.list = self.new_list([{"name": "Milk", "estPriceCents": 400}, {"name": "Bread"}, {"name": "Tent"}])
        self.milk, self.bread, self.tent = (item["id"] for item in self.list["items"])
        self.url = f"/api/lists/{self.list['id']}/item-photo"

    def post(self, url=None, found=None, content_type="image/jpeg"):
        kind = {"side_effect": found} if isinstance(found, Exception) else {"return_value": found or {"itemId": self.milk, "seen": "milk"}}
        with mock.patch.object(photos, "identify_item", **kind) as self.identify:
            return self.client.post(url or self.url, content=b"photo", headers={"Content-Type": content_type})

    def test_it_proposes_an_item_and_checks_nothing_off(self):
        self.assertEqual(self.post().json(), {"itemId": self.milk, "seen": "milk"})
        self.assertIsNone(next(i for i in self.client.get(f"/api/lists/{self.list['id']}").json()["items"] if i["id"] == self.milk)["checkedAt"])
        self.assertEqual(self.db.files, {})

    def test_bought_and_held_items_are_not_candidates(self):
        self.db.update("items", {"checked_at": "earlier"}, id=self.bread)
        self.db.insert("orders", [{"id": "ORDER1", "list_id": self.list["id"], "item_ids": [self.tent], "total_cents": 100, "status": "PENDING"}])
        self.post()
        self.assertEqual([item["id"] for item in self.identify.call_args.args[1]], [self.milk])

    def test_with_nothing_open_no_paid_call_is_made(self):
        for item_id in (self.milk, self.bread, self.tent):
            self.db.update("items", {"checked_at": "earlier"}, id=item_id)
        self.assertEqual(self.post().json(), {"itemId": None, "seen": ""})
        self.identify.assert_not_called()

    def test_bad_requests_failures_and_the_cap(self):
        self.assertEqual(self.post(content_type="image/gif").status_code, 415)
        self.assertEqual(self.post(url="/api/lists/nope/item-photo").status_code, 404)
        with self.assertLogs(main.log):
            self.assertEqual(self.post(found=receipts.ReceiptError("SCANNING_UNAVAILABLE")).status_code, 502)
        main._calls.clear()
        statuses = [self.post().status_code for _ in range(101)]
        self.assertEqual(statuses[-2:], [200, 429])

    def test_the_confirmed_tick_records_the_price_for_the_budget(self):
        member = self.client.post(f"/api/lists/{self.list['id']}/members", json={"name": "Ann"}).json()["id"]
        saved = self.client.patch(f"/api/items/{self.milk}", json={"checked": True, "memberId": member, "priceCents": 459}).json()
        self.assertEqual((saved["priceCents"], saved["boughtBy"]), (459, member))
        self.assertEqual(self.client.get(f"/api/lists/{self.list['id']}/split").json()["members"][0]["paidCents"], 459)


if __name__ == "__main__":
    unittest.main()
