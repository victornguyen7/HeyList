# HeyList — Architecture

What is built. The reasons are in [DECISIONS.md](DECISIONS.md); what is still open is in [ISSUES.md](ISSUES.md).

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js website, mobile-first so it works in phone browsers. Pages only |
| Backend | FastAPI (Python) — all server-side logic. The browser calls same-origin `/api/*`, which Next.js rewrites to it |
| Data | Supabase — Postgres for lists, and a private storage bucket for receipt photos. Only the backend talks to it |
| Payments | PayPal sandbox — Checkout JS SDK v6 in the browser; Orders through the PayPal Server SDK for Python; Invoicing through `httpx` |
| AI | One LLM with vision for lists and receipts, served through the Ollama API |
| Voice | Web Speech API |
| Hosting | Render — two web services, one public (Next.js) and one private (FastAPI); see `render.yaml` |
| Sponsor tools | APIMatic (Context Plugin + PayPal Server SDK), Postman, Render |

Installed: Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5 (`package.json`); FastAPI 0.143.0, uvicorn 0.54.0, httpx 0.28.1, paypal-server-sdk 2.4.0, ollama 0.6.3, supabase 2.32.0 (`backend/requirements.txt`).

## Overview

```
              Phone browser (Next.js, mobile-first)
   type / voice (Web Speech API) / photo        PayPal Checkout JS SDK v6
                      |                                   |
                      v                                   v
              Next.js frontend on Render (pages; proxies /api/*)
                                |
                                v
                  FastAPI backend on Render (private)
          |                     |                        |
          v                     v                        v
   LLM with vision          Supabase                PayPal sandbox
   (Ollama API)             Postgres                Orders (Server SDK)
   starting lists           receipts bucket         Invoicing (httpx)
   item splitting
   receipt reading
```

## Files

| File | What it holds |
|---|---|
| `backend/main.py` | Every route, input checks, and the `{"error": "<CODE>"}` contract |
| `backend/paypal.py` | PayPal: orders through the PayPal Server SDK, invoices through `httpx` |
| `backend/llm.py` | The three LLM calls, and the code that cleans up what the model returns |
| `backend/money.py` | Budget totals, split math, assignment of unclaimed items, history totals. No LLM |
| `backend/db.py` | The Supabase client and the six calls the routes use (`select`, `insert`, `update`, `delete`, `upload`, `download`) |
| `supabase/schema.sql` | Tables `lists`, `members`, `items`, `receipts`, `orders`, `invoices`; bucket `receipts` |
| `app/page.tsx` | Home: start a list from a sentence, confirm the suggestion |
| `app/l/[id]/page.tsx`, `list-view.tsx` | A list: header with spent-versus-budget, share, join, and the page tabs |
| `app/l/[id]/progress.tsx` | Progress page: checklist, voice add, receipt scan and confirm, PayPal button |
| `app/l/[id]/pages.tsx` | Items, Money, Receipts, and Settle up pages |
| `app/history/page.tsx` | History page and "Use this list again" |
| `app/lib.ts`, `app/ui.tsx` | Types, the `api` helper, `localStorage` helpers; shared buttons, `TalkButton`, `DraftEditor` |
| `app/checkout/paypal.d.ts` | Types for the PayPal JS SDK v6 |

## Routes

All in `backend/main.py`. Every error body is `{"error": "<CODE>"}`. Any unplanned failure is `500 SERVER_ERROR`. The [Postman collection](../postman/HeyList.postman_collection.json) has an example of each.

