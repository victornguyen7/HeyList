# HeyList — Changelog

## 2026-10-27

Phase 1 of [IMPROVEMENTS.md](IMPROVEMENTS.md): trustworthy purchase verification.

### Added

- **MIT license** in `LICENSE`, as the hackathon requires an open source license.
- **Soft glass redesign** (decision 46; full write-up in [REDESIGN.md](REDESIGN.md)), from the Figma file's "Soft glass" (mobile) and "Web (soft glass)" screens. Phones get the mobile layout and laptops the website layout from the same link, by screen width:
  - Shared pieces in `app/ui.tsx` (buttons, cards, item rows, progress ring, avatars, web nav, page frame with the background glows) and `app/recent.tsx` ("Your lists" cards). Design assets in `public/ui/`.
  - Home: prompt card with idea chips (Trip, Party, Groceries, Move-in fill in an example), "Your lists" with progress rings, and on the web a "Spent this month" card. A mic button dictates the prompt where the browser supports it; the budget is read from the sentence (decision 47).
  - AI review: "AI made N items in X seconds", budget card with a bar, editable rows, "+ Add an item", and "Looks good, create list" pinned to the bottom on phones.
  - Progress: ring with done/total, stats (spent, still to get, receipts), Scan receipt and Pay buttons ("Pay $X" preselects the items you claimed), "Still to get" and "Done" lists. Tap an item's name to change its quantity or who buys it.
  - Money: spent together, equal share, budget, "Who paid what" bars with the equal share marked, receipt extras. On the web, Settle up sits beside it.
  - Settle up: "N payments and everyone's even", a card per payment (from → amount → to), then "How this was worked out".
  - Items, Receipts and History restyled to match (no Figma screens for them).
