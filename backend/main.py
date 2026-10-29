import logging
import os
import re
import statistics
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

import db
import llm
import market
import money
import paypal
import receipts

log = logging.getLogger(__name__)
app = FastAPI()

# The app's own address: PayPal sends the buyer back here after checkout.
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")

BAD_INPUT = (ValueError, KeyError, TypeError)


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


async def json_body(request: Request) -> dict | None:
    """The JSON object in the body, or None. Read by hand so bad input is our 400, not FastAPI's 422."""
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def camel(row: dict) -> dict:
    return {re.sub(r"_(\w)", lambda match: match[1].upper(), key): value for key, value in row.items()}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Input checks. Each returns the clean value or raises ValueError.


def text(value, limit: int = 120) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("bad text")
    return value.strip()


def cents(value) -> int | None:
    if value is None:
        return None
    # bool is an int in Python, and JSON true must not become 1 cent.
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000_000:
        raise ValueError("bad amount")
    return value


def quantity(value) -> int:
    # bool is an int in Python, and JSON true must not become 1.
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 99:
        raise ValueError("bad quantity")
    return value


def an_id(value) -> str:
    if not isinstance(value, str):
        raise ValueError("bad id")
    return str(uuid.UUID(value))


def email(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) or len(value) > 254:
        raise ValueError("bad email")
    return value


def member_out(row: dict) -> dict:
    """A member as the browser sees it: anyone with the link loads the list, so the PayPal email stays on the server
    and only whether there is one is sent."""
    return camel({key: value for key, value in row.items() if key != "email"} | {"has_email": bool(row["email"])})


def find(table: str, row_id: str) -> dict | None:
    """The row with this ID, or None when the ID is malformed or unknown."""
    try:
        rows = db.select(table, id=an_id(row_id))
    except ValueError:
        return None
    return rows[0] if rows else None


def member_of(list_id: str, member_id) -> str | None:
    """The member ID if it belongs to this list. Raises ValueError otherwise; None stays None."""
    if member_id is None:
        return None
    if not db.select("members", id=an_id(member_id), list_id=list_id):
        raise ValueError("not a member of this list")
    return member_id


