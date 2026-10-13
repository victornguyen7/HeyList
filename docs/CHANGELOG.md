# HeyList — Changelog

## 2026-10-13

- **Phase 1 — PayPal Server SDK.** `backend/paypal.py` rewritten on `paypal-server-sdk` 2.4.0 (decision 48, reversing 21), built from the APIMatic Context Plugin skills. Same routes, same error contract, same idempotency keys and single capped `429` retry. The 17 tests pass, with `test_paypal.py` now faking PayPal below the SDK through a `requests` adapter. Checked live against the sandbox: an order is created, and capturing it unapproved comes back as `422 ORDER_NOT_APPROVED`.
- Added the Supabase client to the backend: `supabase` 2.32.0 and `backend/db.py`, which builds one client from `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Connection checked by hand against the project. No tables and no route uses it yet.
- Added the backend as a FastAPI (Python) service in `backend/`: PayPal order create and capture (Orders API v2, sandbox) and the sample item list at `GET /api/items`. Next.js proxies `/api/*` to it.
- Removed the TypeScript route handlers and `lib/` that the Python service replaces.
- Raised the Next.js rewrite proxy timeout to 100s so a slow capture is not cut off.
- Added PayPal Checkout on `/checkout`: the sample packing list, a PayPal button (JS SDK v6), and the PayPal order shown as proof on paid items. No persistence yet. `/` redirects there (set in `next.config.ts`; the template home page is deleted), and the page title is now HeyList.
- Checkout run by hand in the sandbox, buyer approval included: working.
- Moved the Python virtual environment from `backend/.venv` to `../.venv`; the README commands follow.
- Docs brought in line with the code: decisions 21–47 recorded, issues list rewritten, README and roadmap status corrected, built routes added to the architecture doc.

## 2026-10-12

- Initial commit from Create Next App (Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5).
- Added project docs: spec, architecture, decisions, roadmap, changelog, issues.
- Replaced the template README with the project README.
