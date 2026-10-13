"""The one LLM, through the Ollama API. Everything here returns a suggestion for the user to confirm
(decision 5); nothing is saved. The model estimates prices; all sums and budget checks are plain code
(decision 10)."""

import json
import logging
import os
from functools import cache

from ollama import Client

log = logging.getLogger(__name__)

KINDS = ("groceries", "trip", "home", "party", "other")
MAX_CENTS = 10_000_000


class LlmError(Exception):
    pass


@cache
def _client() -> Client:
    # The client reads OLLAMA_API_KEY from the environment itself.
    if not os.environ.get("OLLAMA_API_KEY"):
        raise RuntimeError("OLLAMA_API_KEY must be set")
    return Client(host=os.environ.get("OLLAMA_HOST", "https://ollama.com"), timeout=90)


def _ask(prompt: str, schema: dict, image: bytes | None = None) -> dict:
    """One question, answered as JSON in the given schema. The tests replace this."""
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set")
    # The schema goes in the prompt as well as in `format`: hosted models can ignore `format`
    # and wrap their JSON in a code fence, so the object is cut out of the reply by hand.
    message = {
        "role": "user",
        "content": f"{prompt}\n\nReply with only a JSON object that matches this JSON schema, "
        f"using exactly these keys:\n{json.dumps(schema)}",
    }
    if image:
        message["images"] = [image]
    try:
        response = _client().chat(
            model=model, messages=[message], format=schema, think=False, options={"temperature": 0}
        )
        content = response.message.content
        answer = json.loads(content[content.index("{") : content.rindex("}") + 1])
    except Exception as exc:
        # The model's text is not logged: it can hold what the user said or what is on their receipt.
        log.error("LLM request failed: %s", type(exc).__name__)
        raise LlmError() from None
    if not isinstance(answer, dict):
        raise LlmError()
    return answer


def _cents(dollars) -> int | None:
    """Dollars from the model as integer cents, or None if it is not a sensible price."""
    if isinstance(dollars, bool) or not isinstance(dollars, (int, float)):
        return None
    cents = round(dollars * 100)
    return cents if 0 <= cents <= MAX_CENTS else None


def _items(raw) -> list[dict]:
    """The well-formed items from the model's answer; anything else is dropped."""
    items = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            items.append(
                {"name": item["name"].strip()[:120], "estPriceCents": _cents(item.get("price_usd"))}
            )
    return items[:100]


_ITEMS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "price_usd": {"type": "number"}},
        "required": ["name", "price_usd"],
    },
}


def within_budget(items: list[dict], budget_cents: int | None) -> list[dict]:
    """Drops items from the end until the estimates fit the budget. Code, not the model, does the sum."""
    if budget_cents is None:
        return items
    kept, total = [], 0
    for item in items:
        price = item["estPriceCents"] or 0
        if total + price <= budget_cents:
            kept.append(item)
            total += price
    return kept


def starting_list(sentence: str) -> dict:
    """A suggested list for one sentence, e.g. "move-in list for 3 roommates, $300 budget"."""
    answer = _ask(
        "You help people start a checklist of things to buy or pack.\n"
        f'The person said: "{sentence}"\n\n'
        "Reply with:\n"
        "- title: a short title for the list (at most 5 words)\n"
        f"- kind: one of {', '.join(KINDS)}\n"
        "- budget_usd: the budget in US dollars if the person stated one, otherwise null\n"
        "- items: 8 to 15 things for this situation, the most important first. Each has a short name "
        "and price_usd, a realistic US price estimate for the quantity needed. "
        "If a budget was stated, the prices must add up to less than it.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "kind": {"type": "string", "enum": list(KINDS)},
                "budget_usd": {"type": ["number", "null"]},
                "items": _ITEMS_SCHEMA,
            },
            "required": ["title", "kind", "budget_usd", "items"],
        },
    )
    items = _items(answer.get("items"))
    if not items:
        raise LlmError()
    title = answer.get("title")
    budget = _cents(answer.get("budget_usd"))
    return {
        "title": title.strip()[:120] if isinstance(title, str) and title.strip() else sentence[:120],
        "kind": answer.get("kind") if answer.get("kind") in KINDS else "other",
        "budgetCents": budget,
        "items": within_budget(items, budget),
    }


def split_items(spoken: str) -> list[dict]:
    """Splits what the person said or typed into separate items, each with a price estimate."""
    answer = _ask(
        "Split what this person said into separate checklist items.\n"
        f'They said: "{spoken}"\n\n'
        'Leave out filler words and any list name ("groceries: eggs, milk" is the two items eggs '
        "and milk). Do not add items they did not say. Give each a short name and price_usd, a "
        "realistic US price estimate.",
        {"type": "object", "properties": {"items": _ITEMS_SCHEMA}, "required": ["items"]},
    )
    return _items(answer.get("items"))


def read_receipt(image: bytes, items: list[dict]) -> dict:
    """Reads a receipt photo and matches its lines to the open items [{"id", "name"}, ...].

    Returns {"totalCents", "matches": [{"itemId", "line", "priceCents"}], "extras": [{"name", "priceCents"}]}.
    """
    # The model sees short numbers, not UUIDs, which it can garble.
    numbered = "\n".join(f"{number}. {item['name']}" for number, item in enumerate(items, 1))
    answer = _ask(
        "This is a photo of a shopping receipt. Read every purchased line on it.\n\n"
        "The shopping list is:\n"
        f"{numbered or '(empty)'}\n\n"
        "Reply with:\n"
        "- total_usd: the receipt total, or null if it cannot be read\n"
        "- lines: one entry per purchased line, with text (as printed), price_usd (the line price), "
        'and item (the number of the list item it is, e.g. "2% MILK 1GAL" is milk; null if it is '
        "not on the list). Leave out tax, subtotal, total, and payment lines. "
        "Use each list item at most once.",
        {
            "type": "object",
            "properties": {
                "total_usd": {"type": ["number", "null"]},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "price_usd": {"type": "number"},
                            "item": {"type": ["integer", "null"]},
                        },
                        "required": ["text", "price_usd", "item"],
                    },
                },
            },
            "required": ["total_usd", "lines"],
        },
        image,
    )

    matches, extras, used = [], [], set()
    lines = answer.get("lines")
    for line in lines if isinstance(lines, list) else []:
        if not isinstance(line, dict) or not isinstance(line.get("text"), str) or not line["text"].strip():
            continue
        text, price, number = line["text"].strip()[:120], _cents(line.get("price_usd")), line.get("item")
        on_list = isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= len(items)
        if on_list and number not in used:
            used.add(number)
            matches.append({"itemId": items[number - 1]["id"], "line": text, "priceCents": price})
        else:
            # A line that matches nothing on the list is an extra.
            extras.append({"name": text, "priceCents": price})
    return {"totalCents": _cents(answer.get("total_usd")), "matches": matches, "extras": extras}
