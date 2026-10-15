# HeyList — Changelog

## 2026-10-15

- Added the Supabase schema (`supabase/schema.sql`): lists, members, items, receipts, orders, invoices, and a private `receipts` bucket. Row level security is on with no policies, so only the backend's secret key can read or write.
- Added `backend/db.py`, the backend's Supabase access (`select`, `insert`, `update`, `delete`).
- Rewrote `backend/main.py` around stored lists: create, read and update lists, join as a member, add, edit and delete items, and PayPal checkout for chosen list items (`POST /api/lists/{id}/orders`). Prices come from the database.
- Items have a quantity (1–99); checkout charges estimated price × quantity, and a captured order records the line total as `price_cents`.
- Capture again reports the capture's own status, not the order's, so a pending or declined payment never checks items off.
- The checklist test UI now makes a sample list in Supabase and keeps its ID in the URL (`/?list=`), which is also PayPal's return address.
- Removed `backend/sample_list.py`; tests rewritten for the new routes, with an in-memory fake of `db`.

## 2026-10-14

- Added the FastAPI backend in `backend/`, with pinned dependencies in `backend/requirements.txt`.
- Added a hard-coded sample list (`backend/sample_list.py`) with server-side prices in cents, for testing before LLM or user-added items exist.
- Added PayPal sandbox orders (`backend/paypal.py`) on the Python PayPal Server SDK: create an order from item IDs, capture it, and report the capture's own status and the items bought (item IDs travel as SKUs).
- Added `POST /api/orders/{order_id}/capture` (`backend/main.py`) and a return page component (`app/paypal-return.tsx`) that captures after PayPal approval.
- Next.js now proxies `/api/*` to the backend (`BACKEND_URL`, default `http://127.0.0.1:8000`).
- Added `.env.example` (committed) listing every environment variable; `.env.local` stays ignored.
- `.gitignore` now ignores `__pycache__/`; previously committed cache files were removed from git.
- Added `GET /api/items` and `POST /api/orders`, and replaced the template home page with a checklist test UI (`app/checklist.tsx`): pick items, pay with PayPal, see them checked off on return. Page title is now HeyList.
- Items can be bought in quantity: a selection is `{item ID: quantity}` (1–99), sent to PayPal as each item's `quantity`; the test UI has −/+ buttons.
- Backend unit tests: `python -m unittest` from `backend/` (16 tests).

## 2026-10-12

- Initial commit from Create Next App (Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5).
- Added project docs: spec, architecture, decisions, roadmap, changelog, issues.
- Replaced the template README with the project README.
