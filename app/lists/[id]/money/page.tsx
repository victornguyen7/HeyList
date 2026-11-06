"use client";

import { useState } from "react";
import { api, itemsTax, percent, priceShown, usd, type List } from "../../../api";
import { typedCents } from "../../../photo";
import { EqualShare, SettleUp, useSplit, WhoPaid, type Split } from "../../../split";
import { mini } from "../../../ui";
import { card, useList } from "../list-context";

// Money: spent together, budget, who paid what, receipt extras. On the website Settle up sits beside it
// (Figma "Web 3 · List — Money & Settle up"); on the phone it has its own tab.
export default function MoneyPage() {
  const { list, me } = useList();
  const split = useSplit(list);
  // Spent as the split counts it: items, sales tax, the list items' part of receipt tips and fees, less refunds,
  // plus items checked off with a price but no buyer. A split saved before tax was counted falls back to the old sum.
  const fees = split?.members.flatMap((m) => m.purchases).reduce((sum, line) => sum + (line.feesOf ? line.cents : 0), 0) ?? 0;
  const spent =
    split?.itemsCents !== undefined
      ? split.totalCents + split.unattributedCents
      : list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), fees);
  const rate = list.tax?.rateBp ?? 0;
  const toBuy = list.items.filter((item) => !item.checkedAt);
  // Still to buy with its sales tax, as a checkout would charge it (decision 80).
  const leftTax = itemsTax(toBuy, rate);
  const left = toBuy.reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0) + leftTax;
  // How far over the budget the list ends up once the rest is bought, said in words as well as colour.
  const projectedOver = list.budgetCents !== null ? spent + left - list.budgetCents : 0;
  // Where the still-to-buy estimate comes from, by the labels Progress shows (Walmart, Kroger, paid before, AI guess),
  // largest first, so it's clear how much of it is a real store price and how much a guess. "~" marks guesses.
  const bySource = new Map<string, { cents: number; approx: boolean }>();
  for (const item of list.items) {
    if (item.checkedAt || item.estPriceCents === null) continue;
    const shown = priceShown(item);
    const key = item.product ? "chosen product" : (shown.label ?? "no source");
    const group = bySource.get(key) ?? { cents: 0, approx: shown.approx };
    bySource.set(key, { cents: group.cents + item.estPriceCents * item.quantity, approx: group.approx });
  }
  const sources = [...bySource.entries()].sort((a, b) => b[1].cents - a[1].cents);
  const extras = list.receipts.filter((r) => r.confirmedAt).flatMap((r) => r.extras);
  const extrasCents = extras.reduce((sum, extra) => sum + (extra.priceCents ?? 0), 0);

  return (
    <div className="flex flex-col gap-[1.125rem] lg:flex-row lg:items-start lg:gap-10">
      <div className="flex min-w-0 flex-1 flex-col gap-[1.125rem] lg:gap-6">
        <div className="flex flex-col gap-[1.125rem] lg:flex-row lg:gap-5">
          <div className="flex flex-1 flex-col gap-1 lg:glass lg:rounded-3xl lg:p-6">
            <span className="text-[0.9375rem] font-medium text-muted-on-bg lg:text-money">Spent together</span>
            <span className="text-[3.5rem] leading-tight font-light tracking-[-0.03em] tabular-nums">{usd(spent)}</span>
            {split && <EqualShare split={split} />}
          </div>
          <div className={`${card} flex flex-1 flex-col gap-2.5 lg:p-6`}>
            <span className="text-[0.9375rem] text-muted">Budget</span>
            <span className="text-[2.5rem] font-light tabular-nums">{list.budgetCents !== null ? usd(list.budgetCents) : "—"}</span>
            <span className={`text-[0.9375rem] ${projectedOver > 0 ? "text-money" : "text-muted"}`}>
              {list.budgetCents !== null
                ? `${spent <= list.budgetCents ? `${usd(list.budgetCents - spent)} left` : `${usd(spent - list.budgetCents)} over`} · about ${usd(left)} still to buy${
                    projectedOver > 0 && spent <= list.budgetCents ? `, which would put you about ${usd(projectedOver)} over` : ""
                  }`
                : `No budget set · about ${usd(left)} still to buy`}
              {leftTax > 0 && ` (with ~${usd(leftTax)} tax)`}
            </span>
            {sources.length > 0 && (
              <ul aria-label="Still to buy, by where the price comes from" className="flex flex-wrap gap-x-3 gap-y-1 text-[0.8125rem] text-muted">
                {sources.map(([label, { cents, approx }]) => (
                  <li key={label} className="whitespace-nowrap tabular-nums">
                    {label} <span className="font-medium text-text">{approx ? "~" : ""}{usd(cents)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {split && split.itemsCents !== undefined && split.totalCents + split.unattributedCents > 0 && <AddsUp split={split} spent={spent} />}
        <SalesTax list={list} />

        {split && <WhoPaid list={list} split={split} />}

        {extras.length > 0 && (
          <div className={`${card} flex items-center justify-between gap-4`}>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="text-base font-medium">Receipt extras</span>
              <span className="text-[0.8125rem] text-muted">{extras.map((extra) => extra.name).join(", ")} — not on the list</span>
            </span>
            <span className="text-lg font-medium text-ai tabular-nums">{usd(extrasCents)}</span>
          </div>
        )}
      </div>

      {split && (
        <div className="hidden lg:block lg:w-[28.75rem] lg:shrink-0 lg:pt-[1.875rem]">
          <SettleUp list={list} split={split} me={me} />
        </div>
      )}
    </div>
  );
}

// How "Spent together" adds up, line by line like the bottom of a receipt: items, sales tax, tip and fees, refunds.
function AddsUp({ split, spent }: { split: Split; spent: number }) {
  const tax = split.taxCents ?? 0;
  const fees = split.feesCents ?? 0;
  const refunded = split.refundedCents ?? 0;
  const rows: [string, number][] = [
    // Whatever isn't tax, fees or a refund is items, so the rows always add up to the total shown.
    ["Items", spent - tax - fees + refunded],
    ["Sales tax", tax],
    ...(fees ? ([["Tip and fees", fees]] as [string, number][]) : []),
    ...(refunded ? ([["Refunded in PayPal", -refunded]] as [string, number][]) : []),
  ];
  return (
    <section aria-label="How the money adds up" className={`${card} flex flex-col gap-1.5 text-base tabular-nums`}>
      <h2 className="mb-1 text-base font-medium">How it adds up</h2>
      {rows.map(([label, cents]) => (
        <span key={label} className="flex justify-between gap-3">
          <span className="text-muted">{label}</span>
          <span>{cents < 0 ? `−${usd(-cents)}` : usd(cents)}</span>
        </span>
      ))}
      <span className="mt-1 flex justify-between gap-3 border-t border-line pt-2 font-medium">
        <span>Spent together</span>
        <span>{usd(spent)}</span>
      </span>
    </section>
  );
}

// The list's sales tax rate (decision 80). Receipts set it once one is confirmed; before that, the rate typed here.
// PayPal payments charge it, and "still to buy" and the shopping agent count it.
function SalesTax({ list }: { list: List }) {
  const { setList, setStatus } = useList();
  const [editing, setEditing] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const tax = list.tax ?? { rateBp: 0, source: null };
  const bp = typedCents(typed.replace(/%\s*$/, ""));
  const bad = bp !== null && (Number.isNaN(bp) || bp > 2500);

  async function save(rateBp: number | null) {
    setBusy(true);
    try {
      setList(await api<List>(`/api/lists/${list.id}`, { method: "PATCH", body: JSON.stringify({ taxRateBp: rateBp }) }));
      setEditing(false);
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  return (
    <div className={`${card} flex flex-col gap-2 text-base`}>
      <span className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="font-medium">Sales tax {tax.source ? percent(tax.rateBp) : ""}</span>
          <span className="text-[0.8125rem] text-muted">
            {tax.source === "receipts"
              ? "From your receipts: what the stores really charged on what you bought."
              : tax.source === "set"
                ? "Set by hand. A scanned receipt will replace it with what the stores really charge."
                : "None yet. Set your local rate, or scan a receipt and it's worked out for you."}
          </span>
        </span>
        {!editing && tax.source !== "receipts" && (
          <button type="button" onClick={() => (setTyped(list.taxRateBp !== null ? percent(list.taxRateBp).replace("%", "") : ""), setEditing(true))} className={mini}>
            {tax.source ? "Change" : "Set rate"}
          </button>
        )}
      </span>
      {editing && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!bad) save(bp);
          }}
        >
          <input
            aria-label="Sales tax rate, percent"
            inputMode="decimal"
            placeholder="8.25"
            autoFocus
            className={`h-11 w-24 rounded-[1.25rem] bg-surface-2 px-3 text-right tabular-nums ${bad ? "outline outline-money" : ""}`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
          <span className="text-muted">%</span>
          <button type="submit" disabled={busy || bad} className={mini}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)} disabled={busy} className="text-[0.8125rem] text-muted">
            Cancel
          </button>
          {bad && <span className="basis-full text-[0.8125rem] text-money">Type a rate like 8.25, up to 25.</span>}
        </form>
      )}
      <span className="text-[0.8125rem] text-muted">PayPal and Venmo payments add it, and the budget counts it.</span>
    </div>
  );
}
