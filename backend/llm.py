import json
import os
from functools import cache

from ollama import Client


@cache
def client() -> Client:
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        raise RuntimeError("OLLAMA_API_KEY must be set")
    # The default is no timeout, so a hung call would hold a server thread forever.
    return Client(host="https://ollama.com", headers={"Authorization": f"Bearer {key}"}, timeout=120)


def chat(messages: list[dict], format: dict | None = None) -> str:
    """format is a JSON schema the reply must follow (Ollama structured outputs)."""
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set")
    return client().chat(model=model, messages=messages, format=format).message.content or ""


def json_reply(text: str) -> dict:
    # Ollama's cloud models don't always honour format: the JSON can come wrapped in a ```json fence,
    # or be followed by more text (even a second object), so only the first whole object is read.
    start = text.find("{")
    if start < 0:
        raise ValueError("reply has no JSON object")
    reply, _ = json.JSONDecoder().raw_decode(text, start)
    if not isinstance(reply, dict):
        raise ValueError("reply is not a JSON object")
    return reply


KINDS = ("groceries", "trip", "home", "party", "other")

STARTER_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": list(KINDS)},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "estPriceCents": {"type": "integer"},
                },
                "required": ["name", "quantity", "estPriceCents"],
            },
        },
    },
    "required": ["title", "kind", "items"],
}

STARTER_PROMPT = """You write starting checklists for HeyList, a shared checklist app.
The user describes a trip, occasion, or event. Reply with the list for it:
- Include every item the group needs for that specific situation, and only those. No generic filler.
- Shared items count once for the group, with the quantity the group needs (3 people, 2 nights: toothpaste 1, water bottles 3).
- Item names are short and plain, as a person would write them ("sunscreen", not "SPF 50 broad-spectrum sunscreen lotion").
- estPriceCents is a typical US store price in cents for ONE unit, 0 if the item is usually already owned.
- If a budget is given, keep the total of estPriceCents x quantity within it, dropping the least essential items first.
- title is a short name for the list. kind is the closest of: groceries, trip, home, party, other.
Reply with only a JSON object matching this schema:
""" + json.dumps(STARTER_SCHEMA)


def starting_list(description: str, budget_cents: int | None = None) -> dict:
    """A suggested list for the user to confirm or edit (decision 5); nothing is saved here.
    The reply is checked field by field, because the schema only shapes it."""
    request = description if budget_cents is None else f"{description}\nBudget: {budget_cents} cents"
    text = chat([{"role": "system", "content": STARTER_PROMPT}, {"role": "user", "content": request}], STARTER_SCHEMA)
    reply = json_reply(text)
    items, seen = [], set()
    for item in reply.get("items", [])[:100]:
        name = str(item.get("name", "")).strip()[:120]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        quantity, cents = item.get("quantity"), item.get("estPriceCents")
        items.append(
            {
                "name": name,
                "quantity": min(max(quantity, 1), 99) if type(quantity) is int else 1,
                # 0 means "already owned", which is no price to pay; anything odd becomes no estimate.
                "estPriceCents": cents if type(cents) is int and 0 < cents <= 10_000_000 else None,
            }
        )
    return {
        "title": str(reply.get("title", "")).strip()[:120] or description.strip()[:120],
        "kind": reply.get("kind") if reply.get("kind") in KINDS else "other",
        "items": items,
    }
