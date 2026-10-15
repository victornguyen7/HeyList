import unittest

from sample_list import ITEMS, total_cents


class TotalCentsTest(unittest.TestCase):
    def test_sums_price_times_quantity_in_cents(self):
        self.assertEqual(total_cents({"sunscreen": 2, "adapter": 1}), 2 * 899 + 1499)
        self.assertEqual(
            total_cents({item["id"]: 1 for item in ITEMS}),
            sum(item["priceCents"] for item in ITEMS),
        )

    def test_rejects_selections_that_must_never_be_charged(self):
        for selection, message in [
            ({}, "at least one"),
            (["sunscreen"], "at least one"),
            (None, "at least one"),
            ({"nope": 1}, "unknown"),
            ({"sunscreen": 0}, "quantity"),
            ({"sunscreen": -1}, "quantity"),
            ({"sunscreen": 100}, "quantity"),
            ({"sunscreen": 1.5}, "quantity"),
            ({"sunscreen": "2"}, "quantity"),
            ({"sunscreen": True}, "quantity"),
        ]:
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(ValueError, message):
                    total_cents(selection)
