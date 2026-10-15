import json
import unittest
from unittest import mock

from botocore.stub import Stubber

import llm
import receipts


def field(kind, text, confidence=99.0):
    return {"Type": {"Text": kind}, "ValueDetection": {"Text": text, "Confidence": confidence}}


def expense(*lines, total="$13.27"):
    return {
        "ExpenseDocuments": [
            {
                "SummaryFields": [field("TOTAL", total)],
                "LineItemGroups": [{"LineItems": [{"LineItemExpenseFields": list(line)} for line in lines]}],
            }
        ]
    }


class ParseTest(unittest.TestCase):
    def test_lines_come_out_in_cents_with_their_confidence(self):
        result = receipts.parse_expense(
            expense(
                [field("ITEM", "2% MILK 1GAL"), field("PRICE", "$4.29")],
                [field("ITEM", "SUNSCRN SPF50", 72.5), field("PRICE", "8.99", 95.0)],
            )
        )

        self.assertEqual(result["totalCents"], 1327)
        self.assertEqual(
            result["lines"],
            [
                {"text": "2% MILK 1GAL", "priceCents": 429, "confidence": 99.0, "lowConfidence": False},
                {"text": "SUNSCRN SPF50", "priceCents": 899, "confidence": 72.5, "lowConfidence": True},
            ],
        )

    def test_discounts_and_lines_without_a_price_are_dropped(self):
        result = receipts.parse_expense(
            expense([field("ITEM", "COUPON"), field("PRICE", "-1.00")], [field("ITEM", "BAG")], [field("PRICE", "2.00")])
        )

        self.assertEqual(result["lines"], [])

    def test_amounts_parse_without_floats(self):
        for text, cents in (("$1,234.5", 123450), ("12", 1200), ("0.07", 7), ("-0.50", -50), ("n/a", None)):
            with self.subTest(text=text):
                self.assertEqual(receipts.cents(text), cents)


class ReadTest(unittest.TestCase):
    def setUp(self):
        receipts._textract.cache_clear()
        self.addCleanup(receipts._textract.cache_clear)
        with mock.patch.dict("os.environ", {"AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "y"}):
            self.stub = Stubber(receipts._textract())
        self.stub.activate()
        self.addCleanup(self.stub.deactivate)

    def test_textract_is_called_with_the_photo(self):
        self.stub.add_response("analyze_expense", expense([field("ITEM", "EGGS"), field("PRICE", "3.49")]), {"Document": {"Bytes": b"jpg"}})

        self.assertEqual(receipts.read_receipt(b"jpg")["lines"][0]["priceCents"], 349)

    def ollama(self, reply=None, error=None):
        chat = mock.patch.object(llm, "chat", side_effect=error, return_value=reply).start()
        self.addCleanup(mock.patch.stopall)
        return chat

    def test_a_bad_photo_is_not_sent_anywhere_else(self):
        chat = self.ollama()
        self.stub.add_client_error("analyze_expense", "UnsupportedDocumentException")

        with self.assertRaisesRegex(receipts.ReceiptError, "UNREADABLE_IMAGE"):
            receipts.read_receipt(b"jpg")
        chat.assert_not_called()

    def test_without_textract_the_ollama_vision_model_reads_the_photo(self):
        reply = {
            "lines": [
                {"text": " 2% MILK 1GAL ", "priceCents": 429},
                {"text": "COUPON", "priceCents": -100},
                {"text": "", "priceCents": 50},
                {"text": "GUM", "priceCents": "1.99"},
            ],
            "totalCents": 329,
        }
        chat = self.ollama("```json\n" + json.dumps(reply) + "\n```")
        self.stub.add_client_error("analyze_expense", "AccessDeniedException")

        self.assertEqual(
            receipts.read_receipt(b"jpg"),
            {"lines": [{"text": "2% MILK 1GAL", "priceCents": 429, "confidence": None, "lowConfidence": False}], "totalCents": 329},
        )
        messages, schema = chat.call_args.args
        self.assertEqual(messages[1]["images"], [b"jpg"])
        self.assertIs(schema, receipts.READ_SCHEMA)

    def test_when_neither_can_read_it_scanning_is_unavailable(self):
        for error, expected in ((ConnectionError(), "SCANNING_UNAVAILABLE"), (None, "UNREADABLE_IMAGE")):
            with self.subTest(error=error):
                self.ollama("not json", error)
                self.stub.add_client_error("analyze_expense", "ThrottlingException")
                with self.assertRaisesRegex(receipts.ReceiptError, expected):
                    receipts.read_receipt(b"jpg")


class MatchTest(unittest.TestCase):
    LINES = [{"text": "2% MILK 1GAL"}, {"text": "GUM"}, {"text": "MILK 2%"}]
    ITEMS = [{"id": "id-bread", "name": "bread"}, {"id": "id-milk", "name": "milk"}]

    def ollama(self, reply="{}", error=None):
        patch = mock.patch.object(llm, "chat", side_effect=error, return_value=reply)
        self.addCleanup(patch.stop)
        return patch.start()

    def test_lines_map_to_item_ids_and_bad_numbers_are_dropped(self):
        matches = [
            {"line": 0, "item": 1},
            {"line": 1, "item": None},
            {"line": 2, "item": 1},
            {"line": 7, "item": 0},  # no such line
            {"line": 1, "item": 9},  # no such item
            {"line": "1", "item": 0},  # not a number
            "junk",
        ]
        chat = self.ollama(json.dumps({"matches": matches}))

        self.assertEqual(receipts.match_lines(self.LINES, self.ITEMS), ["id-milk", None, "id-milk"])
        messages, schema = chat.call_args.args
        self.assertIs(schema, receipts.MATCH_SCHEMA)
        # Only names and receipt text go to the model, never IDs or prices.
        self.assertNotIn("id-milk", messages[1]["content"])

    def test_an_oversized_receipt_is_refused_before_any_call(self):
        chat = self.ollama()

        with self.assertRaisesRegex(receipts.ReceiptError, "RECEIPT_TOO_LONG"):
            receipts.match_lines([{"text": "x"}] * (receipts.MAX_LINES + 1), self.ITEMS)
        chat.assert_not_called()

    def test_nothing_to_match_skips_the_call(self):
        chat = self.ollama()

        self.assertEqual(receipts.match_lines(self.LINES, []), [None, None, None])
        chat.assert_not_called()

    def test_a_garbled_reply_or_an_outage_is_a_receipt_error(self):
        self.ollama("Sorry, I can't help with that.")
        with self.assertRaisesRegex(receipts.ReceiptError, "MATCHING_FAILED"):
            receipts.match_lines(self.LINES, self.ITEMS)

        self.ollama(error=ConnectionError())
        with self.assertRaisesRegex(receipts.ReceiptError, "MATCHING_UNAVAILABLE"):
            receipts.match_lines(self.LINES, self.ITEMS)


if __name__ == "__main__":
    unittest.main()
