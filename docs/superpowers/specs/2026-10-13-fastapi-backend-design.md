# FastAPI Backend — Design

Date: 2026-10-13. Status: implemented 2026-10-13.

## Purpose

Move all server-side logic out of Next.js into a Python FastAPI service. Next.js stays as the frontend only.

Today's backend is two route handlers, `lib/paypal.ts`, and `lib/sample-list.ts` with its test: about 190 lines, uncommitted. This change ports them to Python and deletes the TypeScript versions. The backend pieces not built yet (Supabase, the LLM, PayPal Invoicing) will be written in Python when their time comes; none of them is part of this change.

**Done means:** `app/api/` and `lib/` are gone, the Python tests pass, and a sandbox order can be created and captured by calling `/api/orders` on the Next.js origin.

## Approach

A straight port into a flat `backend/` folder in this repo. Three Python files mirror the three TypeScript ones, with `httpx` calling the PayPal REST API the way `fetch` does today. The browser keeps calling same-origin `/api/*`; Next.js rewrites those requests to FastAPI.

Rejected:

- **PayPal's Python server SDK** — a dependency for three REST calls, the same reason the TypeScript SDK was rejected in the [checkout spec](2026-10-12-paypal-checkout-design.md).
- **Layered layout (`routers/`, `services/`, `schemas/`)** — too much structure for three endpoints. Split a file when it gets big.
- **Direct browser-to-FastAPI calls with CORS** — needs CORS middleware and a public API URL in the frontend. The proxy needs neither.

## Files

| File | Job |
|---|---|
| `backend/main.py` | The FastAPI app and its three routes. |
| `backend/paypal.py` | Port of `lib/paypal.ts`: `PayPalError`, cached OAuth token, `create_order(item_ids)`, `capture_order(order_id)`. |
| `backend/sample_list.py` | Port of `lib/sample-list.ts`: `ITEMS` and `total_cents(item_ids)`. |
| `backend/test_sample_list.py` | Port of `lib/sample-list.test.mjs`. |
| `backend/test_paypal.py` | PayPal client tests against a fake PayPal (`httpx.MockTransport`). |
| `backend/test_main.py` | Route tests with the PayPal client mocked. |
| `backend/requirements.txt` | `fastapi`, `uvicorn[standard]`, `httpx`, each pinned to an exact version. |
| `next.config.ts` | Adds the `/api/:path*` rewrite. |
| `.gitignore` | Adds `backend/.venv/` and `__pycache__/`. |
| `.env.example` | Adds a commented `BACKEND_URL` line. |
| `README.md` | How to run the two servers. |

Deleted: `app/api/`, `lib/`, and the `test` script in `package.json`.

## Endpoints

FastAPI serves the routes under `/api`, so the rewrite forwards paths unchanged.

| Route | Success | Errors |
|---|---|---|
| `POST /api/orders` | `{"orderId": "..."}` | `400 INVALID_ITEMS`, `502 PAYPAL_ERROR` |
| `POST /api/orders/{id}/capture` | `{"orderId": "...", "status": "..."}` | `400 INVALID_ORDER_ID`, `422 INSTRUMENT_DECLINED`, `502 PAYPAL_ERROR` |
| `GET /api/items` | `[{"id", "name", "priceCents"}, ...]` | — |

The two `POST` routes behave exactly as they do today. `GET /api/items` is new: the planned checkout page needs item names and prices, and with the list living in Python it fetches them instead of importing them, so prices are defined in one place.

Every error body is `{"error": "<CODE>"}`, as it is now. Two FastAPI defaults would break that contract, so the port avoids both:

- **No Pydantic model on the `POST /api/orders` body.** FastAPI would answer a bad body with `422` and a `detail` array. The route reads the raw JSON instead, and any failure to parse it or to pass `total_cents` returns `400 INVALID_ITEMS`.
- **`JSONResponse` instead of `HTTPException`.** `HTTPException` wraps the body as `{"detail": ...}`.

## Behaviour carried over

