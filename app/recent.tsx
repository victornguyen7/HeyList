"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, cachedLists, cacheLists, priceShown, seenLists, usd, type Item, type List } from "./api";
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
// it (Figma v2 "History card") so they never squeeze the title. The title gets two lines and what was spent sits on the
// line under it, not in a column beside it (Figma "Overflow fixes", D).
// One item's price and where it came from, for the card's item list: what was paid for a bought item, else the
// estimate with its source, as on Progress.
function ItemPrice({ item }: { item: Item }) {
  if (item.owned) return <PriceCell amount="—" label="already had" />;
  if (item.checkedAt) return <PriceCell amount={item.priceCents !== null ? usd(item.priceCents) : "—"} label="bought" />;
  if (item.estPriceCents === null) return <PriceCell amount="—" label={null} />;
  const shown = priceShown(item);
  return <PriceCell amount={`${shown.approx ? "~" : ""}${usd(item.estPriceCents * item.quantity)}`} label={shown.label} />;
}

function PriceCell({ amount, label }: { amount: string; label: string | null }) {
  return (
    <span className="flex shrink-0 items-baseline gap-2 tabular-nums">
      <span className="font-medium">{amount}</span>
      {label && <span className="w-[5.5rem] text-right text-[12px] text-muted">{label}</span>}
      {!label && <span className="w-[5.5rem]" />}
    </span>
  );
}

// withItems (History): a tap-to-open list of every item with its price and where the price came from.
export function ListCard({ list, children, withItems = false }: { list: List; children?: React.ReactNode; withItems?: boolean }) {
  const done = list.items.filter((item) => item.checkedAt).length;
  return (
    <div className={`${card} flex flex-col gap-3`}>
      <Link href={`/lists/${list.id}`} className="flex min-w-0 items-center gap-4">
        <Ring done={done} total={list.items.length} size={56} />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="line-clamp-2 text-lg leading-snug font-medium [overflow-wrap:anywhere]">{list.title}</span>
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm text-muted">
            <span>
              {list.finishedAt ? "Finished" : `${done} of ${list.items.length} done`} · {list.members.length} {list.members.length === 1 ? "person" : "people"}
            </span>
            <span className="font-medium whitespace-nowrap">
              <span className="text-base text-money tabular-nums">{usd(spent(list))}</span> spent
            </span>
          </span>
        </span>
      </Link>
      {withItems && list.items.length > 0 && (
        <details className="group text-sm">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 font-medium text-muted [&::-webkit-details-marker]:hidden">
            {list.items.length} {list.items.length === 1 ? "item" : "items"}
            <span aria-hidden className="group-open:rotate-90">
              ›
            </span>
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5">
            {list.items.map((item) => (
              <li key={item.id} className="flex items-baseline justify-between gap-3">
                <span className={`min-w-0 truncate ${item.checkedAt ? "text-muted line-through" : ""}`}>
                  {item.name}
                  {item.quantity > 1 && <span className="text-muted"> ×{item.quantity}</span>}
                </span>
                <ItemPrice item={item} />
              </li>
            ))}
          </ul>
        </details>
      )}
      {children && <div className="flex items-center justify-between gap-4">{children}</div>}
    </div>
  );
}
