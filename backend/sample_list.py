ITEMS = [
    {"id": "sunscreen", "name": "Sunscreen", "priceCents": 899},
    {"id": "adapter", "name": "Travel adapter", "priceCents": 1499},
    {"id": "toothbrush", "name": "Toothbrush", "priceCents": 349},
]

_PRICES = {item["id"]: item["priceCents"] for item in ITEMS}


def total_cents(item_ids) -> int:
    if not isinstance(item_ids, list) or not item_ids:
        raise ValueError("Select at least one item")
    seen = set()
    for item_id in item_ids:
        # The str check comes first: JSON can hold a nested list, which cannot be looked up in a dict.
        if not isinstance(item_id, str) or item_id not in _PRICES:
            raise ValueError(f"unknown item: {item_id}")
        if item_id in seen:
            raise ValueError("An item was selected twice")
        seen.add(item_id)
    return sum(_PRICES[item_id] for item_id in item_ids)