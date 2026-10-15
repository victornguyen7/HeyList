"use client";

import { usd } from "../../../api";
import { SplitPanel } from "../../../split";
import { card, useList } from "../list-context";

// Money: spent vs budget, receipt extras, and each person's totals.
export default function MoneyPage() {
  const { list } = useList();
  const spent = list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), 0);
  const left = list.items.reduce((sum, item) => sum + (item.checkedAt ? 0 : (item.estPriceCents ?? 0) * item.quantity), 0);
  const extras = list.receipts.filter((r) => r.confirmedAt).flatMap((r) => r.extras);
  const extrasCents = extras.reduce((sum, extra) => sum + extra.priceCents, 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-2">
        <div className={card}>
          <p className="opacity-70">Spent on items</p>
          <p className="text-2xl font-semibold tabular-nums">{usd(spent)}</p>
        </div>
        <div className={card}>
          <p className="opacity-70">Budget</p>
          <p className="text-2xl font-semibold tabular-nums">{list.budgetCents !== null ? usd(list.budgetCents) : "—"}</p>
        </div>
        <div className={card}>
          <p className="opacity-70">Still to buy (est.)</p>
          <p className="text-2xl font-semibold tabular-nums">{usd(left)}</p>
        </div>
        <div className={card}>
          <p className="opacity-70">Extras</p>
          <p className="text-2xl font-semibold tabular-nums">{usd(extrasCents)}</p>
        </div>
      </div>

      {list.budgetCents !== null && (
        <div className="flex flex-col gap-2">
          <progress className="h-3 w-full" value={Math.min(spent, list.budgetCents)} max={list.budgetCents || 1} aria-label="Spent of budget" />
          {spent + left > list.budgetCents && (
            <p className="text-lg text-amber-700 dark:text-amber-400">Heading {usd(spent + left - list.budgetCents)} over budget.</p>
          )}
        </div>
      )}

      {extras.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold">Not on the list</h2>
          <ul className="flex flex-col gap-1 text-lg">
            {extras.map((extra, index) => (
              <li key={index} className="flex justify-between tabular-nums">
                <span>{extra.name}</span>
                <span>{usd(extra.priceCents)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <SplitPanel list={list} />
    </div>
  );
}
