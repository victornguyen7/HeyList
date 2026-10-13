import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response

import db
import llm
import money
import paypal

log = logging.getLogger(__name__)
app = FastAPI()

KINDS = llm.KINDS
BAD_INPUT = (ValueError, KeyError, TypeError)
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


@app.exception_handler(llm.LlmError)
def llm_failed(request: Request, exc: llm.LlmError) -> JSONResponse:
    return error("LLM_ERROR", 502)


@app.exception_handler(Exception)
def unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Keeps the {"error": "<CODE>"} contract when something we did not plan for fails."""
    log.error("Unhandled %s on %s", type(exc).__name__, request.url.path, exc_info=exc)
    return error("SERVER_ERROR", 500)


async def raw_body(request: Request) -> bytes:
    return await request.body()


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
            "est_price_cents": cents(item.get("estPriceCents")),
            "position": start + index,
        }
        for index, item in enumerate(items)
    ]


def list_state(list_id: str) -> dict:
    """Everything a list page shows, in one response."""

    def rows(table: str, order: str = "created_at", **filters) -> list[dict]:
        return [camel(row) for row in db.select(table, order, list_id=list_id, **filters)]

    members, items, receipts = rows("members"), rows("items", "position"), rows("receipts")
    invoices = rows("invoices")
    return {
        **camel(db.select("lists", id=list_id)[0]),
        "members": members,
        "items": items,
        "receipts": receipts,
        # Only captured orders are proof; an order the buyer walked away from is not shown.
        "orders": rows("orders", status="COMPLETED"),
        "invoices": invoices,
        "money": money.summary(members, items, receipts, invoices),
    }


# Lists


@app.post("/api/lists")
def create_list(body=Depends(json_body)):
    try:
        row = {
            "title": text(body["title"]),
            "kind": body.get("kind", "other"),
            "budget_cents": cents(body.get("budgetCents")),
        }
        if row["kind"] not in KINDS:
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


@app.post("/api/lists/{list_id}/assign")
def assign_unclaimed(list_id: str):
    """Shares the open, unclaimed items out between the members."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    state = list_state(found["id"])
    assigned = money.assign([member["id"] for member in state["members"]], state["items"])
    for item_id, member_id in assigned.items():
        db.update("items", {"claimed_by": member_id}, id=item_id)
    return list_state(found["id"])


