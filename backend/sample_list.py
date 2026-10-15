ITEMS = [
    {"id": "sunscreen", "name": "Sunscreen", "priceCents": 899},
    {"id": "adapter", "name": "Travel adapter", "priceCents": 1499},
    {"id": "toothbrush", "name": "Toothbrush", "priceCents": 349},
]

_PRICES = {item["id"]: item["priceCents"] for item in ITEMS}
MAX_QUANTITY = 99


def total_cents(selection) -> int:
    """selection maps item ID to quantity, e.g. {"sunscreen": 2}."""
    if not isinstance(selection, dict) or not selection:
        raise ValueError("Select at least one item")
    for item_id, quantity in selection.items():
        if item_id not in _PRICES:
            raise ValueError(f"unknown item: {item_id}")
        # bool is a subclass of int, so True would otherwise pass as 1.
        if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
            raise ValueError(f"quantity must be 1 to {MAX_QUANTITY}: {item_id}")
    return sum(_PRICES[item_id] * quantity for item_id, quantity in selection.items())
