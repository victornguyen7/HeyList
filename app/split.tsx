"use client";

import { useEffect, useState } from "react";
import { api, proofLabel, usd, type List } from "./api";
import { Avatar, card, chip } from "./ui";

export type Split = {
  totalCents: number;
  unattributedCents: number;
  // PayPal charges for items something else had already checked off; they count toward the payer anyway.
  boughtTwice: { orderId: string; itemId: string; cents: number }[];
  // purchases are the lines paidCents adds up from; boughtTwice marks a PayPal charge kept after a failed refund.
  members: {
    memberId: string;
    paidCents: number;
    shareCents: number;
    balanceCents: number;
    purchases: { itemId: string; cents: number; boughtTwice: boolean }[];
  }[];
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

const nameOf = (list: List, id: string | null) => list.members.find((m) => m.id === id)?.name ?? "Someone";

// Figma "Who paid what": a bar per person, the tick at the equal share; dark paid more, clay paid less.
export function WhoPaid({ list, split }: { list: List; split: Split }) {
  if (list.members.length === 0) return null;
  const max = Math.max(1, ...split.members.map((m) => Math.max(m.paidCents, m.shareCents)));
  return (
    <section className={`${card} flex flex-col gap-[18px]`}>
      <h2 className="text-lg font-medium">Who paid what</h2>
      {split.members.map((m) => {
        const ahead = m.paidCents >= m.shareCents;
        return (
          <div key={m.memberId} className="flex items-center gap-3">
            <Avatar name={nameOf(list, m.memberId)} />
            <div className="flex flex-1 flex-col gap-1.5">
              <span className="flex justify-between text-base font-medium">
                <span>{nameOf(list, m.memberId)}</span>
                <span className={`tabular-nums ${ahead ? "text-list" : "text-money"}`}>{usd(m.paidCents)}</span>
              </span>
              <span className="relative h-2 rounded-[4px] bg-surface-2">
                <span className={`absolute inset-y-0 left-0 rounded-[4px] ${ahead ? "bg-list" : "bg-money"}`} style={{ width: `${(m.paidCents / max) * 100}%` }} />
                <span className="absolute -top-[3px] h-3.5 w-0.5 bg-text" style={{ left: `${(m.shareCents / max) * 100}%` }} />
              </span>
            </div>
          </div>
        );
      })}
      <p className="text-[13px] text-muted">Tick = equal share. Dark paid more, clay paid less.</p>
      {split.boughtTwice.map((twice) => (
        <p key={twice.orderId + twice.itemId} className="text-[13px] text-money">
          {list.items.find((item) => item.id === twice.itemId)?.name ?? "An item"} was bought again with PayPal ({usd(twice.cents)}) after it was already
          checked off, and the refund didn&apos;t go through. Both purchases count.
        </p>
      ))}
      {split.unattributedCents > 0 && <p className="text-[13px] text-muted">{usd(split.unattributedCents)} was checked off without a name, so it is not split.</p>}
    </section>
  );
}

// Settle up: the fewest payments that even out what everyone paid, how each balance was worked out, and invoices.
export function SettleUp({ list, split, me }: { list: List; split: Split; me: string | null }) {
  const name = (id: string | null) => nameOf(list, id) + (id === me ? " (you)" : "");
  const item = (id: string) => list.items.find((i) => i.id === id);
  if (list.members.length === 0) return <p className="text-base text-muted">Settling up is for shared lists. Add people first.</p>;
  const count = split.transfers.length;

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-col gap-1.5 text-[34px] leading-tight tracking-[-0.015em]">
        {count === 0 ? (
          <span className={split.totalCents > 0 ? "text-list" : ""}>{split.totalCents > 0 ? "Everyone's even" : "Nothing bought yet"}</span>
        ) : (
          <>
            <span>
              {count} {count === 1 ? "payment" : "payments"} and
            </span>
            <span className="text-list">everyone&apos;s even</span>
          </>
        )}
        {count > 0 && <span className="text-[15px] tracking-normal text-muted">We worked out the fewest payments for you.</span>}
      </div>

      {split.transfers.map((t, index) => (
        <div key={index} className={`${card} flex items-center justify-between gap-2 ${t.from === me ? "border-money" : ""}`}>
          <span className="flex w-20 flex-col items-center gap-1.5 text-center text-sm font-medium">
            <Avatar name={nameOf(list, t.from)} size={48} />
            {name(t.from)}
          </span>
          <span className="flex flex-col items-center gap-1">
            <span className="text-[28px] tracking-[-0.015em] text-money tabular-nums">{usd(t.amountCents)}</span>
            {/* eslint-disable-next-line @next/next/no-img-element -- 120x16 design asset */}
            <img src="/ui/arrow.svg" alt="pays" width={120} height={16} />
          </span>
          <span className="flex w-20 flex-col items-center gap-1.5 text-center text-sm font-medium">
            <Avatar name={nameOf(list, t.to)} size={48} />
            {name(t.to)}
          </span>
        </div>
      ))}
      {count > 0 && list.invoices.length === 0 && <p className="text-[13px] text-muted">Sending these as PayPal invoices is coming soon.</p>}

      {list.invoices.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">Invoices</h2>
          {list.invoices.map((invoice) => (
            <div key={invoice.id} className={`${card} flex justify-between text-base tabular-nums`}>
              <span>
                {name(invoice.debtorId)} → {name(invoice.creditorId)} {usd(invoice.amountCents)}
              </span>
              {invoice.payUrl ? (
                <a href={invoice.payUrl} className="text-ai">
                  {invoice.status.toLowerCase()}
                </a>
              ) : (
                <span>{invoice.status.toLowerCase()}</span>
              )}
            </div>
          ))}
        </section>
      )}

      {split.totalCents > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-medium">How this was worked out</h2>
          <p className="text-base">
            {usd(split.totalCents)} was spent on list items, shared equally by {split.members.length} {split.members.length === 1 ? "person" : "people"}:{" "}
            {usd(Math.floor(split.totalCents / split.members.length))} each
            {split.totalCents % split.members.length > 0 && " (the odd cents go to the first people who joined)"}.
          </p>
          {split.members.map((m) => (
            <details key={m.memberId} className={`${card} text-base`}>
              <summary className="flex cursor-pointer justify-between gap-2 tabular-nums">
                <span className="font-medium">{name(m.memberId)}</span>
                <span>
                  paid {usd(m.paidCents)} − share {usd(m.shareCents)} ={" "}
                  {m.balanceCents > 0 ? `gets back ${usd(m.balanceCents)}` : m.balanceCents < 0 ? `owes ${usd(-m.balanceCents)}` : "even"}
                </span>
              </summary>
              {m.purchases.length === 0 ? (
                <p className="mt-2 text-muted">Hasn&apos;t paid for anything on the list yet.</p>
              ) : (
                <ul className="mt-2 flex flex-col gap-1">
                  {m.purchases.map((line, index) => {
                    const bought = item(line.itemId);
                    return (
                      <li key={index} className="flex justify-between gap-2 tabular-nums">
                        <span>
                          {bought?.name ?? "A deleted item"}
                          <span className="text-muted">
                            {" · "}
                            {line.boughtTwice ? "bought again with PayPal" : bought ? proofLabel(bought, list.orders) : ""}
                          </span>
                        </span>
                        <span>{usd(line.cents)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </details>
          ))}
          <p className="text-[13px] text-muted">
            Only list items count. Receipt lines that weren&apos;t on the list are personal and not shared
            {split.unattributedCents > 0 && `, and ${usd(split.unattributedCents)} checked off without a name isn't counted`}.
          </p>
        </section>
      )}
    </div>
  );
}

export function EqualShare({ split }: { split: Split }) {
  if (split.members.length === 0 || split.totalCents === 0) return null;
  return <span className={`${chip} self-start px-3 py-[7px] text-money`}>Equal share: {usd(Math.floor(split.totalCents / split.members.length))} each</span>;
}
