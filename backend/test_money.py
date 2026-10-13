import unittest

import money


def item(item_id, price=None, bought_by=None, claimed_by=None, est=None, checked=None, name="x"):
    return {
        "id": item_id,
        "name": name,
        "priceCents": price,
        "boughtBy": bought_by,
        "claimedBy": claimed_by,
        "estPriceCents": est,
        "checkedAt": checked or ("2026-10-13T10:00:00" if price is not None else None),
    }


MEMBERS = [{"id": "ana"}, {"id": "ben"}, {"id": "cy"}]


class SummaryTest(unittest.TestCase):
    def test_totals_per_person_and_who_owes_whom(self):
        items = [item("1", 6000, "ana"), item("2", 3000, "ben"), item("3", 500, None), item("4")]
        receipts = [{"memberId": "ben", "extras": [{"priceCents": 199}, {"priceCents": None}]}]
        result = money.summary(MEMBERS, items, receipts)
        self.assertEqual((result["spentCents"], result["extrasCents"]), (9500, 199))
        self.assertEqual(
            result["perPerson"],
            [
                {"memberId": "ana", "spentCents": 6000, "extrasCents": 0},
                {"memberId": "ben", "spentCents": 3000, "extrasCents": 199},
                {"memberId": "cy", "spentCents": 0, "extrasCents": 0},
            ],
        )
        # $90 was paid by members, so $30 each. Extras and the anonymous $5 are not split.
        self.assertEqual(result["owes"], [{"from": "cy", "to": "ana", "amountCents": 3000}])

    def test_a_paid_invoice_clears_the_debt_and_an_unpaid_one_does_not(self):
        items = [item("1", 6000, "ana"), item("2", 3000, "ben")]
        invoice = {"debtorId": "cy", "creditorId": "ana", "amountCents": 3000, "status": "SENT"}
        self.assertEqual(len(money.summary(MEMBERS, items, [], [invoice])["owes"]), 1)
        paid = money.summary(MEMBERS, items, [], [{**invoice, "status": "PAID"}])
        self.assertEqual(paid["owes"], [])
        self.assertEqual(paid["perPerson"][0]["spentCents"], 6000)


class SettleTest(unittest.TestCase):
    def test_cents_that_do_not_divide_still_add_up(self):
        ids = ["ana", "ben", "cy"]
        owes = money.settle(ids, {"ana": 1000, "ben": 0, "cy": 0})
        # Shares are 334, 333, 333.
        self.assertEqual(
            owes,
            [{"from": "ben", "to": "ana", "amountCents": 333}, {"from": "cy", "to": "ana", "amountCents": 333}],
        )

    def test_every_balance_ends_at_zero(self):
        ids = ["a", "b", "c", "d"]
        paid = {"a": 4321, "b": 17, "c": 990, "d": 0}
        share, odd = divmod(sum(paid.values()), 4)
        balance = {m: paid[m] - share - (1 if i < odd else 0) for i, m in enumerate(ids)}
        for owed in money.settle(ids, paid):
            self.assertGreater(owed["amountCents"], 0)
            balance[owed["from"]] += owed["amountCents"]
            balance[owed["to"]] -= owed["amountCents"]
        self.assertEqual(set(balance.values()), {0})

    def test_nothing_to_settle(self):
        self.assertEqual(money.settle(["ana"], {"ana": 500}), [])
        self.assertEqual(money.settle(["ana", "ben"], {"ana": 500, "ben": 500}), [])
        self.assertEqual(money.settle([], {}), [])


class AssignTest(unittest.TestCase):
    def test_unclaimed_open_items_go_to_whoever_has_least_to_buy(self):
        items = [
            item("sofa", claimed_by="ana", est=5000),
            item("kettle", est=2000),
            item("mop", est=1500),
            item("bin", est=1000),
            item("done", price=100, est=100),
        ]
        self.assertEqual(
            money.assign(["ana", "ben", "cy"], items), {"kettle": "ben", "mop": "cy", "bin": "cy"}
        )
        self.assertEqual(money.assign([], items), {})


class HistoryTest(unittest.TestCase):
    def test_spending_by_kind_and_month_and_the_last_price_paid(self):
        def state(list_id, kind, created, spent, items):
            return {
                "id": list_id,
                "title": list_id,
                "kind": kind,
                "createdAt": created,
                "finishedAt": None,
                "items": items,
                "money": {"spentCents": spent, "extrasCents": 100},
            }

        result = money.history(
            [
                state("old", "groceries", "2026-09-02T08:00:00", 429, [item("1", 429, name="Milk", checked="2026-09-02")]),
                state("new", "groceries", "2026-10-05T08:00:00", 459, [item("2", 459, name=" milk ", checked="2026-10-05"), item("3")]),
                state("trip", "trip", "2026-10-09T08:00:00", 0, []),
            ]
        )
        self.assertEqual([row["id"] for row in result["lists"]], ["trip", "new", "old"])
        self.assertEqual(result["byKind"], {"groceries": 1088, "trip": 100})
        self.assertEqual(result["byMonth"], {"2026-10": 659, "2026-09": 529})
        self.assertEqual(result["lastPaidCents"], {"milk": 459})
        self.assertEqual((result["lists"][1]["itemCount"], result["lists"][1]["doneCount"]), (2, 1))
