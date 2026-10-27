# HeyList

**Turn everyday needs into shared lists, and know what really got done.**

HeyList turns a sentence like "weekend camping trip for 3 friends, $150" into a list, lets the group split up who buys what, and keeps a record of what was actually bought, by whom, for how much, and how they know. The AI and PayPal aren't separate features: the AI's list sets what PayPal charges, and PayPal payments and AI-read receipts are what check items off.

A checklist website for everyday life, built mobile-first so it works in a phone browser with nothing to install. Anyone can use it, including people with little tech experience. Create lists by typing, speaking, or taking a photo, whichever is easiest at that moment.

The first use case is packing before a holiday; the app stays general-purpose so it fits groceries, errands, routines, and any other daily list.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).

> **Status:** early build. Built so far: AI starting lists from one sentence, claiming and sharing out items, paying through the PayPal sandbox, receipt scanning (Textract, or the Ollama vision model while Textract is unavailable, then Ollama matching, with a confirm step), and the split of who owes whom. Voice, photo recognition, invoices and history are planned, not built. See [docs/ROADMAP.md](docs/ROADMAP.md). Before working with API keys, read [docs/RULES.md](docs/RULES.md).

## The loop

Every step keeps what the step before it established: the quantities and estimates from the AI, who claimed what, and what proves an item was bought.

| Step | Question it answers | How | Status |
|---|---|---|---|
| **Need** | What do we need? | Type or say one sentence ("…, $200 budget"); the AI suggests a list with quantities and estimated prices within the budget; you drop, rename, change or add items before anything is saved | Built |
| **Coordinate** | Who handles it? | Share the link, join by name, claim items, or share out the rest evenly by estimated cost | Built. Realtime updates planned |
| **Verify** | What got done? | Tick it off by hand (you say what you paid), pay with PayPal (a completed capture is the proof), or scan a receipt (the AI reads it and matches lines to items, and you confirm). Each item says what its status rests on: "Paid with PayPal", "On a receipt", "Marked bought by hand", or "Payment pending at PayPal" | Built |
| **Settle** | Who owes whom? | Code (not AI) works out each person's share from the recorded prices and the fewest payments to even up | Built. PayPal invoices planned |

Labels claim only what the evidence shows: a PayPal capture proves the payment, not that the item arrived. If an item is bought twice (a receipt and a PayPal payment at the same time), the PayPal charge is refunded to the person who paid it.

## Why

Existing checklist apps assume users are comfortable tapping through menus, folders, and settings. People with little tech experience often give up on them and fall back to paper or memory.

- Starting a list means facing a blank page.
- Voice input exists but is buried, and usually dumps everything into one line.
- There is no easy way to prove a task was done ("did I turn off the stove?").
- Sharing a list with family usually requires everyone to have an account.

## Features

Built:

- **Smart starting lists** — describe the situation and get a suggested list to edit.
- **Easy sharing** — send a list by link; no account needed to view, claim or check items.
- **PayPal Checkout** — pay for chosen items; the captured order is the proof, and pending payments hold their items.
- **Receipt scanning** — the AI reads a receipt photo and proposes a list item for each line; you confirm.
- **Split and settle** — who paid what, equal shares, and who pays whom.
- **History** — lists this browser has opened, spending by type and month, buy again.

- **Voice** — tap the mic and say it; the words fill the prompt (where the browser supports speech recognition).

Planned:

- **Photo as proof** and **photo recognition** — see [docs/SPEC.md](docs/SPEC.md#photo-recognition-planned-spec-and-learning-plan-only).
- **Reuse** — repeating lists reset with one tap.
- **PayPal invoices** for settle-up.

## How it works

1. Create a list by voice or typing ("move-in list for 3 roommates, $300 budget"). AI builds a smart starting list within the budget; you confirm or edit it.
2. Share by link if others are involved. People claim items they'll buy.
3. Check items off with proof: scan a receipt and AI matches its lines to list items with prices attached, or buy in the app with PayPal Checkout, where the order is the proof.
4. Receipt lines that match nothing are flagged as extras. Unchecked items stay open, so you see what you forgot.
5. On shared lists, the app works out who owes whom and settles up with PayPal invoices.
6. The finished list joins your history.

## Pages

Progress · Items · Money · Receipts · History · Settle-up — see [docs/SPEC.md](docs/SPEC.md#pages).

## Stack

- **App:** Next.js website, mobile-first (native app later); `/api/*` is proxied to the backend
- **Backend:** FastAPI (Python) in `backend/`
- **Data:** Supabase — lists, receipts storage, realtime
- **Payments:** PayPal sandbox — Orders API through the PayPal Server SDK (Python, APIMatic-generated); Checkout JS SDK and Invoicing API planned
- **AI:** one LLM with vision for lists and receipts (Ollama API); Web Speech API for voice
- **Hosting:** Render
- **Sponsor tools:** APIMatic Context Plugin, Postman, Render; Channel3 for the stretch

## Getting started

Copy the env template and fill in your PayPal sandbox keys (and the others as features land):

```bash
cp .env.example .env.local
```

Frontend:

```bash
npm install
npm run dev
```

Backend (FastAPI, proxied under `/api` by Next), in a second terminal. The venv can live anywhere; these commands assume it sits next to the repo, at `../.venv`:

```bash
python3 -m venv ../.venv
../.venv/bin/pip install -r backend/requirements.txt
cd backend && ../../.venv/bin/uvicorn main:app --port 8000 --env-file ../.env.local
```

Open [http://localhost:3000](http://localhost:3000).

Backend tests (from `backend/`): `../../.venv/bin/python -m unittest`

AI evaluation (paid: 20 Ollama calls; see [docs/RULES.md](docs/RULES.md)): `../../.venv/bin/python eval_starter.py --yes` from `backend/`, with `.env.local` loaded.

Other scripts: `npm run build`, `npm run start`, `npm run lint`.

When deploying, set `BACKEND_URL` before `next build`: Next resolves the `/api` rewrite at build time.

## Docs

- [Spec](docs/SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Decisions](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Changelog](docs/CHANGELOG.md)
- [Issues](docs/ISSUES.md)
- [PayPal](docs/PayPal.md)
- [Soft glass redesign](docs/REDESIGN.md)
- [Hackathon rules](docs/HACKATHON.md) · [Submission and demo script](docs/SUBMISSION.md) · [Improvements](docs/IMPROVEMENTS.md)

## License

[MIT](LICENSE)

## Links

- [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/)
- [PayPal developer dashboard](https://developer.paypal.com/dashboard/accounts)
- [Design (Figma)](https://www.figma.com/design/Wv3JGTqJewtLNMax2PWmSk): soft glass (built) and Midnight (dark, later), each with mobile and web screens
- Sponsors: [APIMatic](https://paypalaihackathon.devpost.com/details/apimatic) · [Postman](https://paypalaihackathon.devpost.com/details/postman) · [Render](https://paypalaihackathon.devpost.com/details/render) · [Channel3](https://paypalaihackathon.devpost.com/details/channel3)
