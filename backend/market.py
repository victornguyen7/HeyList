"""Real products from stores, through Channel3 (decision 50): https://channel3.ai/docs. Only item names go out."""

import os
from decimal import Decimal
from functools import cache

import httpx


@cache
def client() -> httpx.Client:
    key = os.environ.get("CHANNEL3_API_KEY")
    if not key:
        raise RuntimeError("CHANNEL3_API_KEY must be set")
    return httpx.Client(base_url="https://api.trychannel3.com", headers={"x-api-key": key}, timeout=20)


def web(url) -> str | None:
    # Shown as a link and an image, so nothing but http(s): a javascript: URL must never reach the page.
    return url if isinstance(url, str) and url.startswith(("https://", "http://")) else None


# Where everything that isn't food is priced (decision 75): what most people would pay at Walmart or Target today.
# Food comes from Kroger (kroger.py), since Channel3 carries no real groceries.
BIG_STORES = ("walmart.com", "target.com")


def domain(offer: dict) -> str:
    return str(offer.get("domain") or "").lower().removeprefix("www.")


def product(raw: dict, stores: tuple[str, ...] | None = None) -> dict | None:
    """What HeyList keeps of a Channel3 product: its cheapest in-stock offer in US dollars (PayPal Checkout charges
    USD), from one of stores when given. None when it has no such offer. Channel3 prices are amounts in dollars,
    like 12.99."""
    offers = []
    for offer in raw.get("offers") or []:
        price = offer.get("price") or {}
        if stores and domain(offer) not in stores:
            continue
        if offer.get("availability") == "InStock" and price.get("currency") == "USD" and web(offer.get("url")):
            cents = int(Decimal(str(price.get("price", 0))) * 100)
            if 0 < cents <= 10_000_000:
                offers.append((cents, offer))
    if not offers or not raw.get("id") or not raw.get("title"):
        return None
    cents, offer = min(offers, key=lambda pair: pair[0])
    images = raw.get("images") or [{}]
    image = next((i for i in images if i.get("is_main_image")), images[0])
    category = raw.get("category") or {}
    return {
        "productId": str(raw["id"]),
        "title": str(raw["title"])[:200],
        "store": str(offer.get("domain") or "")[:100],
        "url": offer["url"],
        "imageUrl": web(image.get("url")),
        "priceCents": cents,
        # "Health & Beauty > Skin Care > Facial Cleansers": what tells a "milk" cleanser from milk (llm.store_matches).
        "category": " > ".join(str(c.get("title", "")) for c in category.get("path") or [category] if c.get("title"))[:300],
    }


def search(name: str, stores: tuple[str, ...] | None = None) -> list[dict]:
    """Up to 10 products for an item name, in Channel3's order, only from stores when given (priced from those
    stores' offers). Search matches words, not meaning (a "milk" face cleanser for milk), so callers have them
    checked by the AI (llm.store_matches, llm.market_matches) before using any."""
    body = {"query": name, "limit": 10} | ({"filters": {"website_ids": list(stores)}} if stores else {})
    response = client().post("/v1/search", json=body)
    response.raise_for_status()
    found = (product(raw, stores) for raw in response.json().get("products") or [])
    return [p for p in found if p]


def get(product_id: str) -> dict | None:
    """The product as Channel3 has it now, so a price is never taken from the browser (decision 21)."""
    response = client().get(f"/v1/products/{product_id}", params={"country": "US", "currency": "USD"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return product(response.json())
