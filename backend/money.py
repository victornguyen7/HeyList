"""Split math (decision 10: done in code, not by AI). Rows are database rows from the items table."""


# Sales tax rates are in basis points: 825 is 8.25% (decision 80). No US sales tax is near 25%.
MAX_TAX_BP = 2500


def tax_of(cents: int, rate_bp: int) -> int:
    """The tax on cents at rate_bp, to the nearest cent (half up), in whole cents (decision 22)."""
    return (cents * rate_bp + 5000) // 10000


def receipt_tax_rate(receipts: list[dict]) -> int | None:
    """The sales tax the list's confirmed receipts really charged, as a share of what they bought: all their tax over
    all their subtotals (lines less discounts), in basis points. It is the rate where the list is shopped, and it
    already counts what is taxed less or not at all (food in many states). A receipt counts only when its tax and
    every line price are known. None when none counts.
    ponytail: a receipt with no tax line doesn't count, so an all-food receipt can't pull the rate to 0%; it may
    read high for a list of only untaxed food."""
    tax = base = 0
    for receipt in receipts:
        fees = receipt.get("fees") or []
        taxes = [fee["amountCents"] for fee in fees if fee["kind"] == "tax"]
        prices = [line["priceCents"] for line in receipt["lines"]]
        if not receipt["confirmed_at"] or not taxes or None in taxes or not prices or None in prices:
            continue
        subtotal = sum(prices) + sum(fee["amountCents"] or 0 for fee in fees if fee["kind"] == "discount")
        if subtotal > 0:
            tax, base = tax + sum(taxes), base + subtotal
    return min((tax * 20000 + base) // (2 * base), MAX_TAX_BP) if base else None


def tax_rate(set_bp: int | None, receipts: list[dict]) -> dict:
    """The list's sales tax rate, used for PayPal orders and every estimate (decision 80): the one its receipts show,
    else the one someone typed on Money, else none. source says which: "receipts", "set" or None."""
    learned = receipt_tax_rate(receipts)
    if learned is not None:
        return {"rateBp": learned, "source": "receipts"}
    return {"rateBp": set_bp, "source": "set"} if set_bp is not None else {"rateBp": 0, "source": None}


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


def split(items: list[dict], member_ids: list[str], orders: list[dict] = (), receipts: list[dict] = (), settlements: list[dict] = ()) -> dict: # pyright: ignore[reportArgumentType]
    """Who paid what for the list's items, each member's equal share, and the transfers that settle it.
    Only bought items count (price_cents is what was paid for all of them). Receipt extras are personal and not split.
    orders are the list's captured PayPal orders: a charge for an item that something else checked off first
    (a receipt, a hand tick) is still money the buyer spent, so it counts too and is listed in boughtTwice.
    receipts are the list's receipts: a confirmed one's fees (tax, tip, discounts...) count in proportion to what it
    bought for the list, and the part for its extras stays with the buyer (decision 57). Its tax and its other fees
    are separate lines (fee "tax" or "other"), so Money can show how the total adds up.
    An order's taxes ({item ID: cents}) are the sales tax PayPal charged on its items (decision 80), one line per order.
    An order's refunded_cents is money given back to its buyer in PayPal's dashboard (issue 46), so it is taken
    off what they paid.
    settlements are completed settle-up payments (decision 60): money one member sent another, which moves their
    balances toward even; settledCents is what a member sent minus what they received.
    Each member's purchases are the lines their paidCents adds up from, so every balance can be traced."""
    purchases: dict[str, list[dict]] = {member_id: [] for member_id in member_ids}
    unattributed = 0

    def credit(member_id, item_id: str | None, cents: int, twice: bool = False, fees_of: str | None = None, refund_of: str | None = None, fee: str | None = None):
        nonlocal unattributed
        if member_id in purchases:
            # feesOf is the receipt or order that charged a fee; fee says whether it is tax or another fee.
            line = {"itemId": item_id, "cents": cents, "boughtTwice": twice, "feesOf": fees_of, "refundOf": refund_of, "fee": fee}
            purchases[member_id].append(line)
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
        if tax := sum((order.get("taxes") or {}).values()):
            credit(order["member_id"], None, tax, fees_of=order["id"], fee="tax")
        if order.get("refunded_cents"):
            credit(order["member_id"], None, -order["refunded_cents"], refund_of=order["id"])

    for receipt in receipts:
        if not receipt["confirmed_at"]:
            continue
        known = [fee for fee in receipt.get("fees") or [] if fee["amountCents"] is not None]
        on_list = sum(item["price_cents"] or 0 for item in items if item["receipt_id"] == receipt["id"])
        extras = sum(extra["priceCents"] or 0 for extra in receipt["extras"])
        for kind in ("tax", "other"):
            fees = sum(fee["amountCents"] for fee in known if (fee["kind"] == "tax") == (kind == "tax"))
            # ponytail: a receipt whose prices are all unknown shares no fees; ask for them if that shows up.
            share = round(fees * on_list / (on_list + extras)) if on_list + extras else 0
            if share:
                credit(receipt["member_id"], None, share, fees_of=receipt["id"], fee=kind)

    paid = {member_id: sum(line["cents"] for line in lines) for member_id, lines in purchases.items()}
    total = sum(paid.values())
    # How the total adds up, as on a receipt: items + tax + other fees (tip, delivery, less discounts) - refunds.
    lines = [line for member_lines in purchases.values() for line in member_lines]
    adds_up = {
        "itemsCents": sum(line["cents"] for line in lines if not line["fee"] and not line["refundOf"]),
        "taxCents": sum(line["cents"] for line in lines if line["fee"] == "tax"),
        "feesCents": sum(line["cents"] for line in lines if line["fee"] == "other"),
        "refundedCents": -sum(line["cents"] for line in lines if line["refundOf"]),
    }
    # Equal shares in whole cents; the leftover cents go to the first members, so the shares add up to the total.
    base, extra = divmod(total, len(member_ids)) if member_ids else (0, 0)
    share = {member_id: base + (index < extra) for index, member_id in enumerate(member_ids)}
    settled = dict.fromkeys(member_ids, 0)
    for payment in settlements:
        # Someone who left the list since stays out, as for purchases.
        if payment["debtor_id"] in settled and payment["creditor_id"] in settled:
            settled[payment["debtor_id"]] += payment["amount_cents"]
            settled[payment["creditor_id"]] -= payment["amount_cents"]
    balance = {member_id: paid[member_id] - share[member_id] + settled[member_id] for member_id in member_ids}
    return {
        "totalCents": total,
        **adds_up,
        "unattributedCents": unattributed,
        "boughtTwice": bought_twice,
        "members": [
            {
                "memberId": m,
                "paidCents": paid[m],
                "shareCents": share[m],
                "settledCents": settled[m],
                "balanceCents": balance[m],
                "purchases": purchases[m],
            }
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


def fit_cart(lines: list[dict], budget: int | None) -> tuple[list[dict], list[str]]:
    """The shopping agent's cart (decision 61). lines are [{"itemId", "quantity", "options": [product, ...]}]: each
    item's checked store matches, closest first. Each item gets its closest match. Over budget, items move to their
    cheapest match, biggest saving first; still over, the most expensive are left out until it fits, so as few items
    as possible are dropped. Returns the cart (each line with its "product") and the IDs of the items left out.
    ponytail: greedy; an item moved to its cheapest match stays there even when a later drop frees room."""
    cost = lambda line, product: product["priceCents"] * line["quantity"]
    pick = {line["itemId"]: line["options"][0] for line in lines}
    total = lambda: sum(cost(line, pick[line["itemId"]]) for line in lines if line["itemId"] in pick)
    if budget is not None:
        cheapest = {line["itemId"]: min(line["options"], key=lambda p: p["priceCents"]) for line in lines}
        for line in sorted(lines, key=lambda l: cost(l, pick[l["itemId"]]) - cost(l, cheapest[l["itemId"]]), reverse=True):
            if total() <= budget:
                break
            pick[line["itemId"]] = cheapest[line["itemId"]]
        for line in sorted(lines, key=lambda l: cost(l, pick[l["itemId"]]), reverse=True):
            if total() <= budget:
                break
            del pick[line["itemId"]]
    cart = [line | {"product": pick[line["itemId"]]} for line in lines if line["itemId"] in pick]
    return cart, [line["itemId"] for line in lines if line["itemId"] not in pick]
