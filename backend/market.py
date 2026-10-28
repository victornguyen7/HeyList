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


def product(raw: dict) -> dict | None:
    """What HeyList keeps of a Channel3 product: its cheapest in-stock offer in US dollars (PayPal Checkout charges
    USD). None when it has no such offer. Channel3 prices are amounts in dollars, like 12.99."""
    offers = []
    for offer in raw.get("offers") or []:
        price = offer.get("price") or {}
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


def search(name: str) -> list[dict]:
    """Up to 10 products for an item name, in Channel3's order. Search matches words, not meaning (a "milk" face
    cleanser for milk), so the route has them checked by llm.store_matches before showing any."""
    response = client().post("/v1/search", json={"query": name, "limit": 10})
    response.raise_for_status()
    found = (product(raw) for raw in response.json().get("products") or [])
    return [p for p in found if p]


def get(product_id: str) -> dict | None:
    """The product as Channel3 has it now, so a price is never taken from the browser (decision 21)."""
    response = client().get(f"/v1/products/{product_id}", params={"country": "US", "currency": "USD"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return product(response.json())
