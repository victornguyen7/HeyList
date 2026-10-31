"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, captureMessage, proofLabel, refundNote, usd, type Capture, type Item, type List } from "../../api";
import { PayPalButtons } from "../../paypal-buttons";
import { ShopAgent } from "../../shop-agent";
import { Check, menuRow, mini, PayCard, payPayPal, Ring } from "../../ui";
import { buttonAi, card, outline, row, useList } from "./list-context";

// Progress: the checklist itself. The tick means "done"; paying with PayPal and shopping in stores are separate modes
// that put a circle on each item to choose, so a plain checklist never shows payment controls unless someone asks.
export default function ProgressPage() {
  const { list, setList, me, memberName, setStatus, joinCard } = useList();
  // "pay": choose items to pay for with PayPal; "shop": choose items for the shopping agent to find in stores.
  const [mode, setMode] = useState<"pay" | "shop" | null>(null);
  // The phone's More actions sheet is open.
  const [sheet, setSheet] = useState(false);
  const sheetRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = sheetRef.current;
    if (sheet && !dialog?.open) dialog?.showModal();
    if (!sheet && dialog?.open) dialog.close();
  }, [sheet]);
  // Set while the agent's cart is shown, so the items it searched for can't change under it.
  const [planned, setPlanned] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  // The item being ticked by hand, and the price typed for it (asked in the row, not in a pop-up).
  const [ticking, setTicking] = useState<string | null>(null);
  const [priceText, setPriceText] = useState("");
  // The name typed into "+ Add an item".
  const [extra, setExtra] = useState("");
  const { items, members } = list;

  async function patchItem(item: Item, change: object) {
    try {
      const saved = await api<Item>(`/api/items/${item.id}`, { method: "PATCH", body: JSON.stringify(change) });
      setList((current) => ({ ...current, items: current.items.map((i) => (i.id === saved.id ? saved : i)) }));
    } catch (err) {
      setStatus(`Could not save that change: ${(err as Error).message}`);
    }
  }

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    const name = extra.trim();
    if (!name) return;
    try {
      const added = await api<Item[]>(`/api/lists/${list.id}/items`, { method: "POST", body: JSON.stringify({ items: [{ name, quantity: 1 }] }) });
      setList((current) => ({ ...current, items: [...current.items, ...added] }));
      setExtra("");
    } catch (err) {
      setStatus(`Could not add ${name}: ${(err as Error).message}`);
    }
  }

  // Removes it for everyone on the list, so it asks first, as Remove does on History.
  async function removeItem(item: Item) {
    if (!window.confirm(`Remove "${item.name}" from this list? It goes for everyone on the list.`)) return;
    try {
      await api(`/api/items/${item.id}`, { method: "DELETE" });
      setList((current) => ({ ...current, items: current.items.filter((i) => i.id !== item.id) }));
    } catch (err) {
      setStatus(`Could not remove ${item.name}: ${(err as Error).message}`);
    }
  }

  // Ticking by hand asks what was paid, in the row, so the split has a real price; blank means "don't know" and
  // leaves it out. Unticking needs no question.
  function tick(item: Item) {
    if (item.checkedAt) return patchItem(item, { checked: false });
    setTicking(item.id);
    setPriceText(item.estPriceCents !== null ? ((item.estPriceCents * item.quantity) / 100).toFixed(2) : "");
  }

  async function confirmTick(e: React.FormEvent, item: Item) {
    e.preventDefault();
    const priceCents = priceText.trim() ? Math.round(Number(priceText.replace("$", "")) * 100) : null;
    if (priceCents !== null && !(priceCents >= 0)) return setStatus("That price wasn't a number, so nothing was changed.");
    setTicking(null);
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

  async function pay(itemIds: string[]) {
    setBusy(true);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list.id}/orders`, {
        method: "POST",
        body: JSON.stringify({ itemIds, memberId: me }),
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

  // The PayPal and Venmo buttons (decision 67): the same order route, approved in PayPal's pop-up instead of a redirect.
  async function orderFor(itemIds: string[], method: "paypal" | "venmo") {
    setStatus(null);
    try {
      const { orderId } = await api<{ orderId: string }>(`/api/lists/${list.id}/orders`, {
        method: "POST",
        body: JSON.stringify({ itemIds, memberId: me, method }),
      });
      return orderId;
    } catch (e) {
      const err = e as Error & { code?: string };
      if (err.code === "PRICE_CHANGED") setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
      setStatus(err.code === "PRICE_CHANGED" ? err.message : `Could not start checkout: ${err.message}`);
      throw err;
    }
  }

  async function captured(orderId: string) {
    try {
      setStatus(captureMessage(await api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })));
    } catch (err) {
      setStatus(`Payment could not be confirmed: ${(err as Error).message}`);
    }
    stopChoosing();
    setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
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

  // Bought items and items held by a pending payment can't be shopped; prices aren't needed, the stores give them.
  const shoppable = (item: Item) => !item.checkedAt && !held(item);
  const choosable = (item: Item) => (mode === "pay" ? payable(item) : shoppable(item));

  function startPaying() {
    setSelected(new Set(mine.map((item) => item.id)));
    setMode("pay");
  }

  // One main action, chosen by where the list is (phase 8C); everything else sits under More.
  const mineCost = mine.reduce((sum, item) => sum + cost(item), 0);
  const main: "pay" | "share" | "settle" | "scan" | null = !me
    ? null
    : mine.length > 0
      ? "pay"
      : members.length > 0 && open.some((item) => !item.claimedBy)
        ? "share"
        : open.length === 0 && done.length > 0
          ? "settle"
          : "scan";

  // Starts with nothing ticked: the person chooses every item the agent searches for.
  function startShopping() {
    setSelected(new Set());
    setMode("shop");
  }

  function stopChoosing() {
    setMode(null);
    setPlanned(false);
    setSelected(new Set());
  }

  function itemRow(item: Item) {
    const isDone = Boolean(item.checkedAt);
    const proof = proofLabel(item, list.orders);
    // A PayPal payment or a receipt is evidence; only a tick made by hand can be taken back here.
    const tickable = !held(item) && !item.orderId && !item.receiptId && Boolean(me) && !busy;
    const who = item.claimedBy ? (item.claimedBy === me ? "You claimed" : memberName(item.claimedBy)) : "Nobody yet";
    return (
      <li key={item.id} className={`${row} items-start`}>
        <label className={`mt-0.5 flex shrink-0 ${mode ? (choosable(item) && !planned ? "cursor-pointer" : "opacity-30") : tickable ? "cursor-pointer" : ""}`}>
          {mode ? (
            <>
              <input
                type="checkbox"
                className="peer sr-only"
                aria-label={mode === "pay" ? `Pay for ${item.name}` : `Shop for ${item.name}`}
                checked={selected.has(item.id)}
                disabled={!choosable(item) || busy || planned}
                onChange={() => toggle(item.id)}
              />
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
          {isDone || held(item) || mode ? (
            <span className={`text-[17px] font-medium lg:font-semibold ${isDone ? "text-muted line-through" : ""}`}>{item.name}</span>
          ) : (
            // Tap the name to change how many, or who buys it.
            <details className="group">
              <summary className="flex cursor-pointer list-none items-baseline gap-1.5 text-[17px] font-medium lg:font-semibold [&::-webkit-details-marker]:hidden">
                <span className="min-w-0">{item.name}</span>
                <span aria-hidden className="shrink-0 font-normal text-muted group-open:rotate-90">
                  ›
                </span>
              </summary>
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
                <button type="button" disabled={busy} onClick={() => removeItem(item)} className="h-8 px-2 font-medium text-muted underline underline-offset-4">
                  Remove
                </button>
              </div>
            </details>
          )}
          <span className={`text-[13px] ${held(item) ? "text-money" : "text-muted"}`}>
            {isDone ? `${proof}${memberName(item.boughtBy) ? ` · ${memberName(item.boughtBy)}` : ""}` : (proof ?? `${who} · ×${item.quantity}`)}
          </span>
          {item.note && !isDone && <span className="text-[13px] text-money">{item.note}</span>}
          {ticking === item.id && (
            <form onSubmit={(e) => confirmTick(e, item)} className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-1.5">
                What did you pay? $
                <input
                  autoFocus
                  inputMode="decimal"
                  className="h-9 w-24 rounded-full bg-surface-2 px-3 tabular-nums"
                  value={priceText}
                  onChange={(e) => setPriceText(e.target.value)}
                  placeholder="Don't know"
                  aria-label={`What you paid for ${item.name}`}
                />
              </label>
              <button type="submit" className="h-9 rounded-full bg-list px-4 font-medium text-on-accent">
                Done
              </button>
              <button type="button" onClick={() => setTicking(null)} className="text-muted">
                Cancel
              </button>
            </form>
          )}
        </div>
        <span className={`mt-0.5 shrink-0 text-base font-medium tabular-nums lg:font-semibold ${isDone ? "text-list" : ""}`}>
          {isDone ? (item.priceCents !== null ? usd(item.priceCents) : "—") : item.estPriceCents !== null ? `~${usd(cost(item))}` : "—"}
        </span>
      </li>
    );
  }

  const stat = (value: string, label: string, color: string) => (
    <div className={`${card} flex flex-1 flex-col gap-0.5 p-3.5 font-medium`}>
      {/* Scales with the screen, so "$1,234.56" fits three across at 320 px. */}
      <span className={`text-[clamp(1.0625rem,5.6vw,1.5rem)] tracking-[-0.015em] tabular-nums ${color}`}>{value}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  );

  // More actions (Figma "Action row"): a bottom sheet on the phone, a menu card on the website. Each row closes the sheet.
  const actions: { label: string; href?: string; onClick?: () => void; disabled?: boolean }[] = [
    ...(main !== "scan" ? [{ label: "Scan a receipt", href: `/lists/${list.id}/receipts` }] : []),
    ...(items.some(payable) ? [{ label: main === "pay" ? "Choose other items to pay for" : "Pay for items with PayPal", onClick: startPaying, disabled: !me }] : []),
    ...(items.some(shoppable) ? [{ label: "Shop this list for me", onClick: startShopping }] : []),
    ...(main !== "share" && members.length > 0 && open.some((item) => !item.claimedBy) ? [{ label: "Share out the rest evenly", onClick: assign }] : []),
    ...(main !== "settle" && done.length > 0 ? [{ label: "Settle up", href: `/lists/${list.id}/settle` }] : []),
  ];
  const actionRows = (
    <div className="flex flex-col divide-y divide-muted/15">
      {actions.map((action) =>
        action.href ? (
          <Link key={action.label} href={action.href} className={menuRow}>
            {action.label}
            <span aria-hidden className="text-xl font-normal text-muted">›</span>
          </Link>
        ) : (
          <button
            key={action.label}
            type="button"
            disabled={action.disabled}
            onClick={() => {
              setSheet(false);
              action.onClick!();
            }}
            className={menuRow}
          >
            {action.label}
            <span aria-hidden className="text-xl font-normal text-muted">›</span>
          </button>
        ),
      )}
    </div>
  );
  const finishButton = (
    <button
      type="button"
      onClick={() => {
        setSheet(false);
        finish(!list.finishedAt);
      }}
      className="py-2 text-[15px] font-medium text-muted"
    >
      {list.finishedAt ? "Reopen this list" : "Mark this list finished"}
    </button>
  );
  const payLabel = `Your ${mine.length === 1 ? "item" : `${mine.length} items`}`;

  return (
    <div className="flex flex-col gap-3.5 lg:flex-row-reverse lg:items-start lg:gap-10">
      <aside className="flex flex-col gap-3.5 lg:w-[400px] lg:shrink-0 lg:gap-5">
        <div className="flex flex-col items-center gap-5 pt-1.5 lg:glass lg:rounded-3xl lg:p-6">
          {/* Smaller on the phone, so the pay card and the first items fit above the tab bar. */}
          <div className="relative size-32 lg:size-44">
            <Ring done={done.length} total={items.length} size={176} className="size-full" />
            <span className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="flex items-baseline gap-0.5">
                <span className="text-[36px] font-light tracking-[-0.03em] tabular-nums lg:text-[49px]">{done.length}</span>
                <span className="text-base font-medium text-muted tabular-nums lg:text-[21px]">/{items.length}</span>
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

        {mode === "shop" ? (
          <ShopAgent itemIds={[...selected]} onPlanned={setPlanned} onClose={stopChoosing} />
        ) : mode === "pay" ? (
          <div className="flex flex-col gap-2.5">
            <PayCard title="Choose what you're paying for" amount={usd(total)}>
              {total === 0 || !me ? (
                <button type="button" disabled className={payPayPal}>
                  Tick items to pay for
                </button>
              ) : (
                <PayPalButtons createOrder={(method) => orderFor([...selected], method)} onApproved={captured} onError={setStatus}>
                  <button type="button" onClick={() => pay([...selected])} disabled={busy} className={payPayPal}>
                    {busy ? "Opening PayPal…" : "Pay with PayPal"}
                  </button>
                </PayPalButtons>
              )}
            </PayCard>
            <button type="button" onClick={stopChoosing} disabled={busy} className="py-2 text-[15px] font-medium text-muted-on-bg">
              Cancel
            </button>
          </div>
        ) : (
          <>
            {joinCard}
            {main === "pay" && (
              <PayCard title={payLabel} amount={usd(mineCost)} note="Ticked off for you as soon as PayPal confirms.">
                <PayPalButtons createOrder={(method) => orderFor(mine.map((item) => item.id), method)} onApproved={captured} onError={setStatus}>
                  <button type="button" onClick={() => pay(mine.map((item) => item.id))} disabled={busy} className={payPayPal}>
                    {busy ? "Opening PayPal…" : "Pay with PayPal"}
                  </button>
                </PayPalButtons>
              </PayCard>
            )}
            {main === "share" && (
              <button type="button" onClick={assign} className={buttonAi}>
                Share out the rest evenly
              </button>
            )}
            {main === "settle" && (
              <Link href={`/lists/${list.id}/settle`} className={buttonAi}>
                Everything&apos;s bought. Settle up
              </Link>
            )}
            {main === "scan" && (
              <Link href={`/lists/${list.id}/receipts`} className={buttonAi}>
                Scan a receipt
              </Link>
            )}

            {me && (
              <>
                <button type="button" onClick={() => setSheet(true)} className="py-1 text-[15px] font-medium text-muted-on-bg lg:hidden">
                  More actions ›
                </button>
                <nav className="glass hidden flex-col rounded-3xl py-2 lg:flex" aria-label="More actions">
                  <span className="px-[18px] pt-2 pb-1 text-[13px] font-medium text-muted">More actions</span>
                  {actionRows}
                  <span className="flex justify-center border-t border-muted/15 pt-1">{finishButton}</span>
                </nav>
              </>
            )}
            {/* A native modal: Esc closes it, focus stays inside, the page behind is inert, and focus returns to
                "More actions" on closing. A click on the backdrop lands on the dialog itself, not the panel. */}
            <dialog
              ref={sheetRef}
              aria-label="More actions"
              onClose={() => setSheet(false)}
              onClick={(e) => e.target === e.currentTarget && setSheet(false)}
              className="fixed inset-x-0 top-auto bottom-0 m-0 max-h-[85dvh] w-full max-w-none overflow-y-auto overscroll-contain rounded-t-[28px] bg-transparent p-0 backdrop:bg-text/30 lg:hidden"
            >
              <div className="flex flex-col gap-1 rounded-t-[28px] bg-surface-2 px-4 pt-2.5 pb-7 shadow-[0_-10px_30px_rgb(30_40_60/0.12)] backdrop-blur-xl">
                <span className="mx-auto h-[5px] w-10 rounded-full bg-muted/40" />
                <span className="flex items-center justify-between pt-2 pb-1.5 pl-[18px]">
                  <span className="text-lg font-medium">More actions</span>
                  <button type="button" onClick={() => setSheet(false)} className="h-11 px-3 text-[15px] font-medium text-muted">
                    Close
                  </button>
                </span>
                <div className="rounded-[20px] bg-bg/70">{actionRows}</div>
                <span className="flex justify-center pt-2">{finishButton}</span>
              </div>
            </dialog>
          </>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-3.5 lg:gap-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-medium lg:text-xl">Still to get</h2>
          <span className="text-[15px] text-muted-on-bg tabular-nums">
            {open.length} {open.length === 1 ? "item" : "items"} · ~{usd(open.reduce((sum, item) => sum + cost(item), 0))}
          </span>
        </div>
        {open.length === 0 ? (
          <p className="text-base text-muted-on-bg">{items.length === 0 ? "Nothing on this list yet. Add the first item below." : "Everything is done."}</p>
        ) : (
          <ul className="flex flex-col gap-2.5">{open.map(itemRow)}</ul>
        )}
        {!mode && (
          <form onSubmit={addItem} className={`${row} py-2.5`}>
            <input
              className="h-8 min-w-0 flex-1 rounded-md bg-transparent text-base font-medium text-ai placeholder:text-ai focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-text"
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              placeholder="+ Add an item"
              aria-label="Add an item"
              maxLength={120}
            />
            {extra.trim() && (
              <button type="submit" className={`${mini} self-center`}>
                Add
              </button>
            )}
          </form>
        )}
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
