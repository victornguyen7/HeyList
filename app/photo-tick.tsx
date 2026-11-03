"use client";

import { useEffect, useState } from "react";
import { api, usd, type Item, type Receipt } from "./api";
import { shrink, typedCents } from "./photo";
import { buttonGlass, card } from "./ui";

// Take a photo of one thing you got: the AI proposes which open item it is, you confirm it and say what you paid, and
// it is ticked like any hand tick, with that price counted in the budget. A photo shows the thing, not a purchase, so
// it is not called proof and isn't kept (decision 70). A model only needs a small picture to tell what's in it.
// A photo of a receipt is told apart in that same call and scanned as a receipt instead, at full size so its
// small print can be read; onReceipt gets the scan to review.
// While a photo is read, a box shows the photo and each step as it really happens, with the seconds the current one
// has taken: a receipt takes a few seconds, and a stuck step or a failure should be plain to see.
type Step = { label: string; state: "active" | "done" | "failed"; detail?: string };

export function PhotoTick({ listId, memberId, items, onTick, onReceipt }: { listId: string; memberId: string; items: Item[]; onTick: (item: Item, priceCents: number | null) => Promise<void>; onReceipt: (receipt: Receipt) => void }) {
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [stepStarted, setStepStarted] = useState(0);
  const [now, setNow] = useState(0);
  const working = steps.some((step) => step.state === "active");
  const failed = steps.some((step) => step.state === "failed");
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [working]);
  // The photo's preview is a blob URL: let it go when it's replaced or the box goes away.
  useEffect(() => (preview ? () => URL.revokeObjectURL(preview) : undefined), [preview]);
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
    setPreview(URL.createObjectURL(file));
    // Each step: finish the one running (with what it found), then start the next.
    let done: Step[] = [];
    const begin = (label: string) => {
      setSteps([...done, { label, state: "active" }]);
      setStepStarted(Date.now());
      setNow(Date.now());
    };
    const finish = (label: string, detail?: string) => {
      done = [...done, { label, state: "done", detail }];
      setSteps(done);
    };
    let current = "Getting your photo ready";
    try {
      begin(current);
      const small = await shrink(file, 1024);
      finish(current);
      current = "Working out what's in it";
      begin(current);
      const reply = await api<{ itemId: string | null; seen: string; receipt?: boolean }>(`/api/lists/${listId}/item-photo`, { method: "POST", body: small });
      if (reply.receipt) {
        finish(current, "It's a receipt");
        current = "Reading the receipt and matching it to your list";
        begin(current);
        const receipt = await api<Receipt>(`/api/lists/${listId}/receipts?memberId=${memberId}`, { method: "POST", body: await shrink(file) });
        finish(current, `${receipt.lines.length} ${receipt.lines.length === 1 ? "line" : "lines"} read`);
        setSteps([]);
        onReceipt(receipt);
      } else {
        const item = items.find((i) => i.id === reply.itemId);
        finish(current, item ? `Looks like ${item.name}` : reply.seen ? `Looks like ${reply.seen}` : "Not sure");
        setSteps([]);
        setFound({ itemId: reply.itemId ?? "", seen: reply.seen, proposed: Boolean(reply.itemId) });
      }
    } catch (err) {
      setSteps([...done, { label: current, state: "failed", detail: (err as Error).message }]);
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

  if (steps.length > 0) {
    const seconds = Math.max(0, Math.floor((now - stepStarted) / 1000));
    return (
      <div className={`${card} flex gap-4 text-base`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- the person's own photo, from a blob URL */}
        {preview && <img src={preview} alt="Your photo" className="size-20 shrink-0 rounded-xl bg-bg object-cover" />}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <ol role="status" aria-live="polite" className="flex flex-col gap-2">
            {steps.map((step) => (
              <li key={step.label} className="flex items-start gap-2.5">
                <span aria-hidden className="mt-0.5 flex size-5 shrink-0 items-center justify-center">
                  {step.state === "active" ? (
                    <span className="size-4 rounded-full border-2 border-muted border-t-transparent motion-safe:animate-spin" />
                  ) : step.state === "done" ? (
                    <span className="flex size-5 items-center justify-center rounded-full bg-list text-[11px] text-on-accent">✓</span>
                  ) : (
                    <span className="flex size-5 items-center justify-center rounded-full bg-money text-[11px] text-on-accent">!</span>
                  )}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className={step.state === "done" ? "text-muted" : "font-medium"}>
                    {step.label}
                    {step.state === "active" && <span className="font-normal text-muted tabular-nums"> · {seconds}s</span>}
                    {step.state === "failed" && <span className="sr-only"> failed</span>}
                  </span>
                  {step.detail && <span className={`text-[13px] ${step.state === "failed" ? "text-money" : "text-muted"}`}>{step.detail}</span>}
                </span>
              </li>
            ))}
          </ol>
          {failed && !busy && (
            <span className="flex items-center gap-4 text-[15px] font-medium">
              <label className="cursor-pointer text-ai has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-text">
                Try another photo
                <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only" onChange={read} />
              </label>
              <button type="button" onClick={() => setSteps([])} className="text-muted">
                Close
              </button>
            </span>
          )}
        </div>
      </div>
    );
  }

  if (!found) {
    return (
      <label className={`${buttonGlass} cursor-pointer gap-2 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-text ${busy ? "pointer-events-none opacity-40" : ""}`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- 24px design asset */}
        <img src="/ui/camera.svg" alt="" width={24} height={24} />
        <span>Check off with a photo of an item or receipt</span>
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
