# HeyList — Roadmap

The project notes do not set dates or phases beyond "first", "stretch", and "later"; this roadmap keeps to that.

## Status

Early build. The FastAPI backend creates and captures PayPal sandbox orders for a hard-coded sample list, and the app shows the capture result when PayPal sends the buyer back. No user-facing features yet.

## First: hackathon build

Target: [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). First use case: packing before a holiday.

Flow, end to end:

- [ ] Create a list by voice or typing; AI builds a smart starting list within the budget; user confirms or edits
- [ ] Share by link; people claim items they'll buy
- [ ] Check off by receipt scan: AI matches lines to items, with prices attached
- [ ] Check off by PayPal Checkout: the order is the proof
  - [x] Backend: create order from item IDs, capture, report capture status and items bought
  - [x] Return page: capture after PayPal approval and show the result
  - [ ] Create-order route and checkout button
  - [ ] Store the order as proof and check the items off
- [ ] Flag receipt lines that match nothing as extras; keep unchecked items open
- [ ] Settle up on shared lists with PayPal invoices
- [ ] Finished list joins history

Core features:

- [ ] Type
- [ ] Voice
- [ ] Photo as proof
- [ ] Photo recognition
- [ ] Smart starting lists
- [ ] Reuse (reset a repeating list with one tap)
- [ ] Easy sharing (no account)
- [ ] Simple interface

Pages:

- [ ] Progress
- [ ] Items
- [ ] Money
- [ ] Receipts
- [ ] History
- [ ] Settle-up

Infrastructure:

- [ ] Supabase (lists, receipts storage, realtime)
- [x] FastAPI backend, proxied under `/api` by Next.js
- [ ] PayPal sandbox (Checkout JS SDK + Orders API, Invoicing API) — Orders API done via the PayPal Server SDK
- [ ] LLM with vision via the Ollama API
- [ ] Deploy on Render
- [ ] Sponsor tools: APIMatic Context Plugin, Postman — APIMatic in use (PayPal Server SDK and its Context Plugin skills)

Validation:

- [ ] Student, busy parent, and older relative can each make and finish a list without help

## Stretch

- [ ] Channel3

## Later

- Native app
- Small-business restocking
