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

See [ARCHITECTURE.md](ARCHITECTURE.md) for the stack.
