"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, seenLists, usd, type List } from "./api";
import { card, Ring } from "./ui";

export const spent = (list: List) => list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), 0);

// One remembered list. Only a list the backend no longer has drops out; any other failure (the backend still
// waking up, a dropped connection) is tried again, so a slow start never looks like an empty history.
async function loadSeen(id: string, tries = 4): Promise<List | null> {
  try {
    return await api<List>(`/api/lists/${encodeURIComponent(id)}`);
  } catch (e) {
    if ((e as { code?: string }).code === "LIST_NOT_FOUND" || tries <= 1) return null;
    await new Promise((wait) => setTimeout(wait, 5000));
    return loadSeen(id, tries - 1);
  }
}

// The lists this browser has opened (no accounts, decision 6), loaded in full. null while loading.
export function useSeenLists() {
  const [lists, setLists] = useState<List[] | null>(null);
  useEffect(() => {
    Promise.all(seenLists().map((id) => loadSeen(id))).then((loaded) => setLists(loaded.filter((list) => list !== null)));
  }, []);
  return lists;
}

// Figma "List card": progress ring, title, how far along, what was spent.
export function ListCard({ list, children }: { list: List; children?: React.ReactNode }) {
  const done = list.items.filter((item) => item.checkedAt).length;
  return (
    <div className={`${card} flex items-center gap-4`}>
      <Link href={`/lists/${list.id}`} className="flex min-w-0 flex-1 items-center gap-4">
        <Ring done={done} total={list.items.length} size={56} />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-lg font-medium">{list.title}</span>
          <span className="text-sm text-muted">
            {list.finishedAt ? "Finished" : `${done} of ${list.items.length} done`} · {list.members.length} {list.members.length === 1 ? "person" : "people"}
          </span>
        </span>
        <span className="flex flex-col items-end gap-0.5 font-medium">
          <span className="text-lg text-money tabular-nums">{usd(spent(list))}</span>
          <span className="text-xs text-muted">spent</span>
        </span>
      </Link>
      {children}
    </div>
  );
}
