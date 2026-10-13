# HeyList — Roadmap

The project notes do not set dates or phases beyond "first", "stretch", and "later"; this roadmap keeps to that.

## Status

The hackathon flow is built end to end on the PayPal sandbox: AI starting lists, sharing by link, check-off by receipt scan or PayPal Checkout, the six pages, settle-up with PayPal invoices, and reuse from History. It is not deployed yet, and the pages, the PayPal approval popup on a real list, and paying an invoice still need a run by hand in a browser (issues 15 and 16). Two spec features are not built: taking a photo as proof for a single item, and recognising items in a photo of a scene.

## First: hackathon build

Target: [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). First use case: packing before a holiday.

Flow, end to end:

- [x] Create a list by voice or typing; AI builds a smart starting list within the budget; user confirms or edits
- [x] Share by link; people claim items they'll buy
- [x] Check off by receipt scan: AI matches lines to items, with prices attached
- [x] Check off by PayPal Checkout: the order is the proof
- [x] Flag receipt lines that match nothing as extras; keep unchecked items open
- [x] Settle up on shared lists with PayPal invoices
- [x] Finished list joins history

Core features:

- [x] Type
- [x] Voice
- [ ] Photo as proof (a receipt photo is kept as proof; a photo per item is not built)
- [ ] Photo recognition
- [x] Smart starting lists
- [x] Reuse (reset a repeating list with one tap)
- [x] Easy sharing (no account)
- [x] Simple interface

Pages:

- [x] Progress
- [x] Items
- [x] Money
- [x] Receipts
- [x] History
- [x] Settle-up

Infrastructure:

- [x] Supabase (lists, receipts storage; shared lists update by polling, not Realtime — decision 55)
- [x] FastAPI backend, reached through the Next.js `/api/*` rewrite
- [x] PayPal sandbox: Orders API (create and capture)
- [x] PayPal sandbox: Checkout JS SDK v6 on the list's Progress page
- [x] PayPal sandbox: Invoicing API
- [x] LLM with vision via the Ollama API
- [ ] Deploy on Render (`render.yaml` is ready; not deployed)
- [x] Sponsor tools: APIMatic Context Plugin, Postman

Validation:

- [ ] Student, busy parent, and older relative can each make and finish a list without help

## Stretch

- [ ] Channel3

## Later

- Native app
- Small-business restocking
