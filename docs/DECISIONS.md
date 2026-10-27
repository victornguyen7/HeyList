# HeyList — Decisions

Decisions recorded in the project notes. A reason is listed only where the notes give one.

| # | Decision | Reason |
|---|---|---|
| 1 | Build a website, mobile-first, rather than a native app (native app later) | Works in a phone browser with nothing to install |
| 2 | Keep the app general-purpose; packing before a holiday is only the first use case | It should fit groceries, errands, routines, and any other daily list |
| 3 | Keep the app neutral, for daily use by many groups, not tied to companies | Tested by trying it with three very different users: student, busy parent, older relative |
| 4 | Three ways to work with a list — type, voice, photo | Users pick whichever is easiest at that moment |
| 5 | Voice and photo results are shown to the user to confirm before they apply | — |
| 6 | Sharing is by link, with no account needed to view or check items | Sharing in existing apps usually requires everyone to have an account |
| 7 | Simple interface: large text, few screens, one big talk button, advanced options hidden | Must work for first-time smartphone users |
| 8 | A PayPal order counts as proof of purchase | No receipt scan needed when buying in the app |
| 9 | Settle-up on shared lists uses PayPal invoices | — |
| 10 | Split math, budget totals, and assignment of unclaimed items are done in code, not by AI | — |
| 11 | Use one LLM with vision for both lists and receipts | — |
| 12 | Use the Ollama API for the LLM | — |
| 13 | Use the Web Speech API for voice | — |
| 14 | Use Next.js for the app | — |
| 15 | Use Supabase for lists, receipts storage, and realtime | — |
| 16 | Deploy on Render | Hackathon sponsor; $50 credit received |
| 17 | Use the PayPal sandbox: Checkout JS SDK + Orders API, Invoicing API | — |
| 18 | Use sponsor tools APIMatic Context Plugin, Postman, and Render; Channel3 only as a stretch | — |
| 19 | History is the retention hook: buy again from a past list, plus price memory | — |
| 20 | Server-side logic lives in a FastAPI (Python) backend; Next.js proxies `/api/*` to it | The browser stays same-origin, so no CORS setup and no backend URL exposed to it |
| 21 | Prices live on the server; the client sends item IDs and quantities only | A buyer must not be able to change what they pay |
| 22 | Money is handled in integer cents, converted to PayPal's string amounts without floats | No rounding errors |
| 23 | Call PayPal through the Python PayPal Server SDK rather than raw REST | It is APIMatic-generated, matching the APIMatic sponsor tool; it also handles OAuth tokens |
| 24 | ~~Send each item's ID as its PayPal `sku`~~ Superseded by 28 | The capture response says which items were bought, with nothing stored on our side |
| 25 | Check items off only when the capture status is `COMPLETED` | An order can complete while its payment is still `PENDING` or `DECLINED` |
| 26 | Use the order ID as the capture's `PayPal-Request-Id` | A repeated capture (retry, refresh) returns the first result instead of charging again |
| 27 | Default `BACKEND_URL` is `http://127.0.0.1:8000`, not `localhost` | uvicorn listens on IPv4, while `localhost` can resolve to IPv6 `::1` on macOS |
| 28 | Store each PayPal order (its item IDs and server-computed total) in Supabase when it is created | The capture knows which list items it paid for without trusting PayPal's item fields |
| 29 | Quantity is a column on the list item; checkout charges `est_price_cents` × `quantity` | The quantity is saved with the list, and the browser still sends only item IDs at checkout |
| 30 | Starting lists come from the existing Ollama model; the suggestion is not saved until the person reviews and creates it | Decision 5; the Ollama key and client were already in place |
| 31 | Receipts are read by AWS Textract `AnalyzeExpense`, then matched to items by one text-only Claude Haiku (`claude-haiku-5-5`) call with structured output. Narrows decision 11 for receipts. **Matching part replaced by decision 38** | Textract gives clean line items with a confidence per line; the matching step is cheap text, not vision |
| 32 | A scan only proposes; items are checked off when the person confirms or corrects the matches. Prices come from the stored lines, not the browser | Decision 5 and decision 21 |
| 33 | `est_price_cents` is the price of one unit; the AI is asked for per-unit prices | Checkout already charges price x quantity (decision 29) |
| 34 | The budget check is done in code: the review screen shows how far over budget the suggestion is, and the person unticks items | The AI doesn't reliably keep within the budget (issue 14); decision 10 |
| 35 | Spending on list items is split equally among the list's members; receipt extras are personal and not split; payments are settled with the fewest transfers | Simplest fair default for a shared list; weighted shares can come later |
| 36 | Unclaimed items are shared out greedily, most expensive first, to whoever carries the least estimated cost | Decision 10; good enough at list size |
| 37 | Receipt photos are taken with `<input type="file" capture="environment">` and shrunk to 2000 px JPEG in the browser | Native camera, no library; keeps uploads under the 5 MB backend limit |
| 38 | Receipt matching uses the Ollama model (`OLLAMA_MODEL`) instead of Claude Haiku, and when Textract is unavailable the same model reads the photo itself (it has vision). Replaces the Claude part of decision 31 | The owner chose to keep the Claude API out for now. Textract is still tried first for its confidence scores; a bad photo is not retried with Ollama |
| 39 | When a PayPal payment goes through for an item that something else checked off first (a receipt, a hand tick): whatever was bought beyond the item's quantity is refunded to the PayPal buyer (Payments API refund, idempotent per order and item). A checked-off item has all its units bought, so today that is the order's whole charge for the item, whatever its quantity. A refund that fails is counted toward the buyer in the split (`boughtTwice`) | The owner's rule: extra purchases are refunded to whoever made them. No money drops out of the split, which it did before. Keeping part of a multi-unit purchase needs buying part of a quantity, which isn't built |
| 40 | A `PENDING` capture is stored on the order and holds its items; the person asks PayPal again with a button, which reads the order (`GET /v2/checkout/orders/{id}`) rather than capturing again | Capturing again with the same `PayPal-Request-Id` only replays the first answer. A button needs no public webhook endpoint; webhooks can replace it later |
| 41 | HeyList is presented as one loop (Need → Coordinate → Verify → Settle), not a list of features; the demo follows one shared camping trip from start to finish, while the product stays general-purpose (decision 2) | The AI, the checklist and PayPal make one story only when each step keeps what the one before it established. One focused scenario is easier for judges to follow |
