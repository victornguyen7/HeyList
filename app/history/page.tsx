"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, usd, type List } from "../api";
import { ListCard, spent, useSeenLists } from "../recent";
import { buttonGlass, card } from "../ui";

const month = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "long", year: "numeric" });

function totalsBy(lists: List[], key: (list: List) => string) {
  const totals = new Map<string, number>();
  for (const list of lists) totals.set(key(list), (totals.get(key(list)) ?? 0) + spent(list));
  return [...totals];
}

function Totals({ heading, rows }: { heading: string; rows: [string, number][] }) {
  return (
    <section className={`${card} flex flex-col gap-2`}>
      <h2 className="text-[15px] text-muted">{heading}</h2>
      <ul className="flex flex-col gap-1 text-base">
        {rows.map(([label, cents]) => (
          <li key={label} className="flex justify-between gap-2 tabular-nums">
            <span className="capitalize">{label}</span>
            <span>{usd(cents)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// History: the lists this browser has opened (no accounts, decision 6), spending by type and month, and buy again.
export default function HistoryPage() {
  const router = useRouter();
  const lists = useSeenLists();
  const [status, setStatus] = useState<string | null>(null);

  // Buy again: a fresh copy of the list with the same items, all unchecked.
  async function again(list: List) {
    try {
      // A proven price (PayPal or a receipt) replaces the old estimate: what one unit really cost (decision 49).
      const items = list.items.map(({ name, note, quantity, estPriceCents, priceCents, orderId, receiptId }) => ({
        name, note, quantity,
        estPriceCents: priceCents && (orderId || receiptId) ? Math.round(priceCents / quantity) : estPriceCents,
      }));
      const created = await api<List>("/api/lists", {
        method: "POST",
        body: JSON.stringify({ title: list.title, kind: list.kind, budgetCents: list.budgetCents, items }),
      });
      router.push(`/lists/${created.id}`);
    } catch (err) {
      setStatus(`Could not copy the list: ${(err as Error).message}`);
    }
  }

  return (
    <main className="flex flex-col gap-5 lg:mx-auto lg:w-full lg:max-w-[760px]">
      <Link href="/" className="text-base font-medium text-muted lg:hidden">
        ← Lists
      </Link>
      <h1 className="text-[32px] tracking-[-0.015em] lg:text-[48px] lg:font-medium">History</h1>

      {status && (
        <p role="status" className={`${card} text-base`}>
          {status}
        </p>
      )}

      {!lists ? (
        <p className="text-base text-muted">Loading…</p>
      ) : lists === "failed" ? (
        <p role="status" className="text-base text-muted">
          Your lists could not be loaded right now. They are still saved; reload the page to try again.
        </p>
      ) : lists.length === 0 ? (
        <p className="text-base text-muted">No lists yet. Lists you make or open on this device show up here.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Totals heading="By type" rows={totalsBy(lists, (list) => list.kind)} />
            <Totals heading="By month" rows={totalsBy(lists, (list) => month(list.createdAt))} />
          </div>

          <ul className="flex flex-col gap-2.5">
            {lists.map((list) => (
              <li key={list.id}>
                <ListCard list={list}>
                  <button type="button" onClick={() => again(list)} className={`${buttonGlass} h-10 shrink-0 px-4 text-sm`}>
                    Buy again
                  </button>
                </ListCard>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
