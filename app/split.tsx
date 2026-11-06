"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, captureMessage, proofLabel, usd, type Capture, type List } from "./api";
import { useList } from "./lists/[id]/list-context";
import { PayPalButtons } from "./paypal-buttons";
import { usePayPalRedirect } from "./paypal-redirect";
import { Avatar, button, card, chip, field, mini, payPayPal } from "./ui";

export type Split = {
  totalCents: number;
  // How totalCents adds up, as on a receipt: items + tax + other fees (tip, delivery, less discounts) - refunds.
  // Missing on a split saved in this browser before tax was counted.
  itemsCents?: number;
  taxCents?: number;
  feesCents?: number;
  refundedCents?: number;
  unattributedCents: number;
  // PayPal charges for items something else had already checked off; they count toward the payer anyway.
  boughtTwice: { orderId: string; itemId: string; cents: number }[];
  // purchases are the lines paidCents adds up from; boughtTwice marks a PayPal charge kept after a failed refund.
  members: {
    memberId: string;
    paidCents: number;
    shareCents: number;
    // Settle-up payments sent minus received (decision 60).
    settledCents: number;
    balanceCents: number;
    // feesOf is the receipt or PayPal order that charged a fee: a receipt's share of its tax, or of its tip and other
    // fees, or an order's sales tax; fee says which ("tax" or "other"). refundOf is set on money given back in PayPal.
    // itemId is null on both.
    purchases: { itemId: string | null; cents: number; boughtTwice: boolean; feesOf: string | null; refundOf: string | null; fee?: "tax" | "other" | null }[];
  }[];
  transfers: { from: string; to: string; amountCents: number }[];
};

