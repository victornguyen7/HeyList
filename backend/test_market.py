import json
import unittest
from unittest import mock

import httpx

import market


def offer(price, currency="USD", availability="InStock", url="https://shop.example/p", domain="shop.example"):
    return {"url": url, "domain": domain, "availability": availability, "price": {"price": price, "currency": currency}}


SUNSCREEN = {
    "id": "P1",
    "title": "SPF 50 Sunscreen",
    "category": {"title": "Sunscreen", "path": [{"title": "Health & Beauty"}, {"title": "Sunscreen"}]},
    "images": [{"url": "https://img.example/side.jpg"}, {"url": "https://img.example/main.jpg", "is_main_image": True}],
    "offers": [offer(12.99), offer(9.5, domain="cheap.example"), offer(3.0, availability="OutOfStock"), offer(2.0, currency="EUR")],
}


class MarketTest(unittest.TestCase):
    def fake(self, handler):
        requests = []

        def record(request):
            requests.append(request)
            return handler(request)

        patch = mock.patch.object(market, "client", return_value=httpx.Client(base_url="https://api.trychannel3.com", transport=httpx.MockTransport(record)))
        self.addCleanup(patch.stop)
        patch.start()
        return requests

    def test_a_product_keeps_its_cheapest_in_stock_dollar_offer(self):
        self.assertEqual(
            market.product(SUNSCREEN),
            {"productId": "P1", "title": "SPF 50 Sunscreen", "store": "cheap.example", "url": "https://shop.example/p",
             "imageUrl": "https://img.example/main.jpg", "priceCents": 950, "category": "Health & Beauty > Sunscreen"},
        )
        # Decimal, not float: 0.29 * 100 is 28.999... as a float.
        self.assertEqual(market.product({**SUNSCREEN, "offers": [offer(0.29)]})["priceCents"], 29)

    def test_products_without_a_usable_offer_or_with_unsafe_links_are_left_out(self):
        for raw in (
            {**SUNSCREEN, "offers": [offer(5, currency="EUR"), offer(5, availability="OutOfStock")]},
            {**SUNSCREEN, "offers": [offer(5, url="javascript:alert(1)")]},
            {**SUNSCREEN, "offers": [offer(0)]},
            {**SUNSCREEN, "title": ""},
        ):
            with self.subTest(raw=raw["offers"]):
                self.assertIsNone(market.product(raw))
        self.assertIsNone(market.product({**SUNSCREEN, "images": [{"url": "javascript:x"}]})["imageUrl"])
        self.assertEqual(market.product({**SUNSCREEN, "category": None})["category"], "")

    def test_search_sends_the_name_and_keeps_the_usable_products(self):
        requests = self.fake(lambda request: httpx.Response(200, json={"products": [SUNSCREEN] * 7 + [{"id": "P2", "offers": []}]}))

        found = market.search("sunscreen")

        self.assertEqual(len(found), 7)
        self.assertEqual(json.loads(requests[0].content), {"query": "sunscreen", "limit": 10})
        self.assertEqual(requests[0].url.path, "/v1/search")

    def test_get_reads_the_product_now_and_an_unknown_one_is_none(self):
        requests = self.fake(lambda request: httpx.Response(200, json=SUNSCREEN) if request.url.path == "/v1/products/P1" else httpx.Response(404))

        self.assertEqual(market.get("P1")["priceCents"], 950)
        self.assertIsNone(market.get("P9"))
        self.assertEqual(requests[0].url.params["currency"], "USD")

    def test_a_server_error_raises(self):
        self.fake(lambda request: httpx.Response(500))
        with self.assertRaises(httpx.HTTPStatusError):
            market.search("sunscreen")


if __name__ == "__main__":
    unittest.main()
