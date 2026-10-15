# HeyList — Spec

**Simple checklists with money built in.**

A simple checklist website for everyday life, built mobile-first so it works in a phone browser with nothing to install. Anyone can use it, including people with little tech experience. Users create lists by typing, speaking, or taking a photo, whichever is easiest at that moment.

The first use case is packing before a holiday; the app stays general-purpose so it fits groceries, errands, routines, and any other daily list.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).

## Problem

Existing checklist apps assume users are comfortable tapping through menus, folders, and settings. People with little tech experience often give up on them and fall back to paper or memory.

- Starting a list means facing a blank page.
- Voice input exists but is buried, and usually dumps everything into one line.
- There is no easy way to prove a task was done ("did I turn off the stove?").
- Sharing a list with family usually requires everyone to have an account.

Apps on the market today do not optimize the process of making a checklist and checking items off when finished, and none of them can be reused each time a user needs a new checklist.

## Target users

The app is neutral and built for daily use by many groups, not tied to companies.

| User | Typical lists | What matters |
|---|---|---|
| Student | Packing for a trip home, assignments, groceries | Speed, voice capture on the go |
| Busy parent | Kids' bags, groceries, weekly chores | Reusable lists, sharing with family |
| Older relative | Medicine bag, travel packing, leaving-the-house checks | Large text, one-tap voice, no account setup |

**Success test:** if all three can make and finish a list without help, the neutral design works.

## Core features

Three ways to work with a list (type, voice, photo) are the heart of the app; everything else keeps it effortless.

| Feature | What it does | Example |
|---|---|---|
| Type | Add items the familiar way | "sunscreen" |
| Voice | Speak naturally; the app splits speech into clean items and shows them to confirm | "Groceries: eggs, milk, rice" becomes 3 items |
| Photo as proof | Take a photo when checking an item; it is saved with the item | Photo of the stove turned off |
| Photo recognition | Snap a scene; the app suggests which items it sees for the user to confirm | Open suitcase checks off toothbrush and charger |
| Smart starting lists | Describe the situation and get a suggested list to edit | "Weekend camping trip" |
| Reuse | Repeating lists reset with one tap | Weekly groceries, gym bag |
| Easy sharing | Send a list by link; no account needed to view or check items | Parent checks off a shared packing list |
| Simple interface | Large text, few screens, one big talk button; advanced options hidden | Works for first-time smartphone users |

## Situations it covers

- Weekly groceries and household restocking
- Moving into a new apartment or dorm
- Party or event supplies
- Trips
- Home repair projects
- Later: small-business restocking

## Flow

1. **Create** a list by voice or typing ("move-in list for 3 roommates, $300 budget"). AI builds a smart starting list for that situation, within the budget. The user confirms or edits it.
2. **Share** by link if others are involved. People claim items they'll buy.
3. **Check items off with proof:**
   - Scan a receipt: AI matches its lines to list items ("2% MILK 1GAL" → milk) and checks off several at once, with prices attached.
   - Or buy in the app with PayPal Checkout: the PayPal order is the proof, no scan needed.
4. **Extras and gaps:** receipt lines that match nothing are flagged as extras ("3 items not on the list, $14.20"). Items still unchecked stay open, so you see what you forgot.
5. **Settle up:** on shared lists, the app works out who owes whom and settles up with PayPal invoices.
6. **History:** the finished list joins your history.

## Pages

| Page | Shows | Details |
|---|---|---|
| Progress | Items done out of total | Looks like other checklists, with items and checkboxes, plus a progress bar showing how many items have been checked off so far |
| Items | Status, price, who bought it; tap to see its receipt | Each item's status and suggested price; for checked-off items, the price and who checked it off. Proof of check-off and purchase is viewable here |
| Money | Spent vs budget, extras, per-person totals on shared lists | A dashboard of money spent on items compared with the total budget, with each person's spending |
| Receipts | Gallery of scans and PayPal orders for this list | Linked directly with the Items page. Stores all receipts and any proof of purchase along with item names, organised per checklist folder (trip, grocery, move-in, …) |
| History | Spending by list type and by month (groceries vs trips vs home) | Buy again: start a new list from a past one. This is the retention hook. Price memory: "Last time you paid $4.29 for this." |
| Settle-up | Who owes whom, PayPal invoice status | Uses invoices to split the money between people in a group purchase |

## Who does what

| Part | Responsibilities |
|---|---|
| AI | Smart starting lists from one sentence; voice input; reading receipts and matching lines to items; spotting extras; price estimates for the budget |
| PayPal | Checkout for buying from the list (order = proof); Invoicing for settle-up on shared lists; PayPal orders stored beside receipts in each list's money view |
| Code | Split math, budget totals, assignment of unclaimed items |

## Feature specs

### Smart starting lists (built)

The person describes the situation in one sentence ("weekend camping trip for 3 friends at a lake"), with an optional budget. The AI returns every item **the group needs for that specific situation**: shared items counted once, with the quantity the group needs, short plain names, and a typical store price per unit (0 for things usually already owned, shown as no price).

