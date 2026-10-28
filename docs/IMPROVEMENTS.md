# HeyList — Improvement options: pros and cons

The five improvement areas suggested for HeyList, each weighed against the code as it stands on 2026-10-27. The deadline is 12 November 2026, so there are about 16 days left ([HACKATHON.md](HACKATHON.md)). Built features are listed in [ARCHITECTURE.md](ARCHITECTURE.md) and [PayPal.md](PayPal.md); open problems are in [ISSUES.md](ISSUES.md).

## Progress

| Phase | Area | Status |
|---|---|---|
| 1 | 3. Trustworthy purchase verification | Done 2026-10-27 (see below) |
| 2 | 1. Core promise | Done 2026-10-27 (see below) |
| 3 | 2. AI reliability (narrow) | Done 2026-10-27, evaluated (see below) |
| 4 | 5. Group accounting (narrow) | Done 2026-10-27 (see below) |
| 5 | 4. Less effort (narrow) | Done 2026-10-27 (see below) |
| 6 | Real prices and real products (AI examples, price memory, Channel3) | Built 2026-10-27; eval run (examples didn't help, see below); live Channel3 test and schema run not done yet |
| 7 | Closing the loop: realtime, settle up with PayPal, agent shopping, sponsor tools | Planned 2026-10-28 (see below) |

### Phase 1 — purchase verification (done)

- **Three states, visible.** Needed / Payment pending at PayPal / verified ("Paid with PayPal", "On a receipt"), plus "Marked bought by hand" for a tick with no evidence. Shown on Progress and Items, with who paid (`proofLabel()` in `app/api.ts`).
- **Pending is real now.** A `PENDING` capture is stored, holds its items, and has a **Check again** button (`POST /api/orders/{id}/refresh`, `paypal.get_order()`). Decision 40, issue 36.
- **Overlap bug fixed.** When a PayPal payment goes through for an item a receipt or hand tick covered first: the extra purchase is refunded to the PayPal buyer, for any quantity; a failed refund counts in the split and is flagged on Money. Decision 39, issue 37. Needs `supabase/schema.sql` run again (`orders.capture_id`, `orders.refunds`).
- **Estimates marked** with `~` on Progress.
- **Tests:** 64 pass (new: pending holds items, pending then completed, pending then declined, get_order, refund request, single item refunded once, every unit of a multi-unit item refunded, failed refund still counted). `tsc` and `eslint` are clean.
- **Not checked live:** the new UI was not run against Supabase or the PayPal sandbox in this phase. A sandbox capture rarely comes back `PENDING`, so that path is covered by unit tests only.

### Phase 2 — core promise (done)

- **Thesis:** "Turn everyday needs into shared lists, and know what really got done." Used in the README, SPEC, the page metadata, and a one-line promise on the home page ("Say what you need. Share who buys what. See what really got done.").
- **README** now opens with the loop (Need → Coordinate → Verify → Settle), with what is built and what is planned for each step. The feature list no longer presents voice, photo and reuse as built.
- **[SUBMISSION.md](SUBMISSION.md):** the 2:40 camping-trip demo script, scene by scene, with timings and the judging criterion each scene serves; a pre-recording checklist; a draft of the Devpost text and the Tools section.
- **Decision 41:** one loop, one demo scenario; the product stays general (decision 2).
- **Not done:** the video itself, the `LICENSE` file, and the hosted URL. The script avoids voice and invoices, which aren't built.

### Phase 3 — AI reliability, narrow (done)

| Challenge (area 2 table) | Now |
|---|---|
| Quantities | Prompt: keep every stated quantity ("two packs of water" → water × 2) |
| Duplicates | Same name and quantity: dropped as a repeat. Same name, different quantities: both kept, flagged "listed twice with different amounts; check how many" (not added up, not dropped) |
| Ambiguity | Unknowable amounts get a best-guess quantity plus a note ("how many? enough snacks for 4 people") |
| Conditions | Kept as a note ("only if nobody has one"); the item stays on the list |
| Named lists | A list the person typed or said comes back exactly: nothing added |
| Estimated prices | Already marked `~` (phase 1) |
| Receipt matching | Not changed (issue 39) |

- **Notes are shown** in amber on the review screen, Progress and Items, and carried by Buy again. `items.note` (≤ 200 characters); run `supabase/schema.sql` again.
- **Evaluation:** `backend/eval_starter.py` and 20 labelled cases: 12 named lists (typed, speech-style with filler and self-corrections, a transcribed photo list, two sizes of one product) and 8 situation descriptions. It reports item recall, quantity accuracy, conditions and unclear amounts kept, and invented items (named lists only). **First run, 2026-10-27, model `gemma4:31b`, owner-approved:**

  | Measure | Score |
  |---|---|
  | Item recall | 62/63 (98.4%) |
  | Quantity accuracy | 12/13 (92.3%) |
  | Conditions and unclear amounts kept as notes | 8/8 |
  | Invented items on named lists | 0 |
  | Failed or malformed replies | 0 of 20 |
  | Cost | 20 calls, 11,007 input and 5,483 output tokens |

  The two misses: "a dozen eggs" became eggs × 12 (the label expected one carton, which is debatable), and the kids' party list left out candles. The full replies are in `backend/eval/eval_report.json`. One run of 20 cases labelled by the team: indicative, not proof (issue 38).
- **Tests:** 69 pass (new: notes kept and cleaned, repeats vs different amounts, note stored and length-checked, the scorer, the case file's shape).
- **Not done:** photo-of-a-list input and voice are still unbuilt; the "photo list" case is a typed transcript.

### Phase 4 — group accounting, narrow (done)

The questions from area 5, and where Settle up now answers them:

| Question | Answer on the page |
|---|---|
| Which items are covered, which are still open? | Items tab (status and proof per item); Money's "Still to buy" |
| Who actually paid for each item? | "How this was worked out": each person's purchases, with the proof of each |
| How was each share calculated? | "$X spent on list items, shared equally by N people: $Y each", plus a note when odd cents don't divide evenly |
| Can everyone trace the balance to the purchases? | Per person: paid − share = gets back / owes, and the items that make up "paid" |

- Built in `money.split()` (`purchases` per member), so the lines on screen are the same numbers the transfers are computed from (decision 44). New test: every member's purchases add up to their paid amount, and paid − share = balance.
- Says what isn't counted: receipt extras (personal) and anything checked off without a name.
- One collapsed box per person (`<details>`), so the page stays short until someone wants the detail (decision 7).
- **Tests:** 70 pass. `tsc` and `eslint` clean. Not checked in a browser.
- **Not done:** PayPal invoices for the transfers (the bigger PayPal-prize item) and weighted shares (issue 18).

### Phase 5 — less effort, narrow (done)

| Moment (area 4) | Now |
|---|---|
| Opening the site | Unchanged: the starter is the home page, with no category, settings or onboarding. Phase 2 added one line saying what HeyList does |
| Turning input into a list | The review screen is editable: untick, rename, change quantities, add missing items. Corrections happen before anything is saved |
| Checking items off | The tick means "done" (it asks what you paid, and can be undone). PayPal is a separate mode, so the plain checklist shows no payment controls until someone asks to pay |

- **Before:** there was no way to tick an item off by hand on Progress; the only checkbox meant "select to pay". The backend has always supported hand ticks (`PATCH /api/items/{id}` with `checked`, `memberId`, `priceCents`).
- Items proven by PayPal or a receipt can't be unticked on Progress (the backend already refuses PayPal ones with `409 ITEM_PAID`).
- **Checks:** `tsc` and `eslint` clean; 70 backend tests pass (no backend change in this phase). **Not checked in a browser**, and the frontend has no tests, so try the tick prompt and the pay mode on a phone before recording.
- **Not done:** voice (the "one big talk button", decision 7), the join form on every tab (issue 34), and timing the three measures with real users. The dark redesign is still the owner's call.

### Phase 6 — real prices and real products (built; Channel3 checked live)

**Goal:** the AI suggests what to buy, prices come from what people really paid through PayPal or from real stores, and a person can choose a real product and pay for it with PayPal. One story for judges: *Need → real product → PayPal → proof → settle*, each step feeding the next.

**Not doing: fine-tuning a model.** Considered and dropped on 2026-10-27. The eval is already at 62/63 item recall, so there's little left to gain. There's no clean open dataset of "occasion → what to buy". A fine-tuned model can't run on Ollama's cloud, so it would need its own paid hosting. And it doesn't touch PayPal, which the rules say must be central ([HACKATHON.md](HACKATHON.md)). The three steps below get most of the benefit for much less.

**Owner's choices (2026-10-27)**

| Question | Answer |
|---|---|
| How is a found product bought? | With PayPal, at the product's real price: the price and store link are saved on the item, and the existing "Pay with PayPal" charges that price. The store link is shown too |
| When does HeyList search stores? | On demand, per item ("Find in stores"), not automatically for every suggested item |
| Which prices does price memory trust? | Proven prices (PayPal captures, confirmed receipts) first, then Channel3 store prices |

#### Built (2026-10-27)

| Part | What was built | Differs from the plan |
|---|---|---|
| 6A | `backend/examples.json`, sent as example turns by `starting_list()`; 10 new situation cases in the eval (30 in all); the "dozen eggs" quantity check dropped (1 carton and 12 eggs are both right); `eval_starter.py --examples` to compare (examples are off in the app after the eval) | **Three fixed examples, not "the 2 closest of 15".** Tried first: with 15 examples, word overlap gave near-random picks (the kids' party got "home office" because both say "home"). The examples teach the shape of an answer, so the same three are always sent (decision 48) |
| 6B | `remember_prices()` in `backend/main.py` on every suggestion; `items.name_key` (generated, indexed); the review screen shows "paid before", "store price" or "AI guess"; Buy again uses the paid unit price (issue 30 closed) | The source shows on the review screen only. After the list is made, Items shows a store price without `~` |
| 6C | `backend/market.py` (`httpx`, `POST /v1/search` and `GET /v1/products/{id}`), `GET /api/items/{id}/products`, `POST /api/items/{id}/product`, `items.product`, "Find in stores" on Items (`app/store-search.tsx`) | One cap of 100 searches an hour for everyone, not 30 per list (a per-list cap is easy to get round by making lists, as for suggestions). No SDK: two REST calls |

- **Tests:** 84 backend tests pass (new: examples sent and valid, price memory sources and median, hand ticks ignored, a price memory failure still returns the list, product mapping with the cheapest in-stock USD offer and Decimal cents, unsafe links dropped, search capped at 5, price read from Channel3 and not the request, PayPal charges it, rename or re-price drops the product, bought or pending items refused, 502 and the cap). `tsc` and `eslint` are clean on the changed files.
- **Not done yet:**
  - A live Channel3 call, waiting for the owner's approval. The response shape was taken from Channel3's OpenAPI spec, not from a real reply.
  - Running `supabase/schema.sql` on the live database (`items.name_key`, `items.product`).
  - Trying "Find in stores" in a browser.
  - The demo scene in SUBMISSION.md.

#### 6A eval result (2026-10-27, `gemma4:31b`, owner-approved, 60 calls)

The owner added 61 example lists, giving 64 in `backend/examples.json`. Their kinds were mapped onto the five app kinds. Each request is sent the 3 closest examples by word overlap. The 14 that are near-copies of eval cases are marked `evalOverlap` and left out of the eval, so it ran with 50.

| Measure (30 cases) | Without examples | With the 3 closest |
|---|---|---|
| Item recall | **96/98** | 91/98 |
| Quantity accuracy | 12/12 | 12/12 |
| Conditions and unclear amounts kept | 8/8 | 8/8 |
| Invented items on named lists | 0 | 0 |
| Failed or malformed replies | 0 | 0, but one empty list |
| Items per reply, on average | 7.7 | 6.2 |
| Tokens (in / out) | 16,447 / 9,412 | 37,117 / 5,690 |

**The examples did not help.** Most of the difference is one reply: "Basics for my first apartment kitchen" came back with no items (0/4). Its examples were a first aid kit, a dorm move and an apartment move, which share "first" and "basic". Leaving that case out, the two runs are nearly equal (93/94 without, 91/94 with). What the run shows:

- **Word overlap picks off-topic examples.** Halloween got an earthquake kit; snow day got a day hike and a date night ("home", "two" and "day" dominate).
- **The examples cap list length.** Every example has 6–8 items, and replies became shorter, dropping candles (kids' party) and pumpkins (Halloween).
- **They cost more**: 2.3 times the input tokens.
- **Named lists were unaffected**: 12/12 cases full marks in both runs.

One run each, labelled by the team: indicative, not proof (issue 38). Reports: `backend/eval/eval_report.json` (without examples) and `backend/eval/eval_report_examples.json` (with examples; it also records which examples each case was given).

**Decision (owner, 2026-10-27): examples are off.** `llm.EXAMPLE_COUNT = 0`, so requests are sent with no examples, as in the 96/98 run. The 64 lists stay in `backend/examples.json`. `eval_starter.py --yes` measures what the app does; `--examples` sends the 3 closest for a comparison. Before turning them back on: pick by embeddings rather than shared words, and lift the 8-item cap on the lists.

#### 6A — curated examples in the prompt (about 1 day)

- `backend/examples.json`: about 15 short examples (camping trip, kids' party, potluck, moving house, new baby, weekly groceries…) as request → the list we'd want, plus 2 named-list examples that show "nothing added". Written by the team; the owner reviews them.
- `starting_list()` picks the 2 examples closest to the request by word overlap (plain Python, no embeddings, no extra AI call) and sends them as example turns before the real request. About 600 more input tokens per call.
- **The eval must stay honest:** no example may repeat an eval case. Add about 10 new situation cases to `backend/eval/starter_cases.json` (there are only 8 today) and fix the "dozen eggs" label.
- **Measure:** run the eval on the new 30 cases without examples, then with them: 2 × 30 = 60 paid Ollama calls, **only with the owner's approval** (RULES.md, decision 43). Report both runs here.
- Decision 48.

#### 6B — price memory (about 1–1.5 days)

- **Where prices come from:** items checked off with proof (`order_id` or `receipt_id`) and a `price_cents`. The unit price is `price_cents ÷ quantity`. Hand ticks are not used: those prices are self-reported. Once 6C ships, the store price of a product someone chose on an item counts too, ranked below proven prices.
- **How items are matched:** a new `items.name_key` column (`lower(btrim(name))`, generated by Postgres, indexed), and an exact match on it, across all lists. Only names and prices are read, never who bought what. `ponytail:` exact names only ("water bottle" ≠ "water bottles"); add plural or fuzzy matching if too few prices match.
- **How it's used:** done in code, not in the prompt (decision 10). After the AI replies, each suggested item takes the median of the last 10 proven prices for its name; with none, the latest store price; with neither, the AI's estimate. One query per suggestion. Each item gets a `priceSource`: `paid`, `store` or `estimate`.
- **On screen:** the review screen and Progress say where each price came from: "$3.49 · paid before", "$3.29 · at Target", "~$4.00 · AI guess". The over-budget check (decision 34) then works on real prices, which helps issue 14.
- **Buy again** uses the paid price where there is one, which closes issue 30.
- Tests: the median, proven-only (hand ticks ignored), the fallback order, Buy again.
- Decision 49. `supabase/schema.sql` must be run again.

#### 6C — find real products with Channel3 and pay with PayPal (about 2–3 days)

- **What Channel3 can and can't do today** (checked on [trychannel3.com/developers](https://trychannel3.com/developers), 2026-10-27): product search with prices, merchant offers and buy links; a free tier. Its own checkout is "coming soon", so HeyList can't place an order with the store.
- `backend/market.py`: `search(name)` returns up to 10 products (title, image, store, unit price in cents, link, product ID, category), calling the REST API with httpx and `CHANNEL3_API_KEY` (no SDK needed; checked live 2026-10-27).
- **Results are checked before they're shown** (added after live testing, decision 51): Channel3 matches words and sells no food, so "milk" returned face cleansers and "eggs" toys. `llm.store_matches()` (one Ollama call per search) keeps only the products that are the item; at most 5 are shown. Groceries now say no online store sells them. Live check: milk 0 kept, eggs 0, sunscreen 10 of 10, paper towels 10 of 10, toddler milk on a baby list kept.
- `GET /api/items/{id}/products`: searches by the item's name. Capped with `allow()`: 100 searches an hour for everyone (a per-list cap is easy to get round). Errors map to `502 MARKET_UNAVAILABLE`.
- `POST /api/items/{id}/product` with `{productId}`: **the server fetches the price from Channel3 again** and never takes it from the browser (decision 21). It then saves `items.product` (a jsonb with title, store, link, image, price and when it was fetched) and sets `est_price_cents` to that price. It refuses an item that's already checked off or held by a payment. Choosing nothing keeps the AI estimate.
- **Frontend:** a "Find in stores" button on an item opens up to 5 product cards (photo, name, store, price). "Choose" saves the product. The item then shows the product, "$3.29 at Target" and "View at Target ↗". "Pay with PayPal" works as it does now, at the store price.
- **Be honest in the demo and docs:** the PayPal sandbox payment goes to HeyList's sandbox merchant. No order is placed with the store. The pitch says: "When Channel3 checkout opens, HeyList places the order; today it gives the real price and the link." Channel3's affiliate links are a possible business model (Impact criterion).
- Tests: a fake Channel3 client; search results mapped and capped at 5; the price taken from the server lookup, not the request; a checked-off or held item refused; the rate limit; a Channel3 failure gives 502.
- Decision 50. `supabase/schema.sql` must be run again. Sponsor prize: Best Use of Channel3; it also supports Best Use of Agentic Commerce.

#### Order and blockers

1. **6A** first: no new services, and it gives a measured result.
2. **6B** with proven prices only.
3. **6C**, which then adds store prices to price memory.

About 5 days in all, leaving about 10 for the hosted URL, the live sandbox payment (issue 25), the video and the write-up.

- **Key:** `CHANNEL3_API_KEY` is in `.env.local` and `render.yaml`. Live search and lookup checked 2026-10-27. The backend only reads its shell's environment, so load `.env.local` before starting it.
- **Approvals:** the two eval runs (60 Ollama calls) and the live Channel3 and store-match checks were approved and run on 2026-10-27.
- **Demo script:** [SUBMISSION.md](SUBMISSION.md) gets a "find it in a store" scene before the PayPal payment.

### Phase 7 — closing the loop, agent shopping and sponsor tools (planned)

Written 2026-10-28, after a review of the code, [HACKATHON.md](HACKATHON.md) and the sponsor prizes. About 15 days are left before the deadline (12 November 2026). Keep the last 4 of them for the hosted URL check, running `supabase/schema.sql` on the live database, the video and the write-up.

**Why this phase:** the loop is built and tested, but three things are weak:

- **The demo's ending.** Settle up ends on text ("Ben → Ann $X"), and [SUBMISSION.md](SUBMISSION.md) says not to show invoices.
- **The agentic story.** Finding real products is manual, one item at a time.
- **The sponsor prizes.** Several have no entry: AG Grid has the biggest sponsor pool (5 prizes, $10,000), and APIMatic has 3 prizes.

#### Overview

| Part | What | Size | Prizes and criteria it helps | Priority |
|---|---|---|---|---|
| 7A | Realtime list updates | 0.5–1 day | Design, Presentation, Best Demo Delivery | Do, first |
| 7B | Settle up with PayPal: pay the person you owe | 1.5–2 days | Best Use of PayPal + AI, Technical, Presentation | Do |
| 7C | "Shop this list for me" agent | 2–3 days | Best Use of Agentic Commerce, Best Use of Channel3, Innovation | Do |
| 7D | AG Grid ledger | About 1 day | Best Use of AG Grid | If time allows |
| 7E | PayPal webhooks on Render | About 1 day | Technical, Best Use of Render | If time allows |
| 7F | APIMatic portal or SDK, and a Postman collection, for HeyList's API | About 0.5 day | Best Use of APIMatic, documentation | If time allows |

Order: 7A, 7B, 7C, then 7D–7F as time allows. 7A–7C come to about 4–6 days.

#### 7A — realtime list updates (issue 31)

- **Problem:** a list loads once. Changes made by someone else show only after a reload (issue 31). The demo uses two browsers, so this shows on camera.
- **Plan:** one Supabase Realtime **broadcast** channel per list (`list:<id>`), through the `@supabase/supabase-js` client the browser already loads for login.
  - After any change the client makes (join, claim, tick, receipt confirm, capture), it sends a "changed" message.
  - Every other open page of that list refetches `GET /api/lists/{id}` when it gets the message.
- **Why broadcast, not Postgres changes:** a Postgres changes feed on `items` needs Row Level Security policies that let anonymous users read items. Link-shared lists would then be readable by anyone. A broadcast carries no list data, only a "changed" ping, so nothing leaks.
- **Edge cases:** debounce the refetch, so several messages in a row cause one request. Refetch when the tab becomes visible again, so a missed message heals itself.
- **Demo value:** Ben claims the tent and it appears on Ann's screen. Ann pays and Ben's list ticks off.
- **Tests:** none in the backend (no backend change). Try it with two browsers before recording.

#### 7B — settle up with PayPal: pay the person you owe

- **Problem:** the Invoicing plan in [PayPal.md §6](PayPal.md) sends money to the wrong person. An invoice is issued by HeyList's own sandbox merchant account (the app's client ID), so Ben's payment would go to HeyList, not to Ann. Payouts have the same problem: they send money *from* HeyList.
- **Plan:** a **Pay Ann $X with PayPal** button on each Settle up payment. It creates an Orders API order with `purchase_units[0].payee.email_address` set to the PayPal email of the person owed, so the money goes straight from Ben to Ann.
  - It reuses `paypal.create_order()` and `capture_order()`, the idempotency keys and the return-page handling.
  - The order has no list items, only one amount: "HeyList: settle up for <list name>".
- **Amount comes from the server:** the amount is read from `money.split()`'s transfers on the server, never from the browser (decision 21). The route refuses an amount that no longer matches the current split.
- **Emails:** ask for the PayPal email of the person owed when the first payment to them is started, and store it in `members.email` (already in the schema).
- **Tracking:** store settlements as their own rows: debtor, creditor, amount, PayPal order ID, status. The `invoices` table can be reused or renamed. The split counts a completed settlement, and Settle up shows "Ben paid Ann $X with PayPal".
- **Check first:** in the sandbox, confirm that a payee override to a sandbox **personal** account is accepted. If it isn't, ask Ann for a sandbox business account, or fall back to showing the transfer only. Record the result as a new decision.
- **Demo:** the video ends with a real PayPal payment between friends instead of a line of text. Update the Settle scene in [SUBMISSION.md](SUBMISSION.md).
- **Tests:**
  - the payee is in the create request;
  - the amount comes from the split, and a stale amount is refused;
  - capturing twice records one settlement;
  - the split after a settlement is even.

#### 7C — "Shop this list for me" agent

- **Problem:** finding real products is manual. Each item needs its own **Find in stores** and **Choose**. That's the strongest place to show agentic commerce, and today it isn't agentic.
- **Plan:** one button on Progress or Items, **Shop this list for me**, for the person's claimed items or all open items.
  1. For each open item, run a Channel3 search (`market.search()`) and filter it with `llm.store_matches()`, as Find in stores does today.
  2. Pick one product per item so the total fits the remaining budget, in code, not by the AI (decision 10). Prefer the closest match, then the cheapest in-stock offer.
  3. Show the plan: each chosen product with store, price and photo. Each skipped item gets a reason ("no online store sells milk; buy it in person and scan the receipt", "over budget").
  4. The person removes or swaps items, then taps **Pay $X with PayPal**. That is one PayPal order for everything, with every price read from Channel3 again on the server (decision 50).
- **Human in the loop:** the agent never pays. It proposes a cart, and the person approves it on PayPal's page. That's the safe version of agentic commerce, and it's the point to make to the judges.
- **Limits:**
  - at most 10 items a run, searched in parallel;
  - it counts against the 100 searches an hour cap;
  - each run costs one Channel3 search and one Ollama call per item. Every live test needs the owner's approval ([RULES.md](RULES.md)).
- **Honest wording:** as for 6C, no order is placed with the stores. The sandbox payment goes to HeyList's merchant account until Channel3's checkout opens.
- **Demo:** it replaces the single-item Find in stores scene. "Shop the rest of our list for $90" → plan → PayPal.
- **Tests:**
  - budget fitting;
  - skipped items have reasons;
  - prices come from the server lookup;
  - a Channel3 failure on one item doesn't stop the rest;
  - bought or pending items are left out.

#### 7D — AG Grid ledger (if time allows)

- **What:** a **Ledger** page in the website layout, with one row per money event across the lists this person has opened:
  - PayPal capture;
  - refund;
  - receipt line;
  - receipt fee (tax, tip, discount);
  - hand tick;
  - settlement (7B).
- **Columns:** date, list, item, who, amount, proof, PayPal order or receipt ID.
- **Features used:** group by person, list or month; filter by proof type; totals in the group rows; CSV export.
- **Why it's genuine:** the data already exists (History loads every list in one request, decision 54), and the grid answers "where did our money go" across lists. It extends History and Money rather than being added for the prize.
- **Phones:** keep the current cards on phones. AG Grid is for the laptop layout only (decision 46).
- **Check first:** the AG Grid Community licence covers what's used (grouping with totals may need Enterprise, which has a trial licence for evaluation). Add the package and its version to [ARCHITECTURE.md](ARCHITECTURE.md#stack).

#### 7E — PayPal webhooks on Render (if time allows)

- **What:** `POST /api/paypal/webhook` for:
  - `PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.CAPTURE.DENIED`: a pending order completes or is released without anyone tapping **Check again**;
  - `PAYMENT.CAPTURE.REFUNDED`: a refund made outside HeyList is recorded on the order.
- **Safety:** verify every event with PayPal's verify-webhook-signature call before acting on it. Handle each event once (store the event ID). Reuse the conditional updates from capture.
- **Setup:** register the webhook in the sandbox app for the Render URL, and add `PAYPAL_WEBHOOK_ID` to `render.yaml` and `.env.example`.
- **Keep Check again** as the fallback for local development, where PayPal can't reach the backend.
- **Tests:**
  - a bad signature is refused;
  - a repeated event is handled once;
  - pending to completed;
  - pending to denied;
  - an outside refund.

#### 7F — APIMatic portal or SDK, and a Postman collection (if time allows)

- **APIMatic:** import FastAPI's `/openapi.json` into APIMatic and generate a developer portal (and optionally a TypeScript SDK) for HeyList's own API. Link it from the README. Today APIMatic shows up only as the generator of PayPal's SDK and the Context Plugin (decision 23). This is a direct use, for the Best Use of APIMatic prize.
- **Before generating:** give the FastAPI routes summaries and response models where they're missing, so the portal is readable.
- **Postman:** export the same OpenAPI file as a public Postman collection, with a sandbox environment (no keys in it). It helps judges try the API, and the README already lists Postman as a tool.

#### Not doing in this phase

| Idea | Why not |
|---|---|
| PayPal Invoicing for settle-up | The invoice comes from HeyList's merchant account, so the money doesn't reach the person owed. 7B replaces it |
| Bryntum | A scheduler or Gantt chart has no natural place in HeyList |
| Photo recognition | Spec only ([SPEC.md](SPEC.md#photo-recognition-planned-spec-and-learning-plan-only)), and too big for the time left |
| Dark ("Midnight") theme, PayPal Checkout JS SDK buttons | Polish that the judging criteria barely score; after the hackathon |

#### The demo after this phase

One sentence → AI list → **the agent shops the rest within budget (7C)** → PayPal → items checked off live on the other phone (7A) → Ben's receipt → **Ben pays Ann with PayPal (7B)**. Every step is PayPal and AI working together. Update [SUBMISSION.md](SUBMISSION.md) once each part is built and checked live.

#### Blockers and approvals

- **Paid calls:** live tests of 7C (Channel3 and Ollama) need the owner's approval ([RULES.md](RULES.md)).
- **Live sandbox:** 7B's payee check needs a second sandbox personal account. 7E needs the deployed Render URL.
- **Schema:** 7B adds a settlements table, or changes `invoices`. Run `supabase/schema.sql` again on the live database.
- **Decisions to record:** the realtime approach (7A), payee orders over invoices (7B), the agent's budget rule and human approval (7C).

## All phases

All five recommended areas are done in their narrow versions; phase 6 is built (above). Left for the deadline (12 November 2026): the hosted URL, one live sandbox payment (issue 25), running `supabase/schema.sql` on the live database (`orders.capture_id`, `orders.refunds`, `items.note`), and the demo video ([SUBMISSION.md](SUBMISSION.md)).

## Summary

| # | Area | Already in the code | Size of the work | Judging criteria it helps | Verdict |
|---|---|---|---|---|---|
| 1 | Core promise: need → coordinate → verify | Each step exists (starter, claims, PayPal and receipts) | Small, mostly wording and the demo script | Presentation, Impact, Design | **Do it**, it costs almost nothing |
| 2 | AI reliability, with an evaluation set | Field checks in `starting_list()` and `match_lines()`; mocked unit tests only | Medium to large; the evaluation runs are paid calls | Technical, Innovation | **Do a narrow version** |
| 3 | Trustworthy purchase verification | Strong backend; weaker UI; two real gaps | Small to medium | Technical, Best Use of PayPal + AI | **Do first** |
| 4 | Less effort in the UX | Home page goes straight to the starter; the Progress row is crowded | Medium | Design, Presentation | **Do the Progress-page part** |
| 5 | Fair, traceable group accounting | `money.py` split and settle exist; no per-item trace | Small to medium | Impact, Design | **Do the "explain the balance" view**; invoices only if time allows |

Suggested order: 3, then 1 (alongside the others), then the narrow version of 2, then 5, then 4. This follows the suggested ranking, but moves the cheap framing work (1) up and keeps 2 small because of the cost rule.

---

## 1. Sharpen the core promise: from intention to completion

The idea is to present HeyList as one loop (Need → Coordinate → Verify) instead of separate features, and to build the demo around one shared camping trip.

**Pros**
- The loop is already built from start to finish: `app/starter.tsx` (need), claiming and "Share out the rest evenly" on `app/lists/[id]/page.tsx` (coordinate), and PayPal capture plus receipt confirmation (verify). Very little new code is needed.
- It directly helps the **Presentation** criterion ("what problem is solved, who it's for") and gives the under-3-minute video a clear plot.
- It ties the AI and PayPal together, which is what the **Best Use of PayPal + AI** prize asks for.
- The starter's placeholder already says "Weekend camping trip for 3 friends", so the demo scenario fits the product's current wording.

**Cons**
- Decision 2 keeps HeyList general-purpose. Telling the story through one scenario risks the app looking like a camping app. The fix is to keep the product general and make only the demo specific.
- "Design principle: every step keeps the context of the previous one" is not fully true today: estimates from step 1 don't show up as estimates once an item is paid (see area 3), and a stalled payment loses its state.
- On its own this is framing, not engineering, so it does nothing for the **Technological Implementation** score.

**Codebase cost:** the README and Devpost description, home-page copy, and the demo script. No schema change.

---

## 2. Make AI reliability your technical differentiator

The idea: keep quantities, merge duplicates correctly, flag ambiguity ("enough snacks"), keep conditions ("if nobody has one"), label estimates as estimates, and refuse weak receipt matches. Measure all of this with an evaluation set of 30–50 examples.

**What the code does today**
- `STARTER_SCHEMA` has only `name`, `quantity` and `estPriceCents`. There is nowhere to put a note, a condition or an "unclear" flag, so "maybe a flashlight if nobody has one" can only become a plain flashlight.
- Duplicates are removed by exact lower-case name (`seen` in `starting_list()`), so "Water" and "water bottles" both survive, and the second "water" is dropped even when it has a different quantity.
- The prompt is written for describing an occasion ("The user describes a trip, occasion, or event"), not for an explicit messy list like the voice example. Voice input isn't built yet (ROADMAP), and neither is turning a photo of a list into items.
- `match_lines()` already says "Only match when the line really is that item", and it drops matches that are out of range. It has no confidence or "unsure" result, though.
- `test_llm.py` has 4 tests, all on mocked replies. Nothing measures what the real model gets right.

**Pros**
- This is the most convincing answer to "is the AI meaningful?", and it scores on both **Technological Implementation** and **Innovation**. Numbers like "quantity accuracy 92% on 40 cases" are rare in hackathon demos.
- Some parts are cheap, deterministic code that fits decision 10 (logic in code, not AI). One example is labelling estimates `~$4.00`, which the Items page already does but the Progress page doesn't. Another is a `note` field on items.
- Better extraction feeds everything after it: correct quantities lead to correct PayPal totals (price × quantity, decision 29), and those lead to correct splits.
- The evaluation set can be a plain JSON file plus one script, which matches the project's small-test style (unittest, no framework).

**Cons**
- **Running the evaluation means paid API calls.** [RULES.md](RULES.md) requires asking the owner before any real Ollama, AWS or Anthropic call. 50 cases × several prompt versions is a real number of calls, and each run needs approval.
- Writing 30–50 hand-labelled examples, including speech transcripts and list photos, is slow work. Photo examples also depend on photo-list input, which isn't built.
- Ambiguity flags and conditional items need a schema change (`items.note` or `items.condition`), a new review UI in the starter, and new display on Progress. That is real scope in a 16-day window.
- Ollama's cloud model has already ignored the JSON schema once (closed issue 20). More fields mean more ways for a reply to be malformed, and more fallbacks to write in `starting_list()`.
- Numbers from 40 cases written by the team are weak evidence. Judges may not give them much weight compared with seeing it work live.

**Narrow version:** add an optional `note` per item (it keeps "if nobody has one" and "for 4 people"), merge duplicates on name *and* quantity, label estimates as estimates everywhere, and build a 20-case evaluation run once with the owner's approval. Leave out the ambiguity-clarification flow.

---

## 3. Make purchase verification exceptionally trustworthy

The idea: three visible states (Needed, Purchase in progress, Purchase verified), with the reason an item counts as done, the payer and the price shown. Labels should claim only what the evidence proves.

**What the code does today**
- Backend safeguards are strong and already documented: the item is checked off only when the *capture* status is `COMPLETED` (decision 25), the order ID is the idempotency key (26), stored prices are recorded rather than re-read (28), conditional updates prevent races, and paid items are locked (`409 ITEM_PAID`).
- **There is no "in progress" state.** A `PENDING` capture leaves the order at `status = 'CREATED'`, and `GET /api/lists/{id}` returns only `COMPLETED` orders (`main.py:131`). Nothing checks again later (no webhook, no polling). The person sees one status message, and then the payment disappears from the app.
- **The PayPal–receipt overlap loses money in the split.** If a receipt checks an item off while the buyer is on PayPal, `capture_order` logs a warning and keeps the receipt. The PayPal charge is never attributed to anyone, so `split()` undercounts what the PayPal buyer paid.
- **There is a third, unproven way to check items off:** `PATCH /api/items/{id}` with `checked: true` and a self-reported `priceCents`. Today it looks the same as a verified purchase.
- The UI shows proof only as "Proof: PayPal order <ID>" on the Items page. Progress shows a struck-through name, so the reason isn't visible where people look.

**Pros**
- This builds on HeyList's most distinctive, already-tested work. It is the strongest showing for **Technological Implementation** and **Best Use of PayPal + AI**.
- Most of it is small: the data needed for the labels (`order_id`, `receipt_id`, `bought_by`, `price_cents`) is already on every item row.
- Fixing the two gaps above is a real correctness improvement, not just polish. The overlap bug affects real money in the split.
- Honest labels ("Paid via PayPal", "On a receipt", "Marked bought by Ann") hold up against a judge's question in a way that a plain checkbox doesn't.

**Cons**
- A true "in progress" state needs either PayPal webhooks (a new public endpoint plus signature verification, and Render has to be reachable) or a "check again" call to `GET /v2/checkout/orders/{id}` (a new `paypal.py` function and route). The second is smaller but is still new PayPal surface to test.
- In the sandbox it's hard to make a capture come back `PENDING` on demand, so the new state is hard to demo live and hard to test end to end. Unit tests with the fake session in `test_paypal.py` can cover it.
- Fixing the overlap means choosing a rule: refund the PayPal capture (a new Refunds API call), count both and flag it, or move the proof to the order. Each changes `items_one_proof` behaviour or adds API surface. It also needs a decision record.
- Showing more status per item works against area 4 (less clutter). The labels have to stay short.

**Codebase cost:** a source label on the Progress and Items rows (frontend only). Store `PENDING` on the order and add a "check again" route (backend plus one test). Choose and implement an overlap rule (backend, decision, tests).

---

## 4. Sharpen the user experience around one principle: less effort

The idea is to work on three moments (first open, review of the AI list, checking off) and measure time to a usable list, the number of corrections, and checkout errors.

**What the code does today**
- First open is already good: `app/page.tsx` shows the starter straight away, with no category picker, settings or onboarding. Decision 7 (large text, few screens) is already followed.
- The AI review is a simple untick list, not a chat, which is already what the suggestion asks for. But items **can't be edited** before creating the list (no rename, no quantity change, no adding one). People can only untick.
- Each Progress row holds a pay-selection checkbox, a quantity stepper, a price and a "who buys it" select. That is exactly the overload the suggestion warns about. The same checkbox means "select to pay", not "done", which is confusing for a simple checklist.
- Issue 34: the join form shows on every tab, even where it isn't needed.

**Pros**
- It directly helps **Design** ("a complete, coherent product, not just a technical proof of concept") and makes the video easier to follow.
- It fits the original audience in decision 3 (student, busy parent, older relative) and the validation item in ROADMAP.
- Editing items in the review screen lowers "corrections after AI generation", which ties back to area 2.

**Cons**
- Separating "done" from "select to pay" changes the main interaction on Progress. It's a frontend rework of the most-used page, with a risk of new bugs close to the deadline.
- The dark redesign in Figma is still being decided by the owner (ROADMAP: "don't build from it yet"). A UX rework now may be redone when the redesign lands.
- The suggested measures (time to list, number of corrections) need real users or logging. The project has no analytics, and adding them is new scope. Informal timing during the three-user test is enough.
- Voice (the "one big talk button" in decision 7) is still unbuilt. It's arguably the biggest less-effort gain, but it is a feature, not a refinement.

**Narrow version:** make the review items editable (name and quantity), and split Progress into a plain "done" tick plus a separate "Pay with PayPal" selection mode. Leave the rest for the redesign.

---

## 5. Make group coordination fair and understandable

The idea: show what is covered and what is still open, who paid for each item, how each share was worked out, and trace every balance back to the purchases behind it.

**What the code does today**
- `money.split()` returns paid, share and balance per member, plus the transfers. `settle()` finds the fewest payments. All of this is tested in `test_money.py`.
- The output is **totals only**. Nothing lists which items make up "paid $X", so a balance can't be traced in the UI.
- Shares are equal only (issue 18, decision 35). Receipt extras are personal and left out (issue 29). Unattributed check-offs are left out, and the UI says so. The PayPal–receipt overlap from area 3 is left out silently.
- Settle up shows who pays whom, but PayPal invoices aren't built ("coming soon").

**Pros**
- A per-member item breakdown is small: the item rows already carry `bought_by` and `price_cents`, so it can be done in the frontend from the list already loaded, with no new endpoint.
- "Each balance explained by its purchases" is a strong **Impact** story for shared lists, and it builds trust in areas 1 and 3.
- It leads naturally to PayPal **Invoicing** for settle-up. That is more PayPal surface for the PayPal prizes, and the `invoices` table and `members.email` are already in the schema.

**Cons**
- Explaining the rules also exposes their limits. Equal shares, extras left out and the overlap gap all become visible. Each needs either a fix or a clear sentence in the UI.
- Invoices are the larger part. They need new `paypal.py` calls (create, send, get status), emails from members, routes, status tracking, and real tests. That's probably several days, and it competes with area 3 for time.
- Weighted shares would mean changing `split()`, its tests, and a UI for setting weights. The suggestion rightly avoids adding more features, so this should stay out.

**Narrow version:** a "how this was worked out" section on Settle up that lists each person's paid items and shows share = total ÷ people. Add PayPal invoices only after area 3 is done.

---

## Deferred: more list types and integrations

Leave these out. Decision 2 already keeps HeyList general without new list types. Channel3 stays a stretch goal (decision 18), and each integration adds setup, secrets and testing without strengthening the core loop.

## Risks across all areas

- **Time:** 16 days, and the submission checklist still needs a `LICENSE` file, one live sandbox payment (issue 25), the video, and the write-up ([PayPal.md §9](PayPal.md)). Keep at least 3 days free for these.
- **Paid calls:** area 2's evaluation runs and any live receipt test need the owner's approval first ([RULES.md](RULES.md)).
- **Redesign:** a large UI change (area 4) before the owner settles the dark redesign may be done twice.
- **Fixing before polishing:** the PayPal–receipt overlap (area 3) is a correctness bug in money handling, so it comes before any presentation work in areas 1 or 5.