def account(request: Request) -> dict | None:
    """The logged-in user from "Authorization: Bearer <Supabase access token>", or None for a guest."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return db.user(token) if scheme.lower() == "bearer" and token else None


def locked(member_id: str | None, request: Request) -> bool:
    """True if the member joined logged in and this request isn't logged in as them (decision 53).
    A guest member is never locked: anyone on the link can act for them, as before. The token is only
    checked with Supabase when the member has an account."""
    rows = db.select("members", id=member_id) if member_id else []
    if not rows or not rows[0]["user_id"]:
        return False
    user = account(request)
    return not user or user["id"] != rows[0]["user_id"]


def new_items(list_id: str, items, start: int = 0) -> list[dict]:
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("bad items")
    return [
        {
            "list_id": list_id,
            "name": text(item["name"]),
            "note": text(item["note"], 200) if item.get("note") is not None else None,
            "est_price_cents": cents(item.get("estPriceCents")),
            "quantity": quantity(item.get("quantity", 1)),
            "position": start + index,
        }
        for index, item in enumerate(items)
    ]


def lists_state(list_ids: list[str]) -> list[dict]:
    """Everything a list page shows, for each of these lists that exists: seven queries however many lists,
    run at the same time (db.py's client is safe across threads)."""

    def rows(table: str, order: str = "created_at", **filters) -> dict[str, list[dict]]:
        by_list = defaultdict(list)
        for row in db.select(table, order, list_id=list_ids, **filters):
            by_list[row["list_id"]].append(row)
        return by_list

    with ThreadPoolExecutor(7) as pool:
        found = pool.submit(db.select, "lists", id=list_ids)
        members, items, receipts = pool.submit(rows, "members"), pool.submit(rows, "items", "position"), pool.submit(rows, "receipts")
        # Captured orders are proof; pending ones hold their items until PayPal decides. An order the buyer
        # walked away from (CREATED) or that was declined is not shown.
        orders = pool.submit(rows, "orders", status=["COMPLETED", "PENDING"])
        settlements = pool.submit(rows, "settlements", status=["COMPLETED", "PENDING"])
    def state(row: dict) -> dict:
        list_id = row["id"]
        parts = {
            "members": members.result()[list_id],
            "items": items.result()[list_id],
            "receipts": receipts.result()[list_id],
            "orders": orders.result()[list_id],
            "settlements": settlements.result()[list_id],
        }
        # Sent with the list, so Money and Settle up don't wait for a second request.
        split = settled(parts["items"], parts["members"], parts["orders"], parts["receipts"], parts["settlements"])
        out = {key: [camel(r) for r in rs] for key, rs in parts.items()} | {"members": [member_out(m) for m in parts["members"]]}
        return {**camel(row), **out, "split": split}

    return [state(row) for row in found.result()]


def settled(items: list[dict], members: list[dict], orders: list[dict], receipts: list[dict] = (), settlements: list[dict] = ()) -> dict: # pyright: ignore[reportArgumentType]
    """What each member paid, their equal share, and who pays whom, from the list's rows. A settle-up payment counts
    once PayPal has captured it."""
    paid = [
        # A refunded charge was given back, so it is not money the buyer spent.
        order | {"prices": {k: v for k, v in order["prices"].items() if order["refunds"].get(k, {}).get("status", "FAILED") in REFUND_FAILED}}
        for order in orders
        if order["status"] == "COMPLETED"
    ]
    done = [payment for payment in settlements if payment["status"] == "COMPLETED"]
    return money.split(items, [member["id"] for member in members], paid, receipts, done)


def list_state(list_id: str) -> dict:
    return lists_state([list_id])[0]


# Paid calls: Ollama and Textract are billed to the owner (RULES.md). Accounts are optional, so anyone with a
# link could repeat them; these caps bound what one list or one client can spend.
# ponytail: in-memory, per process, reset on restart; move to the database if the app runs on several processes.
_calls: dict[str, deque] = defaultdict(deque)


def allow(key: str, limit: int, seconds: int) -> bool:
    """True if fewer than limit calls were made under key in the last seconds, and counts this one."""
    calls, cutoff = _calls[key], time.monotonic() - seconds
    while calls and calls[0] < cutoff:
        calls.popleft()
    if len(calls) >= limit:
        return False
    calls.append(time.monotonic())
    return True


# Lists


@app.post("/api/lists")
def create_list(body=Depends(json_body)):
    try:
        row = {
            "title": text(body["title"]),
            "kind": body.get("kind", "other"),
            "budget_cents": cents(body.get("budgetCents")),
        }
        if row["kind"] not in llm.KINDS:
            raise ValueError("bad kind")
        # Checked before the list is inserted, so bad items leave nothing behind.
        new_items("", body.get("items", []))
    except BAD_INPUT:
        return error("INVALID_BODY", 400)

    list_id = db.insert("lists", [row])[0]["id"]
    db.insert("items", new_items(list_id, body.get("items", [])))
    return list_state(list_id)


# "See how it works with a sample trip" (phase 8B): a real list a person alone can try every step on. Ann and Ben
# have already bought something, so Settle up has payments to show; "You" is the person trying it.
SAMPLE_ITEMS = [
    # name, estimate per unit (cents), quantity, claimed by, paid in total (cents) if already bought
    ("Tent", 9000, 1, "Ann", 9000),
    ("Snacks for the road", 2400, 1, "Ben", 2400),
    ("Sleeping bags", 2500, 3, "You", None),
    ("Water, 24-pack", 600, 2, "You", None),
    ("Firewood", 1200, 1, None, None),
    ("Headlamp", 1500, 1, None, None),
]


@app.post("/api/lists/sample")
def create_sample():
    """A sample camping trip with three people (decision 64). Made from the template above: no AI and no PayPal call.
    Returns the list and the member ID of "You", which the browser remembers as its own."""
    # Anyone can make one, so one cap for everyone, as for suggestions.
    if not allow("sample", 60, 3600):
        return error("TOO_MANY_REQUESTS", 429)
    list_id = db.insert("lists", [{"title": "Weekend camping trip (sample)", "kind": "trip", "budget_cents": 25000}])[0]["id"]
    members = {row["name"]: row["id"] for row in db.insert("members", [{"list_id": list_id, "name": name} for name in ("Ann", "Ben", "You")])}
    bought_at = now()
    db.insert(
        "items",
        [
            {
                "list_id": list_id,
                "name": name,
                "est_price_cents": cents_each,
                "quantity": count,
                "position": position,
                "claimed_by": members.get(claimed),
                # Marked bought by hand, as people do when they bought it before the list existed.
                **({"checked_at": bought_at, "bought_by": members[claimed], "price_cents": paid} if paid else {}),
            }
            for position, (name, cents_each, count, claimed, paid) in enumerate(SAMPLE_ITEMS)
        ],
    )
    return {"list": list_state(list_id), "memberId": members["You"]}


@app.get("/api/lists")
def get_lists(ids: str = ""):
    """?ids=a,b,c: the lists this browser has opened, for Home and History, in one request. Unknown or deleted
    lists are left out; malformed IDs are ignored."""
    list_ids = []
    for value in ids.split(",")[:50]:
        try:
            list_ids.append(an_id(value))
        except ValueError:
            pass
    return {"lists": lists_state(list_ids)}


@app.get("/api/lists/{list_id}")
def get_list(list_id: str):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    return list_state(list_id)


@app.patch("/api/lists/{list_id}")
def update_list(list_id: str, body=Depends(json_body)):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        values = {}
        if "title" in body:
            values["title"] = text(body["title"])
        if "budgetCents" in body:
            values["budget_cents"] = cents(body["budgetCents"])
        if "finished" in body:
            values["finished_at"] = now() if body["finished"] is True else None
        if not values:
            raise ValueError("nothing to change")
    except BAD_INPUT:
        return error("INVALID_BODY", 400)

    db.update("lists", values, id=list_id)
    return list_state(list_id)


@app.post("/api/lists/{list_id}/members")
def join_list(list_id: str, request: Request, body=Depends(json_body)):
    """Adds a person by name, or returns the one already there. An email given here is saved when they have none yet:
    it is where settle-up payments to them go, so someone else on the link can't change it (decision 60).
    Logged in, the name can be left out (the account's is used) and the same member comes back on every device.
    A name taken by an account can't be joined by a guest or another account."""
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    user = account(request)
    if user and (mine := db.select("members", list_id=list_id, user_id=user["id"])):
        return member_out(mine[0])
    body = body or {}
    try:
        name = text(body.get("name") or (user and user["name"]), 40)
        values = {"email": email(body["email"])} if body.get("email") else {}
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    if user:
        values["user_id"] = user["id"]

    existing = db.select("members", list_id=list_id, name=name)
    if not existing:
        return member_out(db.insert("members", [{"list_id": list_id, "name": name, **values}])[0])
    if existing[0]["user_id"]:
        return error("NAME_TAKEN", 409)
    if existing[0]["email"]:
        values.pop("email", None)
    if values:
        return member_out(db.update("members", values, id=existing[0]["id"])[0])
    return member_out(existing[0])


# Items


@app.post("/api/lists/{list_id}/items")
def add_items(list_id: str, body=Depends(json_body)):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        rows = new_items(list_id, body["items"], start=len(db.select("items", list_id=list_id)))
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    return [camel(row) for row in db.insert("items", rows)]


@app.patch("/api/items/{item_id}")
def update_item(item_id: str, request: Request, body=Depends(json_body)):
    item = find("items", item_id)
    if not item:
        return error("ITEM_NOT_FOUND", 404)
    try:
        values = {}
        if "name" in body:
            values["name"] = text(body["name"])
        if "estPriceCents" in body:
            values["est_price_cents"] = cents(body["estPriceCents"])
        # A store product describes this name at this price; change either and it no longer does.
        if "name" in body or "estPriceCents" in body:
            values["product"] = None
        if "quantity" in body:
            values["quantity"] = quantity(body["quantity"])
        if "claimedBy" in body:
            values["claimed_by"] = member_of(item["list_id"], body["claimedBy"])
        if body.get("checked") is True:
            values |= {
                "checked_at": now(),
                "bought_by": member_of(item["list_id"], body.get("memberId")),
                # What the person says they paid, when they check off without a receipt.
                "price_cents": cents(body.get("priceCents")),
            }
        elif body.get("checked") is False:
            values |= {"checked_at": None, "bought_by": None, "price_cents": None, "receipt_id": None, "price_typed": False}
        if not values:
            raise ValueError("nothing to change")
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    if "checked" in body and locked(values.get("bought_by") or item["bought_by"], request):
        return error("NOT_YOURS", 403)

    # A captured PayPal order is proof of purchase; it cannot be unticked or re-priced.
    paid_fields = "checked" in body or "estPriceCents" in body or "quantity" in body
    if item["order_id"] and paid_fields:
        return error("ITEM_PAID", 409)
    # The same rules again in the UPDATE itself, so a capture or receipt landing since the read above isn't
    # overwritten: checking off needs the item still open, and the paid fields need it still unpaid.
    checking = body.get("checked") is True
    filters = ({"order_id": None} if paid_fields else {}) | ({"checked_at": None} if checking else {})
    saved = db.update("items", values, id=item["id"], **filters)
    if not saved:
        return error("ITEM_CHECKED" if checking else "ITEM_PAID" if filters else "ITEM_NOT_FOUND", 409 if filters else 404)
    return camel(saved[0])


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str):
    item = find("items", item_id)
    if not item:
        return error("ITEM_NOT_FOUND", 404)
    if item["order_id"]:
        return error("ITEM_PAID", 409)
    db.delete("items", id=item["id"])
    return Response(status_code=204)


