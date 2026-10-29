"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, cachedLists, cacheLists, seenLists, usd, type List } from "./api";
import { card, Ring } from "./ui";

export const spent = (list: List) => list.items.reduce((sum, item) => sum + (item.checkedAt ? (item.priceCents ?? 0) : 0), 0);

// The lists this browser has opened (no accounts, decision 6), loaded in full in one request, most recently
// opened first. null while loading; "failed" if the backend can't be reached and nothing was cached, so that
// never looks like no lists.
export function useSeenLists() {
  const [lists, setLists] = useState<List[] | null | "failed">(null);
  useEffect(() => {
    const ids = seenLists();
    const cached = cachedLists().filter((list) => ids.includes(list.id));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser storage, readable only after hydration
    if (cached.length) setLists(cached.sort((a, b) => ids.indexOf(a.id) - ids.indexOf(b.id)));
    api<{ lists: List[] }>(`/api/lists?ids=${ids.map(encodeURIComponent).join(",")}`).then(
      (found) => {
        const fresh = found.lists.sort((a, b) => ids.indexOf(a.id) - ids.indexOf(b.id));
        setLists(fresh);
        cacheLists(fresh);
      },
      () => setLists((current) => current ?? "failed"),
    );
  }, []);
  return lists;
}

// Figma "List card": progress ring, title, how far along, what was spent. children are actions, in a footer row under
// it (Figma v2 "History card") so they never squeeze the title.
export function ListCard({ list, children }: { list: List; children?: React.ReactNode }) {
  const done = list.items.filter((item) => item.checkedAt).length;
  return (
    <div className={`${card} flex flex-col gap-3`}>
      <Link href={`/lists/${list.id}`} className="flex min-w-0 items-center gap-4">
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
      {children && <div className="flex items-center justify-between gap-4">{children}</div>}
    </div>
  );
}
