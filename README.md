# HeyList

**Turn everyday needs into shared lists, and know what really got done.**

HeyList turns a sentence like "weekend camping trip for 3 friends, $150" into a list, lets the group split up who buys what, and keeps a record of what was actually bought, by whom, for how much, and how they know. The AI and PayPal aren't separate features: the AI's list sets what PayPal charges, and PayPal payments and AI-read receipts are what check items off.

A checklist website for everyday life, built mobile-first so it works in a phone browser with nothing to install. Anyone can use it, including people with little tech experience. Create lists by typing, speaking, or taking a photo, whichever is easiest at that moment.

The first use case is packing before a holiday; the app stays general-purpose so it fits groceries, errands, routines, and any other daily list.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).

## Try it in 2 minutes

**Live demo:** https://heylist-web.onrender.com (PayPal **sandbox**: no real money moves)

To pay, log in on PayPal's page with this sandbox buyer account, made for judges and testers:

| Email | Password |
|---|---|
| `JUDGE_SANDBOX_EMAIL` | `JUDGE_SANDBOX_PASSWORD` |

1. On the home page, tap **New here? See how it works with a sample trip**. You join a camping trip with Ann and Ben; they've already bought the tent and the snacks.
2. Tap **Pay for your items with PayPal**, approve on PayPal's page with the account above, and come back: your items are checked off, with the PayPal payment as proof.
3. Open **Settle up**: HeyList shows who owes whom. Pay Ann with PayPal (the money goes to her account, not HeyList's), or tap **Remind Ben** for a friendly AI-written message with a link to pay.
4. Or start your own: type one sentence ("camping at Big Sur with 4 friends, $200 budget"), keep what you need, and share the link. Changes show on everyone's phone as they happen.

**PayPal** (sandbox, Orders API v2 through the PayPal Server SDK): create and capture orders for list items, read pending captures, refund an item someone already bought, and pay a friend directly (the order's payee is the person owed).

**AI:** Ollama (`gemma4:31b`) drafts the starting list, matches receipt lines to items, checks store search results and writes payment reminders. AWS Textract reads receipt photos. Channel3 finds real products for "Shop this list for me".

> **Status:** working prototype, deployed on Render. Not built: photo recognition and reusable lists ([docs/ROADMAP.md](docs/ROADMAP.md)). Before working with API keys, read [docs/RULES.md](docs/RULES.md).

## The loop

Every step keeps what the step before it established: the quantities and estimates from the AI, who claimed what, and what proves an item was bought.

| Step | Question it answers | How | Status |
|---|---|---|---|
| **Need** | What do we need? | Type or say one sentence ("…, $200 budget"); the AI suggests a list with quantities and estimated prices within the budget; you drop, rename, change or add items before anything is saved | Built |
| **Coordinate** | Who handles it? | Share the link, join by name, claim items, or share out the rest evenly by estimated cost | Built, with live updates: a change on one phone shows on the others |
| **Verify** | What got done? | Tick it off by hand (you say what you paid), pay with PayPal (a completed capture is the proof), or scan a receipt (the AI reads it and matches lines to items, and you confirm). Each item says what its status rests on: "Paid with PayPal", "On a receipt", "Marked bought by hand", or "Payment pending at PayPal" | Built |
| **Settle** | Who owes whom? | Code (not AI) works out each person's share from the recorded prices and the fewest payments to even up. Pay the person you owe with PayPal, straight to their account; or send them a friendly AI-written reminder with a link to pay | Built |

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
- **Split and settle** — who paid what, equal shares, and who pays whom; pay the person you owe with PayPal, straight to their account.
- **Friendly reminders** — the AI drafts a kind "just a heads-up" message with a link that opens the payment; you send it from your own phone.
- **Shop this list for me** — tick items and the agent proposes real products from online stores within the budget; you approve one PayPal payment.
- **Sample trip** — try the whole loop alone, with a ready-made trip shared with Ann and Ben.
- **Live updates** — a claim, tick or payment on one phone shows on the others.
- **History** — lists this browser has opened, spending by type and month, buy again at the price really paid. Lists you've opened show at once from a saved copy, then refresh.
- **Optional login** — an email link; logged in, you join a list in one tap and are the same person on every device. Guests still just type a name.
- **Find in stores** — real products for an item from Channel3, checked by the AI so only real matches show; the chosen price is what PayPal charges.
- **Price memory** — suggested prices come from what people really paid (PayPal or a receipt), then a chosen store price, then the AI's guess.

- **Voice** — tap the mic and say it; the words fill the prompt (where the browser supports speech recognition).

Planned:

- **Photo as proof** and **photo recognition** — see [docs/SPEC.md](docs/SPEC.md#photo-recognition-planned-spec-and-learning-plan-only).
- **Reuse** — repeating lists reset with one tap.

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

- **Frontend:** Next.js 16 (App Router, Turbopack), React 19, TypeScript 5, Tailwind CSS 4, Geist fonts, on Node.js 24; mobile-first website (native app later); `/api/*` is proxied to the backend
- **Backend:** Python 3.14, FastAPI on uvicorn, in `backend/`; tests with `unittest`
- **Data and login:** Supabase — Postgres, receipt photo storage, Auth (email magic link, through `@supabase/supabase-js` in the browser and the `supabase` Python client in the backend), and Realtime broadcast to tell open pages a list changed
- **Payments:** PayPal sandbox — Orders API (create, capture, refund) through the PayPal Server SDK (Python, APIMatic-generated), with PayPal's hosted approval page. Checkout JS SDK and Invoicing API planned
- **AI:** one LLM with vision through the Ollama API (`ollama` client) for starting lists, receipt matching and checking store results
- **Receipts:** AWS Textract `AnalyzeExpense` (`boto3`), falling back to the Ollama vision model
- **Store products:** Channel3 product search (`httpx`)
- **Browser:** Web Speech API for voice, camera capture and canvas for receipt photos, `localStorage` for lists you've opened
- **Hosting:** Render (`render.yaml`: one Python and one Node web service)
- **Tools:** ESLint, APIMatic Context Plugin, Postman, Figma
- **Sponsor tools:** APIMatic Context Plugin, Postman, Render, Channel3

Versions and what each piece is used for: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#stack).

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
