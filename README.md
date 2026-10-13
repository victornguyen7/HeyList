# HeyList

**Simple checklists with money built in.**

HeyList is a mobile-first checklist website. You say or type one sentence ("move-in list for 3 roommates, $300 budget") and get a priced starting list. You share it by link, with no accounts. Items are checked off **with proof**: scan a receipt and AI matches its lines to your items, or pay with PayPal and the captured order is the proof. The list always shows what was spent against the budget, works out who owes whom, and settles up with PayPal invoices.

Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/). Everything runs on the **PayPal sandbox**: no real money moves and no payment details are stored.

## Status

Built end to end on the PayPal sandbox, Supabase, and a hosted vision model; not deployed yet. The backend has 62 unit tests, and every call the pages make has been run against the real services. Three things have only been checked at the API level and still need a run by hand in a browser: clicking through the pages (voice included), approving a PayPal payment on a real list, and paying a settle-up invoice. Demo steps 5, 8 and 10 below are those runs. Open items are in [docs/ISSUES.md](docs/ISSUES.md).

## What it does

1. **Start a list from one sentence**, typed or spoken. The AI suggests items with price estimates inside your budget. You edit and confirm before anything is saved.
2. **Share it by link.** Anyone with the link can view, check, and claim items. No account; people just give a name.
3. **Check items off with proof**
   - **Scan a receipt:** the AI reads the photo, matches lines to items ("2% MILK 1GAL" → Milk), attaches the prices, and flags lines that match nothing as extras. You confirm before items are checked off.
   - **Pay with PayPal:** tick items and pay. The captured PayPal order is stored as the proof.
4. **Six pages:** Progress, Items, Money, Receipts, Settle up, History. Spent-versus-budget is in the header of every one.
5. **Settle up:** code splits the spending, and each debt becomes a PayPal invoice whose status is shown.
6. **Reuse:** start a new list from a past one with one tap, at the prices you last paid.

## PayPal: what is used and where

| PayPal product | What HeyList does with it | Where in the code |
|---|---|---|
| **Checkout, JS SDK v6** (script tag, sandbox) | The PayPal button on the Progress page | `app/l/[id]/progress.tsx` (`initPayPal`, `pay`, `onApprove`) |
| **Orders API v2, via the PayPal Server SDK for Python** (`paypal-server-sdk` 2.4.0) | Create and capture orders. The server looks up prices and computes the total; the browser only sends item IDs. A completed capture checks the items off, with the order ID stored as proof | `backend/paypal.py` (`create_order`, `capture_order`); routes `POST /api/lists/{id}/orders` and `POST /api/orders/{id}/capture` in `backend/main.py` |
| **Invoicing API v2** | Settle-up: create, send, and read the status of an invoice for each debt | `backend/paypal.py` (`create_invoice`, `send_invoice`, `get_invoice`); routes `POST /api/lists/{id}/invoices` and `.../invoices/refresh`; UI in `SettlePage` in `app/l/[id]/pages.tsx` |

The PayPal Server SDK does not include Invoicing, so those three calls use `httpx` with a token from the SDK's own auth manager ([decisions 48 and 68](docs/DECISIONS.md)). The API base is fixed to the sandbox in code.

## AI: what is used and where

One vision LLM, called through the **Ollama API** (`ollama` Python client; the model name comes from `OLLAMA_MODEL`). Voice uses the browser's **Web Speech API**.

| AI feature | Where in the code |
|---|---|
| Starting list from one sentence, with price estimates inside the budget | `starting_list` in `backend/llm.py`; `POST /api/ai/list`; home page `app/page.tsx` |
| Voice input split into separate items | `TalkButton` in `app/ui.tsx` (Web Speech API) → `split_items` in `backend/llm.py`; `POST /api/ai/items` |
| Receipt reading, line-to-item matching, and extras detection | `read_receipt` in `backend/llm.py`; `POST /api/lists/{id}/receipts/scan`; confirm screen in `app/l/[id]/progress.tsx` |

Two rules hold everywhere. **Every AI result is shown to the user to confirm before it applies.** And **the AI never does the sums**: split math, budget totals, and assigning unclaimed items are plain code in `backend/money.py`.

## Run it locally

