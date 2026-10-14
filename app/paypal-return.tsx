"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type Capture = { orderId: string; status: string; itemIds: string[] };

// PayPal returns the buyer here with ?token=<order id>&PayerID=... after approval,
// or with only ?token= after a cancel, so PayerID is what says "capture this".
export function PayPalReturn() {
  const params = useSearchParams();
  const orderId = params.get("token");
  const approved = params.has("PayerID");
  const [result, setResult] = useState<Capture | { error: string } | null>(null);

  useEffect(() => {
    if (!orderId || !approved) return;
    // Capture is idempotent on the backend, so a repeat (Strict Mode, refresh) returns the same result.
    fetch(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(async (res) => (res.ok ? res.json() : { error: (await res.json().catch(() => null))?.detail ?? res.statusText }))
      .then(setResult, () => setResult({ error: "Could not reach the server" }));
  }, [orderId, approved]);

  if (!orderId) return null;
  if (!approved) return <p role="status">Payment cancelled.</p>;
  if (!result) return <p role="status">Confirming your payment…</p>;
  if ("error" in result) return <p role="alert">Payment could not be confirmed: {result.error}</p>;
  if (result.status !== "COMPLETED") return <p role="status">Payment is {result.status.toLowerCase()}; items stay unchecked for now.</p>;
  return <p role="status">Paid for: {result.itemIds.join(", ")}.</p>;
}
