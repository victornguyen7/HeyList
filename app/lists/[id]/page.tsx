"use client";

import { useState } from "react";
import { api, usd, type Item, type List } from "../../api";
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
          return (
            <li key={item.id} className="flex flex-col gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-xl dark:border-zinc-800">
              <div className="flex min-h-12 items-center gap-4">
                <label className="flex flex-1 cursor-pointer items-center gap-4">
                  <input type="checkbox" className="size-6" checked={isDone || selected.has(item.id)} disabled={isDone || !priced || busy} onChange={() => toggle(item.id)} />
                  <span className={isDone ? "line-through opacity-60" : ""}>{item.name}</span>
                </label>
                {!isDone && (
                  <span className="flex items-center gap-2">
                    <button
                      type="button"
                      aria-label={`One fewer ${item.name}`}
                      disabled={busy || item.quantity <= 1}
                      onClick={() => patchItem(item, { quantity: item.quantity - 1 })}
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
                      onClick={() => patchItem(item, { quantity: item.quantity + 1 })}
                      className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                    >
                      +
                    </button>
                  </span>
                )}
                <span className="tabular-nums">{isDone ? usd(item.priceCents ?? 0) : priced ? usd(item.estPriceCents! * item.quantity) : "—"}</span>
              </div>
              {!isDone && members.length > 0 && (
                <select
                  aria-label={`Who buys ${item.name}`}
                  className="h-11 rounded-lg border border-zinc-300 px-2 text-lg dark:border-zinc-700 dark:bg-zinc-950"
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
              {isDone && memberName(item.boughtBy) && <span className="text-base opacity-70">Bought by {memberName(item.boughtBy)}</span>}
            </li>
          );
        })}
      </ul>

      {members.length > 0 && items.some((item) => !item.checkedAt && !item.claimedBy) && (
        <button type="button" onClick={assign} className={outline}>
          Share out the rest evenly
        </button>
      )}

      <button type="button" onClick={pay} disabled={total === 0 || busy} className={button}>
        {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
      </button>

      <button type="button" onClick={() => finish(!list.finishedAt)} className="text-lg underline underline-offset-4">
        {list.finishedAt ? "Reopen this list" : "Mark this list finished"}
      </button>
    </div>
  );
}
