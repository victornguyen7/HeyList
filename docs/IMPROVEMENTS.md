# HeyList — Improvement options: pros and cons

The five improvement areas suggested for HeyList, each weighed against the code as it stands on 2026-10-27. The deadline is 12 November 2026, so there are about 16 days left ([HACKATHON.md](HACKATHON.md)). Built features are listed in [ARCHITECTURE.md](ARCHITECTURE.md) and [PayPal.md](PayPal.md); open problems are in [ISSUES.md](ISSUES.md).

## Progress

| Phase | Area | Status |
|---|---|---|
| 1 | 3. Trustworthy purchase verification | Done 2026-10-27 (see below) |
| 2 | 1. Core promise | Not started |
| 3 | 2. AI reliability (narrow) | Not started |
| 4 | 5. Group accounting (narrow) | Not started |
| 5 | 4. Less effort (narrow) | Not started |

### Phase 1 — purchase verification (done)

- **Three states, visible.** Needed / Payment pending at PayPal / verified ("Paid with PayPal", "On a receipt"), plus "Marked bought by hand" for a tick with no evidence. Shown on Progress and Items, with who paid (`proofLabel()` in `app/api.ts`).
- **Pending is real now.** A `PENDING` capture is stored, holds its items, and has a **Check again** button (`POST /api/orders/{id}/refresh`, `paypal.get_order()`). Decision 40, issue 36.
- **Overlap bug fixed.** A PayPal charge for an item a receipt covered first now counts toward the buyer in the split and is flagged on Money. Decision 39, issue 37.
- **Estimates marked** with `~` on Progress.
- **Tests:** 61 pass (4 new: pending holds items, pending then completed, pending then declined, get_order; the overlap test now checks the split). `tsc` and `eslint` are clean.
- **Not checked live:** the new UI was not run against Supabase or the PayPal sandbox in this phase. A sandbox capture rarely comes back `PENDING`, so that path is covered by unit tests only.

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
