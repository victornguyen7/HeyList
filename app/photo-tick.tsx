"use client";

import { useState } from "react";
import { api, usd, type Item } from "./api";
import { shrink, typedCents } from "./photo";
import { buttonGlass, card } from "./ui";

// Take a photo of one thing you got: the AI proposes which open item it is, you confirm it and say what you paid, and
// it is ticked like any hand tick, with that price counted in the budget. A photo shows the thing, not a purchase, so
// it is not called proof and isn't kept (decision 70). A model only needs a small picture to tell what's in it.
export function PhotoTick({ listId, items, onTick, onError }: { listId: string; items: Item[]; onTick: (item: Item, priceCents: number | null) => Promise<void>; onError: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  // Set once a photo has been read. itemId "" means the person still has to pick.
  const [found, setFound] = useState<{ itemId: string; seen: string; proposed: boolean } | null>(null);
  const [priceText, setPriceText] = useState("");
  const chosen = items.find((item) => item.id === found?.itemId);
  const price = typedCents(priceText);

  async function read(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setFound(null);
    setPriceText("");
    try {
      const reply = await api<{ itemId: string | null; seen: string }>(`/api/lists/${listId}/item-photo`, { method: "POST", body: await shrink(file, 1024) });
      setFound({ itemId: reply.itemId ?? "", seen: reply.seen, proposed: Boolean(reply.itemId) });
    } catch (err) {
      onError((err as Error).message);
    }
    setBusy(false);
  }

  async function confirm(e: React.FormEvent) {
    e.preventDefault();
    if (!chosen || Number.isNaN(price)) return;
    setBusy(true);
    await onTick(chosen, price);
    setFound(null);
    setBusy(false);
  }

  if (!found) {
    return (
      <label className={`${buttonGlass} cursor-pointer gap-2 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-text ${busy ? "pointer-events-none opacity-40" : ""}`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- 24px design asset */}
        <img src="/ui/camera.svg" alt="" width={24} height={24} />
        <span role="status">{busy ? "Looking at your photo…" : "Check off with a photo"}</span>
        <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only" onChange={read} disabled={busy} />
      </label>
    );
  }

  return (
    <form onSubmit={confirm} className={`${card} flex flex-col gap-3 text-base`}>
      <p role="status" className="font-medium">
        {found.proposed ? "This looks like:" : found.seen ? `That looks like ${found.seen}, which isn't on the list. Is it one of these?` : "Which item is this?"}
      </p>
      <select
        aria-label="Which item this is"
        className="h-11 rounded-[20px] bg-surface-2 px-3"
        value={found.itemId}
        onChange={(e) => setFound({ ...found, itemId: e.target.value })}
      >
        <option value="" disabled>
          Choose an item
        </option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
            {item.quantity > 1 ? ` ×${item.quantity}` : ""}
          </option>
        ))}
      </select>
      {chosen && (
        <label className="flex flex-col gap-1.5">
          <span>
            What did you pay{chosen.quantity > 1 ? ` for all ${chosen.quantity}` : ""}?
            {chosen.estPriceCents !== null && <span className="text-[13px] text-muted"> Estimated {usd(chosen.estPriceCents * chosen.quantity)}</span>}
          </span>
          <input
            autoFocus
            inputMode="decimal"
            placeholder="Don't know"
            className={`h-11 rounded-[20px] bg-surface-2 px-3 tabular-nums ${Number.isNaN(price) ? "outline outline-money" : ""}`}
            value={priceText}
            onChange={(e) => setPriceText(e.target.value)}
          />
        </label>
      )}
      {Number.isNaN(price) && <p className="text-[13px] text-money">Type the price like 4.50.</p>}
      <span className="flex items-center gap-3">
        <button type="submit" disabled={busy || !chosen || Number.isNaN(price)} className="h-10 rounded-full bg-list px-5 text-[15px] font-medium text-on-accent disabled:opacity-40">
          Check it off
        </button>
        <button type="button" disabled={busy} onClick={() => setFound(null)} className="text-[15px] font-medium text-muted">
          Cancel
        </button>
      </span>
    </form>
  );
}
