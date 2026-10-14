"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type Item = { id: string; name: string; priceCents: number };
type Capture = { orderId: string; status: string; itemIds: string[] };

const usd = (cents: number) => `$${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

// Test UI for the sample list: pick items, pay with PayPal, come back to see them checked off.
// PayPal returns the buyer here with ?token=<order id>&PayerID=... after approval,
// or with only ?token= after a cancel, so PayerID is what says "capture this".
export function Checklist() {
  const params = useSearchParams();
  const orderId = params.get("token");
  const approved = params.has("PayerID");

  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [capture, setCapture] = useState<Capture | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Item[]>("/api/items").then(setItems, (e) => setStatus(`Could not load the list: ${e.message}`));
  }, []);

  useEffect(() => {
    if (!orderId || !approved) return;
    // Capture is idempotent on the backend, so a repeat (Strict Mode, refresh) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" }).then(
      (result) => {
        setCapture(result);
        setStatus(
          result.status === "COMPLETED"
            ? "Paid. Those items are checked off."
            : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`,
        );
      },
      (e) => setStatus(`Payment could not be confirmed: ${e.message}`),
    );
  }, [orderId, approved]);

  const message = status ?? (orderId ? (approved ? "Confirming your payment…" : "Payment cancelled.") : null);
  // Only a COMPLETED capture checks items off.
  const paid = new Set(capture?.status === "COMPLETED" ? capture.itemIds : []);
  const total = items.filter((item) => selected.has(item.id)).reduce((sum, item) => sum + item.priceCents, 0);

  function toggle(id: string) {
    const next = new Set(selected);
    if (!next.delete(id)) next.add(id);
    setSelected(next);
  }

  async function pay() {
    setBusy(true);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ itemIds: [...selected] }),
      });
      window.location.assign(approveUrl);
    } catch (e) {
      setStatus(`Could not start checkout: ${(e as Error).message}`);
      setBusy(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-6">
      <h1 className="text-3xl font-semibold">Packing list</h1>

      {message && (
        <p role="status" className="rounded-lg bg-zinc-100 p-4 text-lg dark:bg-zinc-900">
          {message}
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.id}>
            <label className="flex min-h-14 cursor-pointer items-center gap-4 rounded-lg border border-zinc-200 px-4 text-xl dark:border-zinc-800">
              <input
                type="checkbox"
                className="size-6"
                checked={paid.has(item.id) || selected.has(item.id)}
                disabled={paid.has(item.id) || busy}
                onChange={() => toggle(item.id)}
              />
              <span className={`flex-1 ${paid.has(item.id) ? "line-through opacity-60" : ""}`}>{item.name}</span>
              <span className="tabular-nums">{paid.has(item.id) ? "Paid" : usd(item.priceCents)}</span>
            </label>
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={pay}
        disabled={selected.size === 0 || busy}
        className="h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40"
      >
        {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
      </button>
    </div>
  );
}
