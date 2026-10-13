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
