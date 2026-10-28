import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import eval_receipts


def line(text, price, low=False):
    return {"text": text, "priceCents": price, "confidence": None, "lowConfidence": low}


class GoldTest(unittest.TestCase):
    def test_a_label_file_becomes_items_and_amounts_in_cents(self):
        qa = [
            {"question": eval_receipts.ITEMS_QUESTION, "source": "Human", "answer": [
                {"item": "WOVEN DENIM TROUSERS", "quantity": "1", "total_price": "LE1,169.00"},
                {"item": "SOCKS", "quantity": "2", "total_price": "Not Available"},
            ]},
            {"question": "What is the total amount for this receipt?", "source": "Human", "answer": "LE 338.00"},
            {"question": "What is the total tax for this receipt?", "source": "Human", "answer": 41.5},
            {"question": "What is the subtotal for this receipt?", "source": "Human", "answer": "Not Available"},
            {"question": "What is the merchant's name on this receipt?", "source": "Human", "answer": "TEMA RETAIL EG"},
            {"question": "What is the total amount for this receipt?", "source": "GPT", "answer": "1.00"},
        ]

        self.assertEqual(
            eval_receipts.gold(qa),
            {
                "items": [{"name": "WOVEN DENIM TROUSERS", "quantity": 1, "priceCents": 116900}, {"name": "SOCKS", "quantity": 2, "priceCents": None}],
                "totalCents": 33800,
                "subtotalCents": None,
                "taxCents": 4150,
                "merchant": "TEMA RETAIL EG",
            },
        )

    def test_a_label_without_an_item_list_is_skipped(self):
        self.assertIsNone(eval_receipts.gold([{"question": eval_receipts.ITEMS_QUESTION, "source": "Human", "answer": "Not Available"}]))


class EnglishCasesTest(unittest.TestCase):
    def test_a_manifest_label_becomes_a_case_in_cents(self):
        manifest = {"receipts": [{"file": "grocery/docjay-003.jpg", "category": "grocery", "label": {
            "merchantName": "COSTCO WHOLESALE",
            "items": [{"name": " 18CT EGGS ", "quantity": 3, "unitPrice": 4.29, "totalPrice": 12.87}, {"name": "BAG", "quantity": 0.5, "totalPrice": None}],
            "subtotal": 12.87, "tax": None, "total": 13.9,
        }}]}
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "manifest.json").write_text(json.dumps(manifest))
            with mock.patch.object(eval_receipts, "ENGLISH", Path(folder)):
                cases = eval_receipts.english_cases()

        self.assertEqual(
            cases,
            [{
                "id": "docjay-003",
                "image": "grocery/docjay-003.jpg",
                "category": "grocery",
                "merchant": "COSTCO WHOLESALE",
                "items": [{"name": "18CT EGGS", "quantity": 3, "priceCents": 1287}, {"name": "BAG", "quantity": None, "priceCents": None}],
                "totalCents": 1390,
                "subtotalCents": 1287,
                "taxCents": None,
                "tipCents": None,
            }],
        )


class ScoreTest(unittest.TestCase):
    def test_lines_pair_up_by_name_and_price_and_leftovers_are_extras(self):
        case = {
            "totalCents": 1500,
            "items": [
                {"name": "Raw Kettle Potato", "priceCents": 550},
                {"name": "Raw Kettle Potato", "priceCents": 600},
                {"name": "Olive Oil", "priceCents": 350},
                {"name": "Bread", "priceCents": 100},
            ],
        }
        read = {
            "totalCents": 1500,
            "lines": [
                line("RAW KETTLE POTATO", 600),  # two of the same name pair up by price, whatever the order
                line("Raw Kettle Potatoe", 550),
                line("OLIVE OIL", 380, low=True),  # found, wrong price, flagged
                line("Sales VAT (14%)", 210),  # not an item
            ],
        }

        result = eval_receipts.score(case, read)

        self.assertEqual((result["found"], result["priceOk"], result["priceChecked"], result["extra"]), (3, 2, 3, 1))
        self.assertEqual((result["flaggedWrong"], result["wrongLines"], result["flaggedRight"]), (1, 1, 0))
        self.assertEqual((result["missed"], result["extras"]), (["Bread"], ["Sales VAT (14%)"]))
        self.assertTrue(result["totalOk"])
        self.assertFalse(result["perfect"])

    def test_summary_rates(self):
        perfect = eval_receipts.score({"totalCents": None, "items": [{"name": "Milk", "priceCents": 100}]}, {"totalCents": None, "lines": [line("MILK", 100)]})
        summary = eval_receipts.summarize([perfect])

        self.assertEqual((summary["itemRecall"], summary["linePrecision"], summary["perfectReceipts"], summary["totalAccuracy"]), (1.0, 1.0, 1.0, None))


if __name__ == "__main__":
    unittest.main()
