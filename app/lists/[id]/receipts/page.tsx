"use client";

import { usd } from "../../../api";
import { ReceiptScan } from "../../../receipt-scan";
import { card, useList } from "../list-context";

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

// Receipts: scan a new one, and every confirmed scan and PayPal order on this list.
export default function ReceiptsPage() {
  const { list, setList, me, memberName } = useList();
  const itemName = (id: string | null) => list.items.find((item) => item.id === id)?.name;
  const receipts = list.receipts.filter((r) => r.confirmedAt);

  return (
    <div className="flex flex-col gap-6">
      <ReceiptScan list={list} memberId={me} onDone={setList} />

      <section className="flex flex-col gap-3">
        <h2 className="text-2xl font-medium">Scanned receipts</h2>
        {receipts.length === 0 && <p className="text-lg opacity-70">None yet.</p>}
        {receipts.map((receipt) => (
          <article key={receipt.id} id={receipt.id} className={`${card} flex flex-col gap-2`}>
            {/* eslint-disable-next-line @next/next/no-img-element -- private photo served by the backend */}
            <img src={`/api/receipts/${receipt.id}/image`} alt="Receipt photo" loading="lazy" className="max-h-80 w-full rounded object-contain" />
            <p className="opacity-70">
              {day(receipt.createdAt)}
              {memberName(receipt.memberId) && ` · paid by ${memberName(receipt.memberId)}`}
              {receipt.totalCents !== null && ` · ${usd(receipt.totalCents)}`}
            </p>
            <ul className="flex flex-col gap-1">
              {receipt.lines.map((line, index) => (
                <li key={index} className="flex justify-between gap-2 tabular-nums">
                  <span>{itemName(line.itemId) ?? <span className="opacity-60">{line.text} (extra)</span>}</span>
                  <span>{usd(line.priceCents)}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-2xl font-medium">PayPal orders</h2>
        {list.orders.length === 0 && <p className="text-lg opacity-70">None yet.</p>}
        {list.orders.map((order) => (
          <article key={order.id} className={`${card} flex flex-col gap-1`}>
            <span className="flex justify-between tabular-nums">
              <span>
                Order {order.id}
                {order.status === "PENDING" && <span className="text-amber-700"> · pending</span>}
              </span>
              <span>{usd(order.totalCents)}</span>
            </span>
            <span className="opacity-70">
              {day(order.createdAt)}
              {memberName(order.memberId) && ` · paid by ${memberName(order.memberId)}`}
            </span>
            <span>{order.itemIds.map(itemName).filter(Boolean).join(", ")}</span>
          </article>
        ))}
      </section>
    </div>
  );
}
