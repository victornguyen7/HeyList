import os
import unittest
from unittest import mock

import httpx

import kroger


class KrogerTest(unittest.TestCase):
    def test_todays_price_is_the_sale_price_and_the_size_is_in_the_title(self):
        raw = {"productId": "0001", "description": "Heinz Tomato Ketchup", "categories": ["Condiment & Sauces"],
               "items": [{"price": {"regular": 3.49, "promo": 2.79}, "size": "20 oz"}]}
        self.assertEqual(kroger.product(raw), {"productId": "0001", "title": "Heinz Tomato Ketchup (20 oz)", "store": "kroger.com", "priceCents": 279, "category": "Condiment & Sauces"})
        # No sale: the regular price. No price at this store, or a promo that isn't lower: as such.
        self.assertEqual(kroger.product(raw | {"items": [{"price": {"regular": 3.49, "promo": 0}}]})["priceCents"], 349)
        self.assertEqual(kroger.product(raw | {"items": [{"price": {"regular": 3.49, "promo": 3.99}}]})["priceCents"], 349)
        self.assertIsNone(kroger.product(raw | {"items": [{}]}))
        self.assertIsNone(kroger.product(raw | {"items": []}))

    def test_on_only_with_keys_and_a_store(self):
        keys = {"KROGER_CLIENT_ID": "id", "KROGER_CLIENT_SECRET": "secret"}
        with mock.patch.dict(os.environ, keys, clear=True):
            self.assertFalse(kroger.enabled())
        with mock.patch.dict(os.environ, keys | {"KROGER_ZIP": "45202"}, clear=True):
            self.assertTrue(kroger.enabled())

    def test_search_signs_in_once_and_asks_the_chosen_store(self):
        calls = []

        def handler(request: httpx.Request):
            calls.append(request)
            if request.url.path.endswith("/token"):
                return httpx.Response(200, json={"access_token": "T", "expires_in": 1800})
            return httpx.Response(200, json={"data": [{"productId": "1", "description": "Hot Dogs", "items": [{"price": {"regular": 4.99}}]}]})

        kroger._token.clear()
        with mock.patch.dict(os.environ, {"KROGER_CLIENT_ID": "id", "KROGER_CLIENT_SECRET": "s", "KROGER_LOCATION_ID": "01400943"}, clear=True), \
                mock.patch.object(kroger, "client", return_value=httpx.Client(base_url=kroger.API, transport=httpx.MockTransport(handler))):
            kroger.location.cache_clear()
            self.assertEqual([p["priceCents"] for p in kroger.search("hot dogs")], [499])
            kroger.search("buns")
        kroger.location.cache_clear()
        kroger._token.clear()
        self.assertEqual([c.url.path for c in calls], ["/v1/connect/oauth2/token", "/v1/products", "/v1/products"])
        self.assertEqual((calls[1].url.params["filter.term"], calls[1].url.params["filter.locationId"]), ("hot dogs", "01400943"))
        self.assertEqual(calls[1].headers["authorization"], "Bearer T")
        self.assertIn(b"scope=product.compact", calls[0].content)
