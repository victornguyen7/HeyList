"""Scores receipt reading (Textract AnalyzeExpense, and the Ollama vision fallback) against receipts from the
ReceiptQA test split (huggingface.co/datasets/mahmoud2019/ReceiptQA, MIT). From backend/:

    ../../.venv/bin/python eval_receipts.py prepare 100     # free: labels + 100 photos into eval/receipts/
    set -a; . ../.env.local; set +a
    ../../.venv/bin/python eval_receipts.py --yes [--ollama] # paid: one call per receipt without a cached reply
    ../../.venv/bin/python eval_receipts.py                  # free: rescores the cached replies

Add --english to any of the reading commands to score eval/receipts/english/ instead: 189 English-only receipts from
huggingface.co/datasets/docjay131/receipts-ocr-dataset (MIT), listed with their labels in english/manifest.json. Those
labels were written by Gemini, not people, so a miss there can also be a wrong label. Its cached replies and report
are kept in english/, apart from ReceiptQA's. `eval_receipts.py compare` (free) puts both reports side by side in
eval/receipts/comparison.json.

Every raw Textract response and Ollama reply is kept in eval/receipts/, so changes to receipts.parse_expense or
read_with_ollama are rescored without paying again. Paid calls only with --yes, and only when the owner asked
(RULES.md). Photos are shrunk like the app does (2000 px, JPEG 85) before they are read.
"""

import difflib
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import receipts

DATASET = "https://huggingface.co/datasets/mahmoud2019/ReceiptQA/resolve/main/"
RECEIPTQA = Path(__file__).parent / "eval" / "receipts"
ENGLISH = RECEIPTQA / "english"
# The set being scored; --english switches it to ENGLISH.
HERE = RECEIPTQA
CASES = RECEIPTQA / "cases.json"
ITEMS_QUESTION = "List all items and their respective quantities from this receipt.?"
SUMMARY_QUESTIONS = {
    "totalCents": "What is the total amount for this receipt?",
    "subtotalCents": "What is the subtotal for this receipt?",
    "taxCents": "What is the total tax for this receipt?",
    "merchant": "What is the merchant's name on this receipt?",
}
# Which Ollama prompt a cached reply answered: the first 12 hex digits of its SHA-256.
PROMPT_VERSION = hashlib.sha256(receipts.READ_PROMPT.encode()).hexdigest()[:12]
# A read line and a labelled item are the same line when their names are at least this similar.
SAME_NAME = 0.6


def amount(answer) -> int | None:
    if isinstance(answer, (int, float)):
        answer = f"{answer:.2f}"
    return receipts.cents(answer) if isinstance(answer, str) and "not available" not in answer.lower() else None


def gold(qa: list[dict]) -> dict | None:
    """One label file -> {"items": [{"name", "quantity", "priceCents"}], "totalCents", ...}; None if it has no item list."""
    human = {q["question"]: q["answer"] for q in qa if q.get("source") == "Human"}
    listed = human.get(ITEMS_QUESTION)
    if not isinstance(listed, list) or not listed:
        return None
    items = []
    for row in listed:
        if not isinstance(row, dict) or not str(row.get("item", "")).strip():
            return None
        quantity = str(row.get("quantity", "")).strip()
        items.append(
            {
                "name": str(row["item"]).strip(),
                "quantity": int(quantity) if quantity.isdigit() else None,
                "priceCents": amount(row.get("total_price")),
            }
        )
    case = {"items": items}
    for key, question in SUMMARY_QUESTIONS.items():
        answer = human.get(question)
        case[key] = (str(answer).strip() if answer and "not available" not in str(answer).lower() else None) if key == "merchant" else amount(answer) # pyright: ignore[reportArgumentType]
    return case


