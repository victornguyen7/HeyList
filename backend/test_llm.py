import json
import unittest
from pathlib import Path
from unittest import mock

import llm


class StartingListTest(unittest.TestCase):
    def reply(self, text):
        patch = mock.patch.object(llm, "chat", return_value=text)
        self.addCleanup(patch.stop)
        return patch.start()

    def test_a_fenced_reply_is_cleaned_and_checked(self):
        body = {
            "title": "Lake trip",
            "kind": "trip",
            "items": [
                {"name": " Sunscreen ", "quantity": 2, "estPriceCents": 899},
                {"name": "sunscreen ", "quantity": 2, "estPriceCents": 899},  # a repeat
                {"name": "Flashlight", "quantity": 1, "estPriceCents": 1200, "note": " only if  nobody has one "},
                {"name": "Tent", "estPriceCents": 0},  # no quantity, already owned
                {"name": "Firewood", "quantity": 500, "estPriceCents": "lots"},
                {"name": "", "quantity": 1, "estPriceCents": 100},
            ],
        }
        chat = self.reply("```json\n" + json.dumps(body) + "\n```")

        result = llm.starting_list("Lake trip for 3", 15000)

        self.assertEqual(
            result,
            {
                "title": "Lake trip",
                "kind": "trip",
                "items": [
                    {"name": "Sunscreen", "quantity": 2, "estPriceCents": 899, "note": None},
                    {"name": "Flashlight", "quantity": 1, "estPriceCents": 1200, "note": "only if nobody has one"},
                    {"name": "Tent", "quantity": 1, "estPriceCents": None, "note": None},
                    {"name": "Firewood", "quantity": 99, "estPriceCents": None, "note": None},
                ],
            },
        )
        messages, schema = chat.call_args.args
        self.assertIn("Budget: 15000 cents", messages[-1]["content"])
        self.assertIs(schema, llm.STARTER_SCHEMA)

    def test_the_same_item_with_different_amounts_is_kept_twice_and_flagged(self):
        self.reply(json.dumps({"title": "Party", "kind": "party", "items": [
            {"name": "Plates", "quantity": 20, "estPriceCents": 10},
            {"name": "plates", "quantity": 10, "estPriceCents": 10, "note": 7},
        ]}))

        items = llm.starting_list("Party")["items"]

        flag = "listed twice with different amounts; check how many"
        self.assertEqual([(i["quantity"], i["note"]) for i in items], [(20, flag), (10, flag)])

    def test_no_examples_are_sent_by_default(self):
        chat = self.reply('{"title": "Pup", "kind": "home", "items": []}')

        llm.starting_list("Bringing home a puppy we adopted")

        self.assertEqual([m["role"] for m in chat.call_args.args[0]], ["system", "user"])

    def test_when_turned_on_the_closest_examples_are_sent_before_the_request(self):
        chat = self.reply('{"title": "Pup", "kind": "home", "items": []}')

        with mock.patch.object(llm, "EXAMPLE_COUNT", 3):
            llm.starting_list("Bringing home a puppy we adopted")

        messages = chat.call_args.args[0]
        self.assertEqual([m["role"] for m in messages], ["system"] + ["user", "assistant"] * 3 + ["user"])
        self.assertEqual(messages[1]["content"], "Prepare supplies for bringing home a newly adopted puppy")
        self.assertEqual(json.loads(messages[2]["content"])["title"], next(e for e in llm.EXAMPLES if e["request"] == messages[1]["content"])["reply"]["title"])
        self.assertEqual(messages[-1]["content"], "Bringing home a puppy we adopted")

    def test_every_example_is_a_valid_reply_and_none_repeats_an_eval_case(self):
        cases = json.loads((Path(__file__).parent / "eval" / "starter_cases.json").read_text())
        for example in llm.EXAMPLES:
            reply = example["reply"]
            self.assertIn(reply["kind"], llm.KINDS)
            for item in reply["items"]:
                self.assertTrue(item["name"] and 1 <= item["quantity"] <= 99 and item["estPriceCents"] >= 0, item)
            self.assertNotIn(example["request"].lower(), [case["input"].lower() for case in cases])

    def test_an_unknown_kind_and_missing_title_fall_back(self):
        self.reply('{"kind": "picnic", "items": []}')

        self.assertEqual(llm.starting_list("Picnic"), {"title": "Picnic", "kind": "other", "items": []})

    def test_text_after_the_object_is_ignored(self):
        self.reply('{"title": "Picnic", "kind": "party", "items": []}\n\nAlternative: {"title": "x"}')

        self.assertEqual(llm.starting_list("Picnic"), {"title": "Picnic", "kind": "party", "items": []})

    def test_a_reply_that_is_not_json_raises(self):
        self.reply("Sorry, I can't help with that.")

        with self.assertRaises(ValueError):
            llm.starting_list("Picnic")


class StoreMatchTest(unittest.TestCase):
    PRODUCTS = [{"title": "Essential Milk", "category": "Health & Beauty > Skin Care > Facial Cleansers"}, {"title": "Whole Milk", "category": ""}]

    def test_only_the_numbered_matches_are_kept_in_order_and_odd_numbers_ignored(self):
        with mock.patch.object(llm, "chat", return_value='{"matches": [2, 9, "1", true]}') as chat:
            self.assertEqual(llm.store_matches("Milk", "2%", "Weekly Groceries", self.PRODUCTS), self.PRODUCTS[1:])
        request = chat.call_args.args[0][-1]["content"]
        self.assertIn("Item: Milk\nNote: 2%\nList: Weekly Groceries", request)
        self.assertIn("1. Essential Milk (Health & Beauty > Skin Care > Facial Cleansers)\n2. Whole Milk (no category)", request)

    def test_no_products_need_no_call(self):
        with mock.patch.object(llm, "chat") as chat:
            self.assertEqual(llm.store_matches("Milk", None, "", []), [])
        chat.assert_not_called()



class AgentTurnTest(unittest.TestCase):
    def test_text_tool_calls_and_usage_come_back_and_the_model_is_the_servers(self):
        from ollama._types import ChatResponse, Message

        reply = ChatResponse(
            message=Message(role="assistant", content="Here you go", tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(name="who_owes_whom", arguments={"list": "Trip"}))]),
            prompt_eval_count=120,
            eval_count=8,
        )
        fake = mock.Mock()
        fake.chat.return_value = reply
        tools = [{"type": "function", "function": {"name": "who_owes_whom"}}]
        with mock.patch.object(llm, "client", return_value=fake), mock.patch.dict("os.environ", {"OLLAMA_MODEL": "gemma4:31b"}):
            turn = llm.agent_turn([{"role": "user", "content": "hi"}], tools)

        self.assertEqual(
            turn,
            {"content": "Here you go", "toolCalls": [{"name": "who_owes_whom", "arguments": {"list": "Trip"}}], "usage": {"inputTokens": 120, "outputTokens": 8}},
        )
        fake.chat.assert_called_once_with(model="gemma4:31b", messages=[{"role": "user", "content": "hi"}], tools=tools, format=None)


if __name__ == "__main__":
    unittest.main()
