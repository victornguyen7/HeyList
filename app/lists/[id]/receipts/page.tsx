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
    <div className="flex flex-col gap-6 lg:mx-auto lg:w-full lg:max-w-[760px]">
      <ReceiptScan list={list} memberId={me} onDone={setList} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium lg:text-xl">Scanned receipts</h2>
        {receipts.length === 0 && <p className="text-base text-muted">None yet.</p>}
        {receipts.map((receipt) => (
          <article key={receipt.id} id={receipt.id} className={`${card} flex flex-col gap-2 text-base`}>
            {/* eslint-disable-next-line @next/next/no-img-element -- private photo served by the backend */}
            <img src={`/api/receipts/${receipt.id}/image`} alt="Receipt photo" loading="lazy" className="max-h-80 w-full rounded-[18px] object-contain" />
            <p className="text-muted">
              {day(receipt.createdAt)}
              {memberName(receipt.memberId) && ` · paid by ${memberName(receipt.memberId)}`}
              {receipt.totalCents !== null && ` · ${usd(receipt.totalCents)}`}
            </p>
            <ul className="flex flex-col gap-1">
              {receipt.lines.map((line, index) => (
                <li key={index} className="flex justify-between gap-2 tabular-nums">
                  <span>{itemName(line.itemId) ?? <span className="text-muted">{line.text} (extra)</span>}</span>
                  <span>
                    {line.priceCents !== null ? usd(line.priceCents) : "—"}
                    {line.typed && <span className="text-muted"> (typed)</span>}
                  </span>
                </li>
              ))}
              {(receipt.fees ?? []).map((fee, index) => (
                <li key={`fee${index}`} className="flex justify-between gap-2 text-muted tabular-nums">
                  <span>{fee.name}</span>
                  <span>
                    {fee.amountCents !== null ? usd(fee.amountCents) : "—"}
                    {fee.typed && " (typed)"}
                  </span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium lg:text-xl">PayPal orders</h2>
        {list.orders.length === 0 && <p className="text-base text-muted">None yet.</p>}
        {list.orders.map((order) => (
          <article key={order.id} className={`${card} flex flex-col gap-1 text-base`}>
            <span className="flex justify-between tabular-nums">
              <span>
                Order {order.id}
                {order.status === "PENDING" && <span className="text-money"> · pending</span>}
              </span>
              <span>{usd(order.totalCents)}</span>
            </span>
            <span className="text-muted">
              {day(order.createdAt)}
              {memberName(order.memberId) && ` · paid by ${memberName(order.memberId)}`}
            </span>
            <span>{order.itemIds.map(itemName).filter(Boolean).join(", ")}</span>
            {Object.entries(order.refunds).map(([itemId, refund]) => (
              <span key={itemId} className="text-muted">
                Refunded {usd(refund.cents)} for {itemName(itemId) ?? "an item"}: it had already been bought
                {refund.status !== "COMPLETED" && ` (${refund.status.toLowerCase()})`}
              </span>
            ))}
          </article>
        ))}
      </section>
    </div>
  );
}