def english_cases() -> list[dict]:
    """english/manifest.json -> cases shaped like gold()'s, plus the photo's path and its category."""
    cases = []
    for receipt in json.loads((ENGLISH / "manifest.json").read_text())["receipts"]:
        label = receipt["label"]
        items = []
        for item in label.get("items") or []:
            quantity = item.get("quantity")
            items.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "quantity": int(quantity) if isinstance(quantity, (int, float)) and quantity == int(quantity) else None,
                    "priceCents": amount(item.get("totalPrice")),
                }
            )
        cases.append(
            {
                "id": Path(receipt["file"]).stem,
                "image": receipt["file"],
                "category": receipt["category"],
                "merchant": label.get("merchantName"),
                "items": items,
                "totalCents": amount(label.get("total")),
                "subtotalCents": amount(label.get("subtotal")),
                "taxCents": amount(label.get("tax")),
                "tipCents": amount(label.get("tip")),
            }
        )
    return cases


def similarity(a: str, b: str) -> float:
    def norm(text: str) -> str:
        return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())

    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def fee_cents(read: dict, kind: str) -> int | None:
    """What the read fees of one kind add up to; None when there are none or one has no amount."""
    amounts = [fee["amountCents"] for fee in read.get("fees", []) if fee["kind"] == kind]
    return sum(amounts) if amounts and None not in amounts else None


def score(case: dict, read: dict) -> dict:
    """Pairs each labelled item with one read line of a similar name, preferring the right price, then counts.
    A line left over is an extra: something read as an item that the label doesn't list (tax, a header, a split).
    A labelled line that charges nothing or is negative isn't an item (the app drops free lines and reads
    discounts as fees). A price left blank for the person to type is asked, neither right nor wrong."""
    expected = [item for item in case["items"] if item["priceCents"] is None or item["priceCents"] > 0]
    left = list(read["lines"])
    # Lines with the right price pair up first, so a near-same name ("JERSEY BODY" / "JERSEY TROUSERS") on an
    # earlier item can't take a later item's line.
    pairs = {}
    for same_price in (True, False):
        for n, item in enumerate(expected):
            if n in pairs:
                continue
            candidates = [(similarity(item["name"], line["text"]), line) for line in left]
            candidates = [pair for pair in candidates if pair[0] >= SAME_NAME and (not same_price or pair[1]["priceCents"] == item["priceCents"])]
            if candidates:
                pairs[n] = max(candidates, key=lambda pair: pair[0])[1]
                left.remove(pairs[n])
    found = price_ok = price_checked = price_asked = 0
    flagged_right = flagged_wrong = right = wrong = 0
    misses = []
    for n, item in enumerate(expected):
        if n not in pairs:
            misses.append(item["name"])
            continue
        line = pairs[n]
        found += 1
        if item["priceCents"] is not None:
            if line["priceCents"] is None:
                price_asked += 1
                continue
            price_checked += 1
            ok = line["priceCents"] == item["priceCents"]
            price_ok += ok
            # How well the "hard to read" flag picks out the lines that are wrong.
            right, wrong = right + ok, wrong + (not ok)
            flagged_right += ok and line["lowConfidence"]
            flagged_wrong += (not ok) and line["lowConfidence"]
    tax, tip = fee_cents(read, "tax"), fee_cents(read, "tip")
    label_tip = case.get("tipCents")
    prices = [line["priceCents"] for line in read["lines"]]
    amounts = prices + [fee["amountCents"] for fee in read.get("fees", [])]
    return {
        "found": found,
        "expected": len(expected),
        "priceOk": price_ok,
        "priceChecked": price_checked,
        "priceAsked": price_asked,
        "priceWrong": price_checked - price_ok,
        "extra": len(left),
        "totalOk": case["totalCents"] is not None and read["totalCents"] == case["totalCents"],
        "totalChecked": case["totalCents"] is not None,
        "taxOk": case.get("taxCents") is not None and (tax or 0) == case["taxCents"],
        "taxChecked": case.get("taxCents") is not None,
        # A label with no tip (or 0) expects none read.
        "tipOk": "tipCents" in case and (tip or 0) == (label_tip or 0),
        "tipChecked": "tipCents" in case,
        # The read lines and fees add up to the read total: what the review screen can check by itself.
        "addsUp": read["totalCents"] is not None and None not in amounts and sum(amounts) == read["totalCents"],
        "perfect": found == len(expected) and price_ok == price_checked and not price_asked and not left,
        "noWrongPrice": price_ok == price_checked,
        "flaggedRight": flagged_right,
        "flaggedWrong": flagged_wrong,
        "rightLines": right,
        "wrongLines": wrong,
        "missed": misses,
        "extras": [line["text"] for line in left],
    }


