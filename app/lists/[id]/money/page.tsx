"use client";

import { usd } from "../../../api";
import { EqualShare, SettleUp, useSplit, WhoPaid } from "../../../split";
import { card, useList } from "../list-context";

// Money: spent together, budget, who paid what, receipt extras. On the website Settle up sits beside it
// (Figma "Web 3 · List — Money & Settle up"); on the phone it has its own tab.
export default function MoneyPage() {
  const { list, me } = useList();
  const split = useSplit(list);
  // The list items' part of receipt tax, tip and fees counts as spent on the list, as it does in the split.
  const fees = split?.members.flatMap((m) => m.purchases).reduce((sum, line) => sum + (line.feesOf ? line.cents : 0), 0) ?? 0;
  const spent = list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), fees);
  const left = list.items.reduce((sum, item) => sum + (item.checkedAt ? 0 : (item.estPriceCents ?? 0) * item.quantity), 0);
  // How far over the budget the list ends up once the rest is bought, said in words as well as colour.
  const projectedOver = list.budgetCents !== null ? spent + left - list.budgetCents : 0;
  const extras = list.receipts.filter((r) => r.confirmedAt).flatMap((r) => r.extras);
  const extrasCents = extras.reduce((sum, extra) => sum + (extra.priceCents ?? 0), 0);

  return (
    <div className="flex flex-col gap-[18px] lg:flex-row lg:items-start lg:gap-10">
      <div className="flex min-w-0 flex-1 flex-col gap-[18px] lg:gap-6">
        <div className="flex flex-col gap-[18px] lg:flex-row lg:gap-5">
          <div className="flex flex-1 flex-col gap-1 lg:glass lg:rounded-3xl lg:p-6">
            <span className="text-[15px] font-medium text-muted-on-bg lg:text-money">Spent together</span>
            <span className="text-[56px] leading-tight font-light tracking-[-0.03em] tabular-nums">{usd(spent)}</span>
            {split && <EqualShare split={split} />}
          </div>
          <div className={`${card} flex flex-1 flex-col gap-2.5 lg:p-6`}>
            <span className="text-[15px] text-muted">Budget</span>
            <span className="text-[40px] font-light tabular-nums">{list.budgetCents !== null ? usd(list.budgetCents) : "—"}</span>
            <span className={`text-[15px] ${projectedOver > 0 ? "text-money" : "text-muted"}`}>
              {list.budgetCents !== null
                ? `${spent <= list.budgetCents ? `${usd(list.budgetCents - spent)} left` : `${usd(spent - list.budgetCents)} over`} · about ${usd(left)} still to buy${
                    projectedOver > 0 && spent <= list.budgetCents ? `, which would put you about ${usd(projectedOver)} over` : ""
                  }`
                : `No budget set · about ${usd(left)} still to buy`}
            </span>
          </div>
        </div>

        {split && <WhoPaid list={list} split={split} />}

        {extras.length > 0 && (
          <div className={`${card} flex items-center justify-between gap-4`}>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="text-base font-medium">Receipt extras</span>
              <span className="text-[13px] text-muted">{extras.map((extra) => extra.name).join(", ")} — not on the list</span>
            </span>
            <span className="text-lg font-medium text-ai tabular-nums">{usd(extrasCents)}</span>
          </div>
        )}
      </div>

      {split && (
        <div className="hidden lg:block lg:w-[460px] lg:shrink-0 lg:pt-[30px]">
          <SettleUp list={list} split={split} me={me} />
        </div>
      )}
    </div>
  );
}
