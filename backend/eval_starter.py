"""Scores llm.starting_list() against hand-labelled cases in eval/starter_cases.json.

Every case is one real (paid) Ollama call, so this only runs with --yes, and only when the owner asked for it
(RULES.md). From backend/, with the keys loaded from .env.local:

    set -a; . ../.env.local; set +a; ../../.venv/bin/python eval_starter.py --yes
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CASES = Path(__file__).parent / "eval" / "starter_cases.json"
REPORT = Path(__file__).parent / "eval" / "eval_report.json"


def score(case: dict, items: list[dict]) -> dict:
    """Matches each expected item to one returned item whose name contains one of its names, then counts.
    quantity and note are only checked where the case gives them; invented items only count for explicit lists,
    where the person named everything they wanted."""
    left = list(items)
    found = quantity_ok = quantity_checked = notes_kept = notes_checked = 0
    for expected in case["expect"]:
        names = [name.lower() for name in expected["names"]]
        # Prefer a match with the expected quantity, so two sizes of the same thing pair up correctly.
        candidates = [item for item in left if any(name in item["name"].lower() for name in names)]
        candidates.sort(key=lambda item: item["quantity"] != expected.get("quantity"))
        match = candidates[0] if candidates else None
        if "quantity" in expected:
            quantity_checked += 1
            quantity_ok += bool(match and match["quantity"] == expected["quantity"])
        if expected.get("note"):
            notes_checked += 1
            notes_kept += bool(match and match.get("note"))
        if match:
            found += 1
            left.remove(match)
    return {
        "found": found,
        "expected": len(case["expect"]),
        "quantityOk": quantity_ok,
        "quantityChecked": quantity_checked,
        "notesKept": notes_kept,
        "notesChecked": notes_checked,
        "invented": [item["name"] for item in left] if case["explicit"] else [],
    }


def main() -> None:
    if "--yes" not in sys.argv:
        sys.exit(f"Makes {len(json.loads(CASES.read_text()))} paid Ollama calls. Run with --yes once the owner has agreed.")
    import llm  # only when running for real, so the tests can import score() without the Ollama client

    # Token usage is reported back after every paid run (RULES.md), so each reply's counts are added up here.
    usage = {"promptTokens": 0, "outputTokens": 0, "calls": 0}
    real = llm.client()

    class Counting:
        def chat(self, **kwargs):
            response = real.chat(**kwargs)
            usage["calls"] += 1
            usage["promptTokens"] += response.prompt_eval_count or 0
            usage["outputTokens"] += response.eval_count or 0
            return response

    llm.client = lambda: Counting()

    keys = ("found", "expected", "quantityOk", "quantityChecked", "notesKept", "notesChecked")
    totals, invented, cases = dict.fromkeys(keys, 0), 0, []
    for case in json.loads(CASES.read_text()):
        try:
            items, error = llm.starting_list(case["input"])["items"], None
        except Exception as exc:  # a malformed reply counts as nothing found
            items, error = [], type(exc).__name__
        result = score(case, items)
        for key in keys:
            totals[key] += result[key]
        invented += len(result["invented"])
        cases.append({"id": case["id"], "input": case["input"], "explicit": case["explicit"], "error": error, "items": items, "score": result})
        print(
            f"{case['id']}: items {result['found']}/{result['expected']}, quantities {result['quantityOk']}/{result['quantityChecked']},"
            f" notes {result['notesKept']}/{result['notesChecked']}" + (f", invented {result['invented']}" if result["invented"] else "")
            + (f" FAILED ({error})" if error else "")
        )

    def rate(part: int, whole: int) -> float | None:
        return round(part / whole, 3) if whole else None

    summary = {
        "itemRecall": rate(totals["found"], totals["expected"]),
        "quantityAccuracy": rate(totals["quantityOk"], totals["quantityChecked"]),
        "notesKeptRate": rate(totals["notesKept"], totals["notesChecked"]),
        "inventedItems": invented,
        "failedCases": sum(1 for case in cases if case["error"]),
        "counts": totals,
    }
    REPORT.write_text(
        json.dumps(
            {
                "ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": os.environ.get("OLLAMA_MODEL"),
                "cases": len(cases),
                "summary": summary,
                "usage": usage,
                "results": cases,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"\nItem recall {totals['found']}/{totals['expected']} · quantity accuracy {totals['quantityOk']}/{totals['quantityChecked']}"
        f" · conditions and unclear amounts kept {totals['notesKept']}/{totals['notesChecked']} · invented items {invented}"
    )
    print(f"Tokens: {usage['promptTokens']} in, {usage['outputTokens']} out, {usage['calls']} calls. Report: {REPORT}")


if __name__ == "__main__":
    main()
