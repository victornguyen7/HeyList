"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type Item = {
  id: string;
  name: string;
  quantity: number;
  estPriceCents: number | null;
  checkedAt: string | null;
  orderId: string | null;
};
type List = { id: string; title: string; items: Item[] };
type Capture = { orderId: string; status: string };

// Stand-in for an LLM-made list until that exists. Prices are estimates; checkout charges what the server stored.
const SAMPLE = {
  title: "Packing list",
  kind: "trip",
  items: [
    { name: "Sunscreen", estPriceCents: 899 },
    { name: "Travel adapter", estPriceCents: 1499 },
    { name: "Toothbrush", estPriceCents: 349 },
  ],
};

const usd = (cents: number) => `$${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? res.statusText);
  return res.json();
}

// Test UI: make a sample list, pick items, pay with PayPal, come back to see them checked off.
// The list ID lives in the URL (?list=), which is also where PayPal sends the buyer back,
// adding ?token=<order id>&PayerID=... after approval, or only ?token= after a cancel.
export function Checklist() {
  const router = useRouter();
  const params = useSearchParams();
  const listId = params.get("list");
  const orderId = params.get("token");
  const approved = params.has("PayerID");

  const [list, setList] = useState<List | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!listId) return;
    const load = () => api<List>(`/api/lists/${encodeURIComponent(listId)}`).then(setList);
    if (!orderId || !approved) {
      load().catch((e) => setStatus(`Could not load the list: ${e.message}`));
      return;
    }
    // Capture is idempotent on the backend, so a repeat (Strict Mode, refresh) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(
        (result) =>
          setStatus(
            result.status === "COMPLETED"
              ? "Paid. Those items are checked off."
              : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`,
          ),
        (e) => setStatus(`Payment could not be confirmed: ${e.message}`),
      )
      .then(load)
      .catch((e) => setStatus(`Could not load the list: ${e.message}`));
  }, [listId, orderId, approved]);

  async function start() {
    setBusy(true);
    try {
      const created = await api<List>("/api/lists", { method: "POST", body: JSON.stringify(SAMPLE) });
      router.push(`/?list=${created.id}`);
    } catch (e) {
      setStatus(`Could not make the list: ${(e as Error).message}`);
    }
    setBusy(false);
  }

  // The quantity is saved on the item, so the server charges it at checkout.
  async function setQuantity(item: Item, quantity: number) {
    try {
      const saved = await api<Item>(`/api/items/${item.id}`, { method: "PATCH", body: JSON.stringify({ quantity }) });
      setList((current) => current && { ...current, items: current.items.map((i) => (i.id === saved.id ? saved : i)) });
    } catch (e) {
      setStatus(`Could not change the quantity: ${(e as Error).message}`);
    }
  }

  function toggle(id: string) {
    const next = new Set(selected);
    if (!next.delete(id)) next.add(id);
    setSelected(next);
  }

  async function pay() {
    setBusy(true);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list!.id}/orders`, {
        method: "POST",
        body: JSON.stringify({ itemIds: [...selected] }),
      });
      window.location.assign(approveUrl);
    } catch (e) {
      setStatus(`Could not start checkout: ${(e as Error).message}`);
      setBusy(false);
    }
  }

  const message = status ?? (orderId ? (approved ? "Confirming your payment…" : "Payment cancelled.") : null);
  const items = list?.items ?? [];
  const total = items
    .filter((item) => selected.has(item.id) && !item.checkedAt)
    .reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0);

  return (
    <div className="flex w-full flex-col gap-6">
      <h1 className="text-3xl font-semibold">{list?.title ?? "HeyList"}</h1>

      {message && (
        <p role="status" className="rounded-lg bg-zinc-100 p-4 text-lg dark:bg-zinc-900">
          {message}
        </p>
      )}

      {!listId && (
        <button
          type="button"
          onClick={start}
          disabled={busy}
          className="h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40"
        >
          Start a sample packing list
        </button>
      )}

      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const done = Boolean(item.checkedAt);
          const priced = item.estPriceCents !== null;
          return (
            <li
              key={item.id}
              className="flex min-h-14 items-center gap-4 rounded-lg border border-zinc-200 px-4 text-xl dark:border-zinc-800"
            >
              <label className="flex flex-1 cursor-pointer items-center gap-4 py-3">
                <input
                  type="checkbox"
                  className="size-6"
                  checked={done || selected.has(item.id)}
                  disabled={done || !priced || busy}
                  onChange={() => toggle(item.id)}
                />
                <span className={done ? "line-through opacity-60" : ""}>{item.name}</span>
              </label>
              {!done && (
                <span className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label={`One fewer ${item.name}`}
                    disabled={busy || item.quantity <= 1}
                    onClick={() => setQuantity(item, item.quantity - 1)}
                    className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                  >
                    −
                  </button>
                  <span aria-live="polite" className="w-6 text-center tabular-nums">
                    {item.quantity}
                  </span>
                  <button
                    type="button"
                    aria-label={`One more ${item.name}`}
                    disabled={busy || item.quantity >= 99}
                    onClick={() => setQuantity(item, item.quantity + 1)}
                    className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                  >
                    +
                  </button>
                </span>
              )}
              <span className="tabular-nums">
                {item.orderId ? "Paid" : priced ? usd(item.estPriceCents! * item.quantity) : "—"}
              </span>
            </li>
          );
        })}
      </ul>

      {list && (
        <button
          type="button"
          onClick={pay}
          disabled={total === 0 || busy}
          className="h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40"
        >
          {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
        </button>
      )}
    </div>
  );
}
