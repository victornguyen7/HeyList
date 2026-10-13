# HeyList — Decisions

Decisions 1–20 come from the project notes; 21 onward come from the design specs in [superpowers/specs/](superpowers/specs/) and the code. A reason is listed only where the source gives one.

## Product and stack

| # | Decision | Reason |
|---|---|---|
| 1 | Build a website, mobile-first, rather than a native app (native app later) | Works in a phone browser with nothing to install |
| 2 | Keep the app general-purpose; packing before a holiday is only the first use case | It should fit groceries, errands, routines, and any other daily list |
| 3 | Keep the app neutral, for daily use by many groups, not tied to companies | Tested by trying it with three very different users: student, busy parent, older relative |
| 4 | Three ways to work with a list — type, voice, photo | Users pick whichever is easiest at that moment |
| 5 | Voice and photo results are shown to the user to confirm before they apply | — |
| 6 | Sharing is by link, with no account needed to view or check items | Sharing in existing apps usually requires everyone to have an account |
| 7 | Simple interface: large text, few screens, one big talk button, advanced options hidden | Must work for first-time smartphone users |
| 8 | A PayPal order counts as proof of purchase | No receipt scan needed when buying in the app |
| 9 | Settle-up on shared lists uses PayPal invoices | — |
| 10 | Split math, budget totals, and assignment of unclaimed items are done in code, not by AI | — |
| 11 | Use one LLM with vision for both lists and receipts | — |
| 12 | Use the Ollama API for the LLM | — |
| 13 | Use the Web Speech API for voice | — |
| 14 | Use Next.js for the app (narrowed to the frontend by 20) | — |
| 15 | Use Supabase for lists, receipts storage, and realtime | — |
| 16 | Deploy on Render | Hackathon sponsor; $50 credit received |
| 17 | Use the PayPal sandbox: Checkout JS SDK + Orders API, Invoicing API | — |
| 18 | Use sponsor tools APIMatic Context Plugin, Postman, and Render; Channel3 only as a stretch | — |
| 19 | History is the retention hook: buy again from a past list, plus price memory | — |
| 20 | Next.js is the frontend only; all server-side logic runs in a FastAPI (Python) service, which the browser reaches through a Next.js rewrite of `/api/*` | — |

## Backend and payments

