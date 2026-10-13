# HeyList — Issues

Last reviewed 2026-10-13.

## Open

| # | Issue | Notes |
|---|---|---|
| 2 | Most of the planned stack is not installed | PayPal Checkout is in (Orders client on the backend, JS SDK on the page). Supabase holds lists, items, orders and receipts, and the LLM client is in (`backend/llm.py`). Still missing: PayPal Invoicing |
| 3 | The LLM API key was written in plain text in the project notes | It now lives in `.env.local` (gitignored) and is not in the repo or its git history. Rotate the key if the notes were shared |
| 6 | The order endpoints have no authentication or rate limiting | Anyone who can reach the backend can create sandbox orders. On Render, make the FastAPI service private so only Next.js reaches it |
| 7 | The PayPal API base URL is hardcoded to the sandbox | `backend/paypal.py`. Move it to an environment variable before any live use (decision 41) |
| 8 | `.env.example` does not list `OLLAMA_API_KEY` | `.env.local` has it; a fresh checkout would not know it is needed |
| 9 | No merchant story for "buy in the app" | Payments go to HeyList's own sandbox merchant account, but HeyList is not the seller of the items on a list. Fine for the demo; an open product question after it |
| 12 | Nothing is deployed | Render needs two web services, with `BACKEND_URL` set on the Next.js one |
| 13 | Template leftovers remain | The five SVGs in `public/` are not referenced anywhere. `app/globals.css` sets the body font to Arial, which overrides the Geist font that `app/layout.tsx` loads |
| 14 | The old virtual-environment path is still referenced | The environment moved to `../.venv` (decision 47), but `.gitignore` still lists `backend/.venv/`. The dated plans under `superpowers/plans/` also use the old path; they are kept as records |
| 15 | The PayPal button has no automated test | The page was checked by hand only (see closed issue 10). The backend has 17 unit tests; the frontend has none |

## Closed

| # | Issue | Closed | How |
|---|---|---|---|
| 1 | The frontend is still the default `create-next-app` scaffold | 2026-10-13 | The home page redirects to `/checkout` and the title is HeyList. The template SVGs in `public/` are unused and can be deleted |
| 4 | Nothing calls the backend | 2026-10-13 | `/checkout` lists the items and runs the PayPal button against both order endpoints |
| 10 | The buyer approval step has not been run | 2026-10-13 | Run by hand in a browser: a sandbox buyer approved the payment and the items were marked paid |
| 11 | Both design specs still say "Status: awaiting review" | 2026-10-13 | Both are implemented and their status lines now say so |
| 5 | A captured order is not stored | 2026-10-13 | Orders are stored in Supabase when created; a completed capture checks its items off with the order ID as proof, and a paid item cannot be paid for again (decisions 53, 54) |
