# HeyList — Build prompt

> **Run on 2026-10-13.** This is kept as the record of what was asked. Its "Starting state" no longer describes the repo: all six phases are built (see [CHANGELOG.md](CHANGELOG.md)), decision 48 is recorded, and the sample `/checkout` it mentions has been deleted. What is still open is in [ISSUES.md](ISSUES.md).

The prompt for building HeyList end to end with Claude Code and the APIMatic Context Plugin. Paste the block below into a new session started from the repo root, with the Supabase and Ollama variables already in `.env.local`.

It reverses decision 21 (raw `httpx`, no PayPal SDK) in favour of the PayPal Server SDK for Python. Delete the "One decision changes" section to keep `httpx`.

```
Build HeyList end to end in this repo (/Users/hiennguyen/HeyList/heylist), using the PayPal Server SDK in Python for all PayPal calls. It is my PayPal AI Hackathon entry: a mobile-first checklist website with money built in.

Read first, before any code: README.md, AGENTS.md, every file in docs/ (SPEC, ARCHITECTURE, DECISIONS, ROADMAP, ISSUES), backend/*.py, app/checkout/*. Decisions 1–47 in docs/DECISIONS.md are locked unless listed below. AGENTS.md says this Next.js version has breaking changes: read the relevant guide in node_modules/next/dist/docs/ before writing frontend code.

## Hackathon requirements (every one MUST hold at the end)
1. PayPal integration is central, on the free sandbox only. HeyList meets this with Checkout (JS SDK v6 + Orders via the PayPal Server SDK), where the captured order is the proof an item was bought, and Invoicing for settle-up. Money must be visible in the main flow, not on a side page.
2. AI is meaningfully part of the experience: starting lists from one sentence, voice input split into items, receipt reading with line-to-item matching, extras detection, and price estimates.
3. A working prototype: every flow in "Target state" runs end to end against the PayPal sandbox, with no mocked screens and no hardcoded results in the demo path.
4. Documented well enough for judges to evaluate without asking me anything: the README MUST state what it does, which PayPal products and which AI it uses and where in the code, how to run it locally, how to get sandbox credentials and a sandbox buyer account, and a step-by-step demo script.
5. Meaningful progress during the hackathon: keep docs/CHANGELOG.md current, one dated entry per phase, so the progress is provable from the repo.
6. Sponsor tools are optional. Use APIMatic (Context Plugin + PayPal Server SDK), Postman, and Render, and name each one in the README with what it was used for. Do NOT add other sponsor tools.
7. I check the Official Rules myself. Do NOT add anything that takes real money, uses a live PayPal account, or stores real payment details.

## Starting state
PayPal Checkout works on a hardcoded sample list at /checkout (sandbox, nothing stored). FastAPI backend in backend/ with three routes and 17 unittest tests; Next.js proxies /api/* to it. No lists, no database, no AI, no invoicing, not deployed.

## Locked stack (do not substitute)
- Frontend: Next.js 16 + React 19 + Tailwind 4 + TypeScript, frontend only, mobile-first
- Backend: FastAPI on Python 3.13, flat backend/ folder, all server logic here
- Data: Supabase (lists, items, receipts storage, realtime)
- Payments: PayPal sandbox only. JS SDK v6 by script tag in the browser; PayPal Server SDK (Python) on the server
- AI: one vision LLM through the Ollama API (OLLAMA_API_KEY, model name from OLLAMA_MODEL); Web Speech API for voice
- Hosting: Render, two web services (Next.js public, FastAPI private)

## One decision changes
Decision 21 (raw httpx, no PayPal SDK) is reversed: rewrite backend/paypal.py on the PayPal Server SDK for Python, using the APIMatic Context Plugin skills (paypal:python-*) as the source of truth for SDK names, auth, models, and error types. Do NOT guess SDK method names from memory. Keep the existing behaviour: server-computed totals in integer cents, PayPal-Request-Id idempotency, order ID validation, {"error": "<CODE>"} bodies, generic 502 PAYPAL_ERROR with debug_id logged, INSTRUMENT_DECLINED passed through as 422. If the SDK does not expose Invoicing, keep httpx for invoicing only and say so. Record this as decision 48.

## Target state
A user on a phone can:
1. Create a list by typing or speaking one sentence ("move-in list for 3 roommates, $300 budget"); the LLM returns a starting list with price estimates inside the budget; the user confirms or edits before it is saved.
2. Share it by link. No account needed to view, check, or claim items.
3. Check items off with proof: scan a receipt (LLM matches lines to items, attaches prices, flags unmatched lines as extras, user confirms), or pay with PayPal Checkout (the captured order is stored as the proof).
4. See six pages per docs/SPEC.md: Progress, Items, Money, Receipts, History, Settle-up.
5. Settle a shared list: code computes who owes whom; PayPal sandbox invoices are created, sent, and their status shown.
6. Reuse a finished list from History with one tap.
If a payment fails or is cancelled, show a clear message and let them retry; NEVER say "you have not been charged" (decision 44).

## Phases — after each one run tests, output "✅ Phase N: <what works>", add the CHANGELOG entry, and commit
1. PayPal Server SDK swap in backend/paypal.py; existing tests green, adapted to the SDK.
2. Supabase: write the schema to supabase/schema.sql, then STOP for me to run it. After that: list and item CRUD, share links, captured orders persisted (closes issue 5).
3. AI: starting lists, voice input, receipt scan with match and extras.
4. The six pages, replacing the sample /checkout list with real lists.
5. Invoicing settle-up.
6. render.yaml for both services, .env.example listing every variable, a Postman collection in postman/ covering every backend route, README and docs/ updated to meet requirement 4.

## Constraints
- Split math, budget totals, and assignment of unclaimed items are plain code, NEVER the LLM (decision 10).
- The browser NEVER sends an amount; the server looks up prices (decision 23).
- Every LLM result (list, voice items, receipt matches) is shown to the user to confirm before it applies (decision 5).
- Secrets only from environment variables. NEVER print, log, or commit .env.local.
- Large text, few screens, one big talk button. Keep the frontend minimal: no component library, no auth, no dark mode, no animations.
- Backend tests use unittest with faked PayPal, Supabase, and LLM calls. Every new route gets at least one test.
- Allowed new dependencies: paypal-server-sdk, supabase, ollama (pinned to exact versions). Nothing else without asking.
- Only make changes this prompt asks for. No extra abstractions, layers, or features.

## Stop and ask before
Adding any other dependency, deleting any file other than as part of the backend/paypal.py rewrite, changing a locked decision, pointing anything at a live (non-sandbox) PayPal account, or deploying.

## Done when
All six flows in "Target state" work locally against the PayPal sandbox and Supabase; `python -m unittest`, `npm run build`, and `npm run lint` pass; and all seven hackathon requirements hold, each one ticked in a short checklist in your final message with the file or route that satisfies it. Stop there.
```