| Behaviour | Python form |
|---|---|
| Order ID check `^[A-Z0-9]{1,36}$` before calling PayPal | `re.fullmatch` |
| `totalCents` throws on a non-list, an empty list, duplicates, or an unknown ID | `total_cents` raises `ValueError` with the same messages |
| OAuth token cached in the module and refreshed two minutes early | Same, timed with `time.monotonic()` |
| One retry on `429`, waiting `Retry-After` seconds, capped at 5 | Same, with `asyncio.sleep` |
| `PayPal-Request-Id` on every POST; capture uses the order ID as its key | Same |
| PayPal's `debug_id` logged on every PayPal failure | Same, through `logging` |
| Unexpected (non-PayPal) errors logged, then `502` | Same |
| Amounts as integer cents, formatted to two decimals only when sent to PayPal | Same |

The routes and the PayPal calls are `async`, using one shared `httpx.AsyncClient`.

## Wiring

`next.config.ts` gains:

```ts
async rewrites() {
  return [
    {
      source: "/api/:path*",
      destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
    },
  ];
}
```

`BACKEND_URL` is read when Next.js starts. Locally the default is right and the variable stays unset. The default is `127.0.0.1`, not `localhost`: uvicorn listens on IPv4 only, and `localhost` can resolve to IPv6 and reach a different process on the same port.

## Credentials

Both servers read the same `.env.local` at the repo root, so there is one file to fill in.

| Variable | Read by |
|---|---|
| `PAYPAL_CLIENT_SECRET` | Backend only |
| `PAYPAL_CLIENT_ID` | Backend, for OAuth. Later also the Next.js checkout page, to pass to the PayPal button |
| `BACKEND_URL` | Next.js only |

The backend loads the file through uvicorn's `--env-file` flag, which is why the requirement is `uvicorn[standard]`: that extra includes the env-file loader. If either PayPal variable is missing, the first PayPal call fails and the route returns `502`, as it does today.

## Running it

```sh
# once
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# terminal 1
cd backend && .venv/bin/uvicorn main:app --reload --env-file ../.env.local

# terminal 2
npm run dev
```

## Testing

Run with `cd backend && .venv/bin/python -m unittest`. Standard library `unittest`; no test dependency.

- `test_sample_list.py` — the same cases as the TypeScript test: correct sums, and a `ValueError` for an empty list, an unknown ID, a duplicate, a bare string, and `None`.
- `test_paypal.py` — against a fake PayPal: the order carries the server-side total and the token is reused; a `429` is retried once with the same request ID; a second `429`, a declined instrument, and a non-JSON error body each raise `PayPalError`; missing credentials fail before any request.
- `test_main.py` — with FastAPI's `TestClient` and the PayPal client mocked: `GET /api/items` returns the list; `POST /api/orders` returns `400 INVALID_ITEMS` for an empty list, an unknown ID, and a body that is not JSON; capture returns `400 INVALID_ORDER_ID` for a lowercase ID, none of which reaches PayPal; and each PayPal failure maps to its status and error code.
- A sandbox run through the proxy: with both servers up, `POST http://localhost:3000/api/orders`, approve as a sandbox personal account, capture, and confirm the order is `COMPLETED` with the PayPal MCP `get_order` tool.

## Docs to update

| Doc | Change |
|---|---|
| `docs/ARCHITECTURE.md` | Stack table and diagram: Next.js frontend, FastAPI backend, two Render services |
| `docs/DECISIONS.md` | New decision 20, "Next.js for the frontend, FastAPI (Python) for the backend", superseding 14 |
| `docs/CHANGELOG.md` | Entry for the move |
| `docs/superpowers/specs/2026-10-12-paypal-checkout-design.md` | Files table points at the Python files; the checkout page fetches `/api/items` |
| `docs/superpowers/plans/2026-10-12-paypal-checkout.md` | Remaining frontend tasks updated the same way |

## Out of scope

- **Supabase, the LLM, and Invoicing.** Built in Python when their features are.
- **The checkout page.** Still the job of the checkout plan; this change only moves what already exists.
- **Deploying.** Nothing is deployed yet. When it is, Render runs two web services: the Next.js one with `BACKEND_URL` set, and the FastAPI one rooted at `backend/` and started with `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **Docker, and one command that starts both servers.** Two terminals are enough for now.
