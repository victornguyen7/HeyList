"use client";

import { proofLabel, usd } from "../../../api";
import { useSplit } from "../../../split";
import { card, useList } from "../list-context";

// Settle up: the fewest payments that even out what everyone paid, and their PayPal invoices.
export default function SettlePage() {
  const { list, memberName } = useList();
  const item = (id: string) => list.items.find((i) => i.id === id);
  const split = useSplit(list);
  const name = (id: string | null) => memberName(id) ?? "Someone";

  if (list.members.length === 0) return <p className="text-lg">Settling up is for shared lists. Add people first.</p>;
  if (!split) return <p className="text-lg">Working it out…</p>;

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h2 className="text-2xl font-medium">Who pays whom</h2>
        {split.transfers.length === 0 && <p className="text-lg">{split.totalCents > 0 ? "Everyone is even." : "Nothing has been bought yet."}</p>}
        <ul className="flex flex-col gap-2">
          {split.transfers.map((t, index) => (
            <li key={index} className={`${card} flex justify-between text-xl tabular-nums`}>
              <span>
                {name(t.from)} → {name(t.to)}
              </span>
              <span className="font-medium">{usd(t.amountCents)}</span>
            </li>
          ))}
        </ul>
      </section>

      {split.totalCents > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-2xl font-medium">How this was worked out</h2>
          <p className="text-lg">
            {usd(split.totalCents)} was spent on list items, shared equally by {split.members.length}{" "}
            {split.members.length === 1 ? "person" : "people"}: {usd(Math.floor(split.totalCents / split.members.length))} each
            {split.totalCents % split.members.length > 0 && " (the odd cents go to the first people who joined)"}.
          </p>
          <ul className="flex flex-col gap-2">
            {split.members.map((m) => (
              <li key={m.memberId} className={card}>
                <details>
                  <summary className="flex cursor-pointer justify-between gap-2 tabular-nums">
                    <span>{name(m.memberId)}</span>
                    <span>
                      paid {usd(m.paidCents)} − share {usd(m.shareCents)} ={" "}
                      {m.balanceCents > 0 ? `gets back ${usd(m.balanceCents)}` : m.balanceCents < 0 ? `owes ${usd(-m.balanceCents)}` : "even"}
                    </span>
                  </summary>
                  {m.purchases.length === 0 ? (
                    <p className="mt-2 opacity-70">Hasn&apos;t paid for anything on the list yet.</p>
                  ) : (
                    <ul className="mt-2 flex flex-col gap-1">
                      {m.purchases.map((line, index) => {
                        const bought = item(line.itemId);
                        return (
                          <li key={index} className="flex justify-between gap-2 tabular-nums">
                            <span>
                              {bought?.name ?? "A deleted item"}
                              <span className="opacity-60">
                                {" · "}
                                {line.boughtTwice ? "bought again with PayPal" : bought ? proofLabel(bought, list.orders) : ""}
                              </span>
                            </span>
                            <span>{usd(line.cents)}</span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </details>
              </li>
            ))}
          </ul>
          <p className="text-base opacity-70">
            Only list items count. Receipt lines that weren&apos;t on the list are personal and not shared
            {split.unattributedCents > 0 && `, and ${usd(split.unattributedCents)} checked off without a name isn't counted`}.
          </p>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-2xl font-medium">Invoices</h2>
        {list.invoices.length === 0 ? (
          <p className="text-lg opacity-70">Sending these as PayPal invoices is coming soon.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {list.invoices.map((invoice) => (
              <li key={invoice.id} className={`${card} flex justify-between tabular-nums`}>
                <span>
                  {name(invoice.debtorId)} → {name(invoice.creditorId)} {usd(invoice.amountCents)}
                </span>
                {invoice.payUrl ? (
                  <a href={invoice.payUrl} className="underline underline-offset-4">
                    {invoice.status.toLowerCase()}
                  </a>
                ) : (
                  <span>{invoice.status.toLowerCase()}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
