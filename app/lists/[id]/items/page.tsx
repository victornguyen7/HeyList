"use client";

import Link from "next/link";
import { priceShown, proofLabel, usd } from "../../../api";
import { StoreSearch } from "../../../store-search";
import { Check } from "../../../ui";
import { row, useList } from "../list-context";

// Items: each item's status, price, who bought it, and its proof of purchase; and a real product to buy.
export default function ItemsPage() {
  const { list, setList, memberName } = useList();

  return (
    <ul className="flex flex-col gap-2.5 lg:mx-auto lg:w-full lg:max-w-[47.5rem]">
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
              <span className="text-[1.0625rem] font-medium">
                {item.name}
                {item.quantity > 1 && <span className="text-muted"> ×{item.quantity}</span>}
              </span>
              {item.note && <span className="text-[0.8125rem] text-money">{item.note}</span>}
              <span className="text-[0.8125rem] text-muted">{status}</span>
              {item.orderId && <span className="text-[0.8125rem] text-muted">Proof: PayPal order {item.orderId}</span>}
              {item.receiptId && (
                <Link href={`/lists/${list.id}/receipts#${item.receiptId}`} className="text-[0.8125rem] text-ai">
                  See the receipt
                </Link>
              )}
              <StoreSearch item={item} onChosen={(saved) => setList((current) => ({ ...current, items: current.items.map((i) => (i.id === saved.id ? saved : i)) }))} />
            </span>
            <span className={`mt-0.5 flex shrink-0 flex-col items-end text-base font-medium tabular-nums ${item.checkedAt ? "text-list" : ""}`}>
              {item.owned ? "—" : item.checkedAt ? usd(item.priceCents ?? 0) : item.estPriceCents !== null ? `${priceShown(item).approx ? "~" : ""}${usd(item.estPriceCents * item.quantity)}` : "—"}
              {!item.checkedAt && !item.owned && item.estPriceCents !== null && priceShown(item).label && <span className="text-[0.75rem] font-normal text-muted">{priceShown(item).label}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
