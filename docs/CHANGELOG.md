# HeyList — Changelog

## 2026-10-13

- Added the backend as a FastAPI (Python) service in `backend/`: PayPal order create and capture (Orders API v2, sandbox) and the sample item list at `GET /api/items`. Next.js proxies `/api/*` to it.
- Removed the TypeScript route handlers and `lib/` that the Python service replaces.

## 2026-10-12

- Initial commit from Create Next App (Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5).
- Added project docs: spec, architecture, decisions, roadmap, changelog, issues.
- Replaced the template README with the project README.
