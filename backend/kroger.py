"""Grocery prices from Kroger's public Products API (decision 74): https://developer.kroger.com. Channel3's catalog
has store goods but no real food, so groceries are priced here. Only item names and the store's ZIP code go out.

Set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET (a free developer account), and KROGER_LOCATION_ID or KROGER_ZIP for
the store whose prices are used: Kroger only returns prices for a given store. Without them, enabled() is False and
nothing here is called."""

import os
import threading
import time
from decimal import Decimal
from functools import cache

import httpx

API = "https://api.kroger.com/v1"
STORE = "kroger.com"

_token: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return bool(os.environ.get("KROGER_CLIENT_ID") and os.environ.get("KROGER_CLIENT_SECRET") and (os.environ.get("KROGER_LOCATION_ID") or os.environ.get("KROGER_ZIP")))


@cache
def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=20)


def token() -> str:
    """An app token (client credentials), kept until a minute before it expires."""
    with _lock:
        if _token.get("value") and _token["expires"] > time.monotonic():
            return _token["value"]
        response = client().post(
            "/connect/oauth2/token",
            auth=(os.environ["KROGER_CLIENT_ID"], os.environ["KROGER_CLIENT_SECRET"]),
            data={"grant_type": "client_credentials", "scope": "product.compact"},
        )
        response.raise_for_status()
        body = response.json()
        _token.update(value=body["access_token"], expires=time.monotonic() + int(body.get("expires_in", 1800)) - 60)
        return _token["value"]


def _get(path: str, params: dict) -> dict:
    response = client().get(path, params=params, headers={"Authorization": f"Bearer {token()}", "Accept": "application/json"})
    response.raise_for_status()
    return response.json()


@cache
def location() -> str:
    """The store whose prices are used: KROGER_LOCATION_ID, or the nearest store to KROGER_ZIP (looked up once)."""
    if os.environ.get("KROGER_LOCATION_ID"):
        return os.environ["KROGER_LOCATION_ID"]
    found = _get("/locations", {"filter.zipCode.near": os.environ["KROGER_ZIP"], "filter.limit": 1}).get("data") or []
    if not found or not found[0].get("locationId"):
        raise RuntimeError("no Kroger store near KROGER_ZIP")
    return str(found[0]["locationId"])


def product(raw: dict) -> dict | None:
    """What HeyList keeps of a Kroger product, shaped like market.product so both can be checked and priced the same
    way: today's price at the chosen store (the sale price when there is one). None when the store has no price."""
    for item in raw.get("items") or []:
        price = item.get("price") or {}
        regular, promo = (Decimal(str(price.get(key) or 0)) for key in ("regular", "promo"))
        dollars = promo if 0 < promo < regular else regular
        cents = int(dollars * 100)
        if not 0 < cents <= 10_000_000 or not raw.get("description"):
            continue
        size = str(item.get("size") or "").strip()
        return {
            "productId": str(raw.get("productId") or ""),
            # The size is part of what the AI checks: "16 oz" ketchup is a normal bottle, "1 gal" is not.
            "title": (str(raw["description"]) + (f" ({size})" if size else ""))[:200],
            "store": STORE,
            "priceCents": cents,
            "category": " > ".join(str(c) for c in raw.get("categories") or [])[:300],
        }
    return None


def search(name: str) -> list[dict]:
    """Up to 10 products for an item name at the chosen store, priced. Search matches words, so callers have them
    checked by the AI (llm.market_matches) before using a price."""
    body = _get("/products", {"filter.term": name[:100], "filter.locationId": location(), "filter.limit": 10})
    found = (product(raw) for raw in body.get("data") or [])
    return [p for p in found if p]
