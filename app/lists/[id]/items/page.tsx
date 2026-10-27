"use client";

import Link from "next/link";
import { proofLabel, usd } from "../../../api";
import { Check } from "../../../ui";
import { row, useList } from "../list-context";

// Items: each item's status, price, who bought it, and its proof of purchase.
export default function ItemsPage() {
  const { list, memberName } = useList();

  return (
    <ul className="flex flex-col gap-2.5 lg:mx-auto lg:w-full lg:max-w-[760px]">
      {list.items.map((item) => {
        const proof = proofLabel(item, list.orders);
        const by = memberName(item.boughtBy);
        const status = item.checkedAt ? `${proof}${by ? ` · ${by}` : ""}` : (proof ?? (item.claimedBy ? `${memberName(item.claimedBy)} buys it` : "Needed"));
        return (
          <li key={item.id} className={`${row} items-start`}>
            <span className="mt-0.5">
              <Check done={Boolean(item.checkedAt)} />
            </span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[17px] font-medium">
                {item.name}
                {item.quantity > 1 && <span className="text-muted"> ×{item.quantity}</span>}
              </span>
              {item.note && <span className="text-[13px] text-money">{item.note}</span>}
              <span className="text-[13px] text-muted">{status}</span>
              {item.orderId && <span className="text-[13px] text-muted">Proof: PayPal order {item.orderId}</span>}
              {item.receiptId && (
                <Link href={`/lists/${list.id}/receipts#${item.receiptId}`} className="text-[13px] text-ai">
                  See the receipt
                </Link>
              )}
            </span>
            <span className={`mt-0.5 shrink-0 text-base font-medium tabular-nums ${item.checkedAt ? "text-list" : ""}`}>
              {item.checkedAt ? usd(item.priceCents ?? 0) : item.estPriceCents !== null ? `~${usd(item.estPriceCents * item.quantity)}` : "—"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
