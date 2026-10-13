# PayPal Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On `/checkout`, a sandbox buyer ticks items on a hardcoded packing list, pays with PayPal, and sees those items checked off with the PayPal order ID as proof.

**Architecture:** A client component loads the PayPal JS SDK v6 by script tag and renders `<paypal-button>`. It posts only item IDs to two Next.js route handlers; the server looks up prices, creates the order and captures it by calling the Orders API v2 with plain `fetch`. Proof lives in page state.

**Tech Stack:** Next.js 16.4.0 (App Router, `cacheComponents: true`), React 19.3.0, TypeScript 5, Tailwind CSS 4, Node 24 built-in test runner, PayPal JS SDK v6, PayPal Orders API v2 (sandbox).

**Spec:** `docs/superpowers/specs/2026-10-12-paypal-checkout-design.md`

> **Updated 2026-10-13:** Tasks 1 and 2 were completed in TypeScript and then ported to Python by the [FastAPI backend plan](2026-10-13-fastapi-backend.md). Their text below is kept as a record; do not run them. Task 3 is updated for the FastAPI backend and is the only task left.

## Global Constraints

- No new frontend dependencies.
- Sandbox only: API base `https://api-m.sandbox.paypal.com`, SDK script `https://www.sandbox.paypal.com/web-sdk/v6/core`.
- The SDK is initialised with `clientId`, not `clientToken` (PayPal's setup guide reserves client tokens for Fastlane).
- Credentials are `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in `.env.local`. No `NEXT_PUBLIC_` variable. The secret is read only in `backend/paypal.py`.
- The browser never sends an amount. Totals are computed on the server from item IDs.
- Currency is USD. Order intent is `CAPTURE`.
- Every POST to PayPal carries a `PayPal-Request-Id`.
- This Next.js version differs from older ones: dynamic route params are a Promise (`await ctx.params`), typed with the global `RouteContext<'/path'>` helper. Check `node_modules/next/dist/docs/01-app/` before deviating from the code below.
- All commands run from the `heylist/` directory. Work happens on a `paypal-checkout` branch, one commit per task.

## Review Focus

Inputs the spec implies but does not spell out, most likely first. Each is pinned by a check in the task named.

1. The same item ID sent twice — must be rejected, not charged twice (Task 1 unit test).
2. A request body that is not JSON, or has no `itemIds` — must return `400`, not crash with `500` (Task 2 curl check).
3. A capture call with a malformed order ID in the URL — must return `400` and never reach PayPal (Task 2 curl check).
4. A capture call for an order the buyer has not approved — must return `502` with a generic message, and log the `debug_id` (Task 2 curl check).
5. The buyer changes the ticked items while the PayPal window is open — the items marked paid must be the ones in the order, not the current ticks (Task 3, `pending` ref; checked in the sandbox run).

## File Structure

| File | Responsibility |
|---|---|
| `lib/sample-list.ts` | The hardcoded list and `totalCents`. No imports, so Node can run it directly in tests. |
| `lib/sample-list.test.mjs` | Unit test for `totalCents`. |
| `lib/paypal.ts` | Server-only PayPal REST client: token cache, `createOrder`, `captureOrder`, `PayPalError`. |
| `app/api/orders/route.ts` | `POST {itemIds}` → `{orderId}`. |
| `app/api/orders/[id]/capture/route.ts` | `POST` → `{orderId, status}`. |
| `app/checkout/paypal.d.ts` | Types for `window.paypal` and the `<paypal-button>` element. |
| `app/checkout/checkout-list.tsx` | Client component: list, total, button, paid state. |
| `app/checkout/page.tsx` | Server page: reads the client ID, renders the list or "not configured". |
| `.env.example` | Empty key names. |

---

### Task 1: Sample list and total

**Files:**
- Create: `lib/sample-list.ts`
- Test: `lib/sample-list.test.mjs`
- Modify: `package.json` (add `test` script)

**Interfaces:**
- Produces: `type Item = { id: string; name: string; priceCents: number }`, `const ITEMS: Item[]`, `function totalCents(itemIds: unknown): number` (throws `Error` unless `itemIds` is a non-empty array of distinct known IDs).

- [ ] **Step 1: Create the branch**

```bash
git checkout -b paypal-checkout
```

- [ ] **Step 2: Add the test script**

In `package.json`, add to `"scripts"` after `"lint"`:

```json
    "lint": "eslint",
    "test": "node --test \"lib/**/*.test.mjs\""
```

- [ ] **Step 3: Write the failing test**

Create `lib/sample-list.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import { ITEMS, totalCents } from "./sample-list.ts";

test("sums the selected items in cents", () => {
  assert.equal(totalCents(["sunscreen", "adapter"]), 899 + 1499);
  assert.equal(
    totalCents(ITEMS.map((item) => item.id)),
    ITEMS.reduce((sum, item) => sum + item.priceCents, 0),
  );
});

test("rejects selections that must never be charged", () => {
  assert.throws(() => totalCents([]), /at least one/);
  assert.throws(() => totalCents(["sunscreen", "nope"]), /unknown/);
  assert.throws(() => totalCents(["sunscreen", "sunscreen"]), /twice/);
  assert.throws(() => totalCents("sunscreen"), /at least one/);
  assert.throws(() => totalCents(undefined), /at least one/);
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `npm test`
Expected: FAIL with `Cannot find module` for `./sample-list.ts`.

- [ ] **Step 5: Write the implementation**

Create `lib/sample-list.ts`:

```ts
export type Item = { id: string; name: string; priceCents: number };

export const ITEMS: Item[] = [
  { id: "sunscreen", name: "Sunscreen", priceCents: 899 },
  { id: "adapter", name: "Travel adapter", priceCents: 1499 },
  { id: "toothbrush", name: "Toothbrush", priceCents: 349 },
];

export function totalCents(itemIds: unknown): number {
  if (!Array.isArray(itemIds) || itemIds.length === 0) {
    throw new Error("Select at least one item");
  }
  if (new Set(itemIds).size !== itemIds.length) {
    throw new Error("An item was selected twice");
  }
  return itemIds.reduce((sum: number, id) => {
    const item = ITEMS.find((candidate) => candidate.id === id);
    if (!item) throw new Error(`unknown item: ${String(id)}`);
    return sum + item.priceCents;
  }, 0);
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `npm test`
Expected: PASS, 2 tests.

- [ ] **Step 7: Commit**

```bash
git add package.json lib/sample-list.ts lib/sample-list.test.mjs
git commit -m "feat: add sample packing list with server-side total"
```

---

### Task 2: PayPal client and order routes

**Files:**
- Create: `lib/paypal.ts`, `app/api/orders/route.ts`, `app/api/orders/[id]/capture/route.ts`, `.env.example`
- Modify: `.gitignore` (allow `.env.example`)

**Interfaces:**
- Consumes: `ITEMS`, `totalCents(itemIds: unknown): number` from `lib/sample-list.ts`.
- Produces:
  - `class PayPalError extends Error` with `status: number`, `issue: string | undefined`.
  - `createOrder(itemIds: string[]): Promise<string>` — returns the PayPal order ID.
  - `captureOrder(orderId: string): Promise<{ orderId: string; status: string }>`.
  - `POST /api/orders` body `{itemIds: string[]}` → `200 {orderId}` | `400 {error:"INVALID_ITEMS"}` | `502 {error:"PAYPAL_ERROR"}`.
  - `POST /api/orders/{id}/capture` → `200 {orderId, status}` | `400 {error:"INVALID_ORDER_ID"}` | `422 {error:"INSTRUMENT_DECLINED"}` | `502 {error:"PAYPAL_ERROR"}`.

**Prerequisite:** `.env.local` must hold real sandbox credentials before Step 7. Steps 1–6 do not need them.

- [ ] **Step 1: Add the env example and un-ignore it**

Create `.env.example`:

```
# Sandbox app credentials from https://developer.paypal.com/dashboard/applications/sandbox
# Copy this file to .env.local and fill in both values.
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
```

In `.gitignore`, replace:

```
.env*
```

with:

```
.env*
!.env.example
```

Run: `git check-ignore .env.local; git check-ignore .env.example || echo "example is tracked"`
Expected: prints `.env.local`, then `example is tracked`.

- [ ] **Step 2: Write the PayPal client**

Create `lib/paypal.ts`:

```ts
import { randomUUID } from "node:crypto";
import { ITEMS, totalCents } from "./sample-list";

const BASE_URL = "https://api-m.sandbox.paypal.com";

export class PayPalError extends Error {
  status: number;
  issue: string | undefined;

  constructor(status: number, issue: string | undefined) {
    super(`PayPal request failed: ${status} ${issue ?? ""}`);
    this.status = status;
    this.issue = issue;
  }
}

// Logs the debug_id PayPal support asks for, then returns an error the routes can map.
async function toError(response: Response): Promise<PayPalError> {
  const body = await response.json().catch(() => ({}));
  const issue: string | undefined = body.details?.[0]?.issue ?? body.name ?? body.error;
  console.error("PayPal error", {
    status: response.status,
    issue,
    debug_id: body.debug_id ?? response.headers.get("paypal-debug-id"),
  });
  return new PayPalError(response.status, issue);
}

let cachedToken: { value: string; expiresAt: number } | undefined;

async function accessToken(): Promise<string> {
  if (cachedToken && Date.now() < cachedToken.expiresAt) return cachedToken.value;

  const clientId = process.env.PAYPAL_CLIENT_ID;
  const clientSecret = process.env.PAYPAL_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set");
  }

  const response = await fetch(`${BASE_URL}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  if (!response.ok) throw await toError(response);

  const data = await response.json();
  // Refresh two minutes early so a token never expires mid-request.
  cachedToken = {
    value: data.access_token,
    expiresAt: Date.now() + (data.expires_in - 120) * 1000,
  };
  return cachedToken.value;
}

async function post(path: string, requestId: string, body: unknown, retried = false) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${await accessToken()}`,
      "Content-Type": "application/json",
      "PayPal-Request-Id": requestId,
    },
    body: JSON.stringify(body),
  });

  if (response.status === 429 && !retried) {
    const seconds = Math.min(Number(response.headers.get("retry-after")) || 1, 5);
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    return post(path, requestId, body, true);
  }
  if (!response.ok) throw await toError(response);
  return response.json();
}

