import unittest

import money


def item(item_id, cents=None, quantity=1, claimed_by=None, checked_at=None, price_cents=None, bought_by=None):
    return {
        "id": item_id,
        "est_price_cents": cents,
        "quantity": quantity,
        "claimed_by": claimed_by,
        "checked_at": checked_at,
        "price_cents": price_cents,
        "bought_by": bought_by,
    }


class AssignTest(unittest.TestCase):
    def test_unclaimed_items_even_out_the_cost(self):
        items = [item("tent", 9000, claimed_by="ann"), item("stove", 4000), item("gas", 1000, 3), item("map", 500)]

        # ann already carries 90.00, so bob gets the rest.
        self.assertEqual(money.assign_unclaimed(items, ["ann", "bob"]), {"stove": "bob", "gas": "bob", "map": "bob"})

    def test_unpriced_items_spread_by_count(self):
        items = [item("a"), item("b"), item("c"), item("d")]

        self.assertEqual(money.assign_unclaimed(items, ["ann", "bob"]), {"a": "ann", "b": "bob", "c": "ann", "d": "bob"})

    def test_checked_and_claimed_items_are_left_alone(self):
        items = [item("done", 100, checked_at="2026-10-15"), item("mine", 100, claimed_by="ann")]

        self.assertEqual(money.assign_unclaimed(items, ["ann", "bob"]), {})

    def test_a_claim_by_someone_no_longer_a_member_is_reassigned(self):
        self.assertEqual(money.assign_unclaimed([item("x", 100, claimed_by="gone")], ["ann"]), {"x": "ann"})


class SplitTest(unittest.TestCase):
    def test_equal_shares_and_the_transfers_that_settle_them(self):
        items = [
            item("tent", price_cents=9000, bought_by="ann"),
            item("food", price_cents=3000, bought_by="bob"),
            item("open", 500),  # not bought yet: not in the split
        ]

        result = money.split(items, ["ann", "bob", "cat"])

        self.assertEqual(result["totalCents"], 12000)
        self.assertEqual([m["balanceCents"] for m in result["members"]], [5000, -1000, -4000])
        self.assertEqual(
            result["transfers"],
            [{"from": "cat", "to": "ann", "amountCents": 4000}, {"from": "bob", "to": "ann", "amountCents": 1000}],
        )

    def test_odd_cents_still_add_up(self):
        result = money.split([item("x", price_cents=1000, bought_by="ann")], ["ann", "bob", "cat"])

        self.assertEqual([m["shareCents"] for m in result["members"]], [334, 333, 333])
        self.assertEqual(sum(t["amountCents"] for t in result["transfers"]), 666)

    def test_a_price_without_a_buyer_is_reported_not_split(self):
        result = money.split([item("x", price_cents=700)], ["ann"])

        self.assertEqual((result["totalCents"], result["unattributedCents"], result["transfers"]), (0, 700, []))

    def test_no_members_is_not_a_crash(self):
        self.assertEqual(money.split([], [])["members"], [])

    def test_settle_always_reaches_zero(self):
        balance = {"a": 700, "b": -300, "c": -250, "d": -150, "e": 0}
        after = dict(balance)
        for transfer in money.settle(balance):
            after[transfer["from"]] += transfer["amountCents"]
            after[transfer["to"]] -= transfer["amountCents"]

        self.assertEqual(set(after.values()), {0})


if __name__ == "__main__":
    unittest.main()
