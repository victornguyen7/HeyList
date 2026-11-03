# HeyList — Roadmap

The project notes do not set dates or phases beyond "first", "stretch", and "later"; this roadmap keeps to that.

## Status

Hackathon build complete and hosted on Render (2026-11-03). Home makes an AI starting list from one sentence, by voice or from a photo of a paper list, and marks what you already have. A list page lets people join by name, claim items, share out the rest, find real products and let the shopping agent propose a cart, pay through the PayPal sandbox (with Venmo), scan receipts, and settle up with PayPal. Left before the deadline: the demo video and the Devpost form ([SUBMISSION.md](SUBMISSION.md)).

## First: hackathon build

Target: [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). First use case: packing before a holiday.

Flow, end to end:

- [x] Create a list by voice or typing; AI builds a smart starting list within the budget; user confirms or edits
  - [x] Mark what someone already has, so it's checked off and costs nothing (decision 72)
  - [x] Typing: one sentence and an optional budget, AI suggestion reviewed before saving, over-budget shown
  - [x] Voice: the mic dictates the prompt with the browser's speech recognition (decision 47)
- [x] Share by link; people claim items they'll buy
  - [x] Join by name, claim items, share out unclaimed items evenly by estimated cost
  - [x] Realtime updates when someone else changes the list (decision 59)
- [ ] Check off by receipt scan: AI matches lines to items, with prices attached
  - [x] Camera capture, Textract line items with confidence, Ollama matching, confirm step, prices and buyer recorded
  - [x] Ollama vision reads the photo while Textract is unavailable (decision 38)
  - [x] Live test with real receipts and Textract (issue 15: 289 receipts, [RECEIPT_EVAL.md](RECEIPT_EVAL.md))
  - [ ] Claude Haiku matching (later, owner's call)
  - [x] Discounts, tax, tip and fees (decision 57); voided lines still dropped
  - [x] Scan a receipt from **Take a photo** on Progress (decision 72)
- [x] Check off by PayPal Checkout: the order is the proof
  - [x] Backend: create order from item IDs, capture, report capture status and items bought
  - [x] Return page: capture after PayPal approval and show the result
  - [x] Create-order route and checkout button (test UI for the sample list)
  - [x] Store the order as proof and check the items off
- [x] Flag receipt lines that match nothing as extras; keep unchecked items open
- [x] Settle up on shared lists with PayPal
  - [x] Split math: each person's paid amount, equal share, and the fewest payments to settle
  - [x] Pay the person owed with PayPal, straight to their account (decision 60); not yet tried on the sandbox
- [ ] Finished list joins history

Core features:

- [x] Type
- [x] Voice (browser speech recognition, decision 47)
- [ ] Photo as proof
- [x] Photo of a paper list (decision 70); check off one item with a photo and ask its price (decision 71), or scan a receipt from the same button (decision 72). The paper list was tried on one real photo (2026-10-31, [IMPROVEMENTS.md](IMPROVEMENTS.md) 9A); the item photo hasn't been tried live
- [ ] Packing list from a photo of an empty bag (brainstorm in [IMPROVEMENTS.md](IMPROVEMENTS.md), phase 9)
- [ ] Photo recognition of several items at once (spec in [SPEC.md](SPEC.md#photo-recognition-of-several-items-planned-spec-and-learning-plan-only))
  - [ ] Learn: send a photo plus item names to a vision model (the Ollama model, which already reads receipts; or Claude Haiku 5.5 later) and read back structured matches; try 20 real photos and note hits and misses
  - [ ] Learn: AWS Rekognition `DetectLabels` on the same photos, to compare its generic labels with option A
  - [ ] Learn: TensorFlow.js COCO-SSD or MediaPipe Object Detector on a live camera feed in the browser, to see what real-time detection can and can't name
  - [ ] Learn: `getUserMedia` live camera preview on iOS Safari and Android Chrome, with `<input capture>` as the fallback
  - [ ] Decide the option and record it in DECISIONS.md
  - [ ] Build: `photos` table, upload and confirm routes, camera screen with confirm step
  - [ ] Check the acceptance criteria in the spec
- [x] Smart starting lists
- [ ] Reuse (reset a repeating list with one tap)
- [x] Easy sharing (no account)
- [ ] Simple interface

Pages (simple first versions built, at `/lists/<id>` and `/history`):

- [x] Progress
- [x] Items
- [x] Money
- [x] Receipts
- [x] History (by type, by month, buy again, price memory; loads in one request and shows the saved copy at once)
- [x] Settle-up (who pays whom, and paying it with PayPal)

Infrastructure:

- [x] Supabase (lists, receipts storage, realtime)
- [x] FastAPI backend, proxied under `/api` by Next.js
- [x] PayPal sandbox: Orders API via the PayPal Server SDK, JS SDK v6 buttons with Venmo, webhooks (Invoicing dropped, decision 60)
- [x] LLM with vision via the Ollama API: starting lists, receipt matching, store-match checks, reminders, photo checks; Ollama vision reads receipts and paper lists when Textract is unavailable (decision 38)
- [x] Deploy on Render (`render.yaml` Blueprint: heylist-api and heylist-web with health checks, the heylist-shared env group, and the heylist-sweep cron job, decision 74)
- [ ] Sponsor tools: APIMatic Context Plugin, Postman — APIMatic in use (PayPal Server SDK and its Context Plugin skills)

Validation:

- [ ] Student, busy parent, and older relative can each make and finish a list without help

## Stretch

- [x] Channel3: "Find in stores" per item (on Items and Progress), results checked by the AI, the chosen price charged with PayPal (decisions 50, 51). No store order yet: Channel3's checkout isn't open
- [x] Shopping agent: "Shop this list for me" proposes a cart within the budget, paid in one PayPal order (decision 61)

## Redesign ([Figma](https://www.figma.com/design/Wv3JGTqJewtLNMax2PWmSk))

- [x] Soft glass, mobile and web layouts (decision 46)
- [ ] Dark ("Midnight") theme: the Figma file has mobile and web screens. Add its colours as a second set of the CSS variables in `app/globals.css`, with a switch

## Later

- Native app
- Dark mode with a light/dark switch (soft glass is the light set; Midnight is in Figma)
- Small-business restocking