# Store products (Channel3, decision 50)


@app.get("/api/items/{item_id}/products")
def find_products(item_id: str):
    """Real products for this item, to choose from. Nothing is saved."""
    item = find("items", item_id)
    if not item:
        return error("ITEM_NOT_FOUND", 404)
    # One cap for everyone, as for suggestions: anyone can make a list, so a per-list cap is easy to get round.
    if not allow("market", 100, 3600):
        return error("TOO_MANY_REQUESTS", 429)
    try:
        found = market.search(item["name"])
        title = db.select("lists", id=item["list_id"])[0]["title"]
        return {"products": llm.store_matches(item["name"], item["note"], title, found)[:5]}
    except Exception:
        log.exception("Product search failed")
        return error("MARKET_UNAVAILABLE", 502)


@app.post("/api/items/{item_id}/product")
def choose_product(item_id: str, body=Depends(json_body)):
    """{"productId"}: the item gets that product, at the price Channel3 gives now, as the price PayPal charges."""
    item = find("items", item_id)
    if not item:
        return error("ITEM_NOT_FOUND", 404)
    product_id = body.get("productId")
    if not isinstance(product_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", product_id):
        return error("INVALID_BODY", 400)
    if item["checked_at"]:
        return error("ITEM_CHECKED", 409)
    if any(item["id"] in order["item_ids"] for order in db.select("orders", list_id=item["list_id"], status="PENDING")):
        return error("PAYMENT_PENDING", 409)
    try:
        product = market.get(product_id)
    except Exception:
        log.exception("Product lookup failed")
        return error("MARKET_UNAVAILABLE", 502)
    if not product:
        return error("PRODUCT_NOT_FOUND", 404)
    values = {"product": product | {"fetchedAt": now()}, "est_price_cents": product["priceCents"]}
    # checked_at=None: an item checked off while Channel3 answered keeps the price it was bought at.
    saved = db.update("items", values, id=item["id"], checked_at=None)
    if not saved:
        return error("ITEM_CHECKED", 409)
    return camel(saved[0])


# PayPal Checkout


@app.post("/api/lists/{list_id}/orders")
def create_order(list_id: str, request: Request, body=Depends(json_body)):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        item_ids = body["itemIds"]
        if not isinstance(item_ids, list) or not item_ids or len(set(item_ids)) != len(item_ids):
            raise ValueError("select at least one item, each once")
        items = db.select("items", "position", list_id=list_id, id=[an_id(item_id) for item_id in item_ids])
        # The prices come from the database, never the browser (decision 21). Every item must be
        # on this list, still open, and have a price.
        if len(items) != len(item_ids) or any(item["checked_at"] or not item["est_price_cents"] for item in items):
            raise ValueError("an item cannot be bought")
        member_id = member_of(list_id, body.get("memberId"))
        venmo = by_venmo(body)
    except BAD_INPUT:
        return error("INVALID_ITEMS", 400)
    if locked(member_id, request):
        return error("NOT_YOURS", 403)
    # An item whose payment is pending at PayPal may still go through, so it can't be paid for a second time yet.
    if any(set(order["item_ids"]) & {item["id"] for item in items} for order in db.select("orders", list_id=list_id, status="PENDING")):
        return error("PAYMENT_PENDING", 409)
    if store_prices_changed(items):
        return error("PRICE_CHANGED", 409)
    return open_order(list_id, items, member_id, venmo)


def by_venmo(body: dict) -> bool:
    """{"method": "venmo"} from the JS SDK v6 Venmo button (decision 67); anything else pays with PayPal."""
    method = body.get("method", "paypal")
    if method not in ("paypal", "venmo"):
        raise ValueError("bad method")
    return method == "venmo"


def open_order(list_id: str, items: list[dict], member_id: str | None, venmo: bool = False):
    """Creates the PayPal order for these items at their saved prices and stores it, so the capture knows what it
    paid for. The caller checked the items can be bought."""
    try:
        order = paypal.create_order(
            [{"name": item["name"], "priceCents": item["est_price_cents"], "quantity": item["quantity"]} for item in items],
            # Back to this list's page, which captures the order.
            f"{APP_URL}/lists/{list_id}",
            venmo=venmo,
        )
    except Exception as exc:
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Create order failed")
        return error("PAYPAL_ERROR", 502)

    # Stored now so the capture knows which items this order paid for.
    db.insert(
        "orders",
        [
            {
                "id": order["orderId"],
                "list_id": list_id,
                "member_id": member_id,
                "item_ids": [item["id"] for item in items],
                "prices": {item["id"]: item["est_price_cents"] * item["quantity"] for item in items},
                "total_cents": sum(item["est_price_cents"] * item["quantity"] for item in items),
            }
        ],
    )
    return order


def store_prices_changed(items: list[dict]) -> bool:
    """Reads each chosen store product again before checkout, so PayPal charges the store's price of today, not of
    when it was chosen (issue 42). A new price, or a product the store no longer sells, is saved on the item and True
    comes back, so the buyer sees the new total before paying. Read in the last 10 minutes, or Channel3 out of reach
    or over its cap: the saved price is charged, since nothing is bought from the store."""
    changed = False
    for item in items:
        product = item["product"]
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(product["fetchedAt"])
        except (KeyError, TypeError, ValueError):  # no product, or one saved without a time
            age = None
        if not product or (age and age.total_seconds() < 600) or not allow("market", 100, 3600):
            continue
        try:
            fresh = market.get(product["productId"])
        except Exception:
            log.exception("Store price check failed; charging the saved price")
            continue
        # Gone from the store: the last price seen stays, as an estimate without a store label.
        values = {"product": fresh | {"fetchedAt": now()}, "est_price_cents": fresh["priceCents"]} if fresh else {"product": None}
        db.update("items", values, id=item["id"], checked_at=None, order_id=None)
        changed |= not fresh or fresh["priceCents"] != item["est_price_cents"]
    return changed


@app.post("/api/orders/{order_id}/capture")
def capture_order(order_id: str):
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)
    orders, settlement = paid_order(order_id)
    if not orders and not settlement:
        return error("ORDER_NOT_FOUND", 404)

    try:
        result = paypal.capture_order(order_id)
    except Exception as exc:
        if isinstance(exc, paypal.PayPalError) and exc.issue == "INSTRUMENT_DECLINED":
            return error("INSTRUMENT_DECLINED", 422)
        if isinstance(exc, paypal.PayPalError) and payee_refused(exc):
            return error("PAYEE_NOT_ACCEPTED", 422)
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Capture order failed")
        return error("PAYPAL_ERROR", 502)
    return record_capture(orders[0], result) if orders else record_settlement(settlement, result)


