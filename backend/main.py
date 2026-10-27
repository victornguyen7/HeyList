import logging
import os
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

import db
import llm
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


def list_state(list_id: str) -> dict:
    """Everything a list page shows, in one response."""

    def rows(table: str, order: str = "created_at", **filters) -> list[dict]:
        return [camel(row) for row in db.select(table, order, list_id=list_id, **filters)]

    return {
        **camel(db.select("lists", id=list_id)[0]),
        "members": rows("members"),
        "items": rows("items", "position"),
        "receipts": rows("receipts"),
        # Captured orders are proof; pending ones hold their items until PayPal decides. An order the buyer
        # walked away from (CREATED) or that was declined is not shown.
        "orders": rows("orders", status=["COMPLETED", "PENDING"]),
        "invoices": rows("invoices"),
    }


# Paid calls: Ollama and Textract are billed to the owner (RULES.md). There are no accounts, so anyone with a
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
def join_list(list_id: str, body=Depends(json_body)):
    """Adds a person by name, or returns the one already there. An email given here is saved either way."""
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        name = text(body["name"], 40)
        values = {"email": email(body["email"])} if body.get("email") else {}
    except BAD_INPUT:
        return error("INVALID_BODY", 400)

    existing = db.select("members", list_id=list_id, name=name)
    if not existing:
        return camel(db.insert("members", [{"list_id": list_id, "name": name, **values}])[0])
    if values:
        return camel(db.update("members", values, id=existing[0]["id"])[0])
    return camel(existing[0])


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
def update_item(item_id: str, body=Depends(json_body)):
    item = find("items", item_id)
    if not item:
        return error("ITEM_NOT_FOUND", 404)
    try:
        values = {}
        if "name" in body:
            values["name"] = text(body["name"])
        if "estPriceCents" in body:
            values["est_price_cents"] = cents(body["estPriceCents"])
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
            values |= {"checked_at": None, "bought_by": None, "price_cents": None, "receipt_id": None}
        if not values:
            raise ValueError("nothing to change")
    except BAD_INPUT:
        return error("INVALID_BODY", 400)

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


# PayPal Checkout


@app.post("/api/lists/{list_id}/orders")
def create_order(list_id: str, body=Depends(json_body)):
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
    except BAD_INPUT:
        return error("INVALID_ITEMS", 400)
    # An item whose payment is pending at PayPal may still go through, so it can't be paid for a second time yet.
    if any(set(order["item_ids"]) & {item["id"] for item in items} for order in db.select("orders", list_id=list_id, status="PENDING")):
        return error("PAYMENT_PENDING", 409)

    try:
        order = paypal.create_order(
            [{"name": item["name"], "priceCents": item["est_price_cents"], "quantity": item["quantity"]} for item in items],
            # Back to this list's page, which captures the order.
            f"{APP_URL}/lists/{list_id}",
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


@app.post("/api/orders/{order_id}/capture")
def capture_order(order_id: str):
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)
    orders = db.select("orders", id=order_id)
    if not orders:
        return error("ORDER_NOT_FOUND", 404)

    try:
        result = paypal.capture_order(order_id)
    except Exception as exc:
        if isinstance(exc, paypal.PayPalError) and exc.issue == "INSTRUMENT_DECLINED":
            return error("INSTRUMENT_DECLINED", 422)
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Capture order failed")
        return error("PAYPAL_ERROR", 502)
    return record_capture(orders[0], result)


@app.post("/api/orders/{order_id}/refresh")
def refresh_order(order_id: str):
    """Asks PayPal again about an order whose capture came back PENDING, and checks its items off if it has
    since COMPLETED."""
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)
    orders = db.select("orders", id=order_id)
    if not orders:
        return error("ORDER_NOT_FOUND", 404)
    if orders[0]["status"] != "PENDING":
        return error("ORDER_NOT_PENDING", 409)
    try:
        result = paypal.get_order(order_id)
    except Exception as exc:
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Get order failed")
        return error("PAYPAL_ERROR", 502)
    return record_capture(orders[0], result)


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
        db.update("orders", {"refunds": refunds}, id=order_id)
    return {"orderId": order_id, "status": status, "refundedCents": sum(r["cents"] for r in refunds.values() if r["status"] not in REFUND_FAILED)}


# A refund in any other state (COMPLETED, PENDING) is money on its way back to the buyer.
REFUND_FAILED = ("FAILED", "CANCELLED")


# AI starting lists


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
        return llm.starting_list(description, budget)
    except Exception:
        log.exception("Starting list failed")
        return error("AI_UNAVAILABLE", 502)


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
    members = [member["id"] for member in db.select("members", list_id=list_id)]
    orders = db.select("orders", list_id=list_id, status="COMPLETED")
    for order in orders:
        # A refunded charge was given back, so it is not money the buyer spent.
        order["prices"] = {k: v for k, v in order["prices"].items() if order["refunds"].get(k, {}).get("status", "FAILED") in REFUND_FAILED}
    return money.split(db.select("items", list_id=list_id), members, orders)


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
    return await run_in_threadpool(_scan, list_id, request.query_params.get("memberId"), image, content_type)


def _scan(list_id: str, member_id, image: bytes, content_type: str):
    if not find("lists", list_id):
        return error("LIST_NOT_FOUND", 404)
    try:
        member_id = member_of(list_id, member_id)
    except BAD_INPUT:
        return error("INVALID_MEMBER", 400)
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
    }
    return camel(db.insert("receipts", [row])[0])


@app.post("/api/receipts/{receipt_id}/confirm")
def confirm_receipt(receipt_id: str, body=Depends(json_body)):
    """Applies the matches the person confirmed or corrected: {"itemIds": [item ID or null, one per line]}.
    Matched items are checked off with the receipt's prices; the rest of the lines become extras."""
    receipt = find("receipts", receipt_id)
    if not receipt:
        return error("RECEIPT_NOT_FOUND", 404)
    if receipt["confirmed_at"]:
        return error("RECEIPT_CONFIRMED", 409)
    lines = receipt["lines"]
    try:
        item_ids = body["itemIds"]
        if not isinstance(item_ids, list) or len(item_ids) != len(lines):
            raise ValueError("one item ID or null per line")
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

    # Prices come from the stored lines, never the browser (decision 21). Several lines can be one item.
    by_item: dict[str, list[dict]] = {item_id: [] for item_id in items}
    unmatched = []
    for line, item_id in zip(lines, item_ids):
        if item_id is None:
            unmatched.append(line)
        else:
            by_item[str(uuid.UUID(item_id))].append(line)

    for item_id, item_lines in by_item.items():
        values = {
            "checked_at": checked_at,
            "bought_by": receipt["member_id"],
            "price_cents": sum(line["priceCents"] for line in item_lines),
            "receipt_id": receipt["id"],
        }
        # checked_at=None: an item checked off since the check above (a PayPal capture, another receipt) keeps
        # that proof, and its lines count as extras on this receipt.
        if not db.update("items", values, id=item_id, checked_at=None):
            unmatched += item_lines
    extras = [{"name": line["text"], "priceCents": line["priceCents"]} for line in unmatched]
    db.update("receipts", {"extras": extras}, id=receipt["id"])
    return list_state(receipt["list_id"])


@app.get("/api/receipts/{receipt_id}/image")
def receipt_image(receipt_id: str):
    """The photo, served by the backend because the bucket is private."""
    receipt = find("receipts", receipt_id)
    if not receipt:
        return error("RECEIPT_NOT_FOUND", 404)
    media_type = "image/png" if receipt["image_path"].endswith(".png") else "image/jpeg"
    return Response(db.download(receipt["image_path"]), media_type=media_type)
