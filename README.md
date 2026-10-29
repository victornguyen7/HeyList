# HeyList

**Say what you need. Share the list. PayPal proves what got done.**

HeyList turns one sentence ("weekend camping trip for 3 friends, $150") into a shared list, lets the group split up who buys what, and records what was actually bought, by whom, for how much, and how we know. The AI's list sets what PayPal charges, and PayPal captures and AI-read receipts are what check items off.

It's a mobile-first website that needs no install and no account, built for people who give up on fiddly checklist apps.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/) · [MIT License](LICENSE)

## Try it in 2 minutes

**Live demo:** https://heylist-web.onrender.com (PayPal **sandbox**: no real money moves)

Sandbox buyer account for judges (log in on PayPal's page when paying):

| Email | Password |
|---|---|
| `JUDGE_SANDBOX_EMAIL` | `JUDGE_SANDBOX_PASSWORD` |

1. On the home page, tap **New here? See how it works with a sample trip**. You join a camping trip with Ann and Ben, who have already bought the tent and the snacks.
2. Tap **Pay for your items with PayPal**, approve with the account above, and come back: your items are checked off, with the PayPal payment as proof.
3. Open **Settle up** to see who owes whom. Pay Ann with PayPal (the money goes straight to her), or tap **Remind Ben** for a friendly AI-written message with a payment link.
4. Or start your own: type or say one sentence, keep what you need, and share the link. Changes appear on everyone's phone as they happen.

## How it works

| Step | Question | What happens |
|---|---|---|
| **Need** | What do we need? | Type or speak one sentence. The AI drafts a list with quantities and estimated prices that fit the budget, and you edit it before anything is saved. |
| **Coordinate** | Who handles it? | Share a link, join by name, and claim items, or share out the rest evenly by cost. |
| **Shop** | Where do I buy it? | **Find in stores** pulls real products from Channel3, and the AI keeps only the true matches. **Shop this list for me** proposes products within budget for the items you tick, and you approve one PayPal payment. |
| **Verify** | What got done? | Pay with PayPal (a `COMPLETED` capture is the proof), scan a receipt (the AI matches each line to an item and you confirm), or tick it off by hand. Every item shows what its status rests on: *Paid with PayPal*, *On a receipt*, *Marked bought by hand*, or *Payment pending*. |
| **Settle** | Who owes whom? | Deterministic code (not AI) computes each share and the fewest payments needed. You pay a friend directly with PayPal, or send an AI-written reminder. |

Labels claim only what the evidence shows: a capture proves payment, not delivery. If an item is bought twice (a receipt and a PayPal payment at once), the PayPal charge is refunded automatically.

## PayPal integration (sandbox)

- **Orders API v2** through the official **PayPal Server SDK** (Python, APIMatic-generated): create and capture orders for list items. The server sets prices from the list in integer cents and never takes them from the browser.
- **Pay a friend:** for settle-up, the order's payee is the person owed, so money never passes through HeyList.
- **Payments API v2 refunds** for double purchases, with idempotency keys on every call.
- **JS SDK v6** PayPal and Venmo buttons, falling back to PayPal's hosted page.
- **Webhooks**, signature-verified with PayPal, finish pending payments. Items are checked off on *capture* status, not order status.

## AI and tools

| Tool | How HeyList uses it |
|---|---|
| **AWS Textract** `AnalyzeExpense` | Reads receipt line items and totals (primary reader) |
| **Ollama** (`gemma4:31b`, vision) | Drafts starting lists as validated JSON, matches receipt lines to items, filters store results to real matches, writes payment reminders, and reads receipts when Textract is unavailable |
| **Channel3** product search | Real products and prices for "Find in stores" and "Shop this list for me". The chosen price is re-read on the server and is what PayPal charges. |
| **Web Speech API** | Voice input in supported browsers |
| **APIMatic** Context Plugin, **Postman** | PayPal SDK guidance and API testing during development |
| **Render** | Hosting (`render.yaml`) |
| **Claude Code** | Coding assistant during development |

**Measured, not assumed:**

- **Starting lists**, 30 test cases ([`backend/eval/eval_report.json`](backend/eval/eval_report.json)): **96/98** expected items found, **12/12** quantities right, **8/8** conditions kept, **0** invented items.
- **Receipt reading**, 100 real receipts ([docs/RECEIPT_EVAL.md](docs/RECEIPT_EVAL.md)): Textract got **94%** of totals and **89%** of prices right, which is why it reads first and Ollama is the fallback.

## Architecture

```
Next.js 16 (React 19, mobile-first)  ──/api──▶  FastAPI (Python 3.14)  ──▶  PayPal · Ollama · Textract · Channel3
            ▲                                          │
            └──── Supabase Realtime ◀──── Supabase (Postgres, Storage, Auth)
```

Accounts are optional: guests join by name, and signed-in users (Supabase email and password) keep the same identity on every device. More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run locally

Requires Node.js 24 and Python 3.14. Copy the env template and fill in the keys: PayPal sandbox, Ollama and Supabase are required, while Textract and Channel3 are optional.

```bash
cp .env.example .env.local

# Frontend
npm install && npm run dev

# Backend (second terminal)
python3 -m venv ../.venv
../.venv/bin/pip install -r backend/requirements.txt
cd backend && ../../.venv/bin/uvicorn main:app --port 8000 --env-file ../.env.local
```

Open http://localhost:3000, then apply the database schema from [`supabase/schema.sql`](supabase/schema.sql) to your Supabase project.

- **Tests:** `../../.venv/bin/python -m unittest` from `backend/` (159 tests, with every external API mocked) and `npm run lint`.
- **Deploying:** set `BACKEND_URL` before `next build`, because the `/api` proxy is resolved at build time.
- **API keys:** read [docs/RULES.md](docs/RULES.md) before using real keys. The evals make paid calls.

## Status

This is a working prototype deployed on Render, built from scratch during the hackathon (first commit 12 Oct 2026). Planned next: photo proof, photo recognition, and reusable lists ([docs/ROADMAP.md](docs/ROADMAP.md)).

## Docs

[Spec](docs/SPEC.md) · [Architecture](docs/ARCHITECTURE.md) · [Decisions](docs/DECISIONS.md) · [PayPal](docs/PayPal.md) · [Roadmap](docs/ROADMAP.md) · [Changelog](docs/CHANGELOG.md) · [Hackathon rules](docs/HACKATHON.md) · [Submission](docs/SUBMISSION.md) · [Design (Figma)](https://www.figma.com/design/Wv3JGTqJewtLNMax2PWmSk)