| Route | Does | Errors |
|---|---|---|
| `POST /api/ai/list` | Suggests a starting list from `{"sentence"}`. Saves nothing | `400 INVALID_BODY`, `502 LLM_ERROR` |
| `POST /api/ai/items` | Splits `{"text"}` into items with price estimates. Saves nothing | `400 INVALID_BODY`, `502 LLM_ERROR` |
| `POST /api/lists` | Creates a list with its items | `400 INVALID_BODY` |
| `GET /api/lists/{id}` | The whole list state, including the money summary | `404 LIST_NOT_FOUND` |
| `PATCH /api/lists/{id}` | Changes title, budget, or finished | `400 INVALID_BODY`, `404 LIST_NOT_FOUND` |
| `POST /api/lists/{id}/members` | Joins by name (and saves an email if given) | `400 INVALID_BODY`, `404 LIST_NOT_FOUND` |
| `POST /api/lists/{id}/assign` | Shares out unclaimed items between members | `404 LIST_NOT_FOUND` |
| `POST /api/lists/{id}/reuse` | Copies the list, unchecked, at the prices last paid | `404 LIST_NOT_FOUND` |
| `GET /api/history?ids=a,b` | Spending by type and month for those lists; last price paid per item | — |
| `POST /api/lists/{id}/items` | Adds items | `400 INVALID_BODY`, `404 LIST_NOT_FOUND` |
| `PATCH /api/items/{id}` | Renames, re-prices, claims, checks, or unchecks | `400 INVALID_BODY`, `404 ITEM_NOT_FOUND`, `409 ITEM_PAID` |
| `DELETE /api/items/{id}` | Removes an item | `404 ITEM_NOT_FOUND`, `409 ITEM_PAID` |
| `POST /api/lists/{id}/orders` | Creates a PayPal order for `{"itemIds"}` at the stored prices, and stores it | `400 INVALID_ITEMS`, `404 LIST_NOT_FOUND`, `502 PAYPAL_ERROR` |
| `POST /api/orders/{id}/capture` | Captures; on `COMPLETED` checks the items off with the order as proof | `400 INVALID_ORDER_ID`, `404 ORDER_NOT_FOUND`, `422 INSTRUMENT_DECLINED`, `502 PAYPAL_ERROR` |
| `POST /api/lists/{id}/receipts/scan` | Reads a receipt photo (raw image body); proposes matches and extras | `400 INVALID_IMAGE`, `404 LIST_NOT_FOUND`, `502 LLM_ERROR` |
| `POST /api/lists/{id}/receipts` | Saves a confirmed scan and checks its items off | `400 INVALID_BODY`, `404 LIST_NOT_FOUND` |
| `GET /api/receipts/{id}/image` | The receipt photo | `404 RECEIPT_NOT_FOUND` |
| `POST /api/lists/{id}/invoices` | Sends a PayPal invoice for the debt between `{"from", "to"}` | `400 NOTHING_OWED`, `400 EMAIL_NEEDED`, `404 LIST_NOT_FOUND`, `409 ALREADY_INVOICED`, `502 PAYPAL_ERROR` |
| `POST /api/lists/{id}/invoices/refresh` | Reads open invoices' status from PayPal | `404 LIST_NOT_FOUND`, `502 PAYPAL_ERROR` |

## Environment

Read from `.env.local` locally (see `.env.example`) and from the Render dashboard when deployed.

| Variable | Read by | For |
|---|---|---|
| `PAYPAL_CLIENT_ID` | Backend, and the Next.js server page that passes it to the browser | PayPal sandbox app |
| `PAYPAL_CLIENT_SECRET` | Backend only (`backend/paypal.py`) | PayPal sandbox app |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Backend only (`backend/db.py`) | Database and storage |
| `OLLAMA_API_KEY`, `OLLAMA_MODEL`, `OLLAMA_HOST` (optional) | Backend only (`backend/llm.py`) | The LLM |
| `BACKEND_URL` or `BACKEND_HOSTPORT` (both optional locally) | `next.config.ts` | Where `/api/*` is proxied |

## Responsibilities

| Part | Owns |
|---|---|
| AI | Smart starting lists from one sentence; splitting voice input into items; reading receipts and matching lines to items; spotting extras; price estimates |
| PayPal | Checkout for buying from the list (order = proof); Invoicing for settle-up on shared lists |
| Code | Split math, budget totals, assignment of unclaimed items; turning model output into safe data |

## Key flows

**Create a list** — the browser sends the sentence to `POST /api/ai/list`. The LLM returns a title, type, budget and priced items; code converts dollars to cents and drops items until the estimates fit the budget. The page shows the result to edit, and `POST /api/lists` saves what the user confirms.

**Share** — the list's UUID is the link (`/l/{id}`). A visitor gives a name (`POST .../members`); the browser remembers the member ID. Every open page re-fetches the list every five seconds.

**Check off by purchase** — the user ticks items and taps the PayPal button. The browser sends item IDs to `POST .../orders`; the server looks up the prices, creates the order through the PayPal Server SDK, and stores it with its item IDs. After the buyer approves, `POST /api/orders/{id}/capture` captures it, and a `COMPLETED` result checks the items off with the order ID on each.

**Check off by receipt** — the browser shrinks the photo and sends it to `.../receipts/scan`. The LLM sees the photo and the open items as a numbered list and returns each line with a price and an item number or null. Code maps numbers back to items; lines with no item are extras. The page shows the proposal, and `POST .../receipts` saves what the user confirms.

**Settle up** — `backend/money.py` splits what members paid for list items equally and returns the payments that even it out. `POST .../invoices` takes the two people, recomputes the amount, creates and sends a PayPal invoice to the debtor's email, and stores it. A refresh reads the status; a paid invoice counts as money moved.

**Reuse** — `POST .../reuse` copies a list with nothing checked, each item at the price last paid.

## Links

- PayPal developer dashboard: https://developer.paypal.com/dashboard/accounts
- PayPal Server SDK for Python: https://github.com/paypal/PayPal-Python-Server-SDK
- Render Blueprints: https://render.com/docs/blueprint-spec
