# HeyList — Submission and demo script

What goes on the Devpost form, and the script for the demo video (under 3 minutes). Rules are in [HACKATHON.md](HACKATHON.md); deadline **12 November 2026**. Written 2026-10-27 against what is built. Re-check every "Built" claim before submitting.

## Pitch (one line)

HeyList turns everyday needs into shared lists, and makes it clear what really got done, from the first item captured to the last purchase paid.

## Demo video script (target 2:40)

One scenario from start to finish: **three friends planning a weekend camping trip** (decision 41). Record on a phone, or in a desktop browser at phone width, since HeyList is mobile-first. No music, and no third-party logos except PayPal's own sandbox pages.

| Time | Scene | On screen | Say (roughly) | Judging criterion |
|---|---|---|---|---|
| 0:00–0:15 | Problem | Home page | "Planning a trip with friends means a group chat, a list nobody updates, and arguing later about who paid. HeyList turns what you need into a shared list, and keeps track of what really got done." | Impact, Presentation |
| 0:15–0:40 | **Need** | Type "Weekend camping trip for 3 friends, 2 nights" and a $150 budget, then tap **Make my list**. Show quantities, the `~` estimates and the estimated total; untick one item; **Create list** | "One sentence. The AI suggests what we need, with quantities and estimated prices, within our budget. Nothing is saved until I've checked it." | Technical (AI), Design |
| 0:40–1:05 | **Coordinate** | Join as Ann. In a second browser, open the link and join as Ben. Claim the tent; tap **Share out the rest evenly** | "I share the link. No accounts. Ben joins by name. We claim what we're buying, and HeyList shares out the rest so the cost is even." | Design, Impact |
| 1:05–1:45 | **Verify: PayPal** | As Ann, tick three items; **Pay $X with PayPal**; approve on the PayPal sandbox page; back on the list, "Paid. Those items are checked off." Each one shows "Paid with PayPal · Ann" | "Ann pays for her share with PayPal. The server sets the price from the list, not the browser. Only when PayPal confirms the payment is captured do the items get checked off, with Ann as the payer and the price she paid." | Technical (PayPal), Best Use of PayPal + AI |
| 1:45–2:15 | **Verify: receipt** | As Ben, **Receipts** tab: photograph a real receipt. Show the proposed matches; fix one; confirm. Items now show "On a receipt · Ben" | "Ben bought his things in a shop. He snaps the receipt; the AI reads it and matches each line to our list. He checks the matches, and his items are done, at the prices on the receipt." | Technical (AI), Innovation |
| 2:15–2:35 | **Settle** | **Items** tab (every item shows its proof), then **Settle up**: "Ben → Ann $X" | "Every item says how we know it's done. And because the prices are real, HeyList works out who owes whom, in code, not by guessing." | Impact, Design |
| 2:35–2:45 | Close | Progress page, list finished | "Need, coordinate, verify. HeyList." | Presentation |

Cut first if it runs long: the second browser joining (say it instead), then the receipt correction.

Don't show: voice input or photo recognition (not built), or PayPal invoices (not built). If any of these are built before recording, add them to the scene where they fit.

### Before recording

- [ ] Deployed on Render, with the hosted URL working (`render.yaml`).
- [ ] Run `supabase/schema.sql` again on the live database (phase 1 added `orders.capture_id`, `orders.refunds`).
- [ ] A sandbox **personal** buyer account is logged in once, so the PayPal approval page is fast ([Sandbox accounts](https://developer.paypal.com/dashboard/accounts)).
- [ ] One full sandbox payment has already been tested end to end (issue 25).
- [ ] A clear, real receipt that matches two or three items on the generated list. Practise the suggestion first: the AI's list changes between runs, so record the list you practised with, or add the receipt's items by hand.
- [ ] **Paid calls:** the starting list and receipt scan call Ollama (and Textract, if enabled). Each recording take spends a little; the owner approves before recording ([RULES.md](RULES.md)).
- [ ] Upload to YouTube as **public**, under 3:00.

## Devpost text description (draft)

**What it does**

HeyList is a mobile-first checklist website for groups. You describe what you need in one sentence (say, "weekend camping trip for 3 friends, $150"), and the AI suggests a list with quantities and estimated prices within the budget. You review it before anything is saved. You share the list by link, with no accounts. People join by name, claim what they'll buy, and HeyList shares out the rest evenly by estimated cost.

Then HeyList keeps track of what actually got done. Pay for items with PayPal: the server builds the order from the list's own prices, and an item is checked off only when PayPal reports the **capture** as `COMPLETED`, recording who paid and how much. A pending payment holds its items until PayPal confirms it. If someone pays for an item that was already bought, the charge is refunded to them automatically. Or scan a receipt: the AI reads the photo, matches each line to a list item, and you confirm the matches before anything is checked off. Every item shows what its status rests on ("Paid with PayPal", "On a receipt", "Marked bought by hand"). From those recorded prices, code works out each person's share and the fewest payments to settle up.

**How we built it**

- Next.js (mobile-first website) → FastAPI backend → Supabase (lists, receipts, photos).
- **PayPal** (sandbox), through PayPal's official Python Server SDK: Orders API v2 (create, capture, show order details) and Payments API v2 (refund a captured payment). Idempotency keys on every call, capture status checked rather than order status, prices in integer cents, never from the browser.
- **AI:** an Ollama-hosted model with vision for starting lists (structured JSON, every field validated in code) and for matching receipt lines to items; AWS Textract `AnalyzeExpense` reads receipts when available, with the Ollama vision model as fallback.
- Split and settle-up are deterministic code, not AI.
- **Measured, not assumed:** a 20-case evaluation (typed lists, speech-style transcripts, situations) scores the starting lists. First run: 62/63 items found, 12/13 quantities right, 8/8 conditions ("only if nobody has one") kept, 0 invented items (`backend/eval/eval_report.json`).

**Tools used and how** (required field)

| Tool | Used for |
|---|---|
| Ollama (cloud model, `OLLAMA_MODEL`) | Starting lists from one sentence; matching receipt lines to list items; reading receipt photos when Textract is unavailable |
| AWS Textract `AnalyzeExpense` | Reading receipt line items with a confidence per line |
| PayPal Orders API v2, Payments API v2 (sandbox) | Checkout, capture, pending-payment follow-up, refunds for double purchases |
| PayPal Server SDK (Python, APIMatic-generated) and APIMatic Context Plugins | Calling PayPal; SDK usage guidance while building |
| Render | Hosting |
| Claude Code | Coding assistant during development |

Check this table against `.env.example` and `backend/` before submitting; remove anything that isn't used.

**Challenges, accomplishments, what's next:** write these after recording. Candidates: the order-vs-capture status difference (decision 25), Ollama ignoring the JSON schema (closed issue 20), the receipt/PayPal race (decision 39). Next: voice input, PayPal invoices for settle-up, realtime updates.

## Submission checklist

From [HACKATHON.md](HACKATHON.md#what-to-submit) and [PayPal.md §9](PayPal.md):

- [ ] Public repo with a `LICENSE` file shown in the About section (not added yet).
- [ ] README with setup and run steps (present), plus the hosted URL.
- [ ] Text description (draft above).
- [ ] Tools section (draft above).
- [ ] Demo video on YouTube, public, under 3 minutes.
