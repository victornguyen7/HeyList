"use client";

import { useEffect, useState } from "react";
import { api, usd, type List } from "./api";

type Split = {
  totalCents: number;
  unattributedCents: number;
  members: { memberId: string; paidCents: number; shareCents: number; balanceCents: number }[];
  transfers: { from: string; to: string; amountCents: number }[];
};

// Who paid what, each person's equal share, and who pays whom to even it out. Refetched when the list changes.
export function SplitPanel({ list }: { list: List }) {
  const [split, setSplit] = useState<Split | null>(null);
  const name = (id: string) => list.members.find((member) => member.id === id)?.name ?? "Someone";

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

  if (!split || list.members.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-2xl font-semibold">Money</h2>
      <p className="text-lg tabular-nums">
        Spent {usd(split.totalCents)}
        {list.budgetCents !== null && ` of ${usd(list.budgetCents)} budget`}
      </p>
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
      {split.transfers.length > 0 ? (
        <ul className="flex flex-col gap-1 text-lg font-medium">
          {split.transfers.map((t, index) => (
            <li key={index}>
              {name(t.from)} pays {name(t.to)} {usd(t.amountCents)}
            </li>
          ))}
        </ul>
      ) : (
        split.totalCents > 0 && <p className="text-lg">Everyone is even.</p>
      )}
      {split.unattributedCents > 0 && (
        <p className="text-base opacity-70">{usd(split.unattributedCents)} was checked off without a name, so it is not split.</p>
      )}
    </section>
  );
}
