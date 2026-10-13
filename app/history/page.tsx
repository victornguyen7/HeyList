"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { type History, LISTS_KEY, type ListState, api, dollars, rememberList, useStored } from "../lib";
import { Notice, card, primary, small } from "../ui";

const KIND_NAMES: Record<string, string> = {
  groceries: "Groceries",
  trip: "Trips",
  home: "Home",
  party: "Parties",
  other: "Other",
};

const monthName = (month: string) =>
  new Date(`${month}-01T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" });

function Totals({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <section className={`${card} flex flex-col gap-1`}>
      <h2 className="text-xl font-semibold">{title}</h2>
      {rows.map(([label, cents]) => (
        <p key={label} className="flex justify-between gap-2 text-lg">
          <span>{label}</span>
          <span>{dollars(cents)}</span>
        </p>
      ))}
    </section>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  // There are no accounts: "your lists" are the ones this browser has opened.
  const stored = useStored(LISTS_KEY);
  const [history, setHistory] = useState<History | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let ids: string[] = [];
    try {
      ids = JSON.parse(stored ?? "[]");
    } catch {}
    api<History>(`/history?ids=${ids.join(",")}`)
      .then(setHistory)
      .catch(() => setNotice("Your lists could not be loaded. Please refresh the page."));
  }, [stored]);

  async function copyList(id: string) {
    setNotice("");
    try {
      const copy = await api<ListState>(`/lists/${id}/reuse`, { method: "POST" });
      rememberList(copy.id);
      router.push(`/l/${copy.id}`);
    } catch {
      setNotice("That list could not be copied. Please try again.");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-5 p-5">
      <h1 className="text-3xl font-bold">Your lists</h1>
      <Notice text={notice} />
      {!history && !notice && <p className="text-xl">Loading…</p>}
      {history?.lists.length === 0 && <p className="text-xl">No lists yet. Start one and it will show up here.</p>}

      {history && history.lists.length > 0 && (
        <>
          <Totals
            title="Spending by type"
            rows={Object.entries(history.byKind).map(([kind, cents]) => [KIND_NAMES[kind] ?? kind, cents])}
          />
          <Totals
            title="Spending by month"
            rows={Object.entries(history.byMonth).map(([month, cents]) => [monthName(month), cents])}
          />

          <ul className="flex flex-col gap-3">
            {history.lists.map((list) => (
              <li key={list.id} className={`${card} flex flex-col gap-2`}>
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/l/${list.id}`} className="text-xl font-semibold underline">
                    {list.title}
                  </Link>
                  <span className="text-xl">{dollars(list.spentCents)}</span>
                </div>
                <p className="text-base text-zinc-600">
                  {list.finishedAt ? "Finished" : "In progress"} · {list.doneCount} of {list.itemCount} done ·{" "}
                  {new Date(list.createdAt).toLocaleDateString()}
                </p>
                <button type="button" className={`${small} self-start`} onClick={() => copyList(list.id)}>
                  Use this list again
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <Link href="/" className={`${primary} text-center`}>
        Start a new list
      </Link>
    </main>
  );
}