You need Node 20+, Python 3.13, a free [PayPal developer](https://developer.paypal.com/) account, a free [Supabase](https://supabase.com/) project, and an [Ollama](https://ollama.com/) API key.

**1. Install**

```bash
npm install
python3 -m venv ../.venv
../.venv/bin/pip install -r backend/requirements.txt
```

**2. Create the database.** In the Supabase dashboard open **SQL Editor → New query**, paste [`supabase/schema.sql`](supabase/schema.sql), and run it.

**3. Configure.** Copy `.env.example` to `.env.local` and fill it in. Both servers read this one file.

| Variable | Where to get it |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | See [PayPal sandbox setup](#paypal-sandbox-setup) below |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Supabase dashboard → Project Settings → API Keys (the `sb_secret_...` key) |
| `OLLAMA_API_KEY` | [ollama.com/settings/keys](https://ollama.com/settings/keys) |
| `OLLAMA_MODEL` | A model that accepts images, since it reads receipts. Built and tested with `gemma4:31b` |

**4. Start the two servers**, each in its own terminal:

```bash
cd backend && ../../.venv/bin/uvicorn main:app --reload --env-file ../.env.local
```

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Voice needs Chrome, Edge, or Safari.

**Checks:** `cd backend && ../../.venv/bin/python -m unittest` (62 tests; PayPal, Supabase and the LLM are faked), `npm run lint`, `npm run build`.

## PayPal sandbox setup

1. Sign in at [developer.paypal.com/dashboard](https://developer.paypal.com/dashboard/) with any PayPal account. Make sure the **Sandbox** toggle is on.
2. **App credentials:** go to **Apps & Credentials → Create App** (type *Merchant*). Copy the **Client ID** and **Secret** into `.env.local`. Leave **Invoicing** ticked under the app's features.
3. **A sandbox buyer:** go to **Testing Tools → Sandbox Accounts**. PayPal creates a *Personal* account for you (`sb-…@personal.example.com`). Open it (**⋯ → View/Edit account**) to see its **email** and **password**. This fake buyer pays in the demo; it has fake money.

Nothing here touches a live PayPal account.

## Demo script

About five minutes. Use a phone, or a narrow browser window.

1. **Start a list.** On the home page type `move-in list for 3 roommates, $300 budget` and tap **Make my list** (or tap **Talk** and say it). → *The AI proposes a named list of priced items that add up to less than $300.*
2. **Confirm it.** Change a price or remove an item, type your name (`Ana`), and tap **Save list**. → *You land on the list. The header shows "Spent $0.00 of $300.00".*
3. **Share it.** Tap **Share** and copy the link. Open it in a private window. → *The list opens with no login.* Type `Ben`, tap **Join**, open **Items**, and tap **I'll buy this** on an item. → *Within five seconds Ana's window shows "Ben will buy this".*
4. **Add by voice.** As Ana, on **Progress** tap **Talk** and say `also sponges and a shower curtain`. → *The AI shows two separate items with price estimates.* Tap **Add to the list**.
5. **Pay with PayPal.** Tick two items. → *A bar shows the count and total.* Tap the **PayPal** button, log in as your **sandbox personal account**, and approve. → *Both items are crossed out as "Paid with PayPal · Ana", and the header total rises.* Refresh the page. → *They are still paid: the order is stored.*
6. **Scan a receipt.** Tap **Scan a receipt** and pick a photo of any shopping receipt. → *"Is this right?" lists the lines matched to your items with prices, and the rest as "not on the list".* Tap **Confirm**. → *The matched items are checked off as "On a receipt".*
7. **Look at the pages.**
   - **Items:** each item's status, price, who bought it, and its proof (PayPal order ID, or a link to the receipt photo).
   - **Money:** spent versus budget, extras, still-to-buy estimate, and each person's total.
   - **Receipts:** the receipt photo with its items and extras, and the PayPal order with its items.
8. **Settle up.** Open **Settle up**. → *"Ben owes Ana $…", computed by code.* Under **Emails for PayPal invoices**, give Ben your sandbox personal account's email. Tap **Send a PayPal invoice**. → *"Invoice sent, waiting to be paid", with a link.* Open the link, pay as the sandbox buyer, come back and tap **Check if invoices are paid**. → *The debt is replaced by "Ben paid Ana $… · Paid".*
9. **Reuse.** On **Progress** tap **Finish this list**, then open **History**. → *Spending by type and by month, and the list marked Finished.* Tap **Use this list again**. → *A fresh copy opens, nothing checked, each item at the price last paid.*
10. **A failed payment.** Tick an item, tap **PayPal**, and close the popup. → *"The payment was cancelled. You can try again when you are ready."* The button still works.

## Sponsor tools

| Tool | What it was used for |
|---|---|
| **APIMatic** — Context Plugin and the PayPal Server SDK | `backend/paypal.py` is built on the PayPal Server SDK for Python. The Context Plugin's `paypal:python-*` skills were the reference for the client, auth, models, error types and test seams while writing it (decision 48) |
| **Postman** | [`postman/HeyList.postman_collection.json`](postman/HeyList.postman_collection.json) covers all 19 backend routes in demo order, with scripts that carry IDs from one request to the next. Import it and run against `http://127.0.0.1:8000` |
| **Render** | [`render.yaml`](render.yaml) is a Blueprint for the two services: the public Next.js site and the private FastAPI backend. Not deployed yet ([issue 12](docs/ISSUES.md)) |

## How it is built

- **Frontend:** Next.js 16, React 19, Tailwind 4, TypeScript. Pages only; it proxies `/api/*` to the backend.
- **Backend:** FastAPI (Python) in a flat `backend/` folder: `main.py` (routes), `paypal.py`, `llm.py`, `money.py`, `db.py`.
- **Data:** Supabase Postgres and a private storage bucket for receipt photos. Only the backend talks to it.
- **Hosting:** Render, two web services.

## Docs

- [Spec](docs/SPEC.md) — the product
- [Architecture](docs/ARCHITECTURE.md) — the routes, files, and flows
- [Decisions](docs/DECISIONS.md) — why it is built this way
- [Changelog](docs/CHANGELOG.md) — what was built, phase by phase
- [Issues](docs/ISSUES.md) — what is open, honestly
- [Roadmap](docs/ROADMAP.md)
- [Build prompt](docs/BUILD_PROMPT.md) — the prompt this build followed
