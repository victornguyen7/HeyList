# PayPal Checkout — Design

Date: 2026-10-12. Status: awaiting review.

## Purpose

Build the "check off by purchase" flow from [SPEC.md](../../SPEC.md): a user buys list items with PayPal, and the captured order is the proof on those items (decision #8).

Lists and Supabase do not exist yet, so this is a standalone slice on a hardcoded sample list. Real lists plug into the same two endpoints later.

**Done means:** on `/checkout`, a sandbox buyer can tick items, pay with PayPal, and see those items checked off with the PayPal order ID shown as proof.

## Approach

PayPal JS SDK v6 loaded by script tag, and plain `fetch` to the Orders API v2 on the server. No new dependencies. Sandbox only.

Rejected: `@paypal/react-paypal-js` + `@paypal/paypal-server-sdk` (two dependencies for three REST calls); the v5 SDK (legacy).

## Files

| File | Job |
|---|---|
| `lib/sample-list.ts` | Hardcoded packing list: three items, each with `id`, `name`, `priceCents`. Exports `totalCents(itemIds)`, which throws on an unknown or empty selection. |
| `lib/paypal.ts` | Server-only. Cached OAuth token (refreshed from `expires_in`), `createOrder(itemIds)`, `captureOrder(orderId)`. |
| `app/api/orders/route.ts` | `POST {itemIds: string[]}` → `{orderId}` |
| `app/api/orders/[id]/capture/route.ts` | `POST` → `{status, orderId}` |
| `app/checkout/page.tsx` | Server component. Reads `PAYPAL_CLIENT_ID` and passes it to the client component as a prop. |
| `app/checkout/checkout-list.tsx` | Client component: the list, the total, the PayPal button, and the paid state. |
| `.env.example` | `PAYPAL_CLIENT_ID=` and `PAYPAL_CLIENT_SECRET=`, empty. |

## Flow

1. The user ticks the items to buy. The page shows the total.
2. The user taps `<paypal-button>`. The browser posts only the item IDs to `/api/orders`.
3. The server looks up prices, computes the total, and creates an order with `intent: CAPTURE` in USD, one line item per list item.
4. The user approves in PayPal (`presentationMode: "auto"`).
5. `onApprove` posts to `/api/orders/{id}/capture`. The server captures.
6. On `COMPLETED`, the page marks those items checked off with "Paid with PayPal · order `<id>`". Paid items can no longer be selected.

The browser never sends an amount, so the total cannot be tampered with.

## Credentials

`PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` live in `.env.local` (gitignored). The secret is only read in `lib/paypal.ts`. The client ID reaches the browser as a prop from the server page; no `NEXT_PUBLIC_` variable.

If either variable is missing, `/checkout` shows a plain "PayPal is not configured" message instead of the button.

## Errors

| Case | Behaviour |
|---|---|
| Empty or unknown item IDs | `400` from `/api/orders`; nothing is sent to PayPal |
| Buyer cancels | Quiet notice; selection unchanged |
| `INSTRUMENT_DECLINED` (422) on capture | "Try another payment method"; no auto-retry |
| `429` from PayPal | One retry, honouring `Retry-After` |
| Any other PayPal failure | `502` to the browser with a generic message; `debug_id` logged on the server |

Every POST to PayPal carries a `PayPal-Request-Id`. Capture uses the order ID as its key, so a repeated capture call is idempotent.

## Testing

- One test for `totalCents`: correct sum, and throws on empty and unknown IDs. Run with Node's built-in test runner.
- A sandbox run: create an order through `/api/orders`, approve as a sandbox personal account, capture, and confirm the order is `COMPLETED` with the PayPal MCP `get_order` tool.

## Out of scope

- **Persistence.** Proof lives in page state and is lost on refresh. Moves to Supabase when lists exist.
- **Webhooks.** Capture is synchronous and there is no database to reconcile.
- **Venmo, Pay Later, card fields.** PayPal button only.
- **Production credentials.** The API base URL is the sandbox one.

## Open product question

Payments go to HeyList's own sandbox merchant account. That works for the demo, but HeyList is not the seller of the items on a list, so "buy in the app" needs a real merchant story before it is a product.
