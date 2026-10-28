# HeyList — Receipt reading eval (Textract and Ollama)

Run 2026-10-28 with `backend/eval_receipts.py`. First test of Textract on real receipts (issue 15).

## What was measured

- **Data:** 100 receipts from the test split of [ReceiptQA](https://huggingface.co/datasets/mahmoud2019/ReceiptQA) (MIT), one per merchant where possible (100 merchants, 348 labelled items). The labels used are the human-written ones: each receipt's item list (name, quantity, line price), total, subtotal and tax.
- **Photos** are shrunk the way the app does (`app/receipt-scan.tsx`: at most 2000 px, JPEG 85) before they are read.
- **Readers:** Textract `AnalyzeExpense` through `receipts.parse_expense`, and the Ollama vision fallback `receipts.read_with_ollama`, exactly as the app runs them.
- **Scoring:** a read line counts as a labelled item when its name is at least 60% similar (case and punctuation ignored). Lines with the right price pair up first. Lines left over are extras.

| Metric | Meaning |
|---|---|
| Items found | Labelled items with a matching read line |
| Lines that are items | Read lines that matched a labelled item (the rest are tax rows, headers, codes, split lines) |
| Prices right | Of the items found, how many have the labelled price |
| Totals right | Receipt total equals the labelled total |
| Perfect receipts | Every item found at the right price, no extra lines |

**Cost:** 100 Textract pages (about $1.00 at $0.01 a page) and 100 Ollama calls (49,013 tokens in, 14,843 out as Ollama reports them; the image does not seem to be counted). Every reply is kept in `backend/eval/receipts/`, so rescoring is free.

**Caveat about the data:** these are Egyptian receipts in EGP, mostly fashion and retail, with some supermarkets and pharmacies. HeyList is used for US grocery receipts, so read the numbers as relative. Around 15 of the 37 Textract price errors came from the labels, not from Textract: one store's labels are shifted by a row, four items are labelled at 100× their price, and some labels give the price before a discount.

## Results

| | Textract | Ollama |
|---|---|---|
| Items found | 72.7% | **79.6%** |
| Lines that are items | 78.6% | **81.2%** |
| Prices right | **89.4%** | 75.7% |
| Totals right | **93.9%** | 80.6% |
| Perfect receipts | **51%** | 45% |

Textract is the better reader for what HeyList records (prices and totals). Ollama finds slightly more items but misreads more prices. Keeping Textract first (decision 38) is right.

## Why Textract misses items (94 of 348)

| Cause | Items | Fixable in our code? |
|---|---|---|
| Not in Textract's line items at all (read as header or summary text, or skipped) | 34 | No |
| Name read but garbled (13 of these are Arabic; Textract reads Latin script only) | 28 | No |
| Name only in `EXPENSE_ROW`, mixed with quantity, price and SKU (`1 GREY 69.00\nACC/ACTIVN/PNFS21-109`) | 18 | Partly: clean the name |
| Line dropped by our parser: price is `0.00` (free items) or not a number (`L.E`) | 6 | Yes |
| Paired to a different labelled item, or the line has a different price (duplicates, label errors) | 8 | – |

**Extra lines (68):** mostly the same `EXPENSE_ROW` and multi-line names: barcodes and SKUs on their own line (`LID/SS21/075`, `1YPY.VITA\n163607169\nBASIC JOGGER`), discount rows (`1 SALE 299.00 209.30 89.70`), and garbled Arabic.

**Wrong prices that are Textract's:** amounts in a format `cents()` reads wrong (`60,520` for 60.52, `140,000` for 140.000), OCR slips (`59.SL.E`, `5 L.E` for 55), and a discounted net price where the label has the shelf price.

## The "hard to read" flag doesn't work

A line is flagged when Textract's confidence is under 90%. It flags 19% of the lines with a wrong price and 14% of the right ones, so it barely tells them apart. Textract's confidence is about the text, not about whether the line is an item at the right price. The flag does point at extra lines a little more often (39% of extras are under 90, against 15% of real items).

A much better signal is whether **the lines add up to the total**. With the parser fixes below, Textract's lines add up (within 1% or 1.00) on 70 of 100 receipts, and 46 of those 70 are perfect. Only 9 of the 30 receipts that don't add up are perfect.

## Proposed changes

All are changes to `receipts.parse_expense`, measured on the saved replies, each on its own and then together.

| Change | Items found | Lines that are items | Prices right | Perfect |
|---|---|---|---|---|
| Today | 72.7% | 78.6% | 89.4% | 51% |
| **A** When `PRICE` is missing or unreadable, use `QUANTITY`/`UNIT_PRICE` (`6.000@60.00` → 360.00) | 73.9 | 78.8 | 89.1 | 52 |
| **B** Keep `0.00` lines (free items still check off a list item) | 74.4 | 78.5 | 89.3 | 52 |
| **C** Clean names: from a multi-line name keep the wordy lines and drop barcodes and SKUs; from `EXPENSE_ROW` also drop bare numbers | 75.6 | 81.7 | 89.9 | 53 |
| **E** Drop a line priced above the receipt total | 71.3 | 79.2 | 90.9 | 51 |
| A+B+C+E | **77.0** | **82.7** | **91.2** | **55** |

Separately, in the app:

- **F. "Doesn't add up" warning:** on the review screen, when the lines don't add up to the total, say so ("These lines add up to $X, the receipt says $Y. Check for missing lines."). Show it in place of, or next to, the per-line flag. This changes the UI.
- **G. Retune or drop `LOW_CONFIDENCE`:** as a per-line flag it mostly marks right lines. Option: keep it, but also flag lines from E (price above the total).

Tried and **not** proposed:

- **Ollama when Textract doesn't add up:** 30 extra Ollama calls per 100 scans for no gain (perfect receipts went from 55% to 54%).
- **Dropping lines above the total (E alone):** it removes real items whose price was misread (items found falls to 71.3%). Flagging them is better than dropping them.

Not tried, would cost money: sending a larger photo (the app's 2000 px shrink may lose small print). About $0.30 to re-read the 30 receipts that don't add up at full size.

## English receipts and the tuning that followed (2026-10-28)

**Data:** 189 English-only receipts from [docjay131/receipts-ocr-dataset](https://huggingface.co/datasets/docjay131/receipts-ocr-dataset) (MIT), mostly US: 165 food (restaurants, cafés), 14 grocery (Walmart, Costco, Whole Foods, Trader Joe's), 7 household, 3 other. Of the 230, these were left out: 20 with any non-English text (checked with macOS text recognition, then by eye), 9 duplicates or with no labelled items, 12 whose labelled items don't add up to their subtotal. **The labels were written by Gemini, not people,** so a "miss" can also be a wrong label. Photos and labels are in `backend/eval/receipts/english/` (photos git-ignored).

**Cost of the first run:** 189 Textract pages (about $1.90) and 189 Ollama calls (92,493 tokens in, 39,770 out).

**Scoring changes:** a labelled line that charges nothing or is negative is no longer an item to find (the app drops free lines and reads discounts as fees). A price left blank for the person counts as *asked*, neither right nor wrong. New: tax and tip right (against the labels), and *adds up* (the read lines and fees reach the read total, which the review screen can check on its own).

### Changes (decision 57) and their effect on Textract

All measured on the saved replies, so free. "Before" is the reading code as it was, scored the same way.

| English receipts, Textract | Before | After |
|---|---|---|
| Items found | 90.5% | 90.8% |
| Lines that are items | 91.6% | 93.8% |
| Prices shown that are wrong | 4.0% | **2.5%** |
| Prices left blank to type | – | 2.1% |
| Totals right | 94.2% | 94.7% |
| Tax right | 2.2% | **97.2%** |
| Tip right | 92.1% | **96.8%** |
| Perfect receipts | 73.0% | 75.7% |
| Receipts with no wrong price shown | 95.2% | 95.2% |

On ReceiptQA the same code finds 76.5% of items (was 74.2%), shows 8.8% wrong prices (was 10.6%) and leaves 9.2% blank, and reads tax right on 60% of receipts (was 14%); totals are unchanged at 93.9%.

What changed in `receipts.py`:

- **`cents()`:** `.98` was read as $98.00; `9.95-` and `($12.00)` (discounts) were read as charges.
- **Names:** when Textract's ITEM mixes the names of neighbouring lines (144 of 1,001 lines), the name comes from the printed row with the line's price, if that row has a word in it.
- **Blank, not guessed:** a price under 90% confidence, or none, is left for the person (2.1% of prices). Raising the threshold buys little: at 98%, 4.2% are blank and 1.8% still wrong. 15 of the 46 wrong prices before were read at 100% confidence (often a price shifted by a row).
- **Fees:** tax, tip, service, delivery and discounts. Receipts repeat taxes (a breakdown plus a total tax, 21 receipts) and print tip suggestions ("15% / 18% / 20% gratuity"), so the code keeps the taxes and tip with which subtotal + fees = total.
- **The add-up check catches what confidence can't:** all 9 receipts that still show a wrong price fail it (32 of the 180 with no wrong price fail it too). The review screen now says "These add up to $X, but the receipt total is $Y."

By category (after): food finds 92.9% of items with 1.1% wrong prices; **grocery finds 85.4% with 5.7% wrong and 8.5% blank**, the weakest, on only 14 receipts.

**Ollama** (`gemma4:31b`) was told to leave unreadable prices blank and to read fees, then re-read all 189 receipts (189 calls, 139,176 tokens in, 45,707 out):

| English receipts, Ollama | Old prompt | New prompt | Textract (after) |
|---|---|---|---|
| Items found | 95.8% | **96.3%** | 90.8% |
| Prices shown that are wrong | 5.8% | 5.1% | **2.5%** |
| Prices left blank to type | – | 0.6% | 2.1% |
| Totals right | 97.9% | **98.4%** | 94.7% |
| Tax right | 2.2% | **97.8%** | 97.2% |
| Tip right | 92.1% | 96.3% | **96.8%** |
| Perfect receipts | 77.8% | 75.7% | 75.7% |
| Receipts with no wrong price shown | 92.1% | 92.1% | **95.2%** |

The model reads fees well but almost never admits it can't read a price (0.6% blank), so it still guesses: twice as many wrong prices as Textract. Textract stays first (decision 38). The add-up check catches 14 of Ollama's 15 receipts with a wrong price (26 false alarms of 174), so the review screen still warns in the fallback.

## Re-running

From `backend/`:

```
../../.venv/bin/python eval_receipts.py prepare 100   # free: labels and photos (photos are git-ignored)
../../.venv/bin/python eval_receipts.py               # free: rescore saved replies after a parser change
set -a; . ../.env.local; set +a
../../.venv/bin/python eval_receipts.py --yes --ollama  # paid, only for receipts with no saved reply
```

Add `--english` to the last three for the English set. `eval_receipts.py compare` (free) puts both sets' reports side by side in `backend/eval/receipts/comparison.json`. A saved Ollama reply is only reused for the prompt that produced it.

The full per-receipt results are in `backend/eval/receipts/eval_report.json` and `backend/eval/receipts/english/eval_report.json`.
