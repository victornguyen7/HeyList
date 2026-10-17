"use client";

import { useEffect, useState } from "react";
import { api, usd, type List } from "./api";

export type Split = {
  totalCents: number;
  unattributedCents: number;
  members: { memberId: string; paidCents: number; shareCents: number; balanceCents: number }[];
  transfers: { from: string; to: string; amountCents: number }[];
};

// Refetched when the list changes.
export function useSplit(list: List) {
  const [split, setSplit] = useState<Split | null>(null);

  useEffect(() => {
    // Only the latest list's answer counts; an earlier, slower one is dropped.
    let latest = true;
    api<Split>(`/api/lists/${list.id}/split`).then(
      (result) => latest && setSplit(result),
      () => latest && setSplit(null),
    );
    return () => {
      latest = false;
    };
  }, [list]);
  return split;
}

// What each person paid and their equal share. Who pays whom is on the Settle-up page.
export function SplitPanel({ list }: { list: List }) {
  const split = useSplit(list);
  const name = (id: string) => list.members.find((member) => member.id === id)?.name ?? "Someone";

  if (!split || list.members.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-2xl font-bold">Per person</h2>
      <ul className="flex flex-col gap-1 text-lg">
        {split.members.map((member) => (
          <li key={member.memberId} className="flex justify-between tabular-nums">
            <span>{name(member.memberId)}</span>
            <span>
              paid {usd(member.paidCents)}, share {usd(member.shareCents)}
            </span>
          </li>
        ))}
      </ul>
      {split.unattributedCents > 0 && (
        <p className="text-base opacity-70">{usd(split.unattributedCents)} was checked off without a name, so it is not split.</p>
      )}
    </section>
  );
}
