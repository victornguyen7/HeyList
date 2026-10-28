"use client";

import Link from "next/link";
import { useState } from "react";
import { api, proofLabel, refundNote, usd, type Item, type List } from "../../api";
import { ShopAgent } from "../../shop-agent";
import { Check, Ring } from "../../ui";
import { buttonAi, card, outline, row, useList } from "./list-context";

// Progress: the checklist itself. The tick means "done"; paying with PayPal is a separate mode, so a plain
// checklist never shows payment controls unless someone asks to pay.
export default function ProgressPage() {
  const { list, setList, me, memberName, setStatus } = useList();
  const [paying, setPaying] = useState(false);
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

  // Ticking by hand asks what was paid, so the split has a real price; blank means "don't know" and leaves it out.
  async function tick(item: Item) {
    if (item.checkedAt) return patchItem(item, { checked: false });
    const estimate = item.estPriceCents !== null ? (item.estPriceCents * item.quantity) / 100 : "";
    const answer = window.prompt(`What did you pay for ${item.name}? Leave it blank if you don't know.`, String(estimate));
    if (answer === null) return;
    const priceCents = answer.trim() ? Math.round(Number(answer.replace("$", "")) * 100) : null;
    if (priceCents !== null && !(priceCents >= 0)) return setStatus("That price wasn't a number, so nothing was changed.");
    await patchItem(item, { checked: true, memberId: me, priceCents });
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
      const { status, refundedCents } = await api<{ status: string; refundedCents: number }>(`/api/orders/${orderId}/refresh`, { method: "POST" });
      setStatus(status === "COMPLETED" ? `Paid. Those items are checked off.${refundNote(refundedCents)}` : status === "PENDING" ? "Still pending at PayPal." : "That payment did not go through. The items are open again.");
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
      const err = e as Error & { code?: string };
      // The backend saved the store's new price (issue 42): show the new total before they pay again.
      if (err.code === "PRICE_CHANGED") setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
      setStatus(err.code === "PRICE_CHANGED" ? err.message : `Could not start checkout: ${err.message}`);
      setBusy(false);
    }
  }

  const cost = (item: Item) => (item.estPriceCents ?? 0) * item.quantity;
  const held = (item: Item) => !item.checkedAt && proofLabel(item, list.orders) !== null;
  const payable = (item: Item) => !item.checkedAt && !held(item) && item.estPriceCents !== null;
  const open = items.filter((item) => !item.checkedAt);
  const done = items.filter((item) => item.checkedAt);
  const pending = list.orders.filter((order) => order.status === "PENDING");
  const total = items.filter((item) => selected.has(item.id) && payable(item)).reduce((sum, item) => sum + cost(item), 0);
  // "Pay $X" starts with what you said you'd buy already chosen.
  const mine = me ? items.filter((item) => item.claimedBy === me && payable(item)) : [];
  const spent = done.reduce((sum, item) => sum + (item.priceCents ?? 0), 0);

  function startPaying() {
    setSelected(new Set(mine.map((item) => item.id)));
    setPaying(true);
  }

  function itemRow(item: Item) {
    const isDone = Boolean(item.checkedAt);
    const proof = proofLabel(item, list.orders);
    // A PayPal payment or a receipt is evidence; only a tick made by hand can be taken back here.
    const tickable = !held(item) && !item.orderId && !item.receiptId && Boolean(me) && !busy;
    const who = item.claimedBy ? (item.claimedBy === me ? "You claimed" : memberName(item.claimedBy)) : "Nobody yet";
    return (
      <li key={item.id} className={`${row} items-start`}>
        <label className={`mt-0.5 flex shrink-0 ${paying ? (payable(item) ? "cursor-pointer" : "opacity-30") : tickable ? "cursor-pointer" : ""}`}>
          {paying ? (
            <>
              <input type="checkbox" className="peer sr-only" aria-label={`Pay for ${item.name}`} checked={selected.has(item.id)} disabled={!payable(item) || busy} onChange={() => toggle(item.id)} />
              <span className={`size-7 rounded-full border-2 ${selected.has(item.id) ? "border-ai bg-ai" : "border-muted"} peer-focus-visible:outline-2`} />
            </>
          ) : (
            <>
              <input type="checkbox" className="peer sr-only" aria-label={`${item.name} done`} checked={isDone} disabled={!tickable} onChange={() => tick(item)} />
              <span className="flex rounded-full peer-focus-visible:outline-2">
                <Check done={isDone} />
              </span>
            </>
          )}
        </label>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          {isDone || held(item) || paying ? (
            <span className={`text-[17px] font-medium lg:font-semibold ${isDone ? "text-muted line-through" : ""}`}>{item.name}</span>
          ) : (
            // Tap the name to change how many, or who buys it.
            <details className="group">
              <summary className="cursor-pointer list-none text-[17px] font-medium lg:font-semibold">{item.name}</summary>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span className="flex items-center gap-1">
                  <button type="button" aria-label={`One fewer ${item.name}`} disabled={busy || item.quantity <= 1} onClick={() => patchItem(item, { quantity: item.quantity - 1 })} className="size-8 rounded-full bg-surface-2 disabled:opacity-30">
                    −
                  </button>
                  <span aria-live="polite" className="w-6 text-center tabular-nums">
                    {item.quantity}
                  </span>
                  <button type="button" aria-label={`One more ${item.name}`} disabled={busy || item.quantity >= 99} onClick={() => patchItem(item, { quantity: item.quantity + 1 })} className="size-8 rounded-full bg-surface-2 disabled:opacity-30">
                    +
                  </button>
                </span>
                {members.length > 0 && (
                  <select aria-label={`Who buys ${item.name}`} className="h-8 rounded-full bg-surface-2 px-2" value={item.claimedBy ?? ""} onChange={(e) => patchItem(item, { claimedBy: e.target.value || null })}>
                    <option value="">Nobody yet</option>
                    {members.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} buys it
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </details>
          )}
          <span className={`text-[13px] ${held(item) ? "text-money" : "text-muted"}`}>
            {isDone ? `${proof}${memberName(item.boughtBy) ? ` · ${memberName(item.boughtBy)}` : ""}` : (proof ?? `${who} · ×${item.quantity}`)}
          </span>
          {item.note && !isDone && <span className="text-[13px] text-money">{item.note}</span>}
        </div>
        <span className={`mt-0.5 shrink-0 text-base font-medium tabular-nums lg:font-semibold ${isDone ? "text-list" : ""}`}>
          {isDone ? (item.priceCents !== null ? usd(item.priceCents) : "—") : item.estPriceCents !== null ? `~${usd(cost(item))}` : "—"}
        </span>
      </li>
    );
  }

  const stat = (value: string, label: string, color: string) => (
    <div className={`${card} flex flex-1 flex-col gap-0.5 p-3.5 font-medium`}>
      <span className={`text-2xl tracking-[-0.015em] tabular-nums ${color}`}>{value}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  );

  return (
    <div className="flex flex-col gap-3.5 lg:flex-row-reverse lg:items-start lg:gap-10">
      <aside className="flex flex-col gap-3.5 lg:w-[400px] lg:shrink-0 lg:gap-5">
        <div className="flex flex-col items-center gap-5 pt-1.5 lg:glass lg:rounded-3xl lg:p-6">
          <div className="relative size-44">
            <Ring done={done.length} total={items.length} size={176} />
            <span className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="flex items-baseline gap-0.5">
                <span className="text-[49px] font-light tracking-[-0.03em] tabular-nums">{done.length}</span>
                <span className="text-[21px] font-medium text-muted tabular-nums">/{items.length}</span>
              </span>
              <span className="text-[13px] font-medium text-list">done</span>
            </span>
          </div>
          <div className="flex w-full gap-3">
            {stat(usd(spent), "spent so far", "text-money")}
            {stat(String(open.length), "still to get", "text-list")}
            {stat(String(list.receipts.filter((r) => r.confirmedAt).length), "receipts", "text-ai")}
          </div>
        </div>

        {pending.map((order) => (
          <div key={order.id} className={`${card} flex flex-col gap-3 text-base`}>
            <p>
              {memberName(order.memberId) ?? "Someone"}&apos;s payment of {usd(order.totalCents)} is still pending at PayPal. Its items are held until it goes through.
            </p>
            <button type="button" onClick={() => checkAgain(order.id)} disabled={busy} className={outline}>
              Check again
            </button>
          </div>
        ))}

        {paying ? (
          <div className="flex flex-col gap-2.5">
            <p className="text-base text-muted">Choose what you&apos;re paying for.</p>
            <button type="button" onClick={pay} disabled={total === 0 || busy || !me} className={buttonAi}>
              {busy ? "Opening PayPal…" : total === 0 ? "Choose items to pay for" : `Pay ${usd(total)} with PayPal`}
            </button>
            <button
              type="button"
              onClick={() => {
                setPaying(false);
                setSelected(new Set());
              }}
              disabled={busy}
              className={outline}
            >
              Cancel
            </button>
          </div>
        ) : (
          <>
            <div className="flex gap-2.5">
              <Link href={`/lists/${list.id}/receipts`} className={`${buttonAi} flex-1 px-2`}>
                Scan receipt
              </Link>
              {items.some(payable) && (
                <button type="button" onClick={startPaying} disabled={!me} className={`${outline} flex-1 px-2`}>
                  {mine.length > 0 ? `Pay ${usd(mine.reduce((sum, item) => sum + cost(item), 0))}` : "Pay with PayPal"}
                </button>
              )}
            </div>
            <ShopAgent />
            {members.length > 0 && open.some((item) => !item.claimedBy) && (
              <button type="button" onClick={assign} className={outline}>
                Share out the rest evenly
              </button>
            )}
            <button type="button" onClick={() => finish(!list.finishedAt)} className="self-start text-[15px] text-muted">
              {list.finishedAt ? "Reopen this list" : "Mark this list finished"}
            </button>
          </>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-3.5 lg:gap-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-medium lg:text-xl">Still to get</h2>
          <span className="text-[15px] text-muted tabular-nums">
            {open.length} {open.length === 1 ? "item" : "items"} · ~{usd(open.reduce((sum, item) => sum + cost(item), 0))}
          </span>
        </div>
        {open.length === 0 ? <p className="text-base text-muted">Everything is done.</p> : <ul className="flex flex-col gap-2.5">{open.map(itemRow)}</ul>}
        {done.length > 0 && (
          <>
            <h2 className="text-lg font-medium lg:text-xl">Done</h2>
            <ul className="flex flex-col gap-2.5">{done.map(itemRow)}</ul>
          </>
        )}
      </div>
    </div>
  );
}
