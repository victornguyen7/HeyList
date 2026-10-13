import unittest

from sample_list import ITEMS, total_cents


class TotalCentsTest(unittest.TestCase):
    def test_sums_the_selected_items_in_cents(self):
        self.assertEqual(total_cents(["sunscreen", "adapter"]), 899 + 1499)
        self.assertEqual(
            total_cents([item["id"] for item in ITEMS]),
            sum(item["priceCents"] for item in ITEMS),
        )

    def test_rejects_selections_that_must_never_be_charged(self):
        for item_ids, message in [
            ([], "at least one"),
            (["sunscreen", "nope"], "unknown"),
            (["sunscreen", "sunscreen"], "twice"),
            ("sunscreen", "at least one"),
            (None, "at least one"),
            ([["sunscreen"]], "unknown"),
            ([1], "unknown"),
        ]:
            with self.subTest(item_ids=item_ids):
                with self.assertRaisesRegex(ValueError, message):
                    total_cents(item_ids)
