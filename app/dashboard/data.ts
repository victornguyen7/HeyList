import { proofLabel, type List } from "../api";

// The Dashboard's tables (decision 62), built from the lists this browser has opened. Money lines come from each
// list's split (money.split() on the server), so the Dashboard adds up to exactly what Money and Settle up show.
// Amounts are dollars here, since Studio formats them; everywhere else in the app they are cents.

export type LedgerRow = {
  id: string;
  date: string | null;
  month: string;
  list: string;
  listType: string;
  item: string;
  who: string;
  // Purchase, Fees, Bought twice (a PayPal charge for an item something else covered first), Refund.
  kind: string;
  // PayPal, Receipt, Hand tick: what the money rests on.
  proof: string;
  amount: number;
  // The part of amount backed by PayPal or a receipt; a hand tick is someone's word.
  proven: number;
  refunded: number;
};
export type BalanceRow = { id: string; list: string; person: string; paid: number; share: number; settled: number; balance: number };
// Who pays whom: open transfers from the split, and settle-up payments made with PayPal (7B).
export type TransferRow = { id: string; listId: string; list: string; from: string; to: string; amount: number; status: "Owed" | "Paid with PayPal" | "Pending at PayPal" };
export type ItemRow = { id: string; list: string; item: string; status: string; estimate: number | null; paid: number | null; store: string | null };

const dollars = (cents: number) => Math.round(cents) / 100;
const day = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : null);
const month = (iso: string | null | undefined) => (iso ? iso.slice(0, 7) : "Unknown");

export function dashboardData(lists: List[]) {
  const ledger: LedgerRow[] = [];
  const balances: BalanceRow[] = [];
  const transfers: TransferRow[] = [];
  const items: ItemRow[] = [];

  for (const list of lists) {
    const name = (id: string | null) => list.members.find((m) => m.id === id)?.name ?? "Someone";
    const base = { list: list.title, listType: list.kind };

    for (const member of list.split?.members ?? []) {
      member.purchases.forEach((line, index) => {
        const item = line.itemId ? list.items.find((i) => i.id === line.itemId) : undefined;
        const receipt = line.feesOf ? list.receipts.find((r) => r.id === line.feesOf) : undefined;
        const proof = line.boughtTwice || item?.orderId ? "PayPal" : line.feesOf || item?.receiptId ? "Receipt" : "Hand tick";
        const when = receipt?.confirmedAt ?? item?.checkedAt ?? list.createdAt;
        ledger.push({
          ...base,
          id: `${list.id}:${member.memberId}:${index}`,
          date: day(when),
          month: month(when),
          item: line.feesOf ? "Tax, tip and fees" : (item?.name ?? "A deleted item"),
          who: name(member.memberId),
          kind: line.feesOf ? "Fees" : line.boughtTwice ? "Bought twice" : "Purchase",
          proof,
          amount: dollars(line.cents),
          proven: proof === "Hand tick" ? 0 : dollars(line.cents),
          refunded: 0,
        });
      });
      balances.push({
        id: `${list.id}:${member.memberId}`,
        list: list.title,
        person: name(member.memberId),
        paid: dollars(member.paidCents),
        share: dollars(member.shareCents),
        // Missing on a split saved in this browser before settle-up payments existed.
        settled: dollars(member.settledCents ?? 0),
        balance: dollars(member.balanceCents),
      });
    }

    // A refunded charge isn't in the split (it was given back); it shows here as money returned.
    for (const order of list.orders) {
      for (const [itemId, refund] of Object.entries(order.refunds)) {
        if (["FAILED", "CANCELLED"].includes(refund.status)) continue;
        ledger.push({
          ...base,
          id: `${order.id}:${itemId}`,
          date: day(order.createdAt),
          month: month(order.createdAt),
          item: list.items.find((i) => i.id === itemId)?.name ?? "A deleted item",
          who: name(order.memberId),
          kind: "Refund",
          proof: "PayPal",
          amount: 0,
          proven: 0,
          refunded: dollars(refund.cents),
        });
      }
    }

    list.split?.transfers.forEach((t, index) =>
      transfers.push({ id: `${list.id}:t${index}`, listId: list.id, list: list.title, from: name(t.from), to: name(t.to), amount: dollars(t.amountCents), status: "Owed" }),
    );
    for (const s of list.settlements ?? []) {
      transfers.push({
        id: s.id,
        listId: list.id,
        list: list.title,
        from: name(s.debtorId),
        to: name(s.creditorId),
        amount: dollars(s.amountCents),
        status: s.status === "COMPLETED" ? "Paid with PayPal" : "Pending at PayPal",
      });
    }

    for (const item of list.items) {
      items.push({
        id: item.id,
        list: list.title,
        item: item.name,
        status: proofLabel(item, list.orders) ?? "Needed",
        estimate: item.estPriceCents === null ? null : dollars(item.estPriceCents * item.quantity),
        paid: item.priceCents === null ? null : dollars(item.priceCents),
        store: item.product?.store ?? null,
      });
    }
  }
  return { ledger, balances, transfers, items };
}
