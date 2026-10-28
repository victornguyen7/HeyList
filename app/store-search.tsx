"use client";

import { useState } from "react";
import { api, usd, type Item, type Product } from "./api";
import { buttonGlass } from "./ui";

// Find a real product for an item in stores (Channel3, decision 50). Choosing one makes its price the one
// "Pay with PayPal" charges; the store link is there to see the product. Nothing is ordered from the store.
export function StoreSearch({ item, onChosen }: { item: Item; onChosen: (item: Item) => void }) {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run<T>(call: () => Promise<T>, done: (result: T) => void) {
    setBusy(true);
    setStatus(null);
    try {
      done(await call());
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  const find = () =>
    run(
      () => api<{ products: Product[] }>(`/api/items/${item.id}/products`),
      (found) => {
        setProducts(found.products);
        if (!found.products.length) setStatus("No store has this right now.");
      },
    );
  const choose = (product: Product) =>
    run(
      () => api<Item>(`/api/items/${item.id}/product`, { method: "POST", body: JSON.stringify({ productId: product.productId }) }),
      (saved) => {
        setProducts(null);
        onChosen(saved);
      },
    );

  return (
    <div className="flex flex-col gap-2">
      {item.product && (
        <span className="text-[13px] text-muted">
          {item.product.title} · {usd(item.product.priceCents)} at {item.product.store} ·{" "}
          <a href={item.product.url} target="_blank" rel="noopener noreferrer" className="text-ai">
            View at {item.product.store} ↗
          </a>
        </span>
      )}
      {!item.checkedAt && !products && (
        <button type="button" onClick={find} disabled={busy} className={`${buttonGlass} h-10 self-start px-4 text-sm`}>
          {busy ? "Searching…" : item.product ? "Choose another" : "Find in stores"}
        </button>
      )}
      {status && <span role="status" className="text-[13px] text-money">{status}</span>}
      {products && products.length > 0 && (
        <ul className="flex flex-col gap-2">
          {products.map((product) => (
            <li key={product.productId} className="flex items-center gap-3 rounded-[18px] bg-surface-2 p-2.5">
              {product.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element -- store images from many hosts
                <img src={product.imageUrl} alt="" loading="lazy" className="size-14 shrink-0 rounded-xl bg-bg object-contain" />
              ) : (
                <span className="size-14 shrink-0 rounded-xl bg-bg" />
              )}
              <span className="flex min-w-0 flex-1 flex-col text-sm">
                <span className="line-clamp-2 font-medium">{product.title}</span>
                <span className="text-muted">
                  {usd(product.priceCents)} at {product.store}
                </span>
              </span>
              <button type="button" onClick={() => choose(product)} disabled={busy} className={`${buttonGlass} h-10 shrink-0 px-4 text-sm`}>
                Choose
              </button>
            </li>
          ))}
        </ul>
      )}
      {products && (
        <button type="button" onClick={() => setProducts(null)} className="self-start text-[13px] text-muted">
          Cancel
        </button>
      )}
    </div>
  );
}
