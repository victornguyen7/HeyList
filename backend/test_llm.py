import json
import unittest
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
                {"name": "sunscreen", "quantity": 1, "estPriceCents": 899},  # duplicate
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
                    {"name": "Sunscreen", "quantity": 2, "estPriceCents": 899},
                    {"name": "Tent", "quantity": 1, "estPriceCents": None},
                    {"name": "Firewood", "quantity": 99, "estPriceCents": None},
                ],
            },
        )
        messages, schema = chat.call_args.args
        self.assertIn("Budget: 15000 cents", messages[1]["content"])
        self.assertIs(schema, llm.STARTER_SCHEMA)

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


if __name__ == "__main__":
    unittest.main()
