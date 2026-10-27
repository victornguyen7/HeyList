"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, seenLists, usd, type List } from "../api";

const card = "rounded-3xl glass p-4 text-lg";
const spent = (list: List) => list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), 0);
const month = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "long", year: "numeric" });

function totalsBy(lists: List[], key: (list: List) => string) {
  const totals = new Map<string, number>();
  for (const list of lists) totals.set(key(list), (totals.get(key(list)) ?? 0) + spent(list));
  return [...totals];
}

function Totals({ heading, rows }: { heading: string; rows: [string, number][] }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xl font-medium">{heading}</h2>
      <ul className="flex flex-col gap-1 text-lg">
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
  const [lists, setLists] = useState<List[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    // A list deleted since it was opened just drops out.
    Promise.allSettled(seenLists().map((id) => api<List>(`/api/lists/${encodeURIComponent(id)}`))).then((results) =>
      setLists(results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []))),
    );
  }, []);

  // Buy again: a fresh copy of the list with the same items, all unchecked.
  async function again(list: List) {
    try {
      const items = list.items.map(({ name, note, quantity, estPriceCents }) => ({ name, note, quantity, estPriceCents }));
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
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-10">
      <Link href="/" className="text-lg underline-offset-4 hover:underline">
        ← HeyList
      </Link>
      <h1 className="text-4xl font-medium tracking-tight">History</h1>

      {status && (
        <p role="status" className="glass rounded-3xl p-4 text-lg">
          {status}
        </p>
      )}

      {!lists ? (
        <p className="text-lg">Loading…</p>
      ) : lists.length === 0 ? (
        <p className="text-lg">No lists yet. Lists you make or open on this device show up here.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <Totals heading="By type" rows={totalsBy(lists, (list) => list.kind)} />
            <Totals heading="By month" rows={totalsBy(lists, (list) => month(list.createdAt))} />
          </div>

          <ul className="flex flex-col gap-2">
            {lists.map((list) => {
              const done = list.items.filter((item) => item.checkedAt).length;
              return (
                <li key={list.id} className={`${card} flex items-center justify-between gap-4`}>
                  <Link href={`/lists/${list.id}`} className="flex flex-1 flex-col">
                    <span className="text-xl">{list.title}</span>
                    <span className="opacity-70">
                      {list.finishedAt ? "Finished" : `${done} of ${list.items.length} done`} · {usd(spent(list))}
                    </span>
                  </Link>
                  <button type="button" onClick={() => again(list)} className="h-11 shrink-0 rounded-full glass px-4">
                    Buy again
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </main>
  );
}