def paid_order(order_id: str) -> tuple[list[dict], dict | None]:
    """The list order with this PayPal order ID, or else the settle-up payment with it."""
    orders = db.select("orders", id=order_id)
    return orders, None if orders else next(iter(db.select("settlements", id=order_id)), None)


@app.post("/api/orders/{order_id}/refresh")
def refresh_order(order_id: str):
    """Asks PayPal again about an order whose capture came back PENDING, and checks its items off if it has
    since COMPLETED."""
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)
    orders, settlement = paid_order(order_id)
    if not orders and not settlement:
        return error("ORDER_NOT_FOUND", 404)
    if (orders[0] if orders else settlement)["status"] != "PENDING":
        return error("ORDER_NOT_PENDING", 409)
    try:
        result = paypal.get_order(order_id)
    except Exception as exc:
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Get order failed")
        return error("PAYPAL_ERROR", 502)
    return record_capture(orders[0], result) if orders else record_settlement(settlement, result)


def record_capture(order: dict, result: dict) -> dict:
    """Stores the capture's status on the order. PENDING keeps the order on the list page with its items held;
    COMPLETED checks them off. Returns the status and how much was refunded for items already bought."""
    order_id, status = order["id"], result["status"]
    if status != "COMPLETED":
        db.update("orders", {"status": status, "capture_id": result["captureId"]}, id=order_id)
        return {"orderId": order_id, "status": status, "refundedCents": 0}
    # The captured order is the proof: its items are checked off, priced, and tied to it.
    captured_at, refunds = now(), dict(order["refunds"])
    db.update("orders", {"status": "COMPLETED", "captured_at": captured_at, "capture_id": result["captureId"]}, id=order_id)
    for item in db.select("items", id=order["item_ids"]):
        # Already checked off by this order (a repeated capture), or already refunded by an earlier one.
        if (item["checked_at"] and item["order_id"] == order_id) or item["id"] in refunds:
            continue
        # checked_at=None makes the check and the write one step, so a receipt confirmed at the same moment
        # can't be overwritten.
        if not db.update(
            "items",
            {
                "checked_at": captured_at,
                "bought_by": order["member_id"],
                # What PayPal charged, not today's price; orders from before prices were stored fall back.
                "price_cents": order["prices"].get(item["id"], item["est_price_cents"] * item["quantity"]),
                "order_id": order_id,
            },
            id=item["id"],
            checked_at=None,
        ):
            # Checked off first by a receipt or a hand tick while the buyer was on PayPal. An item has one proof
            # (items_one_proof), so that stays. A checked-off item has all its units bought, so every unit this
            # order paid for is beyond what the list needs, and the charge is refunded to the buyer (decision 39).
            # ponytail: whole-item refunds; refund only the extra units once buying part of a quantity is possible.
            cents = order["prices"].get(item["id"], 0)
            if not cents:
                continue
            try:
                refunds[item["id"]] = paypal.refund(result["captureId"], cents, f"{order_id}-{item['id']}") | {"cents": cents}
            except Exception:
                # Not refunded: the charge stays counted toward the buyer, so the split is still right.
                log.exception("Refund for order %s item %s failed", order_id, item["id"])
    if refunds != order["refunds"]:
        # Merged with what is saved now: a capture running at the same moment may have recorded a refund this one
        # couldn't (issue 45).
        refunds = db.select("orders", id=order_id)[0]["refunds"] | refunds
        db.update("orders", {"refunds": refunds}, id=order_id)
    return {"orderId": order_id, "status": status, "refundedCents": sum(r["cents"] for r in refunds.values() if r["status"] not in REFUND_FAILED)}


