# HeyList — Issues

## Open

| # | Issue | Notes |
|---|---|---|
| 2 | Frontend has none of the planned stack yet | No Supabase client in `package.json`. The PayPal Checkout JS SDK isn't added either; checkout currently relies on PayPal's hosted page redirecting back to `APP_URL` |
| 3 | The LLM API key was written in plain text in the project notes | Keep it out of the repo: load it from an environment variable, and rotate the key if the notes were shared |
| 14 | The AI doesn't keep starting lists within the budget | Live run: "birthday party for 10 kids, $100" came back at $125. Not trimmed in code (which items to drop is the person's call); the review screen shows the overage instead (decision 34) |
| 15 | Receipt scanning is not tested against real Textract | Textract still returns `AccessDeniedException` (the IAM user has no `textract:AnalyzeExpense` permission; fix in the AWS Console). Scans now fall back to the Ollama vision model (decision 38), which was tested live on 2026-10-15 (see CHANGELOG). Claude is no longer used. Unit tests cover Textract parsing (botocore `Stubber`), the Ollama fallback, Ollama matching (mocked `llm.chat`) and the routes |
| 17 | Receipt discounts and voided lines are dropped | Lines with no price or a negative price are skipped, so an item's price can be above what was charged. Net them against their item once real receipts show the pattern (`ponytail:` note in `backend/receipts.py`) |
| 18 | Split is equal shares only | Everyone on the list pays the same share; no "Ann isn't eating" or weighted shares yet (decision 35) |
| 23 | Lines read by Ollama have no confidence score | Textract gives one per line; a vision model doesn't, so no line is flagged "hard to read". The person still reviews every line before confirming. Seen in the web test: after the browser's JPEG shrink, "20OZ" was read as "200Z" (the match was still right; line text can't be edited in the review) |
| 19 | `starlette.testclient` warns that `httpx` is deprecated in favour of `httpx2` | Test-only warning from the installed FastAPI/Starlette; harmless. Goes away when FastAPI's test client moves to `httpx2` |

## Closed

| # | Issue | Resolution |
|---|---|---|
| 16 | The live database needed the schema run again | Schema run 2026-10-15; a full scan through the running backend saved the receipt, its photo and its lines, and confirming checked the items off |
| 4 | `backend/__pycache__/` was committed in `4a2b88f` | Untracked in `f1dc1f6`; `.gitignore` now ignores `__pycache__/` |
| 5 | PayPal amounts must be strings, not cents | `_usd()` in `backend/paypal.py` converts cents without floats; currency is USD |
| 7 | Small cleanups in `backend/sample_list.py` | File removed: lists and prices now live in Supabase |
| 8 | Order status is not payment status | `capture_order` returns the capture's own status (`purchase_units[0].payments.captures[0].status`); check items off only when it is `COMPLETED` |
| 9 | Capture doesn't say which items were bought | Item IDs are sent as each PayPal item's `sku`; capture asks for `return=representation` and returns them as `itemIds` |
| 10 | `paypal-server-sdk` was in `requirements.txt` but unused | `backend/paypal.py` now uses the SDK; the unused `httpx` pin was removed |
| 11 | PayPal credentials don't load on their own | The backend is started with `uvicorn --env-file ../.env.local` (see README) |
| 12 | Not every PayPal failure is a `PayPalError` | The capture route maps network failures, timeouts and `AuthValidationException` to `502 PAYPAL_UNREACHABLE` (`backend/main.py`) |
| 1 | App was the default `create-next-app` scaffold | The home page is now the checklist test UI (`app/checklist.tsx`) and the title is HeyList |
| 13 | No way to start a checkout from the app | `POST /api/orders` and the Pay button in `app/checklist.tsx` |
| 6 | No way to buy two of the same item | A selection is now `{item ID: quantity}` (1–99 each); `total_cents` multiplies, and PayPal gets each item's quantity |
| 20 | Ollama's cloud model ignored the `format` JSON schema | Found in the first live run: the reply came wrapped in a ```json fence and left out `quantity`. `starting_list()` now takes the JSON object out of the reply, the schema is also written into the prompt, and every field is checked with a safe fallback |
| 21 | AI prices were for the whole quantity but checkout multiplies by quantity | Caught while writing the starter: it would have charged 10 juice boxes x the price of 10. The prompt now asks for the price of one unit (decision 33) |
| 22 | A missing AWS key gave the person `SCANNING_UNAVAILABLE` with nothing in the server log | Found in the live run; scan failures are now logged with their cause |