function usd(cents: number) {
  return { currency_code: "USD", value: (cents / 100).toFixed(2) };
}

export async function createOrder(itemIds: string[]): Promise<string> {
  const total = totalCents(itemIds);
  const items = ITEMS.filter((item) => itemIds.includes(item.id));

  const order = await post("/v2/checkout/orders", randomUUID(), {
    intent: "CAPTURE",
    purchase_units: [
      {
        amount: { ...usd(total), breakdown: { item_total: usd(total) } },
        items: items.map((item) => ({
          name: item.name,
          quantity: "1",
          unit_amount: usd(item.priceCents),
        })),
      },
    ],
  });
  return order.id;
}

export async function captureOrder(orderId: string): Promise<{ orderId: string; status: string }> {
  // The order ID is the idempotency key, so a repeated capture returns the first result.
  const order = await post(
    `/v2/checkout/orders/${encodeURIComponent(orderId)}/capture`,
    orderId,
    {},
  );
  return { orderId: order.id, status: order.status };
}
```

- [ ] **Step 3: Write the create-order route**

Create `app/api/orders/route.ts`:

```ts
import { createOrder, PayPalError } from "@/lib/paypal";
import { totalCents } from "@/lib/sample-list";

export async function POST(request: Request) {
  let itemIds: string[];
  try {
    ({ itemIds } = await request.json());
    totalCents(itemIds);
  } catch {
    return Response.json({ error: "INVALID_ITEMS" }, { status: 400 });
  }

  try {
    return Response.json({ orderId: await createOrder(itemIds) });
  } catch (error) {
    if (!(error instanceof PayPalError)) console.error(error);
    return Response.json({ error: "PAYPAL_ERROR" }, { status: 502 });
  }
}
```

- [ ] **Step 4: Write the capture route**

Create `app/api/orders/[id]/capture/route.ts`:

```ts
import { captureOrder, PayPalError } from "@/lib/paypal";