# A refund in any other state (COMPLETED, PENDING) is money on its way back to the buyer.
REFUND_FAILED = ("FAILED", "CANCELLED")


# Shopping agent

SHOP_THREADS = 10  # items searched at the same time; any number can be ticked
NOT_SOLD = "No online store we search sells this. Buy it in person and scan the receipt."


@app.post("/api/lists/{list_id}/shop")
def shop_list(list_id: str, body=Depends(json_body)):
    """The shopping agent (decision 61), {itemIds}: finds a real product for each item the person ticked, checks the
    matches, and proposes a cart that fits what is left of the budget. It never pays and saves nothing: the person
    edits the cart, then pays for it with PayPal (POST .../shop/checkout). Each item searched costs one Channel3
    search and one Ollama call; the hourly search cap (100) bounds what a run can spend."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    items = db.select("items", "position", list_id=list_id)
    held = {item_id for order in db.select("orders", list_id=list_id, status="PENDING") for item_id in order["item_ids"]}
    try:
        item_ids = body["itemIds"]
        if not isinstance(item_ids, list) or not item_ids or len(set(item_ids)) != len(item_ids):
            raise ValueError("tick at least one item, each once")
        run_ids = {an_id(item_id) for item_id in item_ids}
        run = [item for item in items if item["id"] in run_ids]
        # Every item on this list, not bought, and not held by a payment pending at PayPal.
        if len(run) != len(run_ids) or any(item["checked_at"] or item["id"] in held for item in run):
            raise ValueError("an item cannot be shopped")
    except BAD_INPUT:
        return error("INVALID_ITEMS", 400)
    # The budget left for this run: the budget, less what was spent and what the rest of the list is expected to cost.
    budget = None
    if found["budget_cents"] is not None:
        spent = sum(item["price_cents"] or 0 for item in items if item["checked_at"])
        rest = sum(money.line_cents(item) for item in items if not item["checked_at"] and item["id"] not in run_ids)
        budget = max(found["budget_cents"] - spent - rest, 0)

    # The cap is counted here, one search per item, before the searches run at the same time.
    allowed = [item for item in run if allow("market", 100, 3600)]

    def options(item: dict) -> list[dict] | None:
        try:
            return llm.store_matches(item["name"], item["note"], found["title"], market.search(item["name"]))[:5]
        except Exception:
            log.exception("Shopping search failed for %s", item["id"])
            return None

    with ThreadPoolExecutor(SHOP_THREADS) as pool:
        results = dict(zip((item["id"] for item in allowed), pool.map(options, allowed)))

    lines, skipped = [], []
    for item in run:
        result = results.get(item["id"], "limit")
        if result == "limit":
            skipped.append({"itemId": item["id"], "reason": "Store searches are used up for this hour. Try again later."})
        elif result is None:
            skipped.append({"itemId": item["id"], "reason": "The store search didn't answer for this one. Try Find in stores on Items."})
        elif not result:
            skipped.append({"itemId": item["id"], "reason": NOT_SOLD})
        else:
            lines.append({"itemId": item["id"], "quantity": item["quantity"], "options": result})
    cart, over = money.fit_cart(lines, budget)
    skipped += [{"itemId": item_id, "reason": "Left out to stay within the budget."} for item_id in over]
    return {
        "cart": cart,
        "skipped": skipped,
        "totalCents": sum(line["product"]["priceCents"] * line["quantity"] for line in cart),
        "budgetLeftCents": budget,
    }


@app.post("/api/lists/{list_id}/shop/checkout")
def shop_checkout(list_id: str, request: Request, body=Depends(json_body)):
    """{memberId, picks: [{itemId, productId}], totalCents}: the cart the person approved. Each product is read again
    from Channel3 and saved on its item at today's price (decision 50), then one PayPal order is opened for all of them.
    If the fresh total isn't the one the person saw, the new prices are saved but no order is made (409 PRICE_CHANGED),
    so they see the new total first. Nothing is ordered from the stores."""
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        picks = body["picks"]
        if not isinstance(picks, list) or not picks:
            raise ValueError("bad picks")
        chosen = {an_id(pick["itemId"]): pick["productId"] for pick in picks}
        if len(chosen) != len(picks) or not all(isinstance(p, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", p) for p in chosen.values()):
            raise ValueError("each item once, with a product")
        seen_total = cents(body["totalCents"])
        member_id = member_of(list_id, body.get("memberId"))
        venmo = by_venmo(body)
        items = db.select("items", "position", list_id=list_id, id=list(chosen))
        if len(items) != len(chosen) or any(item["checked_at"] for item in items):
            raise ValueError("an item cannot be bought")
    except BAD_INPUT:
        return error("INVALID_ITEMS", 400)
    if locked(member_id, request):
        return error("NOT_YOURS", 403)
    if any(set(order["item_ids"]) & set(chosen) for order in db.select("orders", list_id=list_id, status="PENDING")):
        return error("PAYMENT_PENDING", 409)
    if not all(allow("market", 100, 3600) for _ in chosen):
        return error("TOO_MANY_REQUESTS", 429)

    try:
        with ThreadPoolExecutor(SHOP_THREADS) as pool:
            fresh = dict(zip(chosen, pool.map(market.get, chosen.values())))
    except Exception:
        log.exception("Product lookup failed")
        return error("MARKET_UNAVAILABLE", 502)
    if not all(fresh.values()):
        return error("PRODUCT_NOT_FOUND", 404)

    saved = []
    for item in items:
        product = fresh[item["id"]]
        values = {"product": product | {"fetchedAt": now()}, "est_price_cents": product["priceCents"]}
        # checked_at=None: an item checked off meanwhile keeps the price it was bought at.
        rows = db.update("items", values, id=item["id"], checked_at=None)
        if not rows:
            return error("ITEM_CHECKED", 409)
        saved.append(rows[0])
    if sum(item["est_price_cents"] * item["quantity"] for item in saved) != seen_total:
        return error("PRICE_CHANGED", 409)
    return open_order(list_id, saved, member_id, venmo)


# PayPal webhooks

# Events that settle a capture which came back PENDING (decision 66). Anything else is acknowledged and ignored.
CAPTURE_EVENTS = {"PAYMENT.CAPTURE.COMPLETED": "COMPLETED", "PAYMENT.CAPTURE.DENIED": "DENIED", "PAYMENT.CAPTURE.DECLINED": "DECLINED"}


@app.post("/api/paypal/webhook")
def paypal_webhook(request: Request, event=Depends(json_body)):
    """PayPal tells HeyList when a pending capture completes or is denied, so nobody has to press Check again
    (decision 66). Every event is verified with PayPal before it's read, and handled once."""
    if not isinstance(event, dict) or not isinstance(event.get("id"), str):
        return error("INVALID_BODY", 400)
    try:
        genuine = paypal.verify_webhook(dict(request.headers), event)
    except Exception:
        log.exception("Webhook verification failed")
        return error("WEBHOOK_UNVERIFIED", 503)
    if not genuine:
        return error("WEBHOOK_UNVERIFIED", 401)

    status = CAPTURE_EVENTS.get(event.get("event_type"))
    resource = event.get("resource") or {}
    order_id = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
    if not status or not isinstance(order_id, str):
        return {"handled": False}
    # Once per event: PayPal retries until it gets a 2xx, and may deliver the same event twice.
    if db.select("webhook_events", id=event["id"]):
        return {"handled": False}
    db.insert("webhook_events", [{"id": event["id"], "type": event["event_type"]}])

    orders, settlement = paid_order(order_id)
    row = orders[0] if orders else settlement
    # Only a capture we haven't settled yet: a completed one stays completed whatever arrives late.
    if not row or row["status"] not in ("CREATED", "PENDING"):
        return {"handled": False}
    result = {"orderId": order_id, "status": status, "captureId": resource.get("id")}
    record_capture(row, result) if orders else record_settlement(row, result)
    return {"handled": True}