def summarize(scores: list[dict]) -> dict:
    total = defaultdict(int)
    for result in scores:
        for key, value in result.items():
            if isinstance(value, (bool, int)):
                total[key] += value

    def rate(part: str, whole: str | int) -> float | None:
        whole = total[whole] if isinstance(whole, str) else whole
        return round(total[part] / whole, 3) if whole else None

    read_lines = total["found"] + total["extra"]
    return {
        "receipts": len(scores),
        "itemRecall": rate("found", "expected"),
        "linePrecision": round(total["found"] / read_lines, 3) if read_lines else None,
        "priceAccuracy": rate("priceOk", "priceChecked"),
        # Of the found lines with a labelled price: left blank for the person, and shown but wrong.
        "pricesAsked": round(total["priceAsked"] / (total["priceChecked"] + total["priceAsked"]), 3) if total["priceChecked"] + total["priceAsked"] else None,
        "pricesWrong": round(total["priceWrong"] / (total["priceChecked"] + total["priceAsked"]), 3) if total["priceChecked"] + total["priceAsked"] else None,
        "totalAccuracy": rate("totalOk", "totalChecked"),
        "taxAccuracy": rate("taxOk", "taxChecked"),
        "tipAccuracy": rate("tipOk", "tipChecked"),
        "addsUp": rate("addsUp", len(scores)),
        "perfectReceipts": rate("perfect", len(scores)),
        "noWrongPriceReceipts": rate("noWrongPrice", len(scores)),
        "wrongLinesFlagged": rate("flaggedWrong", "wrongLines"),
        "rightLinesFlagged": rate("flaggedRight", "rightLines"),
        "counts": dict(total),
    }


# Preparing: labels are small; the photos come out of a 900 MB zip one by one with HTTP range requests.


class RemoteFile(io.RawIOBase):
    def __init__(self, url: str):
        head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.url, self.size, self.pos = head.url, int(head.headers["Content-Length"]), 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = (offset, self.pos + offset, self.size + offset)[whence]
        return self.pos

    def readinto(self, buffer):
        if self.pos >= self.size or not len(buffer):
            return 0
        end = min(self.pos + len(buffer), self.size) - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        data = urllib.request.urlopen(request, timeout=60).read()
        buffer[: len(data)] = data
        self.pos += len(data)
        return len(data)


def shrink(photo: bytes) -> bytes:
    """What app/receipt-scan.tsx sends: at most 2000 px on the long side, JPEG quality 85 (macOS sips)."""
    with tempfile.TemporaryDirectory() as folder:
        source, target = Path(folder, "in.jpg"), Path(folder, "out.jpg")
        source.write_bytes(photo)
        sizes = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", source], capture_output=True, text=True, check=True)
        longest = max(int(n) for n in re.findall(r"pixel(?:Width|Height): (\d+)", sizes.stdout))
        command = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", source, "--out", target]
        if longest > 2000:
            command[1:1] = ["-Z", "2000"]
        subprocess.run(command, capture_output=True, check=True)
        return target.read_bytes()


