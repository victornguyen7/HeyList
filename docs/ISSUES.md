# HeyList — Issues

## Open

| # | Issue | Notes |
|---|---|---|
| 1 | App is still the default `create-next-app` scaffold | `app/page.tsx` and the page title in `app/layout.tsx` are the template defaults |
| 2 | Frontend has none of the planned stack yet | `backend/requirements.txt` covers PayPal, Supabase, and Ollama, but `package.json` has no Supabase client or PayPal Checkout JS SDK |
| 3 | The LLM API key was written in plain text in the project notes | Keep it out of the repo: load it from an environment variable, and rotate the key if the notes were shared |
| 6 | No way to buy two of the same item | `total_cents` rejects duplicate IDs. Fine for packing lists; if quantity is added later, the selection becomes `{id: qty}` |
| 7 | Small cleanups in `backend/sample_list.py` | No newline at end of file; `priceCents` is camelCase (fine if it matches the frontend JSON). The test-file name mismatch is fixed (`test_sample_list.py`) |
| 8 | Order status is not payment status | PayPal can report the order `COMPLETED` while the capture is `PENDING` or `DECLINED`. Since an order is proof of purchase, `capture_order` should check `purchase_units[0].payments.captures[0].status` and only check items off when it is `COMPLETED` |
| 9 | Capture doesn't say which items were bought | `capture_order` returns only ID and status. Save `order_id → item_ids` at create time (Supabase later, a dict for now), or read the items back from the capture response |
| 10 | `paypal-server-sdk` is in `requirements.txt` but unused | `backend/paypal.py` calls the REST API with `httpx`. Drop the SDK, or switch to it if APIMatic usage matters for sponsor judging |
| 11 | PayPal credentials don't load on their own | `paypal.py` reads `os.environ`, but nothing loads `.env.local` (Next.js reads it, Python doesn't). Export the variables in the shell or load the file when the app starts |
| 12 | Minor gaps in `backend/paypal.py` error handling | A token rejected before expiry raises instead of refreshing (one retry on 401 would cover it); a network timeout raises `httpx.TimeoutException`, not `PayPalError`, so routes must handle both |

## Closed

| # | Issue | Resolution |
|---|---|---|
| 4 | `backend/__pycache__/` was committed in `4a2b88f` | Untracked in `f1dc1f6`; `.gitignore` now ignores `__pycache__/` |
| 5 | PayPal amounts must be strings, not cents | `_usd()` in `backend/paypal.py` converts cents without floats; currency is USD |
