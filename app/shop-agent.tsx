"use client";

import { useState } from "react";
import { api, usd, type List, type Product } from "./api";
import { useList } from "./lists/[id]/list-context";
import { buttonAi, buttonGlass, card } from "./ui";

type Line = { itemId: string; quantity: number; product: Product; options: Product[] };
type Plan = { cart: Line[]; skipped: { itemId: string; reason: string }[]; totalCents: number; budgetLeftCents: number | null };

// "Shop this list for me" (decision 61): the person ticks items on Progress, and the agent finds a real product for
// each and proposes a cart that fits what is left of the budget. It never pays: the person removes or swaps products,
// then approves one PayPal payment. Prices are read from the stores again on the server; nothing is ordered from them.
// onPlanned tells Progress when a cart is shown, so the ticked items stay as they were searched.
export function ShopAgent({ itemIds, onPlanned, onClose }: { itemIds: string[]; onPlanned: (planned: boolean) => void; onClose: () => void }) {
  const { list, me, setList, setStatus } = useList();
  const [plan, setPlan] = useState<Plan | null>(null);
  // The product chosen for each item in the cart; an item taken out of the cart has none.
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"plan" | "pay" | null>(null);
  const itemName = (id: string) => list.items.find((item) => item.id === id)?.name ?? "An item";

  function show(next: Plan | null) {
    setPlan(next);
    onPlanned(next !== null);
  }

  async function shop() {
    setBusy("plan");
    setStatus(null);
    try {
      const found = await api<Plan>(`/api/lists/${list.id}/shop`, { method: "POST", body: JSON.stringify({ itemIds }) });
      show(found);
      setPicked(Object.fromEntries(found.cart.map((line) => [line.itemId, line.product.productId])));
    } catch (err) {
      setStatus(`Could not shop the list: ${(err as Error).message}`);
    }
    setBusy(null);
  }

  const chosen = (plan?.cart ?? [])
    .filter((line) => picked[line.itemId])
    .map((line) => ({ line, product: line.options.find((p) => p.productId === picked[line.itemId]) ?? line.product }));
  const total = chosen.reduce((sum, { line, product }) => sum + product.priceCents * line.quantity, 0);

  async function pay() {
    setBusy("pay");
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list.id}/shop/checkout`, {
        method: "POST",
        body: JSON.stringify({ memberId: me, totalCents: total, picks: chosen.map(({ line, product }) => ({ itemId: line.itemId, productId: product.productId })) }),
      });
      window.location.assign(approveUrl);
    } catch (err) {
      const { code, message } = err as Error & { code?: string };
      setStatus(message);
      // The new prices are saved on the items: show them, and pay from the list with the usual button.
      if (code === "PRICE_CHANGED" || code === "ITEM_CHECKED") {
        onClose();
        setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
      }
      setBusy(null);
    }
  }

  if (!plan) {
    return (
      <div className="flex flex-col gap-2.5">
        <p className="text-base text-muted">Tick the items HeyList should find in online stores.</p>
        <button type="button" onClick={shop} disabled={itemIds.length === 0 || busy !== null} className={buttonAi}>
          {busy ? "Finding products…" : itemIds.length === 0 ? "Tick items to shop for" : `Find products for ${itemIds.length} ${itemIds.length === 1 ? "item" : "items"}`}
        </button>
        <button type="button" onClick={onClose} disabled={busy !== null} className={buttonGlass}>
          Cancel
        </button>
      </div>
    );
  }

  const over = plan.budgetLeftCents !== null && total > plan.budgetLeftCents;
  return (
    <section className={`${card} flex flex-col gap-3`} aria-label="Proposed cart">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-lg font-medium">Your cart</h2>
        <p className="text-[13px] text-muted">
          Found by HeyList{plan.budgetLeftCents !== null && ` to fit the ${usd(plan.budgetLeftCents)} left in the budget`}. Nothing is bought until you approve it on PayPal.
        </p>
      </div>

      {plan.cart.length > 0 && (
        <ul className="flex flex-col gap-2">
          {plan.cart.map((line) => {
            const product = line.options.find((p) => p.productId === picked[line.itemId]) ?? line.product;
            const inCart = Boolean(picked[line.itemId]);
            return (
              <li key={line.itemId} className={`flex items-start gap-3 rounded-[18px] bg-surface-2 p-2.5 ${inCart ? "" : "opacity-50"}`}>
                {product.imageUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- store images from many hosts
                  <img src={product.imageUrl} alt="" loading="lazy" className="size-14 shrink-0 rounded-xl bg-bg object-contain" />
                ) : (
                  <span className="size-14 shrink-0 rounded-xl bg-bg" />
                )}
                <span className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                  <span className="font-medium">
                    {itemName(line.itemId)}
                    {line.quantity > 1 && <span className="text-muted"> ×{line.quantity}</span>}
                  </span>
                  {line.options.length > 1 && inCart ? (
                    <select
                      aria-label={`Product for ${itemName(line.itemId)}`}
                      className="h-9 min-w-0 rounded-full bg-bg px-2 text-[13px]"
                      value={product.productId}
                      onChange={(e) => setPicked({ ...picked, [line.itemId]: e.target.value })}
                    >
                      {line.options.map((option) => (
                        <option key={option.productId} value={option.productId}>
                          {usd(option.priceCents)} · {option.title.slice(0, 60)} · {option.store}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="line-clamp-2 text-muted">{product.title}</span>
                  )}
                  <span className="text-muted">
                    {usd(product.priceCents * line.quantity)} at {product.store} ·{" "}
                    <a href={product.url} target="_blank" rel="noopener noreferrer" className="text-ai">
                      View ↗
                    </a>
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => setPicked(inCart ? Object.fromEntries(Object.entries(picked).filter(([id]) => id !== line.itemId)) : { ...picked, [line.itemId]: line.product.productId })}
                  className={`${buttonGlass} h-9 shrink-0 px-3 text-[13px]`}
                >
                  {inCart ? "Remove" : "Add back"}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {plan.skipped.length > 0 && (
        <ul className="flex flex-col gap-1 text-[13px]">
          {plan.skipped.map((skip) => (
            <li key={skip.itemId}>
              <span className="font-medium">{itemName(skip.itemId)}:</span> <span className="text-muted">{skip.reason}</span>
            </li>
          ))}
        </ul>
      )}
      {over && <p className="text-[13px] text-money">This is {usd(total - plan.budgetLeftCents!)} over what&apos;s left in the budget.</p>}

      <button type="button" onClick={pay} disabled={chosen.length === 0 || busy !== null || !me} className={buttonAi}>
        {busy === "pay" ? "Opening PayPal…" : !me ? "Join the list to pay" : chosen.length === 0 ? "Nothing in the cart" : `Pay ${usd(total)} with PayPal`}
      </button>
      <div className="flex justify-center gap-5">
        <button type="button" onClick={() => show(null)} disabled={busy !== null} className="text-[13px] text-muted">
          Change the items
        </button>
        <button type="button" onClick={onClose} disabled={busy !== null} className="text-[13px] text-muted">
          Cancel
        </button>
      </div>
      <p className="text-[12px] text-muted">No order is placed with the stores yet: the sandbox payment goes to HeyList, and each product&apos;s store link is saved on its item.</p>
    </section>
  );
}