@app.post("/api/lists/{list_id}/reuse")
def reuse_list(list_id: str):
    """A fresh copy of a list: same title, type, budget and items, nothing checked."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    copy = db.insert(
        "lists", [{"title": found["title"], "kind": found["kind"], "budget_cents": found["budget_cents"]}]
    )[0]
    db.insert(
        "items",
        [
            {
                "list_id": copy["id"],
                "name": item["name"],
                "position": item["position"],
                # The price paid last time is the best estimate for next time.
                "est_price_cents": item["price_cents"] or item["est_price_cents"],
            }
            for item in db.select("items", "position", list_id=found["id"])
        ],
    )
    return list_state(copy["id"])


@app.get("/api/history")
def history(ids: str = ""):
    """Spending across the lists this browser knows (it keeps their IDs; there are no accounts)."""
    lists = [found for found in (find("lists", list_id) for list_id in ids.split(",")[:50]) if found]
    return money.history([list_state(found["id"]) for found in lists])


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
    if item["order_id"] and ("checked" in body or "estPriceCents" in body):
        return error("ITEM_PAID", 409)
    return camel(db.update("items", values, id=item["id"])[0])


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
        # The prices come from the database, never the browser (decision 23). Every item must be
        # on this list, still open, and have a price.
        if len(items) != len(item_ids) or any(item["checked_at"] or not item["est_price_cents"] for item in items):
            raise ValueError("an item cannot be bought")
        member_id = member_of(list_id, body.get("memberId"))
    except BAD_INPUT:
        return error("INVALID_ITEMS", 400)

    try:
        order_id = paypal.create_order(
            [{"name": item["name"], "priceCents": item["est_price_cents"]} for item in items]
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
                "id": order_id,
                "list_id": list_id,
                "member_id": member_id,
                "item_ids": [item["id"] for item in items],
                "total_cents": sum(item["est_price_cents"] for item in items),
            }
        ],
    )
    return {"orderId": order_id}


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

    if result["status"] == "COMPLETED":
        # The captured order is the proof: its items are checked off, priced, and tied to it.
        captured_at = now()
        db.update("orders", {"status": "COMPLETED", "captured_at": captured_at}, id=order_id)
        for item in db.select("items", id=orders[0]["item_ids"]):
            db.update(
                "items",
                {
                    "checked_at": captured_at,
                    "bought_by": orders[0]["member_id"],
                    "price_cents": item["est_price_cents"],
                    "order_id": order_id,
                },
                id=item["id"],
            )
    return result


# AI. These three only suggest; the page shows the result and the user confirms it (decision 5).


@app.post("/api/ai/list")
def suggest_list(body=Depends(json_body)):
    """A starting list from one sentence. Saved only when the user confirms, through POST /api/lists."""
    try:
        sentence = text(body["sentence"], 300)
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    return llm.starting_list(sentence)


@app.post("/api/ai/items")
def suggest_items(body=Depends(json_body)):
    """What was said or typed, split into items. Saved through POST /api/lists/{id}/items."""
    try:
        spoken = text(body["text"], 1000)
    except BAD_INPUT:
        return error("INVALID_BODY", 400)
    return {"items": llm.split_items(spoken)}


@app.post("/api/lists/{list_id}/receipts/scan")
def scan_receipt(list_id: str, request: Request, image: bytes = Depends(raw_body)):
    """Reads a receipt photo (the raw image is the body) and proposes matches and extras.

    The photo is stored; nothing is checked off until POST /api/lists/{id}/receipts confirms it.
    """
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    content_type = request.headers.get("content-type", "")
    if content_type not in IMAGE_TYPES or not image or len(image) > MAX_IMAGE_BYTES:
        return error("INVALID_IMAGE", 400)

    open_items = [item for item in db.select("items", "position", list_id=found["id"]) if not item["checked_at"]]
    reading = llm.read_receipt(image, [{"id": item["id"], "name": item["name"]} for item in open_items])
    # ponytail: a scan the user never confirms leaves its photo in the bucket; sweep them if storage matters.
    path = f"{found['id']}/{uuid.uuid4()}.{IMAGE_TYPES[content_type]}"
    db.upload(path, image, content_type)
    return {"imagePath": path, **reading}


@app.post("/api/lists/{list_id}/receipts")
def save_receipt(list_id: str, body=Depends(json_body)):
    """Saves a scan the user confirmed: the matched items are checked off with the receipt as proof."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    try:
        path = body["imagePath"]
        # The photo must be one this list's scan stored, and not already saved as a receipt.
        if not isinstance(path, str) or not re.fullmatch(
            rf"{found['id']}/[0-9a-f-]{{36}}\.(jpg|png|webp)", path
        ):
            raise ValueError("bad image path")
        if db.select("receipts", image_path=path):
            raise ValueError("already saved")
        prices = {an_id(match["itemId"]): cents(match.get("priceCents")) for match in body["matches"]}
        if len(prices) != len(body["matches"]) or len(body["extras"]) > 100:
            raise ValueError("an item is matched twice")
        items = db.select("items", list_id=found["id"], id=list(prices))
        if len(items) != len(prices) or any(item["checked_at"] for item in items):
            raise ValueError("an item cannot be checked off")
        receipt = {
            "list_id": found["id"],
            "member_id": member_of(found["id"], body.get("memberId")),
            "image_path": path,
            "total_cents": cents(body.get("totalCents")),
            "extras": [
                {"name": text(extra["name"]), "priceCents": cents(extra.get("priceCents"))}
                for extra in body["extras"]
            ],
        }
    except BAD_INPUT:
        return error("INVALID_BODY", 400)

    saved = db.insert("receipts", [receipt])[0]
    checked_at = now()
    for item_id, price in prices.items():
        db.update(
            "items",
            {
                "checked_at": checked_at,
                "bought_by": receipt["member_id"],
                "price_cents": price,
                "receipt_id": saved["id"],
            },
            id=item_id,
        )
    return list_state(found["id"])