// The split comes with the list, so it shows at once. A change made on this page (an item ticked, someone
// joined) updates the list without a new split, so then it is asked for again.
export function useSplit(list: List) {
  const [split, setSplit] = useState<Split | null>(list.split ?? null);
  const last = useRef(list);

  useEffect(() => {
    const previous = last.current;
    if (list === previous) return;
    last.current = list;
    if (list.split && list.split !== previous.split) {
      setSplit(list.split);
      return;
    }
    // Only the latest list's answer counts; an earlier, slower one is dropped.
    let latest = true;
    api<Split>(`/api/lists/${list.id}/split`).then(
      (result) => latest && setSplit(result),
      () => {},
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
    <section className={`${card} flex flex-col gap-[1.125rem]`}>
      <h2 className="text-lg font-medium">Who paid what</h2>
      {split.members.map((m) => {
        const ahead = m.paidCents >= m.shareCents;
        return (
          <div key={m.memberId} className="flex items-center gap-3">
            <Avatar name={nameOf(list, m.memberId)} />
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              {/* A long name ends in … and the amount stays whole (Figma "Overflow fixes", C). */}
              <span className="flex justify-between gap-2 text-base font-medium">
                <span className="min-w-0 truncate">{nameOf(list, m.memberId)}</span>
                <span className={`shrink-0 tabular-nums ${ahead ? "text-list" : "text-money"}`}>{usd(m.paidCents)}</span>
              </span>
              <span className="relative h-2 rounded-[0.25rem] bg-surface-2">
                <span className={`absolute inset-y-0 left-0 rounded-[0.25rem] ${ahead ? "bg-list" : "bg-money"}`} style={{ width: `${(m.paidCents / max) * 100}%` }} />
                <span className="absolute -top-[0.1875rem] h-3.5 w-0.5 bg-text" style={{ left: `${(m.shareCents / max) * 100}%` }} />
              </span>
            </div>
          </div>
        );
      })}
      {split.boughtTwice.map((twice) => (
        <p key={twice.orderId + twice.itemId} className="text-[0.8125rem] text-money">
          {list.items.find((item) => item.id === twice.itemId)?.name ?? "An item"} was bought again with PayPal ({usd(twice.cents)}) after it was already
          checked off, and the refund didn&apos;t go through. Both purchases count.
        </p>
      ))}
      {split.unattributedCents > 0 && <p className="text-[0.8125rem] text-muted">{usd(split.unattributedCents)} was checked off without a name, so it is not split.</p>}
    </section>
  );
}

type Transfer = Split["transfers"][number];

// Pay the person you owe with PayPal (decision 60): the order's payee is their PayPal account, so the money goes to
// them, not to HeyList. The first payment to someone asks for their email; the amount is checked on the server.
function PayBack({ transfer }: { transfer: Transfer }) {
  const { list, setList, setStatus } = useList();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const to = nameOf(list, transfer.to);
  const needsEmail = !list.members.find((m) => m.id === transfer.to)?.hasEmail;
  const toPayPal = usePayPalRedirect((message) => {
    setBusy(false);
    setStatus(message);
  });

  // The order for this payment. Redirect checkout uses its approveUrl; the PayPal and Venmo buttons (decision 67) only
  // its ID. Throws after saying why when it can't be made.
  async function order(method: "paypal" | "venmo") {
    setStatus(null);
    if (needsEmail && !email.includes("@")) {
      setStatus(`Type ${to}'s PayPal email first.`);
      throw new Error("email needed");
    }
    try {
      return await api<{ orderId: string; approveUrl: string }>(`/api/lists/${list.id}/settlements`, {
        method: "POST",
        body: JSON.stringify({ fromId: transfer.from, toId: transfer.to, amountCents: transfer.amountCents, method, ...(needsEmail ? { email } : {}) }),
      });
    } catch (err) {
      const { code, message } = err as Error & { code?: string };
      setStatus(message);
      // Someone paid or bought something meanwhile: show the new amounts before they pay again.
      if (code === "SPLIT_CHANGED" || code === "PAYMENT_PENDING") setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
      throw err;
    }
  }

  async function pay(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      toPayPal((await order("paypal")).approveUrl);
    } catch {
      setBusy(false);
    }
  }

  async function captured(orderId: string) {
    try {
      setStatus(captureMessage(await api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })));
    } catch (err) {
      setStatus(`Payment could not be confirmed: ${(err as Error).message}`);
    }
    setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
  }

  return (
    <form onSubmit={pay} className="flex flex-col gap-2">
      {needsEmail && (
        <input
          type="email"
          className={field}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Their PayPal email"
          aria-label={`${to}'s PayPal email`}
          maxLength={254}
          required
        />
      )}
      <PayPalButtons createOrder={async (method) => (await order(method)).orderId} onApproved={captured} onError={setStatus}>
        <button type="submit" className={payPayPal} disabled={busy}>
          Pay {to} with PayPal
        </button>
      </PayPalButtons>
    </form>
  );
}