# Settle up


def payee_refused(exc: paypal.PayPalError) -> bool:
    """PayPal won't send money to that account: unknown email, restricted, can't receive, or the payer's own."""
    return bool(exc.issue) and (exc.issue.startswith("PAYEE_") or exc.issue == "PAYER_CANNOT_PAY_SELF")


@app.post("/api/lists/{list_id}/settlements")
def settle_up(list_id: str, request: Request, body=Depends(json_body)):
    """Starts one Settle up payment with PayPal: {fromId, toId, amountCents, email?}. The order's payee is the PayPal
    email of the person owed, so the money goes straight to them, not to HeyList (decision 60). The amount must be
    the current split's (decision 21): a stale one is refused so the payer sees the new amount first."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    try:
        debtor, creditor = member_of(list_id, body["fromId"]), member_of(list_id, body["toId"])
        amount = cents(body["amountCents"])
        new_email = email(body["email"]) if body.get("email") else None
        venmo = by_venmo(body)
        if not debtor or not creditor or not amount:
            raise ValueError("a payment needs both people and an amount")
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    if locked(debtor, request):
        return error("NOT_YOURS", 403)
    transfers = list_state(list_id)["split"]["transfers"]
    if {"from": debtor, "to": creditor, "amountCents": amount} not in transfers:
        return error("SPLIT_CHANGED", 409)
    # A payment still pending at PayPal may yet go through and change every balance.
    if db.select("settlements", list_id=list_id, debtor_id=debtor, status="PENDING"):
        return error("PAYMENT_PENDING", 409)

    member = db.select("members", id=creditor)[0]
    payee = member["email"]
    # The first payment to someone asks for their PayPal email. After that, only they can change it (logged in), so
    # nobody else on the link can send the money to themselves.
    if new_email and new_email != payee:
        if payee and (not member["user_id"] or locked(creditor, request)):
            return error("NOT_YOURS", 403)
        payee = new_email
    if not payee:
        return error("EMAIL_NEEDED", 409)

    try:
        order = paypal.create_order(
            [{"name": f"HeyList: settle up for {found['title']}", "priceCents": amount, "quantity": 1}],
            # Back to Settle up, where the list layout captures it.
            f"{APP_URL}/lists/{list_id}/settle",
            payee_email=payee,
            venmo=venmo,
        )
    except Exception as exc:
        if isinstance(exc, paypal.PayPalError) and payee_refused(exc):
            return error("PAYEE_NOT_ACCEPTED", 422)
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Create settlement failed")
        return error("PAYPAL_ERROR", 502)

    # Saved only once PayPal took the order, so a mistyped email isn't kept.
    if payee != member["email"]:
        db.update("members", {"email": payee}, id=creditor)
    db.insert(
        "settlements",
        [{"id": order["orderId"], "list_id": list_id, "debtor_id": debtor, "creditor_id": creditor, "amount_cents": amount}],
    )
    return order


@app.post("/api/lists/{list_id}/reminders")
def remind(list_id: str, body=Depends(json_body)):
    """{fromId, toId}: a friendly message asking fromId to pay toId, for one open Settle up payment, with a link that
    opens Settle up ready to pay with PayPal (decision 65). The amount and names come from the current split. The AI
    writes it (one Ollama call); if that fails, a plain template does. HeyList never sends it: the person does."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    try:
        debtor, creditor = member_of(list_id, body["fromId"]), member_of(list_id, body["toId"])
        if not debtor or not creditor:
            raise ValueError("a reminder needs both people")
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    transfer = next((t for t in list_state(list_id)["split"]["transfers"] if t["from"] == debtor and t["to"] == creditor), None)
    if not transfer:
        return error("SPLIT_CHANGED", 409)

    names = {m["id"]: m["name"] for m in db.select("members", list_id=list_id)}
    amount = f"${transfer['amountCents'] // 100}.{transfer['amountCents'] % 100:02d}"
    text, written = None, False
    # A paid call, and anyone with the link can press it: one cap for everyone, as for suggestions.
    if allow("reminder", 30, 3600):
        try:
            text, written = llm.reminder(names[debtor], names[creditor], amount, found["title"]), True
        except Exception:
            log.exception("Reminder failed; using the template")
    text = text or (
        f"Hi {names[debtor]}! Quick heads-up: your part of {found['title']} comes to {amount}, to {names[creditor]}. "
        f"You can pay {names[creditor]} with PayPal here whenever suits you."
    )
    link = f"{APP_URL}/lists/{list_id}/settle?pay={debtor}"
    return {"message": f"{text}\n{link}", "link": link, "amountCents": transfer["amountCents"], "aiWritten": written}