@app.get("/api/receipts/{receipt_id}/image")
def receipt_image(receipt_id: str):
    receipt = find("receipts", receipt_id)
    if not receipt:
        return error("RECEIPT_NOT_FOUND", 404)
    extension = receipt["image_path"].rsplit(".", 1)[-1]
    media_type = next(kind for kind, known in IMAGE_TYPES.items() if known == extension)
    return Response(db.download(receipt["image_path"]), media_type=media_type)


# Settle-up with PayPal Invoicing


def paypal_failed(exc: Exception, what: str) -> JSONResponse:
    if not isinstance(exc, paypal.PayPalError):
        log.exception("%s failed", what)
    return error("PAYPAL_ERROR", 502)


@app.post("/api/lists/{list_id}/invoices")
def send_invoice(list_id: str, body=Depends(json_body)):
    """Invoices one debt from the settle-up. The browser names the two people; code works out the amount."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    state = list_state(found["id"])
    try:
        owed = next(
            owed for owed in state["money"]["owes"] if (owed["from"], owed["to"]) == (body["from"], body["to"])
        )
    except (StopIteration, *BAD_INPUT):
        return error("NOTHING_OWED", 400)
    people = {member["id"]: member for member in state["members"]}
    debtor, creditor = people[owed["from"]], people[owed["to"]]
    if not debtor["email"]:
        return error("EMAIL_NEEDED", 400)

    # One live invoice per debt. A draft left behind by a failed send is sent again, not duplicated.
    live = [
        invoice
        for invoice in state["invoices"]
        if (invoice["debtorId"], invoice["creditorId"]) == (debtor["id"], creditor["id"])
        and invoice["status"] not in ("CANCELLED", *paypal.PAID)
    ]
    if live and live[0]["status"] != "DRAFT":
        return error("ALREADY_INVOICED", 409)

    try:
        if live:
            invoice_id = live[0]["id"]
        else:
            invoice_id = paypal.create_invoice(
                debtor["email"],
                owed["amountCents"],
                f"Your share of {state['title']}",
                f"HeyList settle-up for the list {state['title']}: {debtor['name']} owes {creditor['name']}.",
            )
            db.insert(
                "invoices",
                [
                    {
                        "id": invoice_id,
                        "list_id": found["id"],
                        "debtor_id": debtor["id"],
                        "creditor_id": creditor["id"],
                        "amount_cents": owed["amountCents"],
                        "status": "DRAFT",
                    }
                ],
            )
        paypal.send_invoice(invoice_id)
        current = paypal.get_invoice(invoice_id)
    except Exception as exc:
        return paypal_failed(exc, "Send invoice")

    db.update("invoices", {"status": current["status"], "pay_url": current["payUrl"]}, id=invoice_id)
    return list_state(found["id"])


@app.post("/api/lists/{list_id}/invoices/refresh")
def refresh_invoices(list_id: str):
    """Asks PayPal for the status of every invoice that is not settled yet."""
    found = find("lists", list_id)
    if not found:
        return error("LIST_NOT_FOUND", 404)
    try:
        for invoice in db.select("invoices", list_id=found["id"]):
            if invoice["status"] not in ("CANCELLED", *paypal.PAID):
                current = paypal.get_invoice(invoice["id"])
                db.update("invoices", {"status": current["status"], "pay_url": current["payUrl"]}, id=invoice["id"])
    except Exception as exc:
        return paypal_failed(exc, "Refresh invoices")
    return list_state(found["id"])
