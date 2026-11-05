# HeyList — Submission and demo script

What goes on the Devpost form, and the script for the demo video (under 3 minutes). Rules are in [HACKATHON.md](HACKATHON.md); deadline **12 November 2026**. Written 2026-10-27; script, description, tools and checklist brought up to date 2026-11-03 (up to decision 77). Re-check every "Built" claim before submitting.

## Pitch (one line)

HeyList turns everyday needs into shared lists, and makes it clear what really got done, from the first item captured to the last purchase paid.

## Demo video script (target 2:50, hard limit 3:00)

Rewritten 2026-11-03 against what is built up to decision 78 (Pay Later added). One story from start to finish: **Ann, Ben and Cam plan a weekend camping trip**. Ann films on her phone (HeyList is mobile-first); Ben's screens are a second phone or a desktop browser at phone width. Narration is about 430 words, which fits 2:50 at a steady pace (about 150 words a minute). No music, and no third-party logos except PayPal's and Venmo's own buttons and pages.

The arc the judges should remember: **AI plans it, an agent shops it, PayPal proves it, PayPal settles it.**

### Scene by scene

| Time | Scene | On screen | Judging criterion |
|---|---|---|---|
| 0:00–0:15 | Hook | Home page, then a quick cut of a messy group chat (mocked by you, no real names) | Impact, Presentation |
| 0:15–0:40 | **AI plans it** | Tap the mic, say "Weekend camping trip for three friends, 150 dollar budget", tap **Make my list**. Review screen: quantities, `~` estimates, total under budget. Mark the stove **Already have** (it drops out of the total), add firewood. **Create list** | Technical (AI), Design |
| 0:40–0:55 | **Share it** | Share the link. On Ben's phone: open it, join as Ben. Cut back to Ann's phone: Ben appears without a reload. Ben claims the food; Ann claims the gear. Cam joins too but buys nothing | Design, Impact |
| 0:55–1:22 | **An agent shops it** | As Ann on Progress: **More → Shop this list for me**. Tick headlamp, sleeping bag, sunscreen, marshmallows (leave the tent). The agent's cart: product cards with photo, store, price; the total fits what's left of the budget; marshmallows skipped with "No online store we search sells this". Swap one product. **Pay with PayPal**, approve on the sandbox page. Back on the list: "Paid with PayPal · Ann" on each | Agentic Commerce, Channel3, PayPal + AI |
| 1:22–1:35 | **Pay Later** | Still Ann, on Progress: the main card now says **Pay for your items** with only the tent left. Hold on the three buttons, **Pay with PayPal**, **Venmo** and **Pay Later**, with PayPal's "Pay in 4…" message under them. Tap **Pay Later**, approve in PayPal's pop-up. The tent shows "Paid with PayPal · Ann" | Technical (PayPal), Best Use of PayPal + AI |
| 1:35–1:58 | **A receipt proves it** | As Ben on Progress, tap **Take a photo** and photograph a real grocery receipt. The steps box shows "It's a receipt", then the review opens on the same page: each line matched to an item, tax shown, lines add up to the total. Fix one match, **Confirm**. Items show "On a receipt · Ben" | Technical (AI), Innovation |
| 1:58–2:30 | **PayPal settles it** | **Settle up**: "Cam → Ann $X", "Cam → Ben $Y". Tap **Remind Cam**: the AI-written message with the exact amount and link; share sheet. On Cam's phone: open the link, "I'm Cam, let me pay", PayPal (or Venmo) button pops up on the page, approve. Back on Ann's phone: the balance goes to $0 | PayPal + AI, Technical (PayPal), Impact |
| 2:30–2:45 | **Every item has proof** | **Items** tab, scroll: "Paid with PayPal", "On a receipt", "Already had". Optional 2-second overlay: "Capture COMPLETED · webhooks + Render cron backup · auto refund on double buys" | Technical, Design |
| 2:45–2:50 | Close | Progress page at 100%, HeyList name | Presentation |

### Narration (read this)

