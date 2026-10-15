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
  // Item ID -> quantity; an item is selected when it has a quantity.
  const [quantities, setQuantities] = useState<Record<string, number>>({});
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
  const total = items.reduce((sum, item) => sum + item.priceCents * (quantities[item.id] ?? 0), 0);

  // A quantity of 0 removes the item; the backend caps quantities at 99.
  function setQuantity(id: string, quantity: number) {
    const next = { ...quantities };
    if (quantity > 0) next[id] = Math.min(quantity, 99);
    else delete next[id];
    setQuantities(next);
  }

  async function pay() {
    setBusy(true);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: quantities }),
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
        {items.map((item) => {
          const quantity = quantities[item.id] ?? 0;
          const isPaid = paid.has(item.id);
          return (
            <li
              key={item.id}
              className="flex min-h-14 items-center gap-4 rounded-lg border border-zinc-200 px-4 text-xl dark:border-zinc-800"
            >
              <label className="flex flex-1 cursor-pointer items-center gap-4 py-3">
                <input
                  type="checkbox"
                  className="size-6"
                  checked={isPaid || quantity > 0}
                  disabled={isPaid || busy}
                  onChange={() => setQuantity(item.id, quantity > 0 ? 0 : 1)}
                />
                <span className={isPaid ? "line-through opacity-60" : ""}>{item.name}</span>
              </label>
              {quantity > 0 && !isPaid && (
                <span className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label={`One fewer ${item.name}`}
                    disabled={busy}
                    onClick={() => setQuantity(item.id, quantity - 1)}
                    className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                  >
                    −
                  </button>
                  <span aria-live="polite" className="w-6 text-center tabular-nums">
                    {quantity}
                  </span>
                  <button
                    type="button"
                    aria-label={`One more ${item.name}`}
                    disabled={busy || quantity >= 99}
                    onClick={() => setQuantity(item.id, quantity + 1)}
                    className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                  >
                    +
                  </button>
                </span>
              )}
              <span className="tabular-nums">{isPaid ? "Paid" : usd(item.priceCents * Math.max(quantity, 1))}</span>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={pay}
        disabled={total === 0 || busy}
        className="h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40"
      >
        {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
      </button>
    </div>
  );
}