def record_settlement(settlement: dict, result: dict) -> dict:
    """Stores a settle-up payment's capture status. A COMPLETED one counts in the split from then on; a repeated
    capture changes nothing."""
    if settlement["status"] != "COMPLETED":
        values = {"status": result["status"], "capture_id": result["captureId"]}
        db.update("settlements", values | ({"captured_at": now()} if result["status"] == "COMPLETED" else {}), id=settlement["id"])
    return {"orderId": settlement["id"], "status": result["status"], "refundedCents": 0, "settlement": True}


# AI starting lists


def remember_prices(items: list[dict]) -> list[dict]:
    """Price memory (decision 49): each item's price from what people really paid for the same name on any list,
    else from the store product last chosen for it, else the AI's estimate. Adds priceSource: paid, store or
    estimate (None when there is no price at all). Only names and prices are read, never who bought what.
    ponytail: exact names only ("water bottle" is not "water bottles"); add plural or fuzzy matching if too few match."""
    keys = {item["name"].strip().lower() for item in items}
    paid, store = defaultdict(list), {}
    for row in db.select("items", "created_at", name_key=list(keys)):
        # Proven only: a PayPal capture or a price read from a confirmed receipt. Prices typed in, with a hand tick
        # or for a receipt line that couldn't be read, are self-reported.
        if row["checked_at"] and row["price_cents"] and (row["order_id"] or (row["receipt_id"] and not row.get("price_typed"))):
            paid[row["name_key"]].append(round(row["price_cents"] / row["quantity"]))
        if row["product"]:
            store[row["name_key"]] = row["product"]["priceCents"]
    for item in items:
        key = item["name"].strip().lower()
        if paid[key]:
            item["estPriceCents"], item["priceSource"] = round(statistics.median(paid[key][-10:])), "paid"
        elif key in store:
            item["estPriceCents"], item["priceSource"] = store[key], "store"
        else:
            item["priceSource"] = "estimate" if item["estPriceCents"] else None
    return items


@app.post("/api/lists/suggest")
def suggest_list(body=Depends(json_body)):
    """A starting list from one sentence. Nothing is saved: the person edits it, then creates it with POST /api/lists."""
    # One cap for everyone: behind the Next.js proxy and Render's load balancer, request.client is the proxy,
    # not the person, and X-Forwarded-For can be forged to get round a per-client cap.
    if not allow("suggest", 20, 3600):
        return error("TOO_MANY_REQUESTS", 429)
    try:
        description = text(body["description"], 500)
        budget = cents(body.get("budgetCents"))
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    try:
        suggestion = llm.starting_list(description, budget)
    except Exception:
        log.exception("Starting list failed")
        return error("AI_UNAVAILABLE", 502)
    try:
        remember_prices(suggestion["items"])
    except Exception:
        # Price memory is an extra; the AI's estimates still make a usable list (e.g. before the schema is run).
        log.exception("Price memory failed")
    return suggestion


# Splitting


@app.post("/api/lists/{list_id}/assign")
def assign_items(list_id: str):
    """Gives every open, unclaimed item to a member, evening out the estimated cost."""
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    members = [member["id"] for member in db.select("members", list_id=list_id)]
    if not members:
        return error("NO_MEMBERS", 409)
    for item_id, member_id in money.assign_unclaimed(db.select("items", list_id=list_id), members).items():
        db.update("items", {"claimed_by": member_id}, id=item_id)
    return list_state(list_id)


@app.get("/api/lists/{list_id}/split")
def split_list(list_id: str):
    """What each member paid, their equal share, and who pays whom to settle up."""
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    return list_state(list_id)["split"]


# Receipts

# Textract takes JPEG and PNG (also PDF and TIFF, not offered here). The app shrinks photos well below this.
RECEIPT_TYPES = {"image/jpeg": "jpg", "image/png": "png"}
MAX_RECEIPT_BYTES = 5_000_000


