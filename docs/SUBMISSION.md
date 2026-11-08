# HeyList — Submission and demo script

What goes on the Devpost form, and the script for the demo video (under 3 minutes). Rules are in [HACKATHON.md](HACKATHON.md); deadline **12 November 2026**. Written 2026-10-27; script, description, tools and checklist brought up to date 2026-11-03 (up to decision 77); demo script rewritten for non-technical viewers 2026-11-05. Re-check every "Built" claim before submitting.

## Pitch (one line)

HeyList turns everyday needs into shared lists, and makes it clear what really got done, from the first item captured to the last purchase paid.

## Demo video script (target 2:45, hard limit 3:00)

Rewritten 2026-11-05 for viewers who don't work in tech: one friendly story with no jargon, with the technical details shown as captions for the judges instead of spoken. **Ann, Ben and Cam plan a weekend camping trip.** Ann films on her phone (HeyList is mobile-first); Ben's and Cam's screens are a second phone or a desktop browser at phone width. Narration is about 400 words, about 2:45 at a relaxed pace. No music, and no third-party logos except PayPal's and Venmo's own buttons and pages.

The line viewers should remember: **AI handles the planning and the busywork. PayPal makes the money simple and certain.**

**Recording with an AI voice:** the video is filmed silent and narrated by text-to-speech; the narrated version, retold as a photo trip (AI gear list, AI shopping with PayPal Pay in 4, friends joining, a receipt scanned on the phone, PayPal to settle up), with the voice text ready to paste, is [DEMO_VOICEOVER.md](DEMO_VOICEOVER.md).

### Scene by scene

**0:00 · The problem** (15s, about 38 words)
*On screen: big text "82%" over a made-up group chat (made-up names only). Then the three questions pop up one at a time as chat bubbles: "Who's buying what?", "Who already paid?", "Who owes whom?". End on the HeyList logo. Source in a corner the whole time: "Harris Poll for CIT Bank, May 2026 · 2,067 US adults" ([RESEARCH.md](RESEARCH.md)).*

> "Eighty-two percent of people on group trips would rather overpay than argue about money. Who's buying what? Who already paid? Who owes whom? HeyList answers all three: AI plans the list, and PayPal settles it, down to the cent."

Shorter fallback (10s), if the video runs long: "Almost half of group travelers have had money trouble on a trip. HeyList fixes that: AI plans the list, and PayPal settles it." (45%, same Harris Poll.) Say "group trips", not "everyone": the poll asked US adults who took a group trip in the past 5 years.

**0:15 · Say what you need** (25s)
*Tap the mic and say: "Weekend camping trip for three friends, 150 dollar budget." Then tap **Make my list**. On the review screen, mark the stove **Already have**, then tap **Create list**.*

> "I just say what we need. In seconds, HeyList's AI writes the whole list: how many of each thing, and what it costs at real stores today, so we can see it fits our budget. We already own a stove, so I mark it, and it drops off the total."

**0:40 · Share it** (15s)
*Share the link. Ben's phone opens it and he joins by name. On Ann's phone, Ben appears without a reload. Ben claims the food; Ann claims the gear.*

> "I send the link. No app to download, no sign-up. Ben types his name and he's in, and the list updates on all our phones at once. Ben takes the food. I take the gear."

**0:55 · Let it shop for you** (30s)
*As Ann on Progress: **More → Shop this list for me**, tick the gear (leave the tent), show the product cards and the total within budget, then **Pay with PayPal** and approve on the sandbox page. Back on the list: "Paid with PayPal · Ann" on each item.*

> "Shopping is the part I always put off, so I let HeyList do it. Its AI shopping assistant finds real products from real stores, keeps within what's left of our budget, and tells me what it couldn't find. But I stay in charge: I check it, and pay once with PayPal. Done. Every item shows 'Paid with PayPal', with my name."

**1:25 · Pay Later** (10s, only if the button appears)
*Progress with only the tent left on Ann's items: hold on the **Pay with PayPal**, **Venmo** and **Pay Later** buttons with PayPal's message under them. Tap **Pay Later** and approve in PayPal's pop-up.*

> "The tent's the big one, so PayPal lets me spread the cost with Pay Later, right here."

**1:35 · Snap the receipt** (20s)
*As Ben on Progress: **Take a photo** of a real grocery receipt. The review opens on the same page with each line matched to an item; tap **Confirm**. Items show "On a receipt · Ben".*

> "Ben shopped at the supermarket. He just snaps his receipt. HeyList reads every line, matches it to our list, and checks it all adds up. One tap, and his items are done too."