export async function POST(
  _request: Request,
  ctx: RouteContext<"/api/orders/[id]/capture">,
) {
  const { id } = await ctx.params;
  if (!/^[A-Z0-9]{1,36}$/.test(id)) {
    return Response.json({ error: "INVALID_ORDER_ID" }, { status: 400 });
  }

  try {
    return Response.json(await captureOrder(id));
  } catch (error) {
    if (error instanceof PayPalError && error.issue === "INSTRUMENT_DECLINED") {
      return Response.json({ error: "INSTRUMENT_DECLINED" }, { status: 422 });
    }
    if (!(error instanceof PayPalError)) console.error(error);
    return Response.json({ error: "PAYPAL_ERROR" }, { status: 502 });
  }
}
```

- [ ] **Step 5: Start the dev server**

Run in the background: `npm run dev`
Expected: `Ready` on `http://localhost:3000`. This also generates the `RouteContext` types.

- [ ] **Step 6: Check the rejections that never reach PayPal**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"itemIds":[]}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"itemIds":["sunscreen","sunscreen"]}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d 'not json'
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST "localhost:3000/api/orders/bad%2Fid/capture"
```

Expected: `400` five times.

- [ ] **Step 7: Check a real sandbox order (needs `.env.local`)**

```bash
curl -s -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"itemIds":["sunscreen","adapter"]}'
```

Expected: `{"orderId":"<17 characters>"}`.

Confirm the order with the PayPal MCP tool `get_order` using that ID. Expected: status `CREATED`, amount `23.98` USD, two items.

Then capture it before any buyer has approved:

```bash
curl -s -w "\n%{http_code}\n" -X POST localhost:3000/api/orders/<orderId>/capture
```

Expected: `{"error":"PAYPAL_ERROR"}` and `502`. The dev server log shows `PayPal error` with `issue: 'ORDER_NOT_APPROVED'` and a `debug_id`.

- [ ] **Step 8: Lint and commit**

Run: `npm run lint`
Expected: no errors.

```bash
git add .gitignore .env.example lib/paypal.ts app/api
git commit -m "feat: add PayPal order create and capture routes"
```

---

### Task 3: Checkout page

**Files:**
- Create: `app/checkout/paypal.d.ts`, `app/checkout/checkout-list.tsx`, `app/checkout/page.tsx`
- Modify: `docs/CHANGELOG.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: `GET /api/items` → `[{id, name, priceCents}]`, `POST /api/orders` and `POST /api/orders/{id}/capture`, all served by the FastAPI backend in `backend/main.py`. The browser reaches them at same-origin `/api/*`; the server page reaches the backend directly at `BACKEND_URL` (default `http://127.0.0.1:8000`).
- Produces: the `/checkout` page.

