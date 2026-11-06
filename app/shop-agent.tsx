"use client";

import { useState } from "react";
import { api, percent, taxOf, usd, type List, type Product } from "./api";
import { useList } from "./lists/[id]/list-context";
import { usePayPalRedirect } from "./paypal-redirect";
import { buttonAi, buttonGlass, card, mini, payPayPal } from "./ui";

type Line = { itemId: string; quantity: number; product: Product; options: Product[] };
// budgetLeftCents is with tax; taxRateBp is the list's sales tax rate, which the PayPal order adds (decision 80).
type Plan = { cart: Line[]; skipped: { itemId: string; reason: string }[]; totalCents: number; budgetLeftCents: number | null; taxRateBp?: number };

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
  // Why the last trip to PayPal ended without a payment, shown in the cart above the pay button.
  const [unpaid, setUnpaid] = useState<string | null>(null);
  const toPayPal = usePayPalRedirect((message) => {
    setBusy(null);
    setUnpaid(message);
  });
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
  // Before tax: what the server checks against today's store prices. PayPal charges it with the tax, per unit.
  const total = chosen.reduce((sum, { line, product }) => sum + product.priceCents * line.quantity, 0);
  const rate = plan?.taxRateBp ?? 0;
  const tax = chosen.reduce((sum, { line, product }) => sum + taxOf(product.priceCents, rate) * line.quantity, 0);
  const charged = total + tax;

  async function pay() {
    setBusy("pay");
    setUnpaid(null);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list.id}/shop/checkout`, {
        method: "POST",
        body: JSON.stringify({ memberId: me, totalCents: total, picks: chosen.map(({ line, product }) => ({ itemId: line.itemId, productId: product.productId })) }),
      });
      toPayPal(approveUrl);
    } catch (err) {
      const { code, message, data } = err as Error & { code?: string; data?: { prices?: Record<string, number> } };
      if (code === "PRICE_CHANGED" && data?.prices && plan) {
        // A store changed a price since the cart was made. Nothing was saved on the list: the cart shows today's
        // prices, and the person pays the new total or changes the cart.
        const prices = data.prices;
        const reprice = (line: Line, product: Product) => (product.productId === picked[line.itemId] && prices[line.itemId] !== undefined ? { ...product, priceCents: prices[line.itemId] } : product);
        setPlan({ ...plan, cart: plan.cart.map((line) => ({ ...line, product: reprice(line, line.product), options: line.options.map((option) => reprice(line, option)) })) });
        setUnpaid("A store changed its price since this cart was made, so nothing was paid. The cart shows today's prices: check the new total, then pay again.");
      } else {
        setStatus(message);
        if (code === "ITEM_CHECKED") {
          onClose();
          setList(await api<List>(`/api/lists/${list.id}`).catch(() => list));
        }
      }
      setBusy(null);
    }
  }

  if (!plan) {
    return (
      <div className="flex flex-col gap-2.5">
        <button type="button" onClick={shop} disabled={itemIds.length === 0 || busy !== null} className={buttonAi}>
          {busy ? "Finding products…" : itemIds.length === 0 ? "Tick items to shop for" : `Find products for ${itemIds.length} ${itemIds.length === 1 ? "item" : "items"}`}
        </button>
        <button type="button" onClick={onClose} disabled={busy !== null} className={buttonGlass}>
          Cancel
        </button>
      </div>
    );
  }

  const over = plan.budgetLeftCents !== null && charged > plan.budgetLeftCents;
  return (
    <section className={`${card} flex flex-col gap-3`} aria-label="Proposed cart">
      <h2 className="text-lg font-medium">Your cart</h2>

      {plan.cart.length > 0 && (
        <ul className="flex flex-col gap-2">
          {plan.cart.map((line) => {
            const product = line.options.find((p) => p.productId === picked[line.itemId]) ?? line.product;
            const inCart = Boolean(picked[line.itemId]);
            return (
              <li key={line.itemId} className={`flex items-start gap-3 rounded-[1.125rem] bg-surface-2 p-2.5 ${inCart ? "" : "opacity-50"}`}>
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
                      className="h-9 min-w-0 rounded-full bg-bg px-2 text-[0.8125rem]"
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
                    <span className="line-clamp-2 text-muted [overflow-wrap:anywhere]">{product.title}</span>
                  )}
                  <span className="text-muted">
                    {usd(product.priceCents * line.quantity)} at {product.store} ·{" "}
                    <a href={product.url} target="_blank" rel="noopener noreferrer" className="text-ai">
                      View ↗
                    </a>
                  </span>
                  {/* Under the text (Figma v2 cart), so the product title keeps the row's width. */}
                  <button
                    type="button"
                    onClick={() => setPicked(inCart ? Object.fromEntries(Object.entries(picked).filter(([id]) => id !== line.itemId)) : { ...picked, [line.itemId]: line.product.productId })}
                    className={`${mini} mt-1`}
                  >
                    {inCart ? "Remove" : "Add back"}
                  </button>
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {plan.skipped.length > 0 && (
        <ul className="flex flex-col gap-1 text-[0.8125rem]">
          {plan.skipped.map((skip) => (
            <li key={skip.itemId}>
              <span className="font-medium">{itemName(skip.itemId)}:</span> <span className="text-muted">{skip.reason}</span>
            </li>
          ))}
        </ul>
      )}
      {tax > 0 && (
        <p className="flex justify-between gap-3 text-[0.8125rem] text-muted tabular-nums">
          <span>
            {usd(total)} + {usd(tax)} sales tax ({percent(rate)})
          </span>
          <span className="font-medium text-text">{usd(charged)}</span>
        </p>
      )}
      {over && <p className="text-[0.8125rem] text-money">This is {usd(charged - plan.budgetLeftCents!)} over what&apos;s left in the budget.</p>}

      {unpaid && (
        <p role="alert" className="rounded-2xl bg-money/12 px-3.5 py-2.5 text-[0.8125rem] font-medium text-money">
          {unpaid} The items aren&apos;t checked off.
        </p>
      )}
      <button type="button" onClick={pay} disabled={chosen.length === 0 || busy !== null || !me} className={payPayPal}>
        {busy === "pay" ? "Opening PayPal…" : !me ? "Join the list to pay" : chosen.length === 0 ? "Nothing in the cart" : `Pay ${usd(charged)} with PayPal`}
      </button>
      <div className="flex justify-center gap-5">
        <button type="button" onClick={() => show(null)} disabled={busy !== null} className="text-[0.8125rem] text-muted">
          Change the items
        </button>
        <button type="button" onClick={onClose} disabled={busy !== null} className="text-[0.8125rem] text-muted">
          Cancel
        </button>
      </div>
    </section>
  );
}