**0:00 — Hook**
"Every group trip runs on a chat thread, a list nobody updates, and an awkward 'who paid for what?' at the end. HeyList is a shared list that knows what really got done, and settles up with PayPal."

**0:15 — AI plans it**
"I just say what we need. The AI turns one sentence into a list, with quantities and estimated prices that fit our budget. Nothing's saved until I've checked it. We've already got a stove, so I mark it, and it drops out of the total. I add firewood, and create the list."

**0:40 — Share it**
"I send the link. Ben joins by name. No app, no account, and he appears live. He claims the food, I take the gear, and Cam, who's busy this week, just pays a share at the end."

**0:55 — An agent shops it**
"Now the part I'd normally put off. I tick what I'm buying and ask HeyList to shop it for me. The agent searches real stores through Channel3, and the AI throws out anything that isn't actually a headlamp or a sleeping bag. Code, not the AI, fits the cart to what's left of our budget, and tells me what it couldn't buy online. I swap one product. The agent proposes; I approve, and pay with PayPal. Prices are set on the server, never in the browser, and my items are checked off only when PayPal confirms the capture."

**1:22 — Pay Later**
"The tent is the big one. PayPal offers Pay Later right here, and shows me what the payments would be. It's still one PayPal order, so the tent is checked off just the same."

**1:35 — A receipt proves it**
"Ben bought the food at the supermarket. He takes a photo, and HeyList sees it's a receipt. The AI reads every line, matches it to our list, and checks that it all adds up, tax included. If a price is hard to read, it asks instead of guessing. Ben fixes one match, and his items are done."

**1:58 — PayPal settles it**
"Because every price is real, HeyList knows exactly who owes whom. Cam owes us both, and the split is worked out in code, not by the AI. One tap and the AI drafts a friendly reminder with the exact amount. Cam opens the link, taps PayPal, or Venmo, and the money goes straight to my PayPal account. Not to HeyList. To me. The balance drops to zero."

**2:30 — Every item has proof**
"Every item says how we know it's done: paid with PayPal, on a receipt, or already had. If two people buy the same thing, the second payment is refunded automatically."

**2:45 — Close**
"AI plans it. An agent shops it. PayPal proves it, and settles it. That's HeyList."

### If it runs long

