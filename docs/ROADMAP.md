# HeyList — Roadmap

The project notes do not set dates or phases beyond "first", "stretch", and "later"; this roadmap keeps to that.

## Status

Early build. Lists live in Supabase. The home page makes an AI starting list from one sentence; a list page lets people join by name, claim items, share out the rest, pay through the PayPal sandbox, scan receipts (once AWS and Anthropic keys are set), and see who owes whom.

## First: hackathon build

Target: [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). First use case: packing before a holiday.

Flow, end to end:

- [ ] Create a list by voice or typing; AI builds a smart starting list within the budget; user confirms or edits
  - [x] Typing: one sentence and an optional budget, AI suggestion reviewed before saving, over-budget shown
  - [ ] Voice
- [ ] Share by link; people claim items they'll buy
  - [x] Join by name, claim items, share out unclaimed items evenly by estimated cost
  - [ ] Realtime updates when someone else changes the list
- [ ] Check off by receipt scan: AI matches lines to items, with prices attached
  - [x] Camera capture, Textract line items with confidence, Ollama matching, confirm step, prices and buyer recorded
  - [x] Ollama vision reads the photo while Textract is unavailable (decision 38)
  - [ ] Live test with real receipts and Textract (needs the IAM permission)
  - [ ] Claude Haiku matching (later, owner's call)
  - [ ] Discounts and voided lines (currently dropped)
- [ ] Check off by PayPal Checkout: the order is the proof
  - [x] Backend: create order from item IDs, capture, report capture status and items bought
  - [x] Return page: capture after PayPal approval and show the result
  - [x] Create-order route and checkout button (test UI for the sample list)
  - [x] Store the order as proof and check the items off
- [x] Flag receipt lines that match nothing as extras; keep unchecked items open
- [ ] Settle up on shared lists with PayPal invoices
  - [x] Split math: each person's paid amount, equal share, and the fewest payments to settle
  - [ ] Send those payments as PayPal invoices
- [ ] Finished list joins history

Core features:

- [ ] Type
- [ ] Voice
- [ ] Photo as proof
- [ ] Photo recognition (spec in [SPEC.md](SPEC.md#photo-recognition-planned-spec-and-learning-plan-only))
  - [ ] Learn: send a photo plus item names to a vision model (the Ollama model, which already reads receipts; or Claude Haiku 5.5 later) and read back structured matches; try 20 real photos and note hits and misses
  - [ ] Learn: AWS Rekognition `DetectLabels` on the same photos, to compare its generic labels with option A
  - [ ] Learn: TensorFlow.js COCO-SSD or MediaPipe Object Detector on a live camera feed in the browser, to see what real-time detection can and can't name
  - [ ] Learn: `getUserMedia` live camera preview on iOS Safari and Android Chrome, with `<input capture>` as the fallback
  - [ ] Decide the option and record it in DECISIONS.md
  - [ ] Build: `photos` table, upload and confirm routes, camera screen with confirm step
  - [ ] Check the acceptance criteria in the spec
- [x] Smart starting lists
- [ ] Reuse (reset a repeating list with one tap)
- [ ] Easy sharing (no account)
- [ ] Simple interface

Pages:

- [ ] Progress
- [ ] Items
- [ ] Money (split panel built: spent vs budget, per person, who pays whom)
- [ ] Receipts
- [ ] History
- [ ] Settle-up

Infrastructure:

- [ ] Supabase (lists, receipts storage, realtime): lists and receipt storage done; realtime not yet
- [x] FastAPI backend, proxied under `/api` by Next.js
- [ ] PayPal sandbox (Checkout JS SDK + Orders API, Invoicing API) — Orders API done via the PayPal Server SDK
- [ ] LLM with vision via the Ollama API: starting lists and receipt matching done; receipt photos are read by Ollama vision when Textract is unavailable (decision 38)
- [ ] Deploy on Render
- [ ] Sponsor tools: APIMatic Context Plugin, Postman — APIMatic in use (PayPal Server SDK and its Context Plugin skills)

Validation:

- [ ] Student, busy parent, and older relative can each make and finish a list without help

## Stretch

- [ ] Channel3

## Later

- Native app
- Small-business restocking
