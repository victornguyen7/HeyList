# HeyList — Architecture

Planned architecture, with what is built so far marked in [Built so far](#built-so-far). See [CHANGELOG.md](CHANGELOG.md).

## Stack

Everything the project uses, as of 2026-10-28. Versions are the pinned ones in `package.json` and `backend/requirements.txt`.

### Frontend (`app/`, `package.json`)

| What | Used for |
|---|---|
| Node.js 24 | Runs Next.js locally and on Render |
| Next.js 16.4.3 (App Router, Turbopack) | The website, mobile-first (native app later). `next.config.ts` proxies `/api/*` to the backend so the browser stays same-origin, and redirects old `/?list=` links |
| React 19.3.0 | UI |
| TypeScript 5 | All frontend code |
| Tailwind CSS 4 (`@tailwindcss/turbopack`) | Styles; the soft glass classes live in `app/ui.tsx` (decision 46) |
| Geist and Geist Mono (`next/font/google`) | Fonts (`app/layout.tsx`) |
| `@supabase/supabase-js` 2.117.3 | Login only: the email magic link and the session token sent to the backend (`app/auth.ts`, decision 52). All list data goes through the backend (decision 56) |
| ESLint 9 (`eslint-config-next`) | `npm run lint` |
| Browser APIs | Web Speech API (`SpeechRecognition`) for voice; camera capture (`<input capture="environment">`) and `<canvas>` to shrink receipt photos; `localStorage` for lists this browser has opened and their saved copies (decision 55) |

### Backend (`backend/`, `backend/requirements.txt`)

| What | Used for |
|---|---|
| Python 3.14.9 | Same version locally and on Render |
| FastAPI 0.143.0 | The API (`backend/main.py`) |
| uvicorn 0.54.0 | Serves it |
| `supabase` 2.32.0 | Database and receipt photo storage, with the secret key (`backend/db.py`); checks login tokens |
| `httpx` 0.28.1 | Channel3 REST calls (`backend/market.py`), and the HTTP/1.1 connection to Supabase (decision 54) |
| `paypal-server-sdk` 2.4.0 | PayPal Orders and refunds (`backend/paypal.py`); APIMatic-generated, pulls in `apimatic-core` (decision 23) |
| `ollama` 0.6.3 | The LLM: starting lists, receipt matching, receipt reading while Textract is unavailable, checking store results (`backend/llm.py`, `backend/receipts.py`) |
| `boto3` 1.43.114 | AWS Textract `AnalyzeExpense` for receipts (`backend/receipts.py`) |
| `unittest` (standard library) | Tests; botocore's `Stubber` and mocks, so no paid calls |

### Services

| Service | Used for | Status |
|---|---|---|
| Supabase | Postgres tables, the private `receipts` bucket (`supabase/schema.sql`), Auth (magic link) | Built. Realtime planned |
| PayPal sandbox | Orders API: create, capture, read, refund. The buyer approves on PayPal's hosted page and is sent back to `APP_URL` (decision 56) | Built. Checkout JS SDK and Invoicing API planned |
| Ollama API (cloud) | One LLM with vision (`OLLAMA_MODEL`, measured on `gemma4:31b`) | Built |
| AWS Textract | Reading receipts, with a confidence per line | Built; the IAM user still lacks permission (issue 15), so Ollama reads receipts for now |
| Channel3 | Real store products and prices (`backend/market.py`), results checked by the LLM (decision 51) | Built |
| Render | Hosting both services from `render.yaml`: `heylist-api` (Python) and `heylist-web` (Node) | Built |
| Anthropic (Claude Haiku) | Not used for now (decision 38); the key stays in `.env.local` for when it comes back | Off |

### Tools

| Tool | Used for |
|---|---|
| APIMatic Context Plugin | PayPal SDK context while building (sponsor tool) |
| Postman | Trying the PayPal and backend APIs by hand (sponsor tool) |
| Figma | The soft glass and Midnight designs (see README links) |
| Git and GitHub | Source control |

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
| `supabase/schema.sql` | Tables and the private `receipts` bucket. Run in the Supabase SQL editor; safe to run again |
| `backend/db.py` | Supabase client (secret key, server only) and the calls the routes use: `select`, `insert`, `update`, `delete`, `upload`/`download` (receipt photos), `user()` (a login token's user). It talks to Supabase over HTTP/1.1, not the client's default HTTP/2: route handlers run on many threads, and one shared HTTP/2 connection failed when several used it at once (issue 43) |
| `backend/paypal.py` | PayPal Server SDK client (sandbox, built on first use). `create_order()`, `capture_order()`, `get_order()` and `refund()` |
| `backend/llm.py` | Ollama client, `chat()` (with an optional JSON schema), `json_reply()`, and `starting_list()`, which asks for a starting list (with an optional `note` per item for conditions and unclear amounts) and checks every field of the reply; and `store_matches()`, which keeps only the store products that are the item itself (decision 51). `examples.json` holds 64 example lists, off by default (`EXAMPLE_COUNT = 0`, decision 48) |
| `backend/eval_starter.py`, `backend/eval/starter_cases.json` | Scores `starting_list()` on 30 labelled cases (recall, quantities, notes, invented items). Paid calls; runs only with `--yes` (decision 43). `--examples` measures it with the 3 closest examples; reports in `backend/eval/` |
| `backend/market.py` | Channel3 over REST (`CHANNEL3_API_KEY`): `search(name)` returns up to 10 products (cheapest in-stock USD offer, store, link, image, category), `get(id)` reads one again so a price never comes from the browser (decision 50) |
| `backend/money.py` | Split math: `assign_unclaimed()` shares out open items, `split()` works out paid (with the purchases it adds up from), share and balance per member, `settle()` the transfers |
| `backend/receipts.py` | `read_receipt()` (AWS Textract `AnalyzeExpense` -> line items in cents with confidence; falls back to `read_with_ollama()`, the Ollama vision model) and `match_lines()` (Ollama, JSON schema -> list item per line) |
| `backend/main.py` | FastAPI app. Lists (`POST /api/lists`, `GET /api/lists?ids=a,b,c` for Home and History in one request, `GET`/`PATCH /api/lists/{id}`; every list comes with its `split`), members (`POST /api/lists/{id}/members`), items (`POST /api/lists/{id}/items`, `PATCH`/`DELETE /api/items/{id}`), store products (`GET /api/items/{id}/products`, `POST /api/items/{id}/product`), checkout (`POST /api/lists/{id}/orders` with `{"itemIds": [...]}`, `POST /api/orders/{order_id}/capture`, `POST /api/orders/{order_id}/refresh` for a pending capture), starting lists (`POST /api/lists/suggest`), splitting (`POST /api/lists/{id}/assign`, `GET /api/lists/{id}/split`), receipts (`POST /api/lists/{id}/receipts` with the photo as the body, `POST /api/receipts/{id}/confirm`, `GET /api/receipts/{id}/image`). Errors are `{"error": CODE}` |
| `app/ui.tsx` | Soft glass building blocks (decision 46): button, card, row and chip classes; `Ring`, `Avatar`, `Check`, `WebNav`, and `Shell` (background glows, web nav, page width) |
| `app/recent.tsx` | `useSeenLists()` (lists this browser opened, loaded in one request; the saved copy shows first), `spent()`, `ListCard` |
| `app/auth.ts`, `app/login/page.tsx` | Optional email login (Supabase Auth magic link, decision 52): `useSession()`, `accountName()`, the login page |
| `app/store-search.tsx` | "Find in stores" on Items: up to 5 checked products, choose one to make its price the item's price |
| `public/ui/` | Figma assets: logo dot, sparkle, mic, check, arrow, background glows |
| `app/page.tsx` | Home: the starter, "Your lists", and on the web "Spent this month" |
| `app/lists/[id]/list-context.tsx` | Loads a list once for all its pages, showing the saved copy first; title, tabs, join by name; captures a PayPal order on return (`/lists/<id>?token=`) |
| `app/lists/[id]/page.tsx` | Progress: progress bar, quantities, who buys each item, share out the rest, pay with PayPal, mark finished |
| `app/lists/[id]/items/page.tsx` | Items: status, price, who bought it, proof (PayPal order or a link to the receipt) |
| `app/lists/[id]/money/page.tsx` | Money: spent vs budget, still to buy, extras, per person |
| `app/lists/[id]/receipts/page.tsx` | Receipts: scan, plus every confirmed receipt (photo and lines) and PayPal order |
| `app/lists/[id]/settle/page.tsx` | Settle up: who pays whom, invoice status |
| `app/history/page.tsx` | History: lists this browser has opened, spending by type and month, buy again |
| `app/starter.tsx` | Describe the situation, review the AI's starting list and budget, create it |
| `app/receipt-scan.tsx` | Camera capture, shrink, scan, review and correct matches, confirm |
| `app/split.tsx` | `useSplit()` takes the split sent with the list (`split` on every list response) and fetches `/split` only after a change made on the page; `WhoPaid`, `SettleUp`, `EqualShare` show it |
| `app/api.ts` | Shared types, `api()` fetch helper (sends the login token if any; readable error messages, the code on `error.code`), `seenLists()`, the saved copy of each list (`cachedLists()`/`cacheLists()`, see [Loading](#loading)), `usd()` |
| `next.config.ts` | Rewrites `/api/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`), waiting up to 2 minutes (`proxyTimeout`) for a backend that is waking up; passes the Supabase URL and publishable key to the browser for login |

`photo.py` is an empty placeholder.

### Payment flow

1. The client sends **item IDs only**. The backend reads each item's estimated price and quantity from Supabase, so a buyer cannot change what they pay. Every item must be on the list, unchecked, and priced.
2. `create_order()` sends the order to PayPal with the total (price × quantity) in USD, and the list page (`APP_URL/lists/<id>`) as the return and cancel URL. The order, its item IDs and total are stored in `orders`.
3. The browser goes to the approval URL (PayPal's `payer-action` link). PayPal sends the buyer back with `?token=<order id>&PayerID=...`; `app/lists/[id]/list-context.tsx` posts to the capture route.
4. `capture_order()` captures with `Prefer: return=representation` and returns `{orderId, status}`. `status` is the **capture's** status, not the order's. Only when it is `COMPLETED` does the route mark the order captured and check its items off, with `price_cents` = price × quantity and `order_id` as proof.

Safety details:

- Every POST carries a `PayPal-Request-Id`; capture uses the order ID, so a repeated capture returns the first result instead of charging again. That makes the single retry on `429` (in `_call`, wait capped at 5 seconds) safe.
- PayPal errors become `PayPalError(status, issue)`, with PayPal's `debug_id` logged. The capture route returns `422` for `INSTRUMENT_DECLINED` and `502` for everything else, including network failures and token errors.

### Loading

Pages show something at once and correct it within about half a second:

1. **Saved copy.** Every list this browser loads is saved in `localStorage` (`heylist:lists-cache`, up to 50). Home, History and a list's own pages show that copy first, then replace it with the fresh one. It is a convenience only: it can be missing (first visit, private window, cleared storage) and is never sent anywhere.
2. **One request.** Home and History load every remembered list with `GET /api/lists?ids=`: six Supabase queries, run at the same time, however many lists. A list the backend no longer has is left out; if the request fails, History says so instead of looking empty.
3. **Split with the list.** Every list response carries `split`, so Money and Settle up don't wait for a second request. `/split` is asked for again only after a change made on the page.

### Receipt flow

1. The browser shrinks the photo to 2000 px JPEG and posts it as the request body to `POST /api/lists/{id}/receipts?memberId=`. The backend accepts JPEG or PNG up to 5 MB.
2. `read_receipt()` calls Textract `AnalyzeExpense`. Each line becomes `{text, priceCents, confidence, lowConfidence}` (under 90% is low); lines without a positive price are dropped. If Textract is unavailable (no permission, no keys, outage), `read_with_ollama()` sends the photo to the Ollama model instead; its lines have no confidence (`confidence: null`). An unreadable photo is not retried.
3. `match_lines()` sends the receipt lines and the open items' names (numbered, no IDs or prices) to the Ollama model with a JSON schema. Numbers out of range or malformed matches are discarded.
4. The photo goes to the private `receipts` bucket and the receipt row stores every line with its proposed `itemId`. Nothing is checked off yet.
5. `POST /api/receipts/{id}/confirm` with `{"itemIds": [...]}` (one per line, possibly corrected) checks the items off with the summed line prices and the scanner as buyer, saves unmatched lines as extras, and sets `confirmed_at`, so a receipt can't be applied twice.

Errors: an unreadable photo is `422 UNREADABLE_IMAGE` (retake it); Textract and Ollama both being unavailable, or Ollama for matching, including missing keys, is `502` and logged.

### Environment variables

Listed in `.env.example`; copy it to `.env.local`. The backend reads it via `uvicorn --env-file ../.env.local`.

| Variable | Used by |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | `backend/paypal.py` |
| `APP_URL` | `backend/main.py` — PayPal's return/cancel URL (default `http://localhost:3000`) |
| `BACKEND_URL` | `next.config.ts` — where `/api/*` goes; must be set at build time |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | `backend/db.py`. `SUPABASE_URL` is also passed to the browser for login |
| `OLLAMA_API_KEY`, `OLLAMA_MODEL` | `backend/llm.py`: starting lists, receipt matching, and receipt reading when Textract is unavailable (the model needs vision) |
| `CHANNEL3_API_KEY` | `backend/market.py`: "Find in stores" product search and the server-side price check when a product is chosen |
| `ANTHROPIC_API_KEY` | Not used for now (decision 38) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | `backend/receipts.py`: Textract (region defaults to `us-east-1`) |
| `SUPABASE_PUBLISHABLE_KEY` | `app/auth.ts` (via `next.config.ts`): login in the browser; read at build time |
| `SUPABASE_JWKS_URL` | Not used |

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