- [ ] **Step 1: Declare the SDK types**

Create `app/checkout/paypal.d.ts`:

```ts
import type { DetailedHTMLProps, HTMLAttributes } from "react";

export interface PayPalSession {
  start(
    options: { presentationMode: "auto" },
    order: Promise<{ orderId: string }>,
  ): Promise<void>;
}

interface PayPalSdk {
  findEligibleMethods(options: {
    currencyCode: string;
  }): Promise<{ isEligible(method: string): boolean }>;
  createPayPalOneTimePaymentSession(callbacks: {
    onApprove(data: { orderId: string }): Promise<void>;
    onCancel(): void;
    onError(error: unknown): void;
  }): PayPalSession;
}

declare global {
  interface Window {
    paypal: {
      createInstance(options: {
        clientId: string;
        components: string[];
        pageType: string;
      }): Promise<PayPalSdk>;
    };
  }
}

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "paypal-button": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        type?: string;
      };
    }
  }
}
```

- [ ] **Step 2: Write the client component**

Create `app/checkout/checkout-list.tsx`:

```tsx
"use client";

import Script from "next/script";
import { useRef, useState } from "react";
export type Item = { id: string; name: string; priceCents: number };
import type { PayPalSession } from "./paypal";

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

async function createOrder(itemIds: string[]): Promise<{ orderId: string }> {
  const response = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ itemIds }),
  });
  if (!response.ok) throw new Error(`Create order failed: ${response.status}`);
  return response.json();
}

export default function CheckoutList({ clientId, items }: { clientId: string; items: Item[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  // Item ID -> the PayPal order that paid for it. The order is the proof.
  const [paid, setPaid] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);
  const session = useRef<PayPalSession | null>(null);
  // The items in the order being paid, so changing ticks mid-payment cannot change what is marked paid.
  const pending = useRef<string[]>([]);

  async function onApprove({ orderId }: { orderId: string }) {
    const response = await fetch(`/api/orders/${orderId}/capture`, { method: "POST" });
    const result = await response.json();
    if (response.ok && result.status === "COMPLETED") {
      const items = pending.current;
      setPaid((current) => ({
        ...current,
        ...Object.fromEntries(items.map((id) => [id, orderId])),
      }));
      setSelected((current) => current.filter((id) => !items.includes(id)));
      setNotice("");
    } else if (result.error === "INSTRUMENT_DECLINED") {
      setNotice("Your payment method was declined. Please try another payment method.");
    } else {
      setNotice("The payment did not go through. You have not been charged.");
    }
  }

  async function initPayPal() {
    try {
      const sdk = await window.paypal.createInstance({
        clientId,
        components: ["paypal-payments"],
        pageType: "checkout",
      });
      const methods = await sdk.findEligibleMethods({ currencyCode: "USD" });
      if (!methods.isEligible("paypal")) {
        setNotice("PayPal is not available here.");
        return;
      }
      session.current = sdk.createPayPalOneTimePaymentSession({
        onApprove,
        onCancel: () => setNotice("Payment cancelled. Nothing was charged."),
        onError: (error) => {
          console.error(error);
          setNotice("The payment did not go through. Please try again.");
        },
      });
      setReady(true);
    } catch (error) {
      console.error(error);
      setNotice("PayPal could not be loaded. Please refresh the page.");
    }
  }

  async function pay() {
    if (!session.current || selected.length === 0) return;
    setNotice("");
    pending.current = selected;
    try {
      // start() must receive the promise itself, not a function, and must run inside the click.
      await session.current.start({ presentationMode: "auto" }, createOrder(selected));
    } catch (error) {
      console.error(error);
      setNotice("The payment did not go through. Please try again.");
    }
  }

  // For display only. The backend computes the amount that is charged.
  const total = items
    .filter((item) => selected.includes(item.id))
    .reduce((sum, item) => sum + item.priceCents, 0);

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((other) => other !== id) : [...current, id],
    );
  }

  return (
    <>
      <Script src="https://www.sandbox.paypal.com/web-sdk/v6/core" onReady={initPayPal} />

      <ul className="flex flex-col gap-3">
        {items.map((item) => {
          const orderId = paid[item.id];
          return (
            <li key={item.id}>
              <label className="flex items-center gap-4 rounded-2xl border border-black/10 p-4 text-xl dark:border-white/15">
                <input
                  type="checkbox"
                  className="size-7"
                  checked={Boolean(orderId) || selected.includes(item.id)}
                  disabled={Boolean(orderId)}
                  onChange={() => toggle(item.id)}
                />
                <span className="flex-1">
                  <span className={orderId ? "line-through" : ""}>{item.name}</span>
                  {orderId && (
                    <span className="block text-base text-zinc-600 dark:text-zinc-400">
                      Paid with PayPal · order {orderId}
                    </span>
                  )}
                </span>
                <span>{dollars(item.priceCents)}</span>
              </label>
            </li>
          );
        })}
      </ul>

      <p className="text-xl font-semibold" aria-live="polite">
        {selected.length > 0
          ? `Total: ${dollars(total)}`
          : "Tick the items you want to buy."}
      </p>

      <paypal-button
        type="pay"
        className="paypal-gold w-full"
        hidden={!ready || selected.length === 0}
        onClick={pay}
      />

      {notice && (
        <p role="alert" className="text-lg text-red-700 dark:text-red-400">
          {notice}
        </p>
      )}
    </>
  );
}
```

