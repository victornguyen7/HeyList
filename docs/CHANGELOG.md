# HeyList — Changelog

## 2026-10-28

### Added

- **"Shop this list for me"** (decision 61, phase 7C): on Progress, the button puts a circle on each open item; tick the ones to shop for (any number, starting with the ones you claimed), and the agent searches stores for them, checks each match with the AI, and proposes a cart that fits what is left of the budget. Items it can't fill are listed with a reason (not sold online, over budget, search failed). You remove or swap products, then pay for the whole cart with one PayPal payment; each price is read again from Channel3 first, and a changed total is shown before anything is charged. No order is placed with the stores.
- **Settle up with PayPal** (decision 60, phase 7B): each payment you owe on Settle up has **Pay Ann $X with PayPal**. The order's payee is Ann's PayPal account, so the money goes to her, not to HeyList. The amount comes from the current split on the server, and a stale one is refused (`409 SPLIT_CHANGED`). The first payment to someone asks for their PayPal email. A completed payment evens the balances, and Settle up lists it ("Ben paid Ann $30 · with PayPal"), with **Check again** for a pending one. **Schema:** a `settlements` table replaces the never-used `invoices`; run `supabase/schema.sql` again.
- **Live list updates** (issue 31, decision 59, phase 7A): a change on one phone (join, claim, tick, receipt, PayPal payment) shows on every other open page of the list within a moment, through a Supabase Realtime broadcast ping; the page reloads the list through the API, so no list data goes over the channel. Showing the tab again also reloads it.
- **Unreadable prices are asked, not guessed** (decision 57): a receipt line whose price Textract isn't sure of (under 90%) or couldn't read comes back blank, and the review screen asks for it ("The price couldn't be read. Type it from the receipt, or leave it blank"). A typed price is marked typed (`items.price_typed`), shown "(typed)" on Receipts, and left out of price memory. The Ollama reader is told to give no price rather than guess one.
- **Tax, tip and fees** (decision 57): receipts now read tax, tip, service charges, delivery fees and discounts (`receipts.fees`). The review screen lists them (asking for any it couldn't read) and checks that lines and fees add up to the receipt total. On Money and in the split, a receipt's fees are shared in proportion to the list items on it; the part for extras stays with the buyer. **Schema:** `receipts.fees` and `items.price_typed`; run `supabase/schema.sql` again.
- **English receipt eval** (`eval_receipts.py --english`, `eval_receipts.py compare`): 189 English receipts from [docjay131/receipts-ocr-dataset](https://huggingface.co/datasets/docjay131/receipts-ocr-dataset), scored per category, side by side with ReceiptQA in `backend/eval/receipts/comparison.json`. Results in [RECEIPT_EVAL.md](RECEIPT_EVAL.md).

### Fixed

- **Store prices checked at checkout** (issue 42, decision 58): a store price older than 10 minutes is read again from Channel3 when the PayPal order is created. If it changed, or the store stopped selling the product, the item is updated, the order is refused (`409 PRICE_CHANGED`), and Progress shows the new total so the buyer can pay again.
- **Done tick** (issue 40): white instead of near-black on the dark circle.
- **Receipt amounts:** `.98` was read as $98.00, and discounts printed `9.95-` or `($12.00)` as charges.
- **Receipt names:** when Textract mixes the names of neighbouring lines ("WINCO SNDWCH WT / WINCO HOMO MILK"), the name is taken from the printed row with the line's price.

### Changed

- **Members' emails stay on the server**: list pages get `hasEmail` instead, and joining again by name no longer replaces a saved email (decision 60).
- **Stack documented** (issue 2, decision 56): [ARCHITECTURE.md](ARCHITECTURE.md#stack) now lists every framework, library, service, browser API and tool in use, with its pinned version and what it's for; the README's Stack section matches. The browser uses Supabase only for login, and checkout keeps PayPal's hosted page.
- **PayPal tested live** (issues 25 and 37): on the sandbox, a payment approved on PayPal's page came back to the list page and was captured, and an item ticked by hand during checkout was refunded ($1.75, `COMPLETED`). The test showed that two captures at the same moment could lose a refund record (issue 45): a refund still in progress at PayPal is now asked for again, and refunds are merged into the order rather than overwritten.
- **Render always on:** `render.yaml` moves off the free instances, which slept after 15 idle minutes: `heylist-api` on Standard ($25/month, 2 GB) and `heylist-web` on Starter ($7/month). The site stays up whether or not the owner's computer is on.
- **Issues tidied:** 15 (Textract now works; tested on 289 receipts) and 28 (already fixed by decision 54) closed; 23, 26 and 41 brought up to date.
- **Issue 3 closed**: no API key in any tracked file or in git history; every key is read from the environment.

## 2026-10-27

Phases 1 to 6 of [IMPROVEMENTS.md](IMPROVEMENTS.md): trustworthy purchase verification through real prices and real products.

### Added

- **Find in stores** (phase 6C, decisions 50 and 51): on Items, an item can search real products through Channel3 (`backend/market.py`, `CHANNEL3_API_KEY`) and show up to 5 cards with photo, store and price. **Choose** reads the price from Channel3 again on the server and makes it the item's price, so "Pay with PayPal" charges it; "View at {store} ↗" links to the product. No order is placed with the store (Channel3's checkout isn't open yet). Routes `GET /api/items/{id}/products` and `POST /api/items/{id}/product`, capped at 100 searches an hour. **Schema:** `items.product`; run `supabase/schema.sql` again.
- **Store results checked by the AI** (decision 51): Channel3 matches words and sells no food, so "milk" returned face cleansers and "eggs" toys. Each search now goes through `llm.store_matches()` (one Ollama call), which keeps only products that are the item. Groceries say "No online store we search sells this. Buy it in person and scan the receipt."
- **Price memory** (phase 6B, decision 49): suggested prices on a new list come from the median of the last 10 prices really paid for that item name (PayPal or a receipt; hand ticks don't count), then a chosen store price, then the AI's guess. The review screen says which ("paid before", "store price", "AI guess"); only guesses get a `~`. Buy again uses the paid unit price. **Schema:** `items.name_key` (generated, indexed); run `supabase/schema.sql` again.
- **64 example lists and a bigger eval** (phase 6A, decision 48): `backend/examples.json` holds 64 owner-written lists; the eval grew to 30 cases. Measured on `gemma4:31b`: without examples 96/98 items recalled, with the 3 closest examples 91/98 (and one empty list), so examples are **off** (`EXAMPLE_COUNT = 0`). `eval_starter.py --examples` repeats the comparison.
- **Lists show at once** (decision 55): Home, History and a list's pages show the copy of each list saved in this browser, then the fresh one replaces it. Every list response now includes its `split`, so Money and Settle up no longer wait for a second request.
- **`GET /api/lists?ids=`**: every list this browser remembers in one request (six queries run at the same time), used by Home and History (decision 54).

### Changed

- **Render:** `CHANNEL3_API_KEY` added to the backend in `render.yaml`; Python 3.14.9 (as in local development). The web proxy waits up to 2 minutes for a backend that is waking up (`experimental.proxyTimeout`), instead of 30 seconds.

- **Optional email login** (decision 52): `/login` emails a magic link (Supabase Auth). Logged in, "Join as <name>" joins a list in one tap and you're the same person on every device; guests still type a name. New column `members.user_id`: run `supabase/schema.sql` again. New dependency `@supabase/supabase-js` 2.117.3; the web service now needs `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` at build time.
- **Account lock** (decision 53): only the logged-in person can tick off, untick, pay or scan/confirm receipts as their member (`403 NOT_YOURS`); guest members work as before.
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

- **Old lists disappeared from Home and History** (issue 43). Nothing was lost: the backend shared one HTTP/2 connection to Supabase across threads, and lists loaded at the same time failed with a 500, so History hid them. The backend now uses HTTP/1.1 (`db.py`), History loads in one request, and if loading fails it says so instead of looking empty.
- **Scanned but unconfirmed receipts were invisible** (issue 32). Receipts now lists them under "Scanned but not confirmed yet" with **Finish checking**.
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
