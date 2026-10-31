"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { usd, type List } from "./api";
import { ListCard, spent, useSeenLists } from "./recent";
import { Starter } from "./starter";
import { card } from "./ui";

// Figma "This month", website only. Rendered only once the lists have loaded in the browser, so "now" is the
// visitor's date, not the build's.
function ThisMonth({ lists }: { lists: List[] }) {
  const now = new Date();
  const thisMonth = lists.filter((list) => new Date(list.createdAt).getMonth() === now.getMonth() && new Date(list.createdAt).getFullYear() === now.getFullYear());
  if (thisMonth.length === 0) return null;
  const byKind = new Map<string, number>();
  for (const list of thisMonth) byKind.set(list.kind, (byKind.get(list.kind) ?? 0) + spent(list));
  return (
    <div className={`${card} hidden flex-col gap-3.5 p-6 lg:flex`}>
      <span className="text-[15px] text-muted">Spent in {now.toLocaleDateString(undefined, { month: "long" })}</span>
      <span className="text-[40px] font-light tabular-nums">{usd(thisMonth.reduce((sum, list) => sum + spent(list), 0))}</span>
      {[...byKind].map(([kind, cents]) => (
        <span key={kind} className="flex justify-between text-base">
          <span className="capitalize">{kind}</span>
          <span className="font-medium tabular-nums">{usd(cents)}</span>
        </span>
      ))}
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const lists = useSeenLists();

  const side = Array.isArray(lists) && lists.length > 0 && (
    <>
      <div className="flex items-center justify-between font-medium">
        <h2 className="text-xl">Your lists</h2>
        <Link href="/history" className="text-[15px] text-muted-on-bg">
          See all
        </Link>
      </div>
      {lists.slice(0, 3).map((list) => (
        <ListCard key={list.id} list={list} />
      ))}
      <ThisMonth lists={lists} />
    </>
  );

  return (
    <main>
      <Starter onCreated={(created) => router.push(`/lists/${created.id}`)} side={side} />
    </main>
  );
}