- Nothing is saved until the person reviews it (decision 5): they untick what they don't need, then create the list.
- The AI is asked to stay within the budget, but the check is done in code (decision 10): the review screen shows the estimated total and how far over budget it is.
- `POST /api/lists/suggest` returns the suggestion; `POST /api/lists` saves the edited one.

### Item splitting (built)

Every item can have a person responsible for buying it, and the list keeps who paid and what it cost.

- **Responsibility:** anyone on the list picks "Ann buys it" on an item (`claimed_by`). "Share out the rest evenly" gives every open, unclaimed item to someone, most expensive first to whoever carries the least estimated cost so far (`POST /api/lists/{id}/assign`).
- **Paying and price:** when an item is bought (PayPal order, receipt, or checked off with a price), the item records who paid (`bought_by`) and what was paid for all of it (`price_cents`).
- **Settling up:** the Money panel shows what each person paid, their equal share of what was spent, and the fewest payments that even it out ("Cat pays Ann $20.00"), from `GET /api/lists/{id}/split`. Receipt extras are personal and not split; an item checked off without a name is reported, not split.
- Next: send those payments as PayPal invoices (Settle-up page).

### Receipt scanning (built)

1. On the list, "Take a photo of the receipt" opens the phone's back camera (`<input type="file" capture="environment">`; a file picker on a computer). The photo is shrunk to 2000 px JPEG in the browser.
2. **AWS Textract** (`AnalyzeExpense`) reads it into line items, each with its price and a confidence score; lines under 90% confidence are flagged "hard to read". While Textract is unavailable, the Ollama vision model reads the photo instead (no confidence scores).
3. **The Ollama model** (one text-only call with a JSON schema; decision 38) matches each line to an open list item or to none. It sees item names and receipt text only, never IDs or prices.
4. The person checks the proposals and corrects any line with a dropdown (decision 5), then confirms.
5. Matched items are checked off with the receipt's prices (several lines can be one item) and the scanner as buyer; unmatched lines become extras. The photo is kept in the private `receipts` bucket as proof.

### Photo recognition (planned: spec and learning plan only)

**Goal:** point the camera at real things (an open suitcase, a shopping bag, a shelf) and the app recognises which list items are in view, then checks them off once the person confirms. Example: a photo of a packed suitcase checks off toothbrush, charger and passport.

**User flow**

1. On a list, tap "Check off with the camera". A live camera view opens (back camera), or the native camera on phones without live preview support.
2. Take one photo (or several in a row for a big bag).
3. The app shows "I can see: toothbrush, charger" with a checkbox per item, plus "Not sure: passport?" for low-confidence ones, unticked.
4. The person confirms; those items are checked off, and the photo is saved with each item as proof ("Photo as proof").
5. Nothing is checked off without the confirm step (decision 5).

**Options to learn before choosing**

| Option | How it works | Good at | Weak at | Cost |
|---|---|---|---|---|
| A. Vision LLM (recommended start) | One call to a vision model (Claude Haiku 5.5 with image input, or the Ollama vision model from decision 11) with the photo and the open items' names; structured output returns the matched item numbers and a confidence | Any item name, including vague ones ("charger", "medicine bag"); same pattern as receipt matching | Can't draw boxes live; one call per photo | Per photo |
| B. AWS Rekognition + text LLM | `DetectLabels` returns generic labels ("Toothbrush", "Bottle", "Electronics") with confidence; a cheap text LLM call maps labels to list items, like Textract + Haiku | Cheap, fast, mirrors the receipt pipeline | Labels are generic: "Electronics" is not "phone charger"; small items in a pile are missed | Per photo |
| C. On-device detection | TensorFlow.js COCO-SSD or MediaPipe Object Detector runs in the browser on the live camera feed | Real-time boxes, works offline, no server cost or upload | Only about 80 everyday classes (no "passport", "sunscreen"); heavy download for older phones | Free |

**Recommended plan:** build option A first, because list items are open-ended and only a vision LLM can name them. Keep option C in mind for a live "scanning" feel later.

**Planned API**

- `POST /api/lists/{id}/photos` (body: the image, like receipts): stores the photo, returns `[{itemId, confidence}]` proposals.
- `POST /api/photos/{id}/confirm` with `{"itemIds": [...]}`: checks those items off with the photo as proof.
- Schema: a `photos` table (list, member, image path, proposals, confirmed_at) and `items.photo_id`.

**Acceptance criteria**

- A photo of 5 packed items on a 20-item list proposes at least 4 of the 5, and proposes nothing that isn't in the photo more than 1 time in 10 (measured on 20 test photos).
- Proposals arrive in under 5 seconds on a phone connection.
- Low-confidence matches are shown unticked.
- The photo is never public: private bucket, served by the backend.

**Open questions:** how to treat people in the photo (blur, or warn before upload); whether one item can be "seen" for quantity (3 water bottles); whether to use the same model as receipts or one vision model for both (decision 11).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the stack.
