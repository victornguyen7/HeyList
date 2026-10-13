import unittest
from unittest import mock

import llm


def answering(answer):
    return mock.patch.object(llm, "_ask", return_value=answer)


class StartingListTest(unittest.TestCase):
    def test_prices_become_cents_and_the_budget_is_enforced_in_code(self):
        answer = {
            "title": " Move-in ",
            "kind": "home",
            "budget_usd": 50,
            "items": [
                {"name": "Kettle", "price_usd": 24.99},
                {"name": "Mop", "price_usd": 20},
                {"name": "Sofa", "price_usd": 400},  # the model went over budget
                {"name": "Sponge", "price_usd": 2.5},
                {"name": "", "price_usd": 1},
                "junk",
            ],
        }
        with answering(answer) as ask:
            result = llm.starting_list("move-in, $50 budget")
        self.assertIn("move-in, $50 budget", ask.call_args.args[0])
        self.assertEqual((result["title"], result["kind"], result["budgetCents"]), ("Move-in", "home", 5000))
        self.assertEqual(
            result["items"],
            [
                {"name": "Kettle", "estPriceCents": 2499},
                {"name": "Mop", "estPriceCents": 2000},
                {"name": "Sponge", "estPriceCents": 250},
            ],
        )

    def test_a_sloppy_answer_falls_back_to_safe_values(self):
        answer = {"kind": "spaceship", "budget_usd": "lots", "items": [{"name": "Tent", "price_usd": "cheap"}]}
        with answering(answer):
            result = llm.starting_list("weekend camping trip")
        self.assertEqual(
            result,
            {
                "title": "weekend camping trip",
                "kind": "other",
                "budgetCents": None,
                "items": [{"name": "Tent", "estPriceCents": None}],
            },
        )

    def test_no_usable_items_is_an_error(self):
        with answering({"title": "x", "items": []}), self.assertRaises(llm.LlmError):
            llm.starting_list("anything")


class SplitItemsTest(unittest.TestCase):
    def test_returns_the_items_with_estimates(self):
        with answering({"items": [{"name": "eggs", "price_usd": 3.5}, {"name": "milk", "price_usd": 4}]}):
            self.assertEqual(
                llm.split_items("groceries: eggs, milk"),
                [{"name": "eggs", "estPriceCents": 350}, {"name": "milk", "estPriceCents": 400}],
            )
        with answering({"items": "none"}):
            self.assertEqual(llm.split_items("uh"), [])


class ReadReceiptTest(unittest.TestCase):
    ITEMS = [{"id": "id-milk", "name": "Milk"}, {"id": "id-eggs", "name": "Eggs"}]

    def test_lines_are_matched_by_number_and_the_rest_are_extras(self):
        answer = {
            "total_usd": 12.47,
            "lines": [
                {"text": "2% MILK 1GAL", "price_usd": 4.29, "item": 1},
                {"text": "GUM", "price_usd": 1.99, "item": None},
                {"text": "MILK CHOC", "price_usd": 2.19, "item": 1},  # item 1 is already used
                {"text": "BATTERIES", "price_usd": 4, "item": 7},  # no such item
                {"text": "", "price_usd": 1, "item": 2},
            ],
        }
        with answering(answer) as ask:
            result = llm.read_receipt(b"photo", self.ITEMS)
        prompt, _, image = ask.call_args.args
        self.assertIn("1. Milk\n2. Eggs", prompt)
        self.assertEqual(image, b"photo")
        self.assertEqual(
            result,
            {
                "totalCents": 1247,
                "matches": [{"itemId": "id-milk", "line": "2% MILK 1GAL", "priceCents": 429}],
                "extras": [
                    {"name": "GUM", "priceCents": 199},
                    {"name": "MILK CHOC", "priceCents": 219},
                    {"name": "BATTERIES", "priceCents": 400},
                ],
            },
        )

    def test_an_unreadable_receipt_is_empty_not_an_error(self):
        with answering({"total_usd": None, "lines": None}):
            self.assertEqual(
                llm.read_receipt(b"photo", self.ITEMS), {"totalCents": None, "matches": [], "extras": []}
            )


class AskTest(unittest.TestCase):
    def ask(self, content):
        client = mock.Mock()
        client.chat.return_value.message.content = content
        with mock.patch.object(llm, "_client", return_value=client), mock.patch.dict(
            llm.os.environ, {"OLLAMA_MODEL": "test-model"}
        ):
            return llm._ask("question", {"type": "object"}, b"img"), client

    def test_reads_json_out_of_a_code_fence_and_sends_the_image(self):
        answer, client = self.ask('```json\n{"items": []}\n```')
        self.assertEqual(answer, {"items": []})
        call = client.chat.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["messages"][0]["images"], [b"img"])

    def test_a_reply_that_is_not_json_is_an_llm_error(self):
        for content in ("Sorry, I cannot help.", "{not json}", ""):
            with self.subTest(content=content), self.assertLogs(llm.log, "ERROR"):
                with self.assertRaises(llm.LlmError):
                    self.ask(content)