Cut in this order: the product swap in the cart, the Pay Later approval (keep the shot of the three buttons and PayPal's message, then cut to the tent checked off), the receipt match fix, Cam's phone (show the reminder, then cut straight to the balance at $0 and say "Cam paid with PayPal"), the live join (say "Ben joins" over a single cut).

### Don't say or show

- Don't say the store order is placed. The sandbox payment goes to HeyList's merchant account, and Channel3's checkout isn't open yet. If asked: "When Channel3 checkout opens, the agent places the order; today it finds the real product and price."
- Don't run store search on food: Channel3 sells no groceries. Marshmallows in the cart is on purpose, to show the skip reason; check it still says that on the day.
- Don't call a photo of an item proof: **Take a photo** on an item stays "Marked bought by hand" (decision 71). Only the receipt path is proof.
- Don't look for the sample trip or the idea chips on Home: both were removed (decision 76).
- Venmo shows only when PayPal says the buyer is eligible (US, USD). If it doesn't appear on the recording phone, cut "or Venmo" from the line.
- Pay Later shows only where PayPal says the buyer and amount qualify (decision 78): US sandbox merchant and buyer, and an amount in PayPal's Pay Later range. If it doesn't appear on the day, drop the Pay Later scene and give its 13 seconds to the receipt. Don't state Pay Later's terms yourself ("four payments of $X"); point at PayPal's own message, which says them. It isn't on Settle up or in Shop this list for me.
- Shop this list for me uses the redirect to PayPal's page, not the pop-up (decision 67). That's fine on camera; don't describe it as a pop-up.

### Before recording

- [ ] Render Blueprint synced, so `heylist-sweep` and the health checks exist (Blueprints → heylist → Manual sync). Hosted site up, schema up to date: run `supabase/schema.sql` again on the live database (`items.owned` is new, 2026-11-02).
- [ ] Three people on the list. Ann logged in on the filming phone; Ben and Cam on a second phone or browser.
- [ ] **Ann's PayPal email saved** for settle-up, and it's a **sandbox** account different from the merchant, so the money visibly goes to her (decision 60). Cam's sandbox **personal** buyer account logged in once, so approval is fast.
- [ ] Webhook registered and `PAYPAL_WEBHOOK_ID` set, so a pending capture still finishes on camera.
- [ ] Rehearse **Shop this list for me** with the exact items you'll film on the live site that day. Results change; pick items that return clean product cards. `CHANNEL3_API_KEY` set on heylist-api.
- [ ] Rehearse **Pay Later** with the tent alone left on Ann's items: check that the button and PayPal's message appear for the sandbox buyer at that amount, and that the approval pop-up completes. If the tent's price is too low for Pay Later, pick a pricier tent in **Find in stores** first.
- [ ] A clear, real receipt that matches two or three items on the list. The AI's starting list changes between runs, so record the list you practised with, or add the receipt's items by hand.
- [ ] Voice works in Chrome and Safari; test the mic on the recording phone. Typing the sentence is the fallback.
- [ ] **Paid calls:** the starting list, the shopping agent, the receipt scan and the reminder call Ollama, Channel3 and Textract. Each take spends a little; the owner approves before recording ([RULES.md](RULES.md)).
- [ ] Mock group chat for the hook uses made-up names only.
- [ ] Upload to YouTube as **public**, under 3:00. Add captions (auto, then fix product names).

## Devpost text description (draft)

**What it does**

HeyList is a mobile-first checklist website for groups. You describe what you need in one sentence, typed or spoken, or take a photo of a paper list. The AI suggests a list with quantities and estimated prices within the budget, and you review it before anything is saved, marking what you already have so nobody buys it twice. You share the list by link, with no accounts needed. People join by name, claim what they'll buy, and HeyList shares out the rest evenly by estimated cost. Changes show on everyone's phone as they happen.

Then HeyList helps you buy it and keeps track of what actually got done:

- **Find in stores / Shop this list for me:** real products and prices from Channel3, with the AI keeping only products that really are the item. The shopping agent proposes a whole cart that fits what's left of the budget and says why it skipped anything. You approve it with one PayPal payment; the agent never pays on its own.
- **Pay with PayPal, Venmo or Pay Later:** the server builds the order from the list's own prices (store prices read again first), and an item is checked off only when PayPal reports the **capture** as `COMPLETED`, recording who paid and how much. Webhooks finish pending payments, with a Render cron job as the backup. If someone pays for an item that was already bought, the charge is refunded automatically.
- **Scan a receipt:** take a photo and HeyList sees it's a receipt. The AI reads it, matches each line to a list item, checks that the lines and tax add up to the total, and asks for any price it can't read instead of guessing. You confirm before anything is checked off.
- **Settle up with PayPal:** from those recorded prices, code works out each person's share and the fewest payments. The AI drafts a friendly reminder with the exact amount and a link, and the friend pays the person owed directly with PayPal. The money never passes through HeyList.

Every item shows what its status rests on: "Paid with PayPal", "On a receipt", "Marked bought by hand", "Already had" or "Payment pending".

**How we built it**

- **Real prices, not guesses:** food on a new list is priced from Kroger's Products API at a real store, and everything else from Walmart and Target through Channel3, with the AI checking that each product is the item. The AI's own estimate is the last fallback.
- Next.js 16 (mobile-first website) → FastAPI backend → Supabase (lists, receipts, Auth, Realtime), deployed on Render from one Blueprint: two web services with health checks, a shared environment group, and a cron job that re-checks pending PayPal payments every 15 minutes.
- **PayPal** (sandbox), through PayPal's official Python Server SDK: Orders API v2 (create, capture, show order details, payee set to the person owed for settle-up) and Payments API v2 (refunds), plus JS SDK v6 buttons with Venmo and Pay Later (with PayPal's Pay Later messages) and signature-verified webhooks. Idempotency keys on every call, capture status checked rather than order status, prices in integer cents and never taken from the browser.
- **AI:** an Ollama-hosted vision model (`gemma4:31b`) for starting lists (structured JSON, every field validated in code), receipt matching, checking store results, what a photo shows, and reminders. AWS Textract reads receipts (`AnalyzeExpense`) and paper lists (`DetectDocumentText`), with the Ollama vision model as the fallback.
- **The AI proposes; code decides.** Budgets, the cart fit, the split and settle-up are deterministic code, and a person confirms every AI suggestion.
- **Measured, not assumed:**
  - **Starting lists:** a 30-case evaluation scores them. Latest run (2026-10-27): 96/98 items found, 12/12 quantities right, 8/8 conditions ("only if nobody has one") kept, 0 invented items. It also settled a design question: adding example lists to the prompt lowered recall to 91/98, so they were left out.
  - **Receipts:** 289 real receipts. On the 189 English ones, Textract shows a wrong price on 2.5% of lines and 76% of receipts come out perfect ([RECEIPT_EVAL.md](RECEIPT_EVAL.md)).

