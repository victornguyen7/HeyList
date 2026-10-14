# HeyList — Architecture

Planned architecture, with what is built so far marked in [Built so far](#built-so-far). See [CHANGELOG.md](CHANGELOG.md).

## Stack

| Layer | Choice |
|---|---|
| App | Next.js website, mobile-first so it works in phone browsers (native app later) |
| Backend | FastAPI (Python) in `backend/`; Next.js proxies `/api/*` to it, so the browser stays same-origin |
| Data | Supabase — lists, receipts storage, realtime |
| Payments | PayPal sandbox — Orders API (built, via the Python PayPal Server SDK), Checkout JS SDK and Invoicing API (planned) |
| AI | One LLM with vision for lists and receipts, served through the Ollama API |
| Voice | Web Speech API |
| Hosting | Render |
| Sponsor tools | APIMatic Context Plugin, Postman, Render; Channel3 for the stretch |

Currently installed:

- Frontend (`package.json`): Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5.
- Backend (`backend/requirements.txt`): FastAPI, uvicorn, `paypal-server-sdk` 2.4.0 (pulls in `apimatic-core`), Supabase client, Ollama client.

## Overview

```
              Phone browser (Next.js, mobile-first)
   type / voice (Web Speech API) / photo        PayPal checkout
                      |                                   |
                      v                                   v
                    Next.js app on Render  ── /api/* ──►  FastAPI backend
                                                          |
          +-----------------------+-----------------------+
          |                       |                       |
          v                       v                       v
   LLM with vision          Supabase                PayPal sandbox
   (Ollama API)             lists                   Orders API
   starting lists           receipts storage        Invoicing API
   receipt reading          realtime
   extras, price estimates
```

## Built so far

| File | What it does |
|---|---|
| `backend/sample_list.py` | Hard-coded sample items with prices in integer cents, and `total_cents()`, which validates a selection of item IDs and sums it. Stands in for LLM-generated and user-added items |
| `backend/paypal.py` | PayPal Server SDK client (sandbox, built on first use). `create_order()` and `capture_order()` |
| `backend/main.py` | FastAPI app. `GET /api/items`, `POST /api/orders` (returns the order ID and PayPal approval URL), `POST /api/orders/{order_id}/capture` |
| `app/checklist.tsx` | Test UI on the home page: pick sample items, pay with PayPal, and on return capture the order and show the paid items checked off |
| `next.config.ts` | Rewrites `/api/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`) |

Not yet built: storing orders as proof (nothing persists across reloads except via the return URL). `llm.py`, `money.py` and `photo.py` are empty placeholders.

### Payment flow

1. The client sends **item IDs only**. The backend looks up prices in `sample_list.py`, so a buyer cannot change what they pay.
2. `create_order()` sends the order to PayPal with the server-side total in USD, each item's ID in its `sku`, and the app as the return and cancel URL (`APP_URL`).
3. The browser goes to the approval URL (PayPal's `payer-action` link). PayPal sends the buyer back with `?token=<order id>&PayerID=...`; `app/checklist.tsx` posts to the capture route.
4. `capture_order()` captures with `Prefer: return=representation` and returns `{orderId, status, itemIds}`. `status` is the **capture's** status, not the order's: check items off only when it is `COMPLETED`, since an order can complete while its payment is `PENDING` or `DECLINED`.

Safety details:

- Every POST carries a `PayPal-Request-Id`; capture uses the order ID, so a repeated capture returns the first result instead of charging again. That makes the SDK's single retry on `429` safe.
- PayPal errors become `PayPalError(status, issue)`, with PayPal's `debug_id` logged. The route passes `404`/`422` through (problems with the order) and returns `502` for everything else, including network failures and token errors.

### Environment variables

Listed in `.env.example`; copy it to `.env.local`. The backend reads it via `uvicorn --env-file ../.env.local`.

| Variable | Used by |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | `backend/paypal.py` |
| `APP_URL` | `backend/paypal.py` — PayPal's return/cancel URL (default `http://localhost:3000`) |
| `BACKEND_URL` | `next.config.ts` — where `/api/*` goes; must be set at build time |
| `OLLAMA_*`, `SUPABASE_*` | Planned features |

## Responsibilities

| Part | Owns |
|---|---|
| AI | Smart starting lists from one sentence; voice input; reading receipts and matching lines to items; spotting extras; price estimates for the budget |
| PayPal | Checkout for buying from the list (order = proof); Invoicing for settle-up on shared lists; PayPal orders stored beside receipts in each list's money view |
| Code | Split math, budget totals, assignment of unclaimed items |

## Pages

Six pages, described in [SPEC.md](SPEC.md#pages): Progress, Items, Money, Receipts, History, Settle-up.

- **Receipts** links directly with **Items**: each item's proof (receipt scan or PayPal order) is reachable from the item.
- **Money** draws on prices from receipts and PayPal orders, compared against the list budget.
- **Settle-up** turns per-person totals into PayPal invoices and tracks their status.

## Key flows

**Create a list** — the user types or speaks a sentence; the LLM returns a starting list within the stated budget; the user confirms or edits it.

**Check off by receipt** — the user scans a receipt; the LLM reads it and matches lines to list items, checking off several at once with prices attached. Lines that match nothing are flagged as extras.

**Check off by purchase** — the user buys through PayPal Checkout; the PayPal order is stored as the proof, with no scan needed.

**Share** — a list is shared by link; no account is needed to view or check items. People claim the items they will buy.

**Settle up** — code works out who owes whom; PayPal Invoicing sends and tracks the invoices.

## Links

- PayPal developer dashboard: https://developer.paypal.com/dashboard/accounts
- Render workflows: https://render.com/docs/workflows
- Channel3 developers: https://trychannel3.com/developers
