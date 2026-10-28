import unittest

import money


def item(item_id, cents=None, quantity=1, claimed_by=None, checked_at=None, price_cents=None, bought_by=None, order_id=None, receipt_id=None):
    return {
        "receipt_id": receipt_id,
        "id": item_id,
        "est_price_cents": cents,
        "quantity": quantity,
        "claimed_by": claimed_by,
        "checked_at": checked_at,
        "price_cents": price_cents,
        "bought_by": bought_by,
        "order_id": order_id,
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

    def test_a_settle_up_payment_moves_both_balances_and_a_full_one_evens_them(self):
        items = [item("tent", price_cents=9000, bought_by="ann"), item("food", price_cents=3000, bought_by="bob")]
        part = [{"debtor_id": "bob", "creditor_id": "ann", "amount_cents": 1000}]

        result = money.split(items, ["ann", "bob"], settlements=part)

        self.assertEqual([m["settledCents"] for m in result["members"]], [-1000, 1000])
        self.assertEqual(result["transfers"], [{"from": "bob", "to": "ann", "amountCents": 2000}])
        full = part + [{"debtor_id": "bob", "creditor_id": "ann", "amount_cents": 2000}]
        self.assertEqual(money.split(items, ["ann", "bob"], settlements=full)["transfers"], [])
        # Spending and shares don't change: a settlement is money between people, not money spent on the list.
        self.assertEqual(money.split(items, ["ann", "bob"], settlements=full)["totalCents"], 12000)

    def test_every_balance_adds_up_from_its_purchases(self):
        items = [item("tent", price_cents=9000, bought_by="ann"), item("gas", price_cents=1234, bought_by="ann"), item("food", price_cents=3001, bought_by="bob")]

        for member in money.split(items, ["ann", "bob", "cat"])["members"]:
            self.assertEqual(sum(line["cents"] for line in member["purchases"]), member["paidCents"])
            self.assertEqual(member["paidCents"] - member["shareCents"], member["balanceCents"])

    def test_odd_cents_still_add_up(self):
        result = money.split([item("x", price_cents=1000, bought_by="ann")], ["ann", "bob", "cat"])

        self.assertEqual([m["shareCents"] for m in result["members"]], [334, 333, 333])
        self.assertEqual(sum(t["amountCents"] for t in result["transfers"]), 666)

    def test_a_price_without_a_buyer_is_reported_not_split(self):
        result = money.split([item("x", price_cents=700)], ["ann"])

        self.assertEqual((result["totalCents"], result["unattributedCents"], result["transfers"]), (0, 700, []))

    def test_a_paypal_charge_for_an_item_a_receipt_covered_still_counts(self):
        items = [
            item("tent", price_cents=9000, bought_by="ann", order_id="O1"),
            item("food", price_cents=3000, bought_by="bob"),  # bob's receipt landed while ann was on PayPal
        ]
        orders = [{"id": "O1", "member_id": "ann", "item_ids": ["tent", "food", "gone"], "prices": {"tent": 9000, "food": 2500, "gone": 100}}]

        result = money.split(items, ["ann", "bob"], orders)

        # ann paid 90 + 25 + 1 (an item since deleted) by PayPal, bob 30 by receipt.
        self.assertEqual([m["paidCents"] for m in result["members"]], [11600, 3000])
        self.assertEqual(
            result["members"][0]["purchases"],
            [
                {"itemId": "tent", "cents": 9000, "boughtTwice": False, "feesOf": None},
                {"itemId": "food", "cents": 2500, "boughtTwice": True, "feesOf": None},
                {"itemId": "gone", "cents": 100, "boughtTwice": True, "feesOf": None},
            ],
        )
        self.assertEqual(result["totalCents"], 14600)
        self.assertEqual([b["itemId"] for b in result["boughtTwice"]], ["food", "gone"])

    def test_receipt_fees_are_shared_in_proportion_to_the_list_items(self):
        items = [item("milk", price_cents=600, bought_by="ann", receipt_id="R1"), item("eggs", price_cents=300, bought_by="ann", receipt_id="R1")]
        receipt = {"id": "R1", "member_id": "ann", "confirmed_at": "now", "extras": [{"name": "GUM", "priceCents": 300}, {"name": "?", "priceCents": None}]}
        fees = [{"kind": "tax", "amountCents": 100}, {"kind": "tip", "amountCents": 200}, {"kind": "discount", "amountCents": -60}, {"kind": "tax", "amountCents": None}]

        result = money.split(items, ["ann", "bob"], receipts=[receipt | {"fees": fees}])

        # 240 of fees on 900 of list items and 300 of extras: 180 is shared, 60 stays with ann.
        self.assertEqual(result["members"][0]["purchases"][-1], {"itemId": None, "cents": 180, "boughtTwice": False, "feesOf": "R1"})
        self.assertEqual(result["totalCents"], 1080)
        # An unconfirmed receipt, or one with no fees, adds nothing.
        for other in (receipt | {"fees": fees, "confirmed_at": None}, receipt | {"fees": []}):
            self.assertEqual(money.split(items, ["ann", "bob"], receipts=[other])["totalCents"], 900)

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
