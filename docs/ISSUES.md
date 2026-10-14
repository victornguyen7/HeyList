# HeyList — Issues

Last reviewed 2026-10-13.

## Open

| # | Issue | Notes |
|---|---|---|
| 3 | The LLM API key was written in plain text in the project notes | It now lives in `.env.local` (gitignored) and is not in the repo or its git history. Rotate the key if the notes were shared |
| 9 | No merchant story for "buy in the app" or for settle-up | Payments and invoices go to HeyList's own sandbox merchant account. HeyList is not the seller of the items, and a settle-up invoice pays HeyList, not the person owed (decision 69). Fine for the demo; an open product question after it |
| 13 | Template leftovers remain | The five SVGs in `public/` are not referenced anywhere. `app/globals.css` sets the body font to Arial, which overrides the Geist font that `app/layout.tsx` loads |
| 14 | The old virtual-environment path is still referenced | The environment moved to `../.venv` (decision 47), but `.gitignore` still lists `backend/.venv/`. The dated plans under `superpowers/plans/` also use the old path; they are kept as records |
| 6 | No route has authentication or rate limiting | Anyone who can reach the backend can create sandbox orders and invoices and call the LLM. `render.yaml` makes the FastAPI service private, but the Next.js proxy still forwards `/api/*` from anyone. A list is protected only by its unguessable ID |
| 7 | The PayPal environment is fixed to the sandbox in code | `Environment.SANDBOX` and `INVOICING_URL` in `backend/paypal.py`, and the JS SDK script URL in `app/l/[id]/progress.tsx`. Deliberate for the hackathon (decision 41); all three must change together before any live use |
| 12 | Nothing is deployed | `render.yaml` describes both services and has not been applied. The private service needs a paid Render plan. Set the six backend secrets and `PAYPAL_CLIENT_ID` in the dashboard |
| 15 | The frontend has no automated test and was not clicked through during the build | The backend has 62 unit tests. Every call the pages make was run through the Next.js proxy against Supabase, the model and the sandbox, and lint and build pass. Still to do by hand in a browser: the pages themselves, voice, and the PayPal approval popup on a real list (the popup was hand-tested on the old sample page, closed issue 10) |
| 16 | Paying a settle-up invoice has not been run | Create, send, duplicate refusal and status refresh were run in the sandbox. Paying one as a sandbox buyer and seeing it turn `PAID` has not |
| 18 | Unused photos stay in the bucket | `POST .../receipts/scan` stores the photo before the user confirms, and unticking an item drops its proof photo's path but not the file. Nothing sweeps the orphans |
| 19 | A sent invoice does not follow later spending | If more is bought after an invoice is sent, the debt shown changes but the invoice keeps its amount; the difference shows as still owed once it is paid |
| 20 | A spec feature is not built | "Photo recognition" of a scene (SPEC, core features). "Photo as proof" for a single item is built: `POST /api/items/{id}/photo`, the camera button on Progress |
| 21 | The local virtual environment is Python 3.14, not 3.13 | The tests pass on it. `render.yaml` pins 3.13.5 |

## Closed

| # | Issue | Closed | How |
|---|---|---|---|
| 1 | The frontend is still the default `create-next-app` scaffold | 2026-10-13 | The home page redirects to `/checkout` and the title is HeyList. The template SVGs in `public/` are unused and can be deleted |
| 4 | Nothing calls the backend | 2026-10-13 | `/checkout` lists the items and runs the PayPal button against both order endpoints |
| 10 | The buyer approval step has not been run | 2026-10-13 | Run by hand in a browser: a sandbox buyer approved the payment and the items were marked paid |
| 11 | Both design specs still say "Status: awaiting review" | 2026-10-13 | Both are implemented and their status lines now say so |
| 5 | A captured order is not stored | 2026-10-13 | Orders are stored in Supabase when created; a completed capture checks its items off with the order ID as proof, and a paid item cannot be paid for again (decisions 53, 54) |
| 2 | Most of the planned stack is not installed | 2026-10-13 | Supabase, the LLM client, PayPal Checkout and Invoicing are all in and used |
| 8 | `.env.example` does not list `OLLAMA_API_KEY` | 2026-10-13 | `.env.example` now lists every variable the code reads |
| 17 | The sample checkout files are dead code | 2026-10-13 | Deleted `app/checkout/page.tsx`, `app/checkout/checkout-list.tsx`, `backend/sample_list.py` and `backend/test_sample_list.py`; moved the SDK types to `app/paypal.d.ts`; removed the `/checkout` redirect. Tests, lint and build pass afterwards (decision 71) |
| 22 | Pylance reported three type errors in `backend/llm.py` | 2026-10-13 | Type-only, no behaviour change. The message dict is annotated `dict[str, Any]` so it can hold `images`; an empty reply defaults to `""` before it is sliced; the receipt line's item number is checked with `type(number) is int` inside the `if`, so the checker sees it is not `None` |
| 23 | Pylance rejected the `()` default for `invoices` in `backend/money.py` | 2026-10-13 | `summary` only loops over it, so the parameter is typed `Sequence[dict]` instead of `list[dict]` |
| 24 | Pylance reported seven type errors in `backend/paypal.py` | 2026-10-13 | Type-only. The PayPal Server SDK has no type hints and its optional arguments default to a sentinel string, so `breakdown=` and `items=` carry `# pyright: ignore[reportArgumentType]`. `_call` returns `Any` and `_token` is typed `Any`, which clears the "attribute of None" errors |
| 25 | Pylance reported three return-type errors in `backend/db.py` | 2026-10-13 | Supabase types a row as any JSON value. A `_rows` helper runs the query and casts the result to `list[dict]`; `select`, `insert` and `update` use it |
| 26 | Pylance reported two type errors in `backend/test_paypal.py` | 2026-10-13 | The fake adapter's `send` accepts `*args` to match `HTTPAdapter.send`; the `sleep` assertion casts the patched function to `mock.Mock` |
