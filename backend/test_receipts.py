import json
import unittest
from unittest import mock

from botocore.stub import Stubber

import llm
import receipts


def field(kind, text, confidence=99.0, label=None):
    found = {"Type": {"Text": kind}, "ValueDetection": {"Text": text, "Confidence": confidence}}
    return found | ({"LabelDetection": {"Text": label}} if label else {})


def expense(*lines, total="$13.27", summary=()):
    return {
        "ExpenseDocuments": [
            {
                "SummaryFields": [field("TOTAL", total), *summary],
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

    def test_a_price_textract_is_unsure_of_is_left_blank_not_guessed(self):
        result = receipts.parse_expense(expense([field("ITEM", "EGGS"), field("PRICE", "3.49", 61.0)], [field("ITEM", "BAG")]))

        self.assertEqual([(line["text"], line["priceCents"], line["lowConfidence"]) for line in result["lines"]], [("EGGS", None, True), ("BAG", None, False)])

    def test_an_unsure_price_the_subtotal_confirms_is_kept(self):
        # The Walmart receipt in the eval set: 12.94 read at 42% confidence, and 14.97 + 12.94 + 2.48 = 30.39.
        lines = ([field("ITEM", "GRILL COVER"), field("PRICE", "14.97")], [field("ITEM", "FIBER CHOICE"), field("PRICE", "12.94", 42.3)], [field("ITEM", "CELERY"), field("PRICE", "2.48")])
        result = receipts.parse_expense(expense(*lines, total="32.52", summary=[field("SUBTOTAL", "30.39"), field("TAX", "2.13")]))
        # Still flagged, so the person looks at it.
        self.assertEqual([(line["priceCents"], line["lowConfidence"]) for line in result["lines"]], [(1497, False), (1294, True), (248, False)])
        self.assertEqual(result["fees"], [{"kind": "tax", "name": "Tax", "amountCents": 213}])

    def test_an_unsure_price_stays_blank_unless_a_sure_subtotal_adds_up(self):
        lines = ([field("ITEM", "EGGS"), field("PRICE", "3.49", 61.0)], [field("ITEM", "BREAD"), field("PRICE", "2.00")])
        for summary in ([field("SUBTOTAL", "5.50")], [field("SUBTOTAL", "5.49", 70.0)], []):
            with self.subTest(summary=summary):
                result = receipts.parse_expense(expense(*lines, total="5.49", summary=summary))
                self.assertIsNone(result["lines"][0]["priceCents"])
        # A blank price Textract read nothing for can't be confirmed either.
        result = receipts.parse_expense(expense([field("ITEM", "EGGS")], [field("ITEM", "BREAD"), field("PRICE", "2.00")], summary=[field("SUBTOTAL", "2.00")]))
        self.assertIsNone(result["lines"][0]["priceCents"])

    def test_discounts_are_fees_and_free_or_nameless_lines_are_dropped(self):
        result = receipts.parse_expense(
            expense(
                [field("ITEM", "COUPON"), field("PRICE", "1.00-")],
                [field("ITEM", "+ AMERICAN CHEESE"), field("PRICE", "0.00")],
                [field("PRICE", "2.00")],
            )
        )

        self.assertEqual(result["lines"], [])
        self.assertEqual(result["fees"], [{"kind": "discount", "name": "COUPON", "amountCents": -100}])

    def test_a_discount_under_an_item_comes_off_that_item(self):
        result = receipts.parse_expense(
            expense(
                [field("ITEM", "QUANTUM ULT"), field("PRICE", "23.99")],
                [field("ITEM", "TPD/4254844"), field("PRICE", "5.00-")],
                [field("ITEM", "SWEET POTATO"), field("PRICE", "16.99")],
                total="$35.98",
            )
        )

        self.assertEqual([(l["text"], l["priceCents"], l.get("discountCents")) for l in result["lines"]], [("QUANTUM ULT", 1899, 500), ("SWEET POTATO", 1699, None)])
        self.assertEqual(result["lines"][0]["discountName"], "TPD/4254844")
        self.assertEqual(result["fees"], [])

    def test_a_discount_that_isnt_for_the_item_above_stays_a_fee(self):
        result = receipts.parse_expense(
            expense(
                # Bigger than the line above: a comp for the bill.
                [field("ITEM", "Corona"), field("PRICE", "6.00")],
                [field("ITEM", "Comp Item"), field("PRICE", "12.00-")],
                # Two discounts in a row: the second has no item right above it.
                [field("ITEM", "MILK"), field("PRICE", "4.29")],
                [field("ITEM", "COUPON"), field("PRICE", "1.00-")],
                [field("ITEM", "COUPON 2"), field("PRICE", "0.50-")],
                # Under an item whose price wasn't read surely.
                [field("ITEM", "EGGS"), field("PRICE", "3.00", confidence=50)],
                [field("ITEM", "SAVE"), field("PRICE", "0.40-")],
                # Read unsurely itself.
                [field("ITEM", "GUM"), field("PRICE", "1.99")],
                [field("ITEM", "SAVE"), field("PRICE", "0.20-", confidence=50)],
            )
        )

        self.assertEqual([l["priceCents"] for l in result["lines"]], [600, 329, None, 199])
        self.assertEqual([f["name"] for f in result["fees"]], ["Comp Item", "COUPON 2", "SAVE", "SAVE"])

    def test_a_name_mixed_with_neighbouring_lines_is_taken_from_its_printed_row(self):
        result = receipts.parse_expense(
            expense(
                [
                    field("ITEM", "WINCO SNDWCH WT\nWINCO HOMO MILK"),
                    field("PRICE", "2.48"),
                    field("EXPENSE_ROW", "WINCO SNDWCH WT 7055200115 .91 FS\nWINCO HOMO MILK 7055240600 2.48 FS"),
                ]
            )
        )

        self.assertEqual(result["lines"][0]["text"], "WINCO HOMO MILK")

    def test_the_taxes_and_tip_kept_are_the_ones_that_add_up_to_the_total(self):
        summary = [
            field("SUBTOTAL", "36.00"),
            field("SUBTOTAL", "39.19", label="Sub w/Tax"),
            field("TAX", "3.00", label="Sales Tax"),
            field("TAX", "0.19", label="City Tax"),
            field("TAX", "3.19", label="Total Tax"),
            field("TAX", "3.19", label="Total Tax"),
            field("GRATUITY", "5.40", label="15% Gratuity"),
            field("GRATUITY", "7.20", label="20% Gratuity"),
        ]
        line = [field("ITEM", "CHEESE STEAK"), field("PRICE", "36.00")]

        added = receipts.parse_expense(expense(line, total="$46.39", summary=summary))
        self.assertEqual(added["fees"], [{"kind": "tax", "name": "Total Tax", "amountCents": 319}, {"kind": "tip", "name": "20% Gratuity", "amountCents": 720}])
        self.assertEqual(added["totalCents"], 4639)

        # Tip suggestions that weren't added: only the tax adds up.
        suggested = receipts.parse_expense(expense(line, total="$39.19", summary=summary))
        self.assertEqual([fee["kind"] for fee in suggested["fees"]], ["tax"])

    def test_fees_that_dont_add_up_keep_the_total_tax_and_leave_unsure_amounts_blank(self):
        summary = [
            field("TAX", "1.52", label="IL Sales"),
            field("TAX", "1.67", 70.0, label="TOTAL TAX"),
            field("GRATUITY", "2.00", label="Tip"),
            field("SERVICE_CHARGE", "4g67"),
        ]

        result = receipts.parse_expense(expense([field("ITEM", "SOUP"), field("PRICE", "9.00")], total="$99.00", summary=summary))

        self.assertEqual(result["fees"], [{"kind": "tax", "name": "TOTAL TAX", "amountCents": None}, {"kind": "tip", "name": "Tip", "amountCents": 200}])

    def test_tax_under_another_label_is_kept_when_it_adds_up(self):
        # The UMass store receipt: "Taxable 1.62", which Textract didn't type as TAX.
        line = [field("ITEM", "Kingston Canvas 128GB SD Ca"), field("PRICE", "26.00")]
        summary = [field("SUBTOTAL", "$26.00", label="Sub Total"), field("OTHER", "1.62", label="Taxable"), field("TAX_PAYER_ID", "200-218-727", label="Tax Registration:")]

        result = receipts.parse_expense(expense(line, total="$27.62", summary=summary))

        self.assertEqual(result["fees"], [{"kind": "tax", "name": "Taxable", "amountCents": 162}])

        # "Taxable" as the amount taxed doesn't add up, so it isn't taken for the tax.
        base = receipts.parse_expense(expense(line, total="$26.00", summary=[field("OTHER", "26.00", label="Taxable")]))
        self.assertEqual(base["fees"], [])

    def test_the_rest_of_the_total_is_a_fee_when_everything_else_was_read(self):
        line = [field("ITEM", "SD CARD"), field("PRICE", "26.00")]

        result = receipts.parse_expense(expense(line, total="$27.62"))

        self.assertEqual(result["fees"], [{"kind": "other", "name": "Rest of the total (tax or fees not itemized)", "amountCents": 162}])

        # Not when a price is still blank, the total is less, or the gap is too big to be charges (a misread total).
        unsure = receipts.parse_expense(expense([field("ITEM", "SD CARD"), field("PRICE", "26.00", 60.0)], total="$27.62"))
        self.assertEqual(unsure["fees"], [])
        for total in ("$25.00", "$26.01", "$79.62"):
            with self.subTest(total=total):
                self.assertEqual(receipts.parse_expense(expense(line, total=total))["fees"], [])

    def test_amounts_parse_without_floats(self):
        for text, cents in (
            ("$1,234.5", 123450),
            ("12", 1200),
            ("0.07", 7),
            (".98", 98),
            ("-0.50", -50),
            ("9.95-", -995),
            ("($12.00)", -1200),
            ("$-3.00", -300),
            ("n/a", None),
        ):
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
                {"text": "GUM", "priceCents": "1.99"},  # not a number: asked, not guessed
                {"text": "BAG", "priceCents": 0},
            ],
            "fees": [
                {"kind": "tax", "name": "TAX", "amountCents": 30},
                {"kind": "discount", "name": "MEMBER SAVINGS", "amountCents": 50},
                {"kind": "surcharge", "name": "", "amountCents": None},
                "junk",
            ],
            "totalCents": 329,
        }
        chat = self.ollama("```json\n" + json.dumps(reply) + "\n```")
        self.stub.add_client_error("analyze_expense", "AccessDeniedException")

        self.assertEqual(
            receipts.read_receipt(b"jpg"),
            {
                "lines": [
                    # The coupon printed under the milk comes off the milk (issue 17).
                    {"text": "2% MILK 1GAL", "priceCents": 329, "confidence": None, "lowConfidence": False, "discountCents": 100, "discountName": "COUPON"},
                    {"text": "GUM", "priceCents": None, "confidence": None, "lowConfidence": False},
                ],
                "fees": [
                    {"kind": "tax", "name": "TAX", "amountCents": 30},
                    {"kind": "discount", "name": "MEMBER SAVINGS", "amountCents": -50},
                    {"kind": "other", "name": "Other", "amountCents": None},
                ],
                "totalCents": 329,
            },
        )
        messages, schema = chat.call_args.args
        self.assertEqual(messages[1]["images"], [b"jpg"])
        self.assertIs(schema, receipts.READ_SCHEMA)

    def test_the_ollama_reader_also_counts_the_rest_of_the_total(self):
        self.ollama(json.dumps({"lines": [{"text": "SD CARD", "priceCents": 2600}], "fees": [], "totalCents": 2762}))
        self.stub.add_client_error("analyze_expense", "AccessDeniedException")

        self.assertEqual(receipts.read_receipt(b"jpg")["fees"], [{"kind": "other", "name": "Rest of the total (tax or fees not itemized)", "amountCents": 162}])

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
