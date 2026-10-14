# HeyList — Changelog

## 2026-10-14

- Added the FastAPI backend in `backend/`, with pinned dependencies in `backend/requirements.txt`.
- Added a hard-coded sample list (`backend/sample_list.py`) with server-side prices in cents, for testing before LLM or user-added items exist.
- Added PayPal sandbox orders (`backend/paypal.py`) on the Python PayPal Server SDK: create an order from item IDs, capture it, and report the capture's own status and the items bought (item IDs travel as SKUs).
- Added `POST /api/orders/{order_id}/capture` (`backend/main.py`) and a return page component (`app/paypal-return.tsx`) that captures after PayPal approval.
- Next.js now proxies `/api/*` to the backend (`BACKEND_URL`, default `http://127.0.0.1:8000`).
- Added `.env.example` (committed) listing every environment variable; `.env.local` stays ignored.
- `.gitignore` now ignores `__pycache__/`; previously committed cache files were removed from git.
- Added `GET /api/items` and `POST /api/orders`, and replaced the template home page with a checklist test UI (`app/checklist.tsx`): pick items, pay with PayPal, see them checked off on return. Page title is now HeyList.
- Backend unit tests: `python -m unittest` from `backend/` (15 tests).

## 2026-10-12

- Initial commit from Create Next App (Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5).
- Added project docs: spec, architecture, decisions, roadmap, changelog, issues.
- Replaced the template README with the project README.