- [ ] **Step 3: Write the page**

Create `app/checkout/page.tsx`:

```tsx
import type { Metadata } from "next";
import { Suspense } from "react";
import CheckoutList, { type Item } from "./checkout-list";

export const metadata: Metadata = { title: "Holiday packing — HeyList" };

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Fetches on every request, so it has to render inside <Suspense> (cacheComponents is on).
async function Checkout({ clientId }: { clientId: string }) {
  let items: Item[];
  try {
    const response = await fetch(`${BACKEND_URL}/api/items`);
    if (!response.ok) throw new Error(`Items request failed: ${response.status}`);
    items = await response.json();
  } catch (error) {
    console.error(error);
    return <p className="text-xl">The list could not be loaded. Please refresh the page.</p>;
  }
  return <CheckoutList clientId={clientId} items={items} />;
}

export default function CheckoutPage() {
  const clientId = process.env.PAYPAL_CLIENT_ID;

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 p-6">
      <h1 className="text-3xl font-semibold">Holiday packing</h1>
      {clientId ? (
        <Suspense fallback={<p className="text-xl">Loading the list…</p>}>
          <Checkout clientId={clientId} />
        </Suspense>
      ) : (
        <p className="text-xl">PayPal is not configured.</p>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Lint, test and build**

Run: `npm run lint && npm run build && (cd backend && .venv/bin/python -m unittest)`
Expected: lint clean, build succeeds and lists `/checkout` with no `/api` routes, 17 backend tests pass. If the build reports uncached data accessed outside `<Suspense>`, read `node_modules/next/dist/docs/01-app/01-getting-started/08-caching.md` before changing `page.tsx`.

- [ ] **Step 5: Check the page renders**

With both servers running (`cd backend && .venv/bin/uvicorn main:app --reload --env-file ../.env.local`, and `npm run dev`) and `.env.local` filled in:

```bash
curl -s localhost:3000/checkout | grep -o "Holiday packing\|paypal-button\|Travel adapter" | sort -u
```

Expected: all three strings.

- [ ] **Step 6: Sandbox run in a browser**

This step needs a person: the buyer approval cannot be scripted.

1. Open `http://localhost:3000/checkout`.
2. Tick Sunscreen and Travel adapter. Expected: "Total: $23.98" and the PayPal button appears.
3. Tap the button. While the PayPal window is open, tick Toothbrush on the page behind it.
4. Log in as a sandbox **personal** account (from https://developer.paypal.com/dashboard/accounts) and approve.
5. Expected: Sunscreen and Travel adapter are checked, struck through and show "Paid with PayPal · order `<id>`". Toothbrush is still only ticked, not paid.
6. Confirm with the PayPal MCP tool `get_order` on that ID. Expected: status `COMPLETED`, amount `23.98` USD.
7. Tap the button again for Toothbrush and close the PayPal window. Expected: "Payment cancelled. Nothing was charged." and Toothbrush is not marked paid.

- [ ] **Step 7: Update the docs**

In `docs/CHANGELOG.md`, add under `## 2026-10-12`:

```markdown
- Added PayPal Checkout on `/checkout`: a hardcoded sample packing list, server-side order create and capture (Orders API v2, sandbox), and the PayPal order shown as proof on paid items. No persistence yet.
```

In `docs/ROADMAP.md`, replace the Status section body:

```markdown
PayPal Checkout works on a hardcoded sample list at `/checkout`. Lists, Supabase and the other features are not built yet.
```

and under Flow change the checkout line to:

```markdown
- [ ] Check off by PayPal Checkout: the order is the proof (working on a sample list at `/checkout`; needs real lists and persistence)
```

In `docs/ARCHITECTURE.md`, replace the first paragraph with:

```markdown
Planned architecture. Only PayPal Checkout is implemented, on a hardcoded sample list at `/checkout` (see [CHANGELOG.md](CHANGELOG.md)); everything else below is still planned.
```

- [ ] **Step 8: Commit**

```bash
git add app/checkout docs/CHANGELOG.md docs/ROADMAP.md docs/ARCHITECTURE.md
git commit -m "feat: add PayPal checkout page for the sample packing list"
```
