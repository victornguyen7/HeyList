# HeyList

**Simple checklists with money built in.**

A simple checklist website for everyday life, built mobile-first so it works in a phone browser with nothing to install. Anyone can use it, including people with little tech experience. Create lists by typing, speaking, or taking a photo, whichever is easiest at that moment.

The first use case is packing before a holiday; the app stays general-purpose so it fits groceries, errands, routines, and any other daily list.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).

> **Status:** early build. Built so far: AI starting lists from one sentence, claiming and sharing out items, paying through the PayPal sandbox, receipt scanning (Textract, or the Ollama vision model while Textract is unavailable, then Ollama matching, with a confirm step), and the split of who owes whom. Voice, photo recognition, invoices and history are planned, not built. See [docs/ROADMAP.md](docs/ROADMAP.md). Before working with API keys, read [docs/RULES.md](docs/RULES.md).

## Why

Existing checklist apps assume users are comfortable tapping through menus, folders, and settings. People with little tech experience often give up on them and fall back to paper or memory.

- Starting a list means facing a blank page.
- Voice input exists but is buried, and usually dumps everything into one line.
- There is no easy way to prove a task was done ("did I turn off the stove?").
- Sharing a list with family usually requires everyone to have an account.

## Features

- **Type** — add items the familiar way.
- **Voice** — speak naturally; the app splits speech into clean items and shows them to confirm.
- **Photo as proof** — take a photo when checking an item; it is saved with the item.
- **Photo recognition** — snap a scene; the app suggests which items it sees for you to confirm.
- **Smart starting lists** — describe the situation and get a suggested list to edit.
- **Reuse** — repeating lists reset with one tap.
- **Easy sharing** — send a list by link; no account needed to view or check items.
- **Simple interface** — large text, few screens, one big talk button; advanced options hidden.

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

## Links

- [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/)
- [PayPal developer dashboard](https://developer.paypal.com/dashboard/accounts)
- [Dark redesign draft (Figma)](https://www.figma.com/design/Wv3JGTqJewtLNMax2PWmSk)
- Sponsors: [APIMatic](https://paypalaihackathon.devpost.com/details/apimatic) · [Postman](https://paypalaihackathon.devpost.com/details/postman) · [Render](https://paypalaihackathon.devpost.com/details/render) · [Channel3](https://paypalaihackathon.devpost.com/details/channel3)
