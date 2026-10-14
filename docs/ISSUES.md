# HeyList — Issues

## Open

| # | Issue | Notes |
|---|---|---|
| 1 | App is still mostly the default `create-next-app` scaffold | `app/page.tsx` keeps the template content (it now also renders the PayPal return message) and `app/layout.tsx` keeps the template title |
| 2 | Frontend has none of the planned stack yet | No Supabase client in `package.json`. The PayPal Checkout JS SDK isn't added either; checkout currently relies on PayPal's hosted page redirecting back to `APP_URL` |
| 3 | The LLM API key was written in plain text in the project notes | Keep it out of the repo: load it from an environment variable, and rotate the key if the notes were shared |
| 6 | No way to buy two of the same item | `total_cents` rejects duplicate IDs. Fine for packing lists; if quantity is added later, the selection becomes `{id: qty}` |
| 7 | Small cleanups in `backend/sample_list.py` | No newline at end of file; `priceCents` is camelCase (fine if it matches the frontend JSON). The test-file name mismatch is fixed (`test_sample_list.py`) |
| 13 | No way to start a checkout from the app | `paypal.create_order()` exists, but there is no create-order route or checkout button, so orders can only be created from Python |

## Closed

| # | Issue | Resolution |
|---|---|---|
| 4 | `backend/__pycache__/` was committed in `4a2b88f` | Untracked in `f1dc1f6`; `.gitignore` now ignores `__pycache__/` |
| 5 | PayPal amounts must be strings, not cents | `_usd()` in `backend/paypal.py` converts cents without floats; currency is USD |
| 8 | Order status is not payment status | `capture_order` returns the capture's own status (`purchase_units[0].payments.captures[0].status`); check items off only when it is `COMPLETED` |
| 9 | Capture doesn't say which items were bought | Item IDs are sent as each PayPal item's `sku`; capture asks for `return=representation` and returns them as `itemIds` |
| 10 | `paypal-server-sdk` was in `requirements.txt` but unused | `backend/paypal.py` now uses the SDK; the unused `httpx` pin was removed |
| 11 | PayPal credentials don't load on their own | The backend is started with `uvicorn --env-file ../.env.local` (see README) |
| 12 | Not every PayPal failure is a `PayPalError` | The capture route maps network failures, timeouts and `AuthValidationException` to `502 PAYPAL_UNREACHABLE` (`backend/main.py`) |