- **Less effort** (phase 5, decision 45):
  - Progress: the tick now means "done". Ticking asks what you paid (estimate filled in; blank if you don't know) and can be undone; items proven by PayPal or a receipt stay locked. Paying is its own mode: **Pay for items with PayPal** → choose items → **Pay $X with PayPal**, or **Cancel**. Quantity steppers and "who buys it" are hidden while paying.
  - AI review: rename any item, change its quantity, and **Add something missing**, before the list is created. An emptied name drops the item.
- **How this was worked out** (phase 4): Settle up explains every balance. The total spent and the equal share; then, for each person, a tap-to-open line "paid $X − share $Y = gets back / owes $Z", with each item behind "paid", its price and its proof ("Paid with PayPal", "On a receipt", "Marked bought by hand", "bought again with PayPal"); and what isn't counted (receipt extras, anything checked off without a name). The lines come from `money.split()`'s new `purchases` (decision 44), so they always add up.
- **Item notes** (phase 3): starting lists keep conditions and unclear amounts as a note on the item ("only if nobody has one"), shown in amber on the review screen, Progress and Items, and copied by Buy again. Named lists come back exactly as named, with their quantities; the same item listed twice with different amounts is kept twice and flagged (decision 42). **Schema:** `items.note`. Run `supabase/schema.sql` again.
- **AI evaluation** (phase 3): `backend/eval_starter.py` scores starting lists against 20 labelled cases in `backend/eval/starter_cases.json` (typed lists, speech-style transcripts, a transcribed photo list, situation descriptions). Paid; runs only with `--yes` (decision 43). The scorer has its own tests (`test_eval_starter.py`). It writes `backend/eval/eval_report.json`, with every reply, the scores and the token usage. First run (`gemma4:31b`): recall 62/63, quantities 12/13, notes 8/8, nothing invented.
- **Product framing** (phase 2): the README and SPEC open with the Need → Coordinate → Verify → Settle loop and a new tagline; the home page has a one-line promise; [SUBMISSION.md](SUBMISSION.md) has the demo script and Devpost text draft (decision 41).
- **Pending payments.** A capture that comes back `PENDING` is now stored on the order. Progress shows the payment as pending, holds its items (they can't be ticked, re-quantified or paid for again: `409 PAYMENT_PENDING`), and offers **Check again**. That calls the new `POST /api/orders/{id}/refresh`, which reads the order with `paypal.get_order()` and checks the items off if the payment has completed, or releases them if it was declined.
- **Proof labels.** Every item on Progress and Items says what its status rests on: "Paid with PayPal", "On a receipt", "Marked bought by hand" or "Payment pending at PayPal", and who paid. An open item is "Needed".
- **Estimates marked.** Open items' prices on Progress show as `~$4.00`, as on Items; a bought item shows what was paid.

### Fixed

- **A PayPal payment could drop out of the split.** When a receipt or a hand tick checked an item off while its buyer was on PayPal, the PayPal charge was only logged. Now (decision 39) the extra purchase is **refunded** to the PayPal buyer, for any quantity (`paypal.refund()`, recorded in `orders.refunds`, shown on Receipts and in the payment message). If the refund fails, the charge counts toward the buyer in the split (`boughtTwice`, with a note on Money).
- **Schema:** `orders.capture_id` and `orders.refunds`. Run `supabase/schema.sql` again in the Supabase SQL editor.

## 2026-10-24

### Fixed

- **Paying without a name.** The Pay button now needs the person to join first, as receipt scanning does; a payment with no buyer was left out of the split.
- **Starting-list cap.** 20 per hour across all clients. It was keyed on the client address, which behind the Next.js proxy and Render is the proxy, so it was already shared; now it says so.
- **Ollama timeout.** Calls time out after 120 s instead of never.
- **PayPal return.** After the capture, `?token=&PayerID=` is removed from the address, so a reload or shared link doesn't capture again and report a failure for a paid order.

## 2026-10-15

### Added

- **Pages.** Home (`/`), the list pages at `/lists/<id>` (Progress, Items, Money, Receipts, Settle up, as tabs) and History (`/history`). The old single list page `app/checklist.tsx` is split across them. History shows the lists this browser has opened (there are no accounts), spending by type and month, and "Buy again", which copies a list with its items unchecked. PayPal now returns the buyer to `/lists/<id>`.

- **Supabase storage.** Schema in `supabase/schema.sql`: lists, members, items, receipts, orders, invoices, and a private `receipts` bucket. Row level security is on with no policies, so only the backend's secret key can read or write. `backend/db.py` wraps it (`select`, `insert`, `update`, `delete`, `upload`, `download`).
- **Lists API** in `backend/main.py`: create, read and update lists; join as a member; add, edit and delete items; PayPal checkout for chosen items (`POST /api/lists/{id}/orders`), with prices read from the database.
- **AI starting lists.** `POST /api/lists/suggest` turns one sentence and an optional budget into a starting list that the person reviews before creating (`backend/llm.py` on Ollama, `app/starter.tsx`). Prices are per unit, and the review screen shows the estimated total and any amount over budget.
- **Item splitting.** Claim items ("who buys it"), share out unclaimed items evenly by estimated cost (`POST /api/lists/{id}/assign`), and see what each person paid, their equal share and who pays whom (`GET /api/lists/{id}/split`; `backend/money.py`, `app/split.tsx`).
- **Receipt scanning** (`backend/receipts.py`, `app/receipt-scan.tsx`):
  - The phone camera takes the photo, which is shrunk to 2000 px JPEG in the browser.
  - `POST /api/lists/{id}/receipts?memberId=` reads the receipt and proposes a list item for each line. Nothing is checked off yet.
  - `POST /api/receipts/{id}/confirm` applies the person's checked or corrected matches: items are checked off with the receipt prices and the scanner as buyer, and the other lines are saved as extras.
  - `GET /api/receipts/{id}/image` serves the stored photo.
- **Reading and matching** (decision 38):
  - **Reading:** AWS Textract is tried first, because it gives a confidence score per line. When Textract is unavailable (no permission, no keys, an outage), `read_with_ollama()` reads the photo with the Ollama model's vision. An unreadable photo is not retried.
  - **Matching:** `match_lines()` uses one text-only Ollama call. The model sees item names and receipt text only, never IDs or prices.
- **Spend guards:** 10 receipt scans per list per hour and 20 starting lists per client per hour (`429 TOO_MANY_REQUESTS`). A matching call takes at most 150 receipt lines and 300 list items (`RECEIPT_TOO_LONG`).
- **List page** (`app/checklist.tsx`): join by name (remembered in this browser), a who-buys-it picker per item, "Share out the rest evenly", a progress bar, scanning and the Money panel. Shared types, fetch helper and error messages live in `app/api.ts`.
- **`docs/RULES.md`:** Anthropic's rules for API keys (from Anthropic's support article, authentication docs, Commercial Terms and Usage Policy) and how this project applies them to the Anthropic, AWS and Ollama keys. `AGENTS.md` and the README point to it.
- **Spec and roadmap:** photo recognition of real objects, with options to learn and a plan (not built).
- **Tests:** `test_llm.py`, `test_money.py` and `test_receipts.py`, plus route tests in `test_main.py`, for 51 in total. None calls a paid service: Ollama is mocked and Textract is stubbed.

### Changed

- **Items have a quantity** (1–99). Checkout charges estimated price × quantity, and a captured order records the line total as `price_cents`.
- **Capture reports the capture's own status,** not the order's, so a pending or declined payment never checks items off.
- **The list ID lives in the URL** (`/?list=`), which is also PayPal's return address.
- **Removed:**
  - `backend/sample_list.py`. The route tests use an in-memory fake of `db` that reads its columns from `schema.sql`.
  - The `anthropic` dependency. The first version of receipt matching used Claude Haiku (decision 31); the owner chose to keep the Claude API out for now, so `ANTHROPIC_API_KEY` is unused.
- **Dependencies:** `boto3` 1.43.114 added (Textract).
- **New variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_REGION`.
- **Schema:** added `receipts.lines` and `receipts.confirmed_at`, applied to the live database.
- **`llm.json_reply()`:** pulls the JSON out of an Ollama reply, even inside a ```json fence. Starting lists and receipts share it.

### Fixed

- **Join could be undone.** The list page's first load could arrive after Join and replace the list with a copy without the new member, so the scan button said "add your name first". A late first load no longer overwrites a newer list (`app/checklist.tsx`).
- **Money panel could show an old total.** An older `/split` answer could overwrite a newer one, leaving the panel at "Spent $0.00" after confirming a receipt. Only the latest answer is used now (`app/split.tsx`).

### Tested live

All test lists and photos were deleted afterwards.

- **Ollama, on its own:**
  - Starting lists: a camping trip (26 items, $132 against a $150 budget) and a kids' party ($125 against $100; the AI ignores the budget, see issue 14).
  - Receipt scanning on a synthetic receipt: Textract was denied, so Ollama read all 6 lines and the $24.89 total exactly (1.4 s). It matched milk, bread, eggs and sunscreen, and left bananas and gum as extras (0.6 s).
- **Backend with the live Supabase database:**
  - The scan returned 200 and the photo came back byte-for-byte identical.
  - Confirm checked off the 4 items with the receipt prices and the scanner as buyer, and saved the extras.
  - A second confirm was refused (409).
  - The split was $19.76.
- **Web page** (Chrome at phone size, driven by Playwright from outside the project):
  - Join, photo upload, review, a correction by hand (gum -> toothbrush), then confirm.
  - Afterwards: 5 of 5 items checked off, Money panel at $21.75, no browser errors. This run found the two bugs under Fixed.
  - One misread: the photo, shrunk and compressed in the browser, made "20OZ" read as "200Z" (issue 23).
- **Not yet live:**
  - Textract: the IAM user lacks `textract:AnalyzeExpense` (issue 15).
  - Claude: not used. The key was valid but the account had no credit, so nothing was charged.

## 2026-10-14

- Added the FastAPI backend in `backend/`, with pinned dependencies in `backend/requirements.txt`.
- Added a hard-coded sample list (`backend/sample_list.py`) with server-side prices in cents, for testing before LLM or user-added items exist.
- Added PayPal sandbox orders (`backend/paypal.py`) on the Python PayPal Server SDK: create an order from item IDs, capture it, and report the capture's own status and the items bought (item IDs travel as SKUs).
- Added `POST /api/orders/{order_id}/capture` (`backend/main.py`) and a return page component (`app/paypal-return.tsx`) that captures after PayPal approval.
- Next.js now proxies `/api/*` to the backend (`BACKEND_URL`, default `http://127.0.0.1:8000`).
- Added `.env.example` (committed) listing every environment variable; `.env.local` stays ignored.
- `.gitignore` now ignores `__pycache__/`; previously committed cache files were removed from git.
- Added `GET /api/items` and `POST /api/orders`, and replaced the template home page with a checklist test UI (`app/checklist.tsx`): pick items, pay with PayPal, see them checked off on return. Page title is now HeyList.
- Items can be bought in quantity: a selection is `{item ID: quantity}` (1–99), sent to PayPal as each item's `quantity`; the test UI has −/+ buttons.
- Backend unit tests: `python -m unittest` from `backend/` (16 tests).

## 2026-10-12

- Initial commit from Create Next App (Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5).
- Added project docs: spec, architecture, decisions, roadmap, changelog, issues.
- Replaced the template README with the project README.
