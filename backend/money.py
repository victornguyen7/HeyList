"""Budget totals, split math, and assignment of unclaimed items. Plain code, never the LLM (decision 10).

Everything is integer cents. The dicts are the camelCase rows the API returns.
"""

from collections.abc import Sequence


def summary(members: list[dict], items: list[dict], receipts: list[dict], invoices: Sequence[dict] = ()) -> dict:
    """What was spent, by whom, and who still owes whom once paid invoices are counted."""
    spent = {member["id"]: 0 for member in members}
    extras = {member["id"]: 0 for member in members}
    spent_total = extras_total = 0

    for item in items:
        price = item["priceCents"] or 0
        spent_total += price
        if item["boughtBy"] in spent:
            spent[item["boughtBy"]] += price
    for receipt in receipts:
        cost = sum(extra["priceCents"] or 0 for extra in receipt["extras"])
        extras_total += cost
        if receipt["memberId"] in extras:
            extras[receipt["memberId"]] += cost

    # A paid settle-up invoice moved money from the debtor to the creditor.
    settled = dict(spent)
    for invoice in invoices:
        if invoice["status"] in ("PAID", "MARKED_AS_PAID") and {invoice["debtorId"], invoice["creditorId"]} <= settled.keys():
            settled[invoice["debtorId"]] += invoice["amountCents"]
            settled[invoice["creditorId"]] -= invoice["amountCents"]

    return {
        "spentCents": spent_total,
        "extrasCents": extras_total,
        "perPerson": [
            {"memberId": member["id"], "spentCents": spent[member["id"]], "extrasCents": extras[member["id"]]}
            for member in members
        ],
        "owes": settle([member["id"] for member in members], settled),
    }


def settle(member_ids: list[str], paid: dict[str, int]) -> list[dict]:
    """Splits what the members paid for list items equally and returns the payments that even it out.

    Extras are not split: they were not on the list, so whoever bought them keeps the cost.
    """
    if len(member_ids) < 2:
        return []
    share, odd_cents = divmod(sum(paid[member_id] for member_id in member_ids), len(member_ids))
    # The cents that do not divide evenly go to the first members, one each, so shares sum to the total.
    balance = {
        member_id: paid[member_id] - share - (1 if index < odd_cents else 0)
        for index, member_id in enumerate(member_ids)
    }

    owes = []
    while True:
        debtor = min(member_ids, key=lambda member_id: balance[member_id])
        creditor = max(member_ids, key=lambda member_id: balance[member_id])
        amount = min(-balance[debtor], balance[creditor])
        if amount <= 0:
            return owes
        owes.append({"from": debtor, "to": creditor, "amountCents": amount})
        balance[debtor] += amount
        balance[creditor] -= amount


def assign(member_ids: list[str], items: list[dict]) -> dict[str, str]:
    """Gives each open, unclaimed item to whoever has the least to buy so far. Returns {item ID: member ID}."""
    if not member_ids:
        return {}
    load = {member_id: 0 for member_id in member_ids}
    open_items = [item for item in items if not item["checkedAt"]]
    for item in open_items:
        if item["claimedBy"] in load:
            load[item["claimedBy"]] += item["estPriceCents"] or 0

    assigned = {}
    for item in open_items:
        if item["claimedBy"] is None:
            member_id = min(member_ids, key=lambda candidate: load[candidate])
            load[member_id] += item["estPriceCents"] or 0
            assigned[item["id"]] = member_id
    return assigned


def history(lists: list[dict]) -> dict:
    """Spending across list states by type and by month, and the last price paid for each item name."""
    by_kind: dict[str, int] = {}
    by_month: dict[str, int] = {}
    last_paid: dict[str, tuple[str, int]] = {}
    rows = []
    for state in lists:
        spent = state["money"]["spentCents"] + state["money"]["extrasCents"]
        month = state["createdAt"][:7]
        by_kind[state["kind"]] = by_kind.get(state["kind"], 0) + spent
        by_month[month] = by_month.get(month, 0) + spent
        for item in state["items"]:
            name = item["name"].strip().lower()
            if item["priceCents"] and item["checkedAt"] > last_paid.get(name, ("", 0))[0]:
                last_paid[name] = (item["checkedAt"], item["priceCents"])
        rows.append(
            {
                "id": state["id"],
                "title": state["title"],
                "kind": state["kind"],
                "createdAt": state["createdAt"],
                "finishedAt": state["finishedAt"],
                "spentCents": spent,
                "itemCount": len(state["items"]),
                "doneCount": sum(1 for item in state["items"] if item["checkedAt"]),
            }
        )
    return {
        "lists": sorted(rows, key=lambda row: row["createdAt"], reverse=True),
        "byKind": by_kind,
        "byMonth": dict(sorted(by_month.items(), reverse=True)),
        "lastPaidCents": {name: price for name, (_, price) in last_paid.items()},
    }
