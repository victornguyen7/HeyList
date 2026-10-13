# HeyList — Changelog

## 2026-10-13

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
