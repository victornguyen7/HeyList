# HeyList — Roadmap

The project notes do not set dates or phases beyond "first", "stretch", and "later"; this roadmap keeps to that.

## Status

Next.js scaffold only. No features built yet.

## First: hackathon build

Target: [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). First use case: packing before a holiday.

Flow, end to end:

- [ ] Create a list by voice or typing; AI builds a smart starting list within the budget; user confirms or edits
- [ ] Share by link; people claim items they'll buy
- [ ] Check off by receipt scan: AI matches lines to items, with prices attached
- [ ] Check off by PayPal Checkout: the order is the proof
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
- [ ] PayPal sandbox (Checkout JS SDK + Orders API, Invoicing API)
- [ ] LLM with vision via the Ollama API
- [ ] Deploy on Render
- [ ] Sponsor tools: APIMatic Context Plugin, Postman

Validation:

- [ ] Student, busy parent, and older relative can each make and finish a list without help

## Stretch

- [ ] Channel3

## Later

- Native app
- Small-business restocking
