# HeyList — Architecture

Planned architecture. Only PayPal Checkout is implemented, on a hardcoded sample list at `/checkout` (see [CHANGELOG.md](CHANGELOG.md)); everything else below is still planned.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js website, mobile-first so it works in phone browsers (native app later) |
| Backend | FastAPI (Python) — all server-side logic. The browser calls same-origin `/api/*`, which Next.js rewrites to it |
| Data | Supabase — lists, receipts storage, realtime |
| Payments | PayPal sandbox — Checkout JS SDK + Orders API, Invoicing API |
| AI | One LLM with vision for lists and receipts, served through the Ollama API |
| Voice | Web Speech API |
| Hosting | Render — two web services, one for Next.js and one for FastAPI |
| Sponsor tools | APIMatic Context Plugin, Postman, Render; Channel3 for the stretch |

Currently installed: Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5 (from `package.json`); FastAPI 0.143.0, uvicorn 0.54.0, httpx 0.28.1 on Python 3.13 (from `backend/requirements.txt`).

## Built so far

Three backend routes, in `backend/main.py`. Every error body is `{"error": "<CODE>"}`.

| Route | Success | Errors |
|---|---|---|
| `GET /api/items` | The hardcoded sample list: `[{"id", "name", "priceCents"}, ...]` | — |
| `POST /api/orders` with `{"itemIds": [...]}` | `{"orderId": "..."}` | `400 INVALID_ITEMS`, `502 PAYPAL_ERROR` |
| `POST /api/orders/{id}/capture` | `{"orderId": "...", "status": "..."}` | `400 INVALID_ORDER_ID`, `422 INSTRUMENT_DECLINED`, `502 PAYPAL_ERROR` |

`backend/paypal.py` is the PayPal client (OAuth token cache, idempotency keys, one `429` retry); `backend/sample_list.py` holds the items and the server-side total. One page uses them, `/checkout` (`app/checkout/`): a server page fetches the items and passes them, with the PayPal client ID, to a client component that holds the ticks, the PayPal button, and the paid state. Nothing is stored; a refresh loses the proof. The reasons behind this design are decisions 21–47 in [DECISIONS.md](DECISIONS.md).

Environment, read from `.env.local`: `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` (backend), `BACKEND_URL` (Next.js, optional locally), `OLLAMA_API_KEY` (not used by any code yet).

## Overview

```
              Phone browser (Next.js, mobile-first)
   type / voice (Web Speech API) / photo        PayPal Checkout JS SDK
                      |                                   |
                      v                                   v
              Next.js frontend on Render (pages; proxies /api/*)
                                |
                                v
                  FastAPI backend on Render (Python)
          |                     |                        |
          v                     v                        v
   LLM with vision          Supabase                PayPal sandbox
   (Ollama API)             lists                   Orders API
   starting lists           receipts storage        Invoicing API
   receipt reading          realtime
   extras, price estimates
```

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
