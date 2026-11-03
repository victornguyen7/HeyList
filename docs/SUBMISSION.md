# HeyList — Submission and demo script

What goes on the Devpost form, and the script for the demo video (under 3 minutes). Rules are in [HACKATHON.md](HACKATHON.md); deadline **12 November 2026**. Written 2026-10-27 against what is built; video script rewritten 2026-11-03. Re-check every "Built" claim before submitting.

## Pitch (one line)

HeyList turns everyday needs into shared lists, and makes it clear what really got done, from the first item captured to the last purchase paid.

## Demo video script (target 2:50, hard limit 3:00)

Rewritten 2026-11-03 against what is built up to decision 72. One story from start to finish: **Ann, Ben and Cam plan a weekend camping trip**. Ann films on her phone (HeyList is mobile-first); Ben's screens are a second phone or a desktop browser at phone width. Narration is about 410 words, which fits 2:50 at a calm pace. No music, and no third-party logos except PayPal's and Venmo's own buttons and pages.

The arc the judges should remember: **AI plans it, an agent shops it, PayPal proves it, PayPal settles it.**

### Scene by scene

| Time | Scene | On screen | Judging criterion |
|---|---|---|---|
| 0:00–0:15 | Hook | Home page, then a quick cut of a messy group chat (mocked by you, no real names) | Impact, Presentation |
| 0:15–0:40 | **AI plans it** | Tap the mic, say "Weekend camping trip for three friends, 150 dollar budget", tap **Make my list**. Review screen: quantities, `~` estimates, total under budget. Untick one item, add one. **Create list** | Technical (AI), Design |
| 0:40–0:55 | **Share it** | Share the link. On Ben's phone: open it, join as Ben. Cut back to Ann's phone: Ben appears without a reload. Ben claims the food; Ann claims the gear. Cam joins too but buys nothing | Design, Impact |
| 0:55–1:30 | **An agent shops it** | As Ann on Progress: **More → Shop this list for me**. Tick headlamp, sleeping bag, sunscreen, marshmallows. The agent's cart: product cards with photo, store, price; the total fits what's left of the budget; marshmallows skipped with "No online store we search sells this". Swap one product. **Pay with PayPal**, approve on the sandbox page. Back on the list: "Paid with PayPal · Ann" on each | Agentic Commerce, Channel3, PayPal + AI |
| 1:30–1:55 | **A receipt proves it** | As Ben, **Receipts**: photograph a real grocery receipt. Review screen: each line matched to an item, tax shown, lines add up to the total. Fix one match, **Confirm**. Items show "On a receipt · Ben" | Technical (AI), Innovation |
| 1:55–2:30 | **PayPal settles it** | **Settle up**: "Cam → Ann $X", "Cam → Ben $Y". Tap **Remind Cam**: the AI-written message with the exact amount and link; share sheet. On Cam's phone: open the link, "I'm Cam, let me pay", PayPal (or Venmo) button pops up on the page, approve. Back on Ann's phone: the balance goes to $0 | PayPal + AI, Technical (PayPal), Impact |
| 2:30–2:45 | **Every item has proof** | **Items** tab, scroll: "Paid with PayPal", "On a receipt", "Marked bought by hand". Optional 2-second overlay: "Capture COMPLETED · webhooks · auto refund on double buys" | Technical, Design |
| 2:45–2:50 | Close | Progress page at 100%, HeyList name | Presentation |

### Narration (read this)

**0:00 — Hook**
"Every group trip runs on a chat thread, a list nobody updates, and an awkward 'who paid for what?' at the end. HeyList fixes that. It's a shared list that knows what really got done, and settles up with PayPal."

**0:15 — AI plans it**
"I just say what we need. The AI turns one sentence into a list, with quantities and estimated prices that fit our budget. Nothing's saved until I've checked it. I drop the stove, we've got one, add firewood, and create the list."

**0:40 — Share it**
"I send the link. Ben joins by name. No app to install, no account needed, and I see him appear live. He claims the food, I take the gear, and Cam, who's busy this week, just pays a share at the end."

**0:55 — An agent shops it**
"Now the part I'd normally put off. I tick what I'm buying and ask HeyList to shop it for me. The agent searches real stores through Channel3, and the AI throws out anything that isn't actually a headlamp or a sleeping bag. Code, not the AI, fits the cart to what's left of our budget, and it tells me what it couldn't buy online and why. I swap one product, and pay with PayPal. The agent proposes; I approve. Prices are read again from the store and set on the server, never in the browser. And only when PayPal confirms the capture are my items checked off, with my name and the price I paid."

**1:30 — A receipt proves it**
"Ben bought the food at the supermarket. He snaps the receipt. The AI reads every line, matches it to our list, and checks that it all adds up, tax included. If a price is hard to read, it asks instead of guessing. Ben fixes one match, confirms, and his items are done."

**1:55 — PayPal settles it**
"Because every price is real, HeyList knows exactly who owes whom. Cam owes us both, and the split is worked out in code, not by the AI. One tap and the AI drafts a friendly reminder with the exact amount. Cam opens the link, taps PayPal, or Venmo, and the money goes straight to my PayPal account. Not to HeyList. To me. The balance drops to zero."

**2:30 — Every item has proof**
"Every item says how we know it's done: paid with PayPal, on a receipt, or ticked by hand. If two people buy the same thing, the second payment is refunded automatically."

**2:45 — Close**
"AI plans it. An agent shops it. PayPal proves it, and settles it. That's HeyList."

### If it runs long

Cut in this order: the product swap in the cart, the receipt match fix, Cam's phone (show the reminder, then cut straight to the balance at $0 and say "Cam paid with PayPal"), the live join (say "Ben joins" over a single cut).

### Don't say or show