| # | Decision | Reason |
|---|---|---|
| 21 | ~~Call the PayPal REST API directly with `httpx`; no PayPal server SDK~~ and no `@paypal/react-paypal-js`. **Reversed by 48** for the server SDK; the frontend half still holds | A dependency is not worth it for three REST calls |
| 22 | The frontend will load the PayPal JS SDK v6 by script tag (not built yet) | No new frontend dependency; the v5 SDK is legacy |
| 23 | The browser sends only item IDs; the server looks up prices and computes the total | The browser never sends an amount, so the total cannot be tampered with |
| 24 | Money is held as integer cents and formatted to two decimals only when sent to PayPal | — |
| 25 | Prices are defined in one place, the backend; the frontend fetches them from `GET /api/items` | The list lives in Python, so the page fetches it instead of importing it |
| 26 | Every error body is `{"error": "<CODE>"}`. So `POST /api/orders` reads its body by hand (no Pydantic model) and routes return `JSONResponse` (no `HTTPException`) | FastAPI's defaults would answer with `422` and a `detail` array, or wrap the body as `{"detail": ...}` |
| 27 | PayPal failures reach the browser as a generic `502 PAYPAL_ERROR`; PayPal's `debug_id` is logged on the server. Only `INSTRUMENT_DECLINED` is passed through, as `422` | — |
| 28 | Every POST to PayPal carries a `PayPal-Request-Id`; capture uses the order ID as its key | A repeated capture returns the first result instead of charging again |
| 29 | A `429` from PayPal is retried once, waiting `Retry-After` seconds capped at 5. A declined payment is never retried automatically | — |
| 30 | Order IDs are checked against `^[A-Z0-9]{1,36}$` before PayPal is called | — |
| 31 | The OAuth token is cached in the backend process and refreshed two minutes early | A token never expires mid-request |
| 32 | The browser reaches the backend through the Next.js `/api/*` rewrite, not by calling FastAPI directly | Direct calls need CORS middleware and a public API URL in the frontend; the proxy needs neither |
| 33 | The rewrite's default target is `127.0.0.1:8000`, not `localhost` | uvicorn listens on IPv4 only, and `localhost` can resolve to IPv6 and reach a different process on the same port |
| 34 | The rewrite proxy timeout is raised from 30s to 100s | The backend can take up to 95s (token, order call, one `429` retry), and a capture cut off at the proxy may still complete |
| 35 | Both servers read one `.env.local` at the repo root; the backend loads it with uvicorn's `--env-file` | One file to fill in |
| 36 | The PayPal client ID will reach the browser as a prop from a server page; no `NEXT_PUBLIC_` variable. The secret is read only in `backend/paypal.py` | — |
| 37 | The backend is a flat `backend/` folder, with no `routers/`, `services/`, or `schemas/` layers | Too much structure for three endpoints; split a file when it gets big |
| 38 | Backend tests use the standard library `unittest`; PayPal is faked with `httpx.MockTransport` | No test dependency |
| 39 | Python dependencies are pinned to exact versions in `backend/requirements.txt` | — |
| 40 | Checkout is built first as a standalone slice on a hardcoded sample list | Lists and Supabase do not exist yet; real lists plug into the same endpoints later |
| 41 | Sandbox only for now: the PayPal API base URL is hardcoded to the sandbox | — |
| 42 | No PayPal webhooks, and no Venmo, Pay Later, or card fields, for now | Webhooks: capture is synchronous and there is no database to reconcile |
| 43 | No Docker and no single command that starts both servers | Two terminals are enough for now |
| 44 | When a capture fails or cannot be confirmed, the page says to check the PayPal account; it never says "you have not been charged" | A capture that fails on the way back may still have completed at PayPal |
| 45 | The checkout page renders at request time (`connection()`), not at build time | The item list and the PayPal client ID come from the running servers, not the build machine |
| 46 | `/` redirects to `/checkout` from `next.config.ts`; there is no home page file | The sample checkout is the only page so far |
| 47 | The Python virtual environment lives at `../.venv`, in the folder above the repo, not in `backend/` | — |
| 48 | Reverses 21: `backend/paypal.py` calls PayPal through the PayPal Server SDK for Python (`paypal-server-sdk` 2.4.0), with the APIMatic Context Plugin skills (`paypal:python-*`) and the installed SDK source as the reference for names, auth, models, and errors. The behaviour of 23, 24, 27–31 is kept: the SDK caches the OAuth token (`o_auth_clock_skew=120` is the two-minute early refresh), `PayPal-Request-Id` goes in as `paypal_request_id`, the one `429` retry stays in our code so the wait is capped at 5s (the SDK's own retries are off), and `ApiException` is mapped to `PayPalError`. The SDK is synchronous, so calls run in a thread. Tests fake PayPal with a `requests` adapter instead of `httpx.MockTransport` (amends 38). The SDK has no Invoicing controller (Orders, Payments, Vault, Transaction Search, Subscriptions only), so invoicing uses `httpx` | The hackathon build uses the sponsor's SDK; typed models and errors replace hand-written JSON |
| 49 | A list's UUID is its share link; there is no separate share token. Anyone holding it can view, check, and claim (decision 6) | One unguessable ID is enough without accounts |
| 50 | People on a list are `members`: a name, plus an email only for settle-up. Joining twice with one name is one member | No accounts (decision 6), but split math and invoices need to know who paid |
| 51 | Routes are plain `def`, not `async def`; a small `json_body` dependency still reads bodies by hand (decision 26) | The PayPal SDK and the Supabase client are both synchronous; FastAPI runs sync routes in a thread pool |
| 52 | All Supabase access goes through four functions in `backend/db.py` (`select`, `insert`, `update`, `delete`); tests swap them for an in-memory fake | The client's chained query builder is awkward to fake |
| 53 | An order row is stored when the PayPal order is created, holding its item IDs. Capture refuses an order ID it has no row for, and a completed capture checks the items off at their estimated price | The capture must know what it paid for, and a refresh must not lose the proof (issue 5) |
| 54 | An item paid by a captured order cannot be unticked, re-priced, deleted, or put in another order | The order is the proof (decision 8) |
| 55 | The browser does not talk to Supabase. Shared lists update by re-fetching through the backend every few seconds, not Supabase Realtime | Realtime in the browser needs `@supabase/supabase-js`, a dependency outside the allowed list |
| 56 | The JSON schema for each LLM answer is written into the prompt as well as passed as `format`, and the JSON object is cut out of the reply in code | The hosted model ignored `format`: it replied in a code fence with its own key names |
| 57 | The LLM only estimates and matches. Code converts its dollar prices to cents, drops malformed entries, and drops items from the end of a starting list until the estimates fit the budget | Budget totals are code, not AI (decision 10) |
| 58 | For receipt matching the model is shown the open items numbered 1..n and answers with a number per line; code maps numbers back to item IDs, uses each item once, and treats every other line as an extra | A model can garble a UUID; a small integer it cannot |
| 59 | A receipt photo is sent as the raw request body with its image `Content-Type`, not as a multipart form | FastAPI needs `python-multipart` for forms, a dependency outside the allowed list |
| 60 | A scan stores the photo and returns a proposal; nothing is checked off until `POST /api/lists/{id}/receipts` confirms it, with whatever prices and matches the user left in | Every LLM result is confirmed first (decision 5) |
