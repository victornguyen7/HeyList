"""Split math (decision 10: done in code, not by AI). Rows are database rows from the items table."""


def line_cents(item: dict) -> int:
    """The estimated cost of an item: its price times its quantity, 0 when it has no price."""
    return (item["est_price_cents"] or 0) * item["quantity"]


def assign_unclaimed(items: list[dict], member_ids: list[str]) -> dict[str, str]:
    """Gives every open, unclaimed item to a member, keeping each member's estimated cost as even as possible.
    Returns {item ID: member ID} for the items it assigned. Items someone already claimed count toward their load."""
    open_items = [item for item in items if not item["checked_at"]]
    load = {member_id: [0, 0] for member_id in member_ids}  # estimated cents, item count
    for item in open_items:
        if item["claimed_by"] in load:
            load[item["claimed_by"]][0] += line_cents(item)
            load[item["claimed_by"]][1] += 1

    assigned = {}
    # Most expensive first, each to whoever carries the least so far; the item count breaks ties, so unpriced
    # items spread out too. ponytail: greedy, not an optimal partition; fine for list-sized inputs.
    for item in sorted((i for i in open_items if i["claimed_by"] not in load), key=line_cents, reverse=True):
        member_id = min(member_ids, key=lambda m: (load[m][0], load[m][1], member_ids.index(m)))
        assigned[item["id"]] = member_id
        load[member_id][0] += line_cents(item)
        load[member_id][1] += 1
    return assigned


def split(items: list[dict], member_ids: list[str], orders: list[dict] = (), receipts: list[dict] = ()) -> dict: # pyright: ignore[reportArgumentType]
    """Who paid what for the list's items, each member's equal share, and the transfers that settle it.
    Only bought items count (price_cents is what was paid for all of them). Receipt extras are personal and not split.
    orders are the list's captured PayPal orders: a charge for an item that something else checked off first
    (a receipt, a hand tick) is still money the buyer spent, so it counts too and is listed in boughtTwice.
    receipts are the list's receipts: a confirmed one's fees (tax, tip, discounts...) count in proportion to what it
    bought for the list, and the part for its extras stays with the buyer (decision 57).
    Each member's purchases are the lines their paidCents adds up from, so every balance can be traced."""
    purchases: dict[str, list[dict]] = {member_id: [] for member_id in member_ids}
    unattributed = 0

    def credit(member_id, item_id: str | None, cents: int, twice: bool = False, fees_of: str | None = None):
        nonlocal unattributed
        if member_id in purchases:
            purchases[member_id].append({"itemId": item_id, "cents": cents, "boughtTwice": twice, "feesOf": fees_of})
        else:
            # A price but no buyer: nobody to pay back, so it stays out of the split.
            unattributed += cents

    for item in items:
        if item["price_cents"] is not None:
            credit(item["bought_by"], item["id"], item["price_cents"])

    proof = {item["id"]: item["order_id"] for item in items}
    bought_twice = []
    for order in orders:
        for item_id in order["item_ids"]:
            # The item's proof is another order, a receipt, a hand tick, or the item was deleted since.
            if proof.get(item_id) != order["id"] and order["prices"].get(item_id):
                credit(order["member_id"], item_id, order["prices"][item_id], twice=True)
                bought_twice.append({"orderId": order["id"], "itemId": item_id, "cents": order["prices"][item_id]})

    for receipt in receipts:
        fees = sum(fee["amountCents"] for fee in receipt.get("fees") or [] if fee["amountCents"] is not None)
        if not receipt["confirmed_at"] or not fees:
            continue
        on_list = sum(item["price_cents"] or 0 for item in items if item["receipt_id"] == receipt["id"])
        extras = sum(extra["priceCents"] or 0 for extra in receipt["extras"])
        # ponytail: a receipt whose prices are all unknown shares no fees; ask for them if that shows up.
        share = round(fees * on_list / (on_list + extras)) if on_list + extras else 0
        if share:
            credit(receipt["member_id"], None, share, fees_of=receipt["id"])

    paid = {member_id: sum(line["cents"] for line in lines) for member_id, lines in purchases.items()}
    total = sum(paid.values())
    # Equal shares in whole cents; the leftover cents go to the first members, so the shares add up to the total.
    base, extra = divmod(total, len(member_ids)) if member_ids else (0, 0)
    share = {member_id: base + (index < extra) for index, member_id in enumerate(member_ids)}
    balance = {member_id: paid[member_id] - share[member_id] for member_id in member_ids}
    return {
        "totalCents": total,
        "unattributedCents": unattributed,
        "boughtTwice": bought_twice,
        "members": [
            {"memberId": m, "paidCents": paid[m], "shareCents": share[m], "balanceCents": balance[m], "purchases": purchases[m]}
            for m in member_ids
        ],
        "transfers": settle(balance),
    }


def settle(balance: dict[str, int]) -> list[dict]:
    """Payments that bring every balance to zero: whoever owes most pays whoever is owed most, until all are even.
    At most one fewer payment than there are people."""
    owes = sorted(([-b, m] for m, b in balance.items() if b < 0), reverse=True)
    owed = sorted(([b, m] for m, b in balance.items() if b > 0), reverse=True)
    transfers = []
    while owes and owed:
        amount = min(owes[0][0], owed[0][0])
        transfers.append({"from": owes[0][1], "to": owed[0][1], "amountCents": amount})
        owes[0][0] -= amount # pyright: ignore[reportOperatorIssue]
        owed[0][0] -= amount # pyright: ignore[reportOperatorIssue]
        owes = sorted((pair for pair in owes if pair[0]), reverse=True)
        owed = sorted((pair for pair in owed if pair[0]), reverse=True)
    return transfers