- Don't say the store order is placed. The sandbox payment goes to HeyList's merchant account, and Channel3's checkout isn't open yet. If asked: "When Channel3 checkout opens, the agent places the order; today it finds the real product and price."
- Don't run store search on food: Channel3 sells no groceries. Marshmallows in the cart is on purpose, to show the skip reason; check it still says that on the day.
- Don't call **Check off with a photo** proof: it stays "Marked bought by hand" (decision 71).
- Venmo shows only when PayPal says the buyer is eligible (US, USD). If it doesn't appear on the recording phone, cut "or Venmo" from the line.
- Shop this list for me uses the redirect to PayPal's page, not the pop-up (decision 67). That's fine on camera; don't describe it as a pop-up.

### Before recording

- [ ] Hosted site up on Render, schema up to date (`supabase/schema.sql` run again on the live database).
- [ ] Three people on the list. Ann logged in on the filming phone; Ben and Cam on a second phone or browser.
- [ ] **Ann's PayPal email saved** for settle-up, and it's a **sandbox** account different from the merchant, so the money visibly goes to her (decision 60). Cam's sandbox **personal** buyer account logged in once, so approval is fast.
- [ ] Webhook registered and `PAYPAL_WEBHOOK_ID` set, so a pending capture still finishes on camera.
- [ ] Rehearse **Shop this list for me** with the exact items you'll film on the live site that day. Results change; pick items that return clean product cards. `CHANNEL3_API_KEY` set on heylist-api.
- [ ] A clear, real receipt that matches two or three items on the list. The AI's starting list changes between runs, so record the list you practised with, or add the receipt's items by hand.
- [ ] Voice works in Chrome and Safari; test the mic on the recording phone. Typing the sentence is the fallback.
- [ ] **Paid calls:** the starting list, the shopping agent, the receipt scan and the reminder call Ollama, Channel3 and Textract. Each take spends a little; the owner approves before recording ([RULES.md](RULES.md)).
- [ ] Mock group chat for the hook uses made-up names only.
- [ ] Upload to YouTube as **public**, under 3:00. Add captions (auto, then fix product names).

## Devpost text description (draft)

**What it does**

HeyList is a mobile-first checklist website for groups. You describe what you need in one sentence (say, "weekend camping trip for 3 friends, $150"), and the AI suggests a list with quantities and estimated prices within the budget. You review it before anything is saved. You share the list by link, with no accounts. People join by name, claim what they'll buy, and HeyList shares out the rest evenly by estimated cost.

Then HeyList keeps track of what actually got done. Pay for items with PayPal: the server builds the order from the list's own prices, and an item is checked off only when PayPal reports the **capture** as `COMPLETED`, recording who paid and how much. A pending payment holds its items until PayPal confirms it. If someone pays for an item that was already bought, the charge is refunded to them automatically. Or scan a receipt: the AI reads the photo, matches each line to a list item, and you confirm the matches before anything is checked off. Every item shows what its status rests on ("Paid with PayPal", "On a receipt", "Marked bought by hand"). From those recorded prices, code works out each person's share and the fewest payments to settle up.

**How we built it**

- Next.js (mobile-first website) → FastAPI backend → Supabase (lists, receipts, photos).
- **PayPal** (sandbox), through PayPal's official Python Server SDK: Orders API v2 (create, capture, show order details) and Payments API v2 (refund a captured payment). Idempotency keys on every call, capture status checked rather than order status, prices in integer cents, never from the browser.
- **AI:** an Ollama-hosted model with vision for starting lists (structured JSON, every field validated in code) and for matching receipt lines to items; AWS Textract `AnalyzeExpense` reads receipts when available, with the Ollama vision model as fallback.
- Split and settle-up are deterministic code, not AI.
- **Measured, not assumed:** a 30-case evaluation (typed lists, speech-style transcripts, situations) scores the starting lists. Latest run (2026-10-27): 96/98 items found, 12/12 quantities right, 8/8 conditions ("only if nobody has one") kept, 0 invented items (`backend/eval/eval_report.json`). It also decided a design question: adding example lists to the prompt lowered recall to 91/98, so they were left out.

**Tools used and how** (required field)

| Tool | Used for |
|---|---|
| Ollama (cloud model, `OLLAMA_MODEL`) | Starting lists from one sentence; matching receipt lines to list items; reading receipt photos when Textract is unavailable; keeping only the store products that are the item |
| Channel3 product search | "Find in stores": real products and prices for an item; the chosen price is read again on the server and charged with PayPal |
| AWS Textract `AnalyzeExpense` | Reading receipt line items with a confidence per line |
| PayPal Orders API v2, Payments API v2 (sandbox) | Checkout, capture, pending-payment follow-up, refunds for double purchases |
| PayPal Server SDK (Python, APIMatic-generated) and APIMatic Context Plugins | Calling PayPal; SDK usage guidance while building |
| Render | Hosting |
| Claude Code | Coding assistant during development |

Check this table against `.env.example` and `backend/` before submitting; remove anything that isn't used.

**Challenges, accomplishments, what's next:** write these after recording. Candidates: the order-vs-capture status difference (decision 25), Ollama ignoring the JSON schema (closed issue 20), the receipt/PayPal race (decision 39). Next: voice input, PayPal invoices for settle-up, realtime updates.

## Submission checklist

From [HACKATHON.md](HACKATHON.md#what-to-submit) and [PayPal.md §9](PayPal.md):

- [x] `LICENSE` file (MIT, added 2026-10-27).
- [ ] Repo made public, with "MIT license" shown in the About section (GitHub reads it from `LICENSE`).
- [ ] README with setup and run steps (present), plus the hosted URL.
- [ ] Text description (draft above).
- [ ] Tools section (draft above).
- [ ] Demo video on YouTube, public, under 3 minutes.
