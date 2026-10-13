import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";
import CheckoutList, { type Item } from "./checkout-list";

export const metadata: Metadata = { title: "Holiday packing — HeyList" };

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Renders on every request, so it has to sit inside <Suspense> (cacheComponents is on).
async function Checkout() {
  // Without this the build tries to prerender the fetch below and logs its failure.
  await connection();

  let items: Item[];
  try {
    const response = await fetch(`${BACKEND_URL}/api/items`);
    if (!response.ok) throw new Error(`Items request failed: ${response.status}`);
    items = await response.json();
  } catch (error) {
    console.error(error);
    return <p className="text-xl">The list could not be loaded. Please refresh the page.</p>;
  }

  const clientId = process.env.PAYPAL_CLIENT_ID;
  if (!clientId) return <p className="text-xl">PayPal is not configured.</p>;

  return <CheckoutList clientId={clientId} items={items} />;
}

export default function CheckoutPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 p-6">
      <h1 className="text-3xl font-semibold">Holiday packing</h1>
      <Suspense fallback={<p className="text-xl">Loading the list…</p>}>
        <Checkout />
      </Suspense>
    </main>
  );
}