@app.post("/api/lists/{list_id}/receipts")
async def scan_receipt(list_id: str, request: Request):
    """The body is the photo itself. Reads it, proposes a list item for each line, and stores the receipt
    unconfirmed: nothing is checked off until POST /api/receipts/{id}/confirm (decision 5)."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in RECEIPT_TYPES:
        return error("UNSUPPORTED_IMAGE", 415)
    image = await request.body()
    if not image or len(image) > MAX_RECEIPT_BYTES:
        return error("IMAGE_TOO_LARGE" if image else "INVALID_BODY", 413 if image else 400)
    # Textract, Ollama and Supabase are blocking calls; keep them off the event loop.
    return await run_in_threadpool(_scan, list_id, request.query_params.get("memberId"), image, content_type, request)


def _scan(list_id: str, member_id, image: bytes, content_type: str, request: Request):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        member_id = member_of(list_id, member_id)
    except BAD_INPUT:
        return error("INVALID_MEMBER", 400)
    if locked(member_id, request):
        return error("NOT_YOURS", 403)
    # Checked after the list and member, so made-up IDs can't use up a real list's scans.
    if not allow(f"scan:{list_id}", 10, 3600):
        return error("TOO_MANY_REQUESTS", 429)

    try:
        read = receipts.read_receipt(image)
        if not read["lines"]:
            return error("NO_LINES_FOUND", 422)
        open_items = [item for item in db.select("items", "position", list_id=list_id) if not item["checked_at"]]
        proposed = receipts.match_lines(read["lines"], open_items)
    except receipts.ReceiptError as exc:
        # The cause (missing keys, an Ollama outage) is for the server log, not the person.
        log.warning("Receipt scan failed: %s (%r)", exc, exc.__cause__)
        return error(str(exc), 422 if str(exc) in ("UNREADABLE_IMAGE", "RECEIPT_TOO_LONG") else 502)
    except Exception:
        log.exception("Receipt scan failed")
        return error("SCANNING_UNAVAILABLE", 502)

    path = f"{list_id}/{uuid.uuid4()}.{RECEIPT_TYPES[content_type]}"
    db.upload(path, image, content_type)
    row = {
        "list_id": list_id,
        "member_id": member_id,
        "image_path": path,
        "total_cents": read["totalCents"],
        "lines": [line | {"itemId": item_id} for line, item_id in zip(read["lines"], proposed)],
        "fees": read["fees"],
    }
    return camel(db.insert("receipts", [row])[0])


def typed_amounts(values, rows: list[dict], key: str) -> list[int | None]:
    """The amounts the person typed for rows the photo left blank: one entry per row, None where nothing was typed.
    A row the photo gave an amount for keeps it, whatever is sent (decision 21)."""
    if values is None:
        return [None] * len(rows)
    if not isinstance(values, list) or len(values) != len(rows):
        raise ValueError("one amount or null per row")
    return [cents(value) if row[key] is None else None for value, row in zip(values, rows)]


@app.post("/api/receipts/{receipt_id}/confirm")
def confirm_receipt(receipt_id: str, request: Request, body=Depends(json_body)):
    """Applies the matches the person confirmed or corrected: {"itemIds": [item ID or null, one per line]}, and
    optionally what they typed where the photo gave no amount: "prices" (one per line) and "feeAmounts" (one per
    fee), each in cents or null; a discount is typed as a positive amount. Matched items are checked off with
    the receipt's prices; the rest of the lines become extras. Typed prices are marked typed (decision 57)."""
    receipt = find("receipts", receipt_id)
    if not receipt:
        return error("RECEIPT_NOT_FOUND", 404)
    if receipt["confirmed_at"]:
        return error("RECEIPT_CONFIRMED", 409)
    if locked(receipt["member_id"], request):
        return error("NOT_YOURS", 403)
    lines, fees = receipt["lines"], receipt.get("fees") or []
    try:
        item_ids = body["itemIds"]
        if not isinstance(item_ids, list) or len(item_ids) != len(lines):
            raise ValueError("one item ID or null per line")
        prices = typed_amounts(body.get("prices"), lines, "priceCents")
        fee_amounts = typed_amounts(body.get("feeAmounts"), fees, "amountCents")
        chosen = {an_id(item_id) for item_id in item_ids if item_id is not None}
        items = {item["id"]: item for item in db.select("items", list_id=receipt["list_id"], id=list(chosen))}
        # Every chosen item must be on this list and still open.
        if len(items) != len(chosen) or any(item["checked_at"] for item in items.values()):
            raise ValueError("an item cannot be checked off")
    except BAD_INPUT:
        return error("INVALID_MATCHES", 400)

    # Claimed first, in one step, so two confirms at the same moment can't both check items off.
    checked_at = now()
    if not db.update("receipts", {"confirmed_at": checked_at}, id=receipt["id"], confirmed_at=None):
        return error("RECEIPT_CONFIRMED", 409)

    # Prices come from the stored lines, never the browser (decision 21), except one the photo didn't give.
    lines = [line | {"priceCents": price, "typed": True} if price is not None else line for line, price in zip(lines, prices)]
    fees = [
        fee | {"amountCents": -amount if fee["kind"] == "discount" else amount, "typed": True} if amount else fee
        for fee, amount in zip(fees, fee_amounts)
    ]
    # Several lines can be one item.
    by_item: dict[str, list[dict]] = {item_id: [] for item_id in items}
    unmatched = []
    for line, item_id in zip(lines, item_ids):
        if item_id is None:
            unmatched.append(line)
        else:
            by_item[str(uuid.UUID(item_id))].append(line)

    for item_id, item_lines in by_item.items():
        item_prices = [line["priceCents"] for line in item_lines]
        values = {
            "checked_at": checked_at,
            "bought_by": receipt["member_id"],
            # Unknown when a line's price is still blank: part of a price would understate what was paid.
            "price_cents": None if None in item_prices else sum(item_prices),
            "price_typed": any(line.get("typed") for line in item_lines),
            "receipt_id": receipt["id"],
        }
        # checked_at=None: an item checked off since the check above (a PayPal capture, another receipt) keeps
        # that proof, and its lines count as extras on this receipt.
        if not db.update("items", values, id=item_id, checked_at=None):
            unmatched += item_lines
    extras = [{"name": line["text"], "priceCents": line["priceCents"]} for line in unmatched]
    db.update("receipts", {"lines": lines, "fees": fees, "extras": extras}, id=receipt["id"])
    return list_state(receipt["list_id"])


@app.get("/api/receipts/{receipt_id}/image")
def receipt_image(receipt_id: str):
    """The photo, served by the backend because the bucket is private."""
    receipt = find("receipts", receipt_id)
    if not receipt:
        return error("RECEIPT_NOT_FOUND", 404)
    media_type = "image/png" if receipt["image_path"].endswith(".png") else "image/jpeg"
    return Response(db.download(receipt["image_path"]), media_type=media_type)