def prepare(count: int) -> None:
    with urllib.request.urlopen(DATASET + "test_label.zip", timeout=120) as response:
        labels = zipfile.ZipFile(io.BytesIO(response.read()))
    by_merchant = defaultdict(list)
    for name in sorted(labels.namelist()):
        found = re.fullmatch(r"test_label/([0-9a-f-]{36})\.json", name)
        case = found and gold(json.loads(labels.read(name)))
        if case:
            by_merchant[case["merchant"] or "?"].append({"id": found[1], **case}) # pyright: ignore[reportOptionalSubscript]
    # Round-robin over merchants so one chain doesn't fill the sample.
    rng = random.Random(7)
    pools = [rng.sample(cases, len(cases)) for _, cases in sorted(by_merchant.items())]
    rng.shuffle(pools)
    chosen = []
    while len(chosen) < count and any(pools):
        for pool in pools:
            if pool and len(chosen) < count:
                chosen.append(pool.pop())

    photos = zipfile.ZipFile(io.BufferedReader(RemoteFile(DATASET + "test_images.zip"), 1 << 20))
    (HERE / "images").mkdir(parents=True, exist_ok=True)
    for n, case in enumerate(chosen, 1):
        path = HERE / "images" / f"{case['id']}.jpg"
        if not path.exists():
            path.write_bytes(shrink(photos.read(f"test_images/{case['id']}.jpg")))
        print(f"{n}/{len(chosen)} {case['id']} {case['merchant']}")
    CASES.write_text(json.dumps(chosen, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(chosen)} receipts from {len(by_merchant)} merchants. Cases: {CASES}")


def photo(case: dict) -> bytes:
    """What the app would send. prepare already shrank ReceiptQA's photos; english/ holds the originals."""
    if "image" in case:
        return shrink((HERE / case["image"]).read_bytes())
    return (HERE / "images" / f"{case['id']}.jpg").read_bytes()


# Reading: a cached reply is used when there is one; otherwise, with --yes, the service is called and the reply kept.


def read_textract(case: dict, paid: bool, usage: dict) -> dict | None:
    cached = HERE / "textract" / f"{case['id']}.json"
    if not cached.exists():
        if not paid:
            return None
        response = receipts._textract().analyze_expense(Document={"Bytes": photo(case)})
        usage["textractPages"] += response.get("DocumentMetadata", {}).get("Pages", 1)
        response.pop("ResponseMetadata", None)
        cached.parent.mkdir(exist_ok=True)
        cached.write_text(json.dumps(response) + "\n")
    return receipts.parse_expense(json.loads(cached.read_text()))


def read_ollama(case: dict, paid: bool, usage: dict) -> dict | None:
    import llm

    cached = HERE / "ollama" / f"{case['id']}.json"
    # A reply to an older prompt says nothing about this one: it is read again (paid), or left out of the score.
    if cached.exists() and json.loads(cached.read_text()).get("prompt") != PROMPT_VERSION:
        if not paid:
            return None
        cached.unlink()
    if not cached.exists():
        if not paid:
            return None
        replies = []
        real = llm.client()

        class Recording:
            def chat(self, **kwargs):
                response = real.chat(**kwargs)
                usage["ollamaCalls"] += 1
                usage["promptTokens"] += response.prompt_eval_count or 0
                usage["outputTokens"] += response.eval_count or 0
                replies.append(response.message.content or "")
                return response

        with mock.patch.object(llm, "client", lambda: Recording()):
            try:
                receipts.read_with_ollama(photo(case))
            except receipts.ReceiptError:
                if not replies:  # the call itself failed; nothing to keep, try again next run
                    raise
        cached.parent.mkdir(exist_ok=True)
        cached.write_text(json.dumps({"model": os.environ.get("OLLAMA_MODEL"), "prompt": PROMPT_VERSION, "reply": replies[0]}) + "\n")
    # Rescored through read_with_ollama, so changes to its parsing count.
    with mock.patch.object(llm, "chat", lambda *args, **kwargs: json.loads(cached.read_text())["reply"]):
        return receipts.read_with_ollama(b"")


COMPARISON = RECEIPTQA / "comparison.json"
SHOWN = {"itemRecall": "items found", "linePrecision": "lines that are items", "priceAccuracy": "prices right",
         "pricesAsked": "prices asked", "pricesWrong": "prices wrong", "totalAccuracy": "totals right",
         "taxAccuracy": "tax right", "tipAccuracy": "tip right", "perfectReceipts": "perfect receipts",
         "noWrongPriceReceipts": "no wrong price"}


def compare() -> None:
    """Free: the two sets' saved reports side by side in eval/receipts/comparison.json."""
    reports = {"receiptQA": RECEIPTQA / "eval_report.json", "english": ENGLISH / "eval_report.json"}
    comparison = {}
    for name, path in reports.items():
        report = json.loads(path.read_text())
        comparison[name] = {"ranAt": report["ranAt"]} | {
            reader: {"summary": report[reader]["summary"], "byCategory": report[reader].get("byCategory", {})}
            for reader in ("textract", "ollama") if reader in report
        }
    COMPARISON.write_text(json.dumps(comparison, indent=1) + "\n")
    for reader in ("textract", "ollama"):
        print(f"\n{reader:22} {'ReceiptQA':>10} {'English':>10}")
        for key, label in SHOWN.items():
            print(f"  {label:20}" + "".join(f"{comparison[name].get(reader, {}).get('summary', {}).get(key)!s:>11}" for name in reports))
    print(f"\nSaved: {COMPARISON}")


def main() -> None:
    if sys.argv[1:2] == ["prepare"]:
        return prepare(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
    if sys.argv[1:2] == ["compare"]:
        return compare()
    global HERE
    if "--english" in sys.argv:
        HERE, cases = ENGLISH, english_cases()
    elif not CASES.exists():
        sys.exit("No receipts yet: run `eval_receipts.py prepare 100` first.")
    else:
        cases = json.loads(CASES.read_text())
    report_path = HERE / "eval_report.json"
    paid = "--yes" in sys.argv
    readers = {"textract": read_textract} | ({"ollama": read_ollama} if "--ollama" in sys.argv or (HERE / "ollama").exists() else {})
    usage = {"textractPages": 0, "ollamaCalls": 0, "promptTokens": 0, "outputTokens": 0}
    report = {"ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lowConfidence": receipts.LOW_CONFIDENCE}
    for reader_name, reader in readers.items():
        scores, results, missing = [], [], 0
        for case in cases:
            try:
                read, error = reader(case, paid, usage), None
            except receipts.ReceiptError as exc:  # an unreadable reply counts as nothing read
                read, error = {"lines": [], "totalCents": None}, str(exc)
            if read is None:
                missing += 1
                continue
            result = score(case, read)
            scores.append(result)
            results.append({"id": case["id"], "category": case.get("category"), "merchant": case["merchant"], "error": error, "read": read, "score": result})
        summary = summarize(scores)
        by_category = defaultdict(list)
        for result in results:
            if result["category"]:
                by_category[result["category"]].append(result["score"])
        report[reader_name] = {"summary": summary, "byCategory": {name: summarize(group) for name, group in sorted(by_category.items())}, "results": results}
        print(f"\n{reader_name}: {len(scores)} receipts scored" + (f", {missing} not read yet (run with --yes)" if missing else ""))
        if scores:
            print(
                f"  items found {summary['itemRecall']}, lines that are items {summary['linePrecision']}, prices right {summary['priceAccuracy']},"
                f" totals right {summary['totalAccuracy']}, perfect receipts {summary['perfectReceipts']}"
            )
            print(
                f"  prices asked {summary['pricesAsked']}, prices wrong {summary['pricesWrong']}, receipts with no wrong price"
                f" {summary['noWrongPriceReceipts']}, tax right {summary['taxAccuracy']}, tip right {summary['tipAccuracy']}, adds up {summary['addsUp']}"
            )
            print(f"  hard-to-read flag: on {summary['wrongLinesFlagged']} of wrong lines, {summary['rightLinesFlagged']} of right ones")
            for name, part in report[reader_name]["byCategory"].items():
                print(f"  {name} ({part['receipts']}): items found {part['itemRecall']}, prices right {part['priceAccuracy']}, perfect {part['perfectReceipts']}")
    report["usage"] = usage
    report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"\nPaid this run: {usage['textractPages']} Textract pages, {usage['ollamaCalls']} Ollama calls"
          f" ({usage['promptTokens']} tokens in, {usage['outputTokens']} out). Report: {report_path}")


if __name__ == "__main__":
    main()