**Tools used and how** (required field)

| Tool | Used for |
|---|---|
| Ollama (cloud model, `OLLAMA_MODEL`) | Starting lists from one sentence or a paper list; matching receipt lines to list items; keeping only store products that are the item; telling an item photo from a receipt; drafting settle-up reminders; reading photos when Textract is unavailable |
| Channel3 product search | "Find in stores" and "Shop this list for me": real products and prices; the chosen price is read again on the server and charged with PayPal |
| Kroger Products API | Today's grocery prices at one real Kroger store, for food items on a new list; the AI checks each product is the item first (decisions 74, 75) |
| AWS Textract `AnalyzeExpense`, `DetectDocumentText` | Receipt line items, tax and totals with a confidence per line; photos of paper lists |
| PayPal Orders API v2, Payments API v2, webhooks (sandbox) | Checkout, capture, settle-up payments to the person owed, pending-payment follow-up, refunds for double purchases |
| PayPal JS SDK v6 (PayPal, Venmo and Pay Later buttons, Pay Later messages) | Paying on the list page, with the redirect checkout as the fallback |
| PayPal Server SDK (Python, APIMatic-generated) and APIMatic Context Plugins | Calling PayPal; SDK usage guidance while building |
| Supabase | Postgres, receipt storage, Auth (email and password), Realtime list updates |
| Web Speech API | Voice input |
| Render | Blueprint (`render.yaml`): web services `heylist-api` and `heylist-web` with health checks, a shared environment group, and the `heylist-sweep` cron job that finishes pending PayPal payments every 15 minutes |
| Claude Code | Coding assistant during development |

Check this table against `.env.example` and `backend/` before submitting; remove anything that isn't used.

**Challenges, accomplishments, what's next:** write these after recording. Candidates: the order-vs-capture status difference (decision 25), Ollama ignoring the JSON schema (closed issue 20), the receipt/PayPal race (decision 39), never guessing a receipt price (decisions 57 and 72), keeping the shopping agent from paying on its own (decision 61). Next: placing the store order once Channel3's checkout opens, weighted shares (issue 18), recognising several items in one photo ([SPEC.md](SPEC.md)).

## Submission checklist

From [HACKATHON.md](HACKATHON.md#what-to-submit) and [PayPal.md §9](PayPal.md):

- [x] `LICENSE` file (MIT, added 2026-10-27).
- [ ] Repo made public, with "MIT license" shown in the About section (GitHub reads it from `LICENSE`).
- [ ] README with setup and run steps (present), plus the hosted URL. Sandbox buyer login for judges added 2026-11-05.
- [ ] Text description (draft above).
- [ ] Tools section (draft above).
- [ ] Demo video on YouTube, public, under 3 minutes.
- [ ] Optional: submit by **Thu 5 Nov** for the early eligibility check ([HACKATHON.md](HACKATHON.md)).
