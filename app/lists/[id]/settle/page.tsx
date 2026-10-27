"use client";

import { usd } from "../../../api";
import { useSplit } from "../../../split";
import { card, useList } from "../list-context";

// Settle up: the fewest payments that even out what everyone paid, and their PayPal invoices.
export default function SettlePage() {
  const { list, memberName } = useList();
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