// Remind someone to pay (decision 65): the AI drafts a friendly message with a link that opens this page ready to pay
// with PayPal. The person sends it from their own phone (share sheet) or copies it; HeyList never sends anything.
function Remind({ transfer }: { transfer: Transfer }) {
  const { list, setStatus } = useList();
  const [busy, setBusy] = useState(false);
  const who = nameOf(list, transfer.from);

  async function remind() {
    setBusy(true);
    setStatus(null);
    try {
      const { message } = await api<{ message: string }>(`/api/lists/${list.id}/reminders`, {
        method: "POST",
        body: JSON.stringify({ fromId: transfer.from, toId: transfer.to }),
      });
      try {
        if (navigator.share) await navigator.share({ text: message });
        else {
          await navigator.clipboard.writeText(message);
          setStatus(`Reminder copied. Paste it to ${who} in your chat:\n${message}`);
        }
      } catch {
        // Closing the share sheet is not an error.
      }
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-medium text-money">Not paid yet</span>
      <button type="button" onClick={remind} disabled={busy} className={mini}>
        {busy ? "Writing it…" : `Remind ${who}`}
      </button>
    </div>
  );
}

// Opened from a reminder (?pay=<member>) on a phone that hasn't joined: one tap to be that person and pay.
function ClaimPayer({ memberId }: { memberId: string }) {
  const { list, joinAs } = useList();
  const name = nameOf(list, memberId);
  return (
    <button type="button" onClick={() => joinAs(name)} className={button}>
      I&apos;m {name}, let me pay
    </button>
  );
}

// Settle-up payments made with PayPal. A pending one counts once PayPal has captured it; PayPal doesn't call back,
// so anyone can ask again.
function Payments({ list, name }: { list: List; name: (id: string | null) => string }) {
  const { setList, setStatus } = useList();
  const [busy, setBusy] = useState(false);
  const payments = list.settlements ?? [];
  if (payments.length === 0) return null;

  async function checkAgain(orderId: string) {
    setBusy(true);
    try {
      const { status } = await api<{ status: string }>(`/api/orders/${orderId}/refresh`, { method: "POST" });
      setStatus(status === "COMPLETED" ? "Paid. Settle up is updated." : status === "PENDING" ? "Still pending at PayPal." : "That payment did not go through.");
      setList(await api<List>(`/api/lists/${list.id}`));
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-medium">Paid back with PayPal</h2>
      {payments.map((p) => (
        <div key={p.id} className={`${card} flex items-center justify-between gap-2 text-base tabular-nums`}>
          <span>
            {name(p.debtorId)} paid {name(p.creditorId)} {usd(p.amountCents)}
            <span className="text-muted"> · {p.status === "COMPLETED" ? "with PayPal" : "pending at PayPal"}</span>
          </span>
          {p.status === "PENDING" && (
            <button type="button" className={mini} disabled={busy} onClick={() => checkAgain(p.id)}>
              Check again
            </button>
          )}
        </div>
      ))}
    </section>
  );
}

// Settle up: the fewest payments that even out what everyone paid, paying them with PayPal, and how each balance
// was worked out.
export function SettleUp({ list, split, me }: { list: List; split: Split; me: string | null }) {
  // Someone named "You" (the sample trip's member) is shown as just "You", not "You (you)".
  const name = (id: string | null) => {
    const shown = nameOf(list, id);
    return id === me && shown.trim().toLowerCase() !== "you" ? `${shown} (you)` : shown;
  };
  const item = (id: string) => list.items.find((i) => i.id === id);
  // The payment a reminder link points to.
  const payFor = useSearchParams().get("pay");
  if (list.members.length === 0) return <p className="text-base text-muted-on-bg">Settling up is for shared lists. Add people first.</p>;
  const count = split.transfers.length;

  return (
    <div className="flex flex-col gap-[1.125rem]">
      <div className="flex flex-col gap-1.5 text-[2.125rem] leading-tight tracking-[-0.015em]">
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
      </div>

      {split.transfers.map((t, index) => (
        <div key={index} className={`${card} flex flex-col gap-3.5 ${t.from === me ? "border-money" : ""} ${t.from === payFor ? "ring-2 ring-ai" : ""}`}>
          {/* The amount on its own line, then the two people in equal columns with the arrow between, names up to two
              lines: fixed 80 px columns let a long name run out of the card (Figma "Overflow fixes", C). */}
          <div className="flex flex-col items-center gap-2">
            <span className="text-[1.75rem] tracking-[-0.015em] whitespace-nowrap text-money tabular-nums">{usd(t.amountCents)}</span>
            <div className="grid w-full grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-2">
              <span className="flex min-w-0 flex-col items-center gap-1.5 text-center text-sm font-medium">
                <Avatar name={nameOf(list, t.from)} size={48} />
                <span className="line-clamp-2 w-full [overflow-wrap:anywhere]">{name(t.from)}</span>
              </span>
              {/* eslint-disable-next-line @next/next/no-img-element -- 120x16 design asset */}
              <img src="/ui/arrow.svg" alt="pays" width={120} height={16} className="mt-4 w-16 sm:w-[7.5rem]" />
              <span className="flex min-w-0 flex-col items-center gap-1.5 text-center text-sm font-medium">
                <Avatar name={nameOf(list, t.to)} size={48} />
                <span className="line-clamp-2 w-full [overflow-wrap:anywhere]">{name(t.to)}</span>
              </span>
            </div>
          </div>
          {t.from === me && <PayBack transfer={t} />}
          {t.from === payFor && !me && <ClaimPayer memberId={t.from} />}
          {t.from !== me && <Remind transfer={t} />}
        </div>
      ))}

      <Payments list={list} name={name} />

      {split.totalCents > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-medium">How this was worked out</h2>
          <p className="text-base">
            {usd(split.totalCents)} was spent on list items{split.taxCents || split.feesCents ? ", with tax and fees" : ""}, shared equally by {split.members.length} {split.members.length === 1 ? "person" : "people"}:{" "}
            {usd(Math.floor(split.totalCents / split.members.length))} each.
          </p>
          {split.members.map((m) => (
            <details key={m.memberId} className={`${card} group text-base`}>
              {/* Name, then the sum under it, then the result as a pill: the sum used to be squeezed into a narrow
                  column beside a long name (Figma "Overflow fixes", C). */}
              <summary className="flex cursor-pointer flex-col gap-1.5 tabular-nums [&::-webkit-details-marker]:hidden">
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-medium">{name(m.memberId)}</span>
                  <span aria-hidden className="shrink-0 text-muted group-open:rotate-90">
                    ›
                  </span>
                </span>
                <span className="text-[0.9375rem]">
                  {usd(m.paidCents)} <span className="text-muted">paid</span> − {usd(m.shareCents)} <span className="text-muted">share</span>
                  {m.settledCents > 0 ? (
                    <>
                      {" "}+ {usd(m.settledCents)} <span className="text-muted">sent</span>
                    </>
                  ) : m.settledCents < 0 ? (
                    <>
                      {" "}− {usd(-m.settledCents)} <span className="text-muted">received</span>
                    </>
                  ) : null}
                </span>
                <span
                  className={`self-start rounded-full px-2.5 py-1 text-[0.8125rem] font-medium whitespace-nowrap ${m.balanceCents > 0 ? "bg-ai/12 text-ai" : m.balanceCents < 0 ? "bg-money/12 text-money" : "bg-list/10 text-list"}`}
                >
                  {m.balanceCents > 0 ? `Gets back ${usd(m.balanceCents)}` : m.balanceCents < 0 ? `Owes ${usd(-m.balanceCents)}` : "Even"}
                </span>
              </summary>
              {m.purchases.length === 0 ? (
                <p className="mt-2 text-muted">Hasn&apos;t paid for anything on the list yet.</p>
              ) : (
                <ul className="mt-2 flex flex-col gap-1">
                  {m.purchases.map((line, index) => {
                    const bought = line.itemId ? item(line.itemId) : undefined;
                    if (line.refundOf) {
                      return (
                        <li key={index} className="flex justify-between gap-2 tabular-nums">
                          <span className="min-w-0">
                            Refunded<span className="text-muted"> · given back in PayPal</span>
                          </span>
                          <span className="shrink-0">{usd(line.cents)}</span>
                        </li>
                      );
                    }
                    if (line.feesOf) {
                      const fromOrder = list.orders.some((order) => order.id === line.feesOf);
                      return (
                        <li key={index} className="flex justify-between gap-2 tabular-nums">
                          <span className="min-w-0">
                            {line.fee === "tax" ? "Sales tax" : line.fee === "other" ? "Tip and fees" : "Tax, tip and fees"}
                            <span className="text-muted">{fromOrder ? " · on a PayPal payment" : " · list items' share, on a receipt"}</span>
                          </span>
                          <span className="shrink-0">{usd(line.cents)}</span>
                        </li>
                      );
                    }
                    return (
                      <li key={index} className="flex justify-between gap-2 tabular-nums">
                        <span className="min-w-0">
                          {bought?.name ?? "A deleted item"}
                          <span className="text-muted">
                            {" · "}
                            {line.boughtTwice ? "bought again with PayPal" : bought ? proofLabel(bought, list.orders) : ""}
                          </span>
                        </span>
                        <span className="shrink-0">{usd(line.cents)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </details>
          ))}
        </section>
      )}
    </div>
  );
}

export function EqualShare({ split }: { split: Split }) {
  if (split.members.length === 0 || split.totalCents === 0) return null;
  return <span className={`${chip} self-start px-3 py-[0.4375rem] text-money`}>Equal share: {usd(Math.floor(split.totalCents / split.members.length))} each</span>;
}