**1:55 · Settle up** (30s)
*Tap **Settle up**: "Cam → Ann $X", "Cam → Ben $Y". Tap **Remind Cam** and show the message. On Cam's phone: open the link, pay with PayPal, approve. Back on Ann's phone: the balance goes to $0.*

> "Here's my favorite part. HeyList knows what everyone really paid, so it works out who owes whom, to the cent. Cam couldn't come shopping, so he owes us. One tap, and it writes a friendly reminder for me. Cam pays with PayPal, and the money comes straight to me. No maths, no awkward chasing."

**2:25 · Every item has proof** (12s)
*Scroll the **Items** tab: "Paid with PayPal", "On a receipt", "Already had".*

> "Every item shows how we know it's done: paid with PayPal, on a receipt, or already had. And if two of us buy the same thing, PayPal refunds the second one automatically."

**2:37 · Close** (10s)
*Progress at 100%, then the HeyList logo with `heylist-web.onrender.com` and "Built with PayPal + AI".*

> "From one sentence to everyone settled up. AI handles the planning and the busywork. PayPal makes the money simple and certain. That's HeyList."

### Captions for the judges (on screen, not spoken)

Show each for 2–3 seconds in a corner, so non-technical viewers can ignore them and judges see PayPal and AI named and working:

| Scene | Caption |
|---|---|
| Say what you need | "AI: Ollama (`gemma4:31b`) · prices from Kroger, Walmart and Target" |
| Share it | "Live updates: Supabase Realtime" |
| Let it shop for you | "Agent: Channel3 product search + AI check · PayPal Orders API · prices set on the server" |
| Pay Later | "PayPal JS SDK v6: PayPal, Venmo, Pay Later" |
| Snap the receipt | "AWS Textract + AI matching · every price checked against the total" |
| Settle up | "Split worked out in code, not AI · PayPal pays the person owed directly" |
| Every item has proof | "Checked off only on a COMPLETED capture · webhooks + Render cron · auto refunds" |

### If it runs long

Cut in this order: the Pay Later scene, the live join (say "Ben joins" over a single cut), then Cam's phone (show the reminder, then jump straight to the balance at $0 and say "Cam paid with PayPal"). Cut loading waits in editing, and keep each shot under about 8 seconds.

### Don't say or show

- Don't say the store order is placed. HeyList finds the real product and price, and the sandbox payment goes to HeyList's merchant account; Channel3's checkout isn't open yet. If asked: "When Channel3 checkout opens, the agent places the order; today it finds the real product and price."
- Don't run Shop this list for me on food: Channel3 sells no groceries (groceries are priced from Kroger, decision 74). Pick gear items that return clean product cards on the day.
- Don't call a photo of an item proof: **Take a photo** on an item stays "Marked bought by hand" (decision 71). Only the receipt path is proof.
- Don't look for the sample trip or the idea chips on Home: both were removed (decision 76).
- Venmo shows only when PayPal says the buyer is eligible (US, USD). If it doesn't appear on the recording phone, don't mention it.
- Pay Later shows only where PayPal says the buyer and amount qualify (decision 78). If it doesn't appear, drop that scene. Don't state Pay Later's terms yourself; PayPal's own message says them. It isn't on Settle up or in Shop this list for me.
- Shop this list for me uses the redirect to PayPal's page, not the pop-up (decision 67). Don't describe it as a pop-up.

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
- **Pay with PayPal, Venmo or Pay Later:** the server builds the order from the list's own prices (store prices read again first), and an item is checked off only when PayPal reports the **capture** as `COMPLETED`, recording who paid and how much. The list's sales tax is on the order too, so PayPal shows Items + Tax = Total like a real checkout. Webhooks finish pending payments, with a Render cron job as the backup. If someone pays for an item that was already bought, the charge is refunded automatically.
- **Scan a receipt:** take a photo and HeyList sees it's a receipt. The AI reads it, matches each line to a list item, checks that the lines and tax add up to the total, takes a coupon off the item it was for, and asks for any price it can't read instead of guessing. You confirm before anything is checked off. The tax it read becomes the list's tax rate for later payments and estimates.
- **Settle up with PayPal:** from those recorded prices, with tax, tips and fees counted as on a real receipt, code works out each person's share and the fewest payments. Money shows how the total adds up: items + tax + fees − refunds. The AI drafts a friendly reminder with the exact amount and a link, and the friend pays the person owed directly with PayPal. The money never passes through HeyList.

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
