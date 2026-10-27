"use client";

import Link from "next/link";
import { proofLabel, usd } from "../../../api";
import { card, useList } from "../list-context";

// Items: each item's status, price, who bought it, and its proof of purchase.
export default function ItemsPage() {
  const { list, memberName } = useList();

  return (
    <ul className="flex flex-col gap-2">
      {list.items.map((item) => {
        const proof = proofLabel(item, list.orders);
        const by = memberName(item.boughtBy);
        const status = item.checkedAt ? `${proof}${by ? ` · ${by}` : ""}` : (proof ?? (item.claimedBy ? `${memberName(item.claimedBy)} buys it` : "Needed"));
        return (
          <li key={item.id} className={`${card} flex flex-col gap-1`}>
            <span className="flex justify-between gap-2 text-xl">
              <span>
                {item.name}
                {item.quantity > 1 && <span className="opacity-60"> × {item.quantity}</span>}
              </span>
              <span className="tabular-nums">
                {item.checkedAt ? usd(item.priceCents ?? 0) : item.estPriceCents !== null ? `~${usd(item.estPriceCents * item.quantity)}` : "—"}
              </span>
            </span>
            {item.note && <span className="text-amber-700">{item.note}</span>}
            <span className="self-start rounded-full bg-chip px-3 py-1">{status}</span>
            {item.orderId && <span className="opacity-70">Proof: PayPal order {item.orderId}</span>}
            {item.receiptId && (
              <Link href={`/lists/${list.id}/receipts#${item.receiptId}`} className="underline underline-offset-4">
                See the receipt
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}
