import json
import os
import re
from functools import cache
from pathlib import Path

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
                    "note": {"type": "string"},
                },
                "required": ["name", "quantity", "estPriceCents"],
            },
        },
    },
    "required": ["title", "kind", "items"],
}

STARTER_PROMPT = """You write starting checklists for HeyList, a shared checklist app.
The user either describes a trip, occasion, or event, or lists the things they need (often typed fast or spoken,
so it can be messy). Reply with the list:
- If the user lists things, the list is exactly those things: one item each, nothing added. If they describe a
  situation, include every item the group needs for it, and only those. No generic filler.
- Keep every quantity the user states ("two packs of water" is water, quantity 2). Otherwise shared items count once
  for the group, with the quantity the group needs (3 people, 2 nights: toothpaste 1, water bottles 3).
- note keeps what the name and quantity can't, in a few of the user's words; leave it out when there is nothing:
  a condition ("only if nobody has one", for "maybe a flashlight if nobody has one already"), or an amount you
  can't know ("how many? enough snacks for 4 people") - then set the quantity to your best guess. Never drop a
  condition: a conditional item is still on the list, with its note.
- Item names are short and plain, as a person would write them ("sunscreen", not "SPF 50 broad-spectrum sunscreen lotion").
- estPriceCents is a typical US store price in cents for ONE unit, 0 if the item is usually already owned.
- If a budget is given, keep the total of estPriceCents x quantity within it, dropping the least essential items first.
- title is a short name for the list. kind is the closest of: groceries, trip, home, party, other.
Reply with only a JSON object matching this schema:
""" + json.dumps(STARTER_SCHEMA)


# Hand-written requests and the lists we'd want back (decision 48). Off: in the first measured run the 3 closest
# lowered item recall (96/98 without, 91/98 with) at 2.3 times the input tokens. Kept as data; eval_starter.py
# --examples measures them again. Ones marked evalOverlap are near-copies of eval cases, which the eval leaves out.
EXAMPLES = json.loads((Path(__file__).parent / "examples.json").read_text())
EXAMPLE_COUNT = 0
# Words that say nothing about what to buy.
SMALL_WORDS = set(
    "a an and the for of to my our we i at on in with is are if or up some get need so like um uh ok oh yeah this"
    " that it be have has from about just all prepare ready everything thing make plan go do want next".split()
)


def words(text: str) -> set[str]:
    return {word.rstrip("s") for word in re.findall(r"[a-z]+", text.lower())} - SMALL_WORDS


def closest_examples(description: str) -> list[dict]:
    """The EXAMPLE_COUNT examples whose requests share the most words with this one; ties keep the file's order.
    ponytail: word overlap, which picked off-topic examples in the eval; use embeddings before turning this on."""
    asked = words(description)
    return sorted(EXAMPLES, key=lambda example: -len(asked & words(example["request"])))[:EXAMPLE_COUNT]


def starting_list(description: str, budget_cents: int | None = None) -> dict:
    """A suggested list for the user to confirm or edit (decision 5); nothing is saved here.
    The reply is checked field by field, because the schema only shapes it."""
    request = description if budget_cents is None else f"{description}\nBudget: {budget_cents} cents"
    shown = []
    for example in closest_examples(description):
        shown += [{"role": "user", "content": example["request"]}, {"role": "assistant", "content": json.dumps(example["reply"])}]
    messages = [{"role": "system", "content": STARTER_PROMPT}, *shown, {"role": "user", "content": request}]
    text = chat(messages, STARTER_SCHEMA)
    reply = json_reply(text)
    items: list[dict] = []
    for item in reply.get("items", [])[:100]:
        name = " ".join(str(item.get("name", "")).split())[:120]
        if not name:
            continue
        quantity, cents, note = item.get("quantity"), item.get("estPriceCents"), item.get("note")
        quantity = min(max(quantity, 1), 99) if type(quantity) is int else 1
        same = [kept for kept in items if kept["name"].lower() == name.lower()]
        # The same item twice with the same quantity is a repeat. With a different quantity it isn't clear which
        # is meant, so both stay, flagged, rather than being added up or one dropped.
        if any(kept["quantity"] == quantity for kept in same):
            continue
        if same:
            note = "listed twice with different amounts; check how many"
            for kept in same:
                kept["note"] = note
        items.append(
            {
                "name": name,
                "quantity": quantity,
                # 0 means "already owned", which is no price to pay; anything odd becomes no estimate.
                "estPriceCents": cents if type(cents) is int and 0 < cents <= 10_000_000 else None,
                "note": (" ".join(note.split())[:200] or None) if isinstance(note, str) else None,
            }
        )
    return {
        "title": str(reply.get("title", "")).strip()[:120] or description.strip()[:120],
        "kind": reply.get("kind") if reply.get("kind") in KINDS else "other",
        "items": items,
    }


STORE_MATCH_SCHEMA = {
    "type": "object",
    "properties": {"matches": {"type": "array", "items": {"type": "integer"}}},
    "required": ["matches"],
}

STORE_MATCH_PROMPT = """You check store search results for HeyList, a shared shopping list app.
Someone needs to buy one item for a list. The store search matches words, not meaning, so many results only
share a word with the item: a "milk" face cleanser or a milk bottle for milk, toy or decorative eggs for eggs.
Reply with the numbers of the results that are the item itself, something a person buying it for this list would
accept. Leave out containers, accessories, toys, decor, clothing with the word on it, and anything else only named
after the item. A special kind (toddler milk, a pet version) fits only if the item, note or list asks for it.
Use each result's category to tell.
Reply with JSON only, like {"matches": [2, 5]}, or {"matches": []} if none fit."""


def store_matches(name: str, note: str | None, list_title: str, products: list[dict]) -> list[dict]:
    """The products that really are the item, in the order given (decision 51). Raises when the model fails, so
    word-only matches are never shown as if they were checked."""
    if not products:
        return []
    lines = "\n".join(f"{n}. {p['title']} ({p.get('category') or 'no category'})" for n, p in enumerate(products, 1))
    request = f"Item: {name}\n" + (f"Note: {note}\n" if note else "") + f"List: {list_title}\nResults:\n{lines}"
    reply = json_reply(chat([{"role": "system", "content": STORE_MATCH_PROMPT}, {"role": "user", "content": request}], STORE_MATCH_SCHEMA))
    chosen = {n for n in reply.get("matches", []) if type(n) is int}
    return [p for n, p in enumerate(products, 1) if n in chosen]


REMINDER_SCHEMA = {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}

REMINDER_PROMPT = """You write a short reminder for HeyList, a shared shopping list app, that one friend sends another.
Write two or three warm, light sentences, the way a friend would text ("hey, just a heads-up..."). Say the list,
the exact amount as given, and who to pay. Say they can pay with PayPal from the link that follows. Never sound like
a debt collector, never add a deadline or guilt, and don't write the link itself. At most one emoji.
Reply as JSON: {"message": "..."}"""


def reminder(debtor: str, creditor: str, amount: str, list_title: str) -> str:
    """A friendly reminder to pay (decision 65). Raises when the reply isn't usable, so the route falls back to its
    template: the text must name the exact amount and stay short enough for a chat message."""
    request = f"To: {debtor}\nPay: {creditor}\nAmount: {amount}\nList: {list_title}"
    text = json_reply(chat([{"role": "system", "content": REMINDER_PROMPT}, {"role": "user", "content": request}], REMINDER_SCHEMA))["message"]
    if not isinstance(text, str) or not 20 <= len(text.strip()) <= 400 or amount not in text or "http" in text:
        raise ValueError("unusable reminder")
    return text.strip()

