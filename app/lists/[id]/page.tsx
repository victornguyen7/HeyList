"use client";

import { useState } from "react";
import { api, proofLabel, usd, type Item, type List } from "../../api";
import { button, outline, useList } from "./list-context";

// Progress: the checklist itself. Tick open items to pay for them with PayPal; claim who buys what.
export default function ProgressPage() {
  const { list, setList, me, memberName, setStatus } = useList();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const { items, members } = list;

  async function patchItem(item: Item, change: object) {
    try {
      const saved = await api<Item>(`/api/items/${item.id}`, { method: "PATCH", body: JSON.stringify(change) });
      setList((current) => ({ ...current, items: current.items.map((i) => (i.id === saved.id ? saved : i)) }));
    } catch (err) {
      setStatus(`Could not save that change: ${(err as Error).message}`);
    }
  }

  async function assign() {
    try {
      setList(await api<List>(`/api/lists/${list.id}/assign`, { method: "POST" }));
    } catch (err) {
      setStatus((err as Error).message);
    }
  }

  async function finish(finished: boolean) {
    try {
      setList(await api<List>(`/api/lists/${list.id}`, { method: "PATCH", body: JSON.stringify({ finished }) }));
    } catch (err) {
      setStatus((err as Error).message);
    }
  }

  // A pending capture can settle later; PayPal doesn't call back, so the person asks again.
  async function checkAgain(orderId: string) {
    setBusy(true);
    try {
      const { status } = await api<{ status: string }>(`/api/orders/${orderId}/refresh`, { method: "POST" });
      setStatus(status === "COMPLETED" ? "Paid. Those items are checked off." : status === "PENDING" ? "Still pending at PayPal." : "That payment did not go through. The items are open again.");
      setList(await api<List>(`/api/lists/${list.id}`));
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
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
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list.id}/orders`, {
        method: "POST",
        body: JSON.stringify({ itemIds: [...selected], memberId: me }),
      });
      window.location.assign(approveUrl);
    } catch (e) {
      setStatus(`Could not start checkout: ${(e as Error).message}`);
      setBusy(false);
    }
  }

  const done = items.filter((item) => item.checkedAt).length;
  const pending = list.orders.filter((order) => order.status === "PENDING");
  const total = items.filter((item) => selected.has(item.id) && !item.checkedAt).reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <p className="text-lg tabular-nums">
          {done} of {items.length} done
        </p>
        <progress className="h-3 w-full" value={done} max={items.length || 1} aria-label={`${done} of ${items.length} done`} />
      </div>

      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const isDone = Boolean(item.checkedAt);
          const priced = item.estPriceCents !== null;
          const proof = proofLabel(item, list.orders);
          const held = !isDone && proof !== null;
          return (
            <li key={item.id} className="flex flex-col gap-2 rounded-3xl glass px-4 py-3 text-xl">
              <div className="flex min-h-12 items-center gap-4">
                <label className="flex flex-1 cursor-pointer items-center gap-4">
                  <input type="checkbox" className="size-6" checked={isDone || selected.has(item.id)} disabled={isDone || held || !priced || busy} onChange={() => toggle(item.id)} />
                  <span className={isDone ? "line-through opacity-60" : ""}>{item.name}</span>
                </label>
                {!isDone && !held && (
                  <span className="flex items-center gap-2">
                    <button
                      type="button"
                      aria-label={`One fewer ${item.name}`}
                      disabled={busy || item.quantity <= 1}
                      onClick={() => patchItem(item, { quantity: item.quantity - 1 })}
                      className="size-10 rounded-full glass"
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
                      onClick={() => patchItem(item, { quantity: item.quantity + 1 })}
                      className="size-10 rounded-full glass"
                    >
                      +
                    </button>
                  </span>
                )}
                <span className="tabular-nums">{isDone ? usd(item.priceCents ?? 0) : priced ? `~${usd(item.estPriceCents! * item.quantity)}` : "—"}</span>
              </div>
              {!isDone && !held && members.length > 0 && (
                <select
                  aria-label={`Who buys ${item.name}`}
                  className="h-11 rounded-3xl glass px-2 text-lg"
                  value={item.claimedBy ?? ""}
                  onChange={(e) => patchItem(item, { claimedBy: e.target.value || null })}
                >
                  <option value="">Nobody yet</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} buys it
                    </option>
                  ))}
                </select>
              )}
              {proof && (
                <span className={`text-base ${held ? "text-amber-700" : "opacity-70"}`}>
                  {proof}
                  {isDone && memberName(item.boughtBy) && ` · ${memberName(item.boughtBy)}`}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {pending.map((order) => (
        <div key={order.id} className="flex flex-col gap-2 rounded-3xl glass p-4 text-lg">
          <p>
            {memberName(order.memberId) ?? "Someone"}&apos;s payment of {usd(order.totalCents)} is still pending at PayPal. Its items are held until it
            goes through.
          </p>
          <button type="button" onClick={() => checkAgain(order.id)} disabled={busy} className={outline}>
            Check again
          </button>
        </div>
      ))}

      {members.length > 0 && items.some((item) => !item.checkedAt && !item.claimedBy) && (
        <button type="button" onClick={assign} className={outline}>
          Share out the rest evenly
        </button>
      )}

      {/* A payment with no name can't be paid back in the split, so joining comes first (as for receipts). */}
      {!me && total > 0 && <p className="text-lg">Add your name above first, so the payment counts as yours.</p>}
      <button type="button" onClick={pay} disabled={total === 0 || busy || !me} className={button}>
        {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
      </button>

      <button type="button" onClick={() => finish(!list.finishedAt)} className="text-lg underline underline-offset-4">
        {list.finishedAt ? "Reopen this list" : "Mark this list finished"}
      </button>
    </div>
  );
}
