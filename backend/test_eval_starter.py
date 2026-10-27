import json
import unittest

import eval_starter


class ScoreTest(unittest.TestCase):
    def test_a_reply_is_scored_on_items_quantities_notes_and_inventions(self):
        case = {
            "explicit": True,
            "expect": [
                {"names": ["water"], "quantity": 2},
                {"names": ["olive oil"], "quantity": 1},
                {"names": ["olive oil"], "quantity": 2},
                {"names": ["flashlight", "torch"], "note": True},
                {"names": ["plate"]},
            ],
        }
        items = [
            {"name": "Water", "quantity": 3},  # found, wrong quantity
            {"name": "Olive oil", "quantity": 2},
            {"name": "Olive oil (big)", "quantity": 1},  # two sizes pair up by quantity, whatever the order
            {"name": "Torch", "quantity": 1, "note": None},  # condition lost
            {"name": "Napkins", "quantity": 1},  # not asked for
        ]

        self.assertEqual(
            eval_starter.score(case, items),
            {"found": 4, "expected": 5, "quantityOk": 2, "quantityChecked": 3, "notesKept": 0, "notesChecked": 1, "invented": ["Napkins"]},
        )

    def test_extra_items_only_count_as_invented_for_explicit_lists(self):
        self.assertEqual(eval_starter.score({"explicit": False, "expect": []}, [{"name": "Tent", "quantity": 1}])["invented"], [])

    def test_every_case_file_entry_is_well_formed(self):
        cases = json.loads(eval_starter.CASES.read_text())

        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case["id"] for case in cases}), 20)
        for case in cases:
            self.assertTrue(case["input"] and case["expect"] and isinstance(case["explicit"], bool), case["id"])


if __name__ == "__main__":
    unittest.main()
