"use client";

import { useState } from "react";
import { api, percent, usd, type Item, type List, type Receipt, type ReceiptFee } from "./api";
import { shrink, typedCents } from "./photo";
import { button, buttonAi, buttonGlass, card } from "./ui";

const FEE_KINDS: Record<ReceiptFee["kind"], string> = { tax: "Tax", tip: "Tip", service: "Service charge", delivery: "Delivery", discount: "Discount", other: "Fee" };

// Take a photo of a receipt, check what the AI matched, then confirm to check those items off.
// A price or fee the photo couldn't be read for surely is left blank for the person to type, never guessed (decision 57).
// capture="environment" opens the back camera on phones; on a computer it is a file picker.
// With scanned (a receipt photo taken on Progress), only its review shows, and onClose ends it; give it key={scanned.id}.
export function ReceiptScan({ list, memberId, onDone, scanned, onClose }: { list: List; memberId: string | null; onDone: (list: List) => void; scanned?: Receipt; onClose?: () => void }) {
  const open: Item[] = list.items.filter((item) => !item.checkedAt);
  // An item checked off since the scan can't be chosen any more; its line starts as an extra.
  const choicesFor = (next: Receipt) => next.lines.map((line) => (open.some((item) => item.id === line.itemId) ? line.itemId : null));
  const [receipt, setReceipt] = useState<Receipt | null>(scanned ?? null);
  const [choices, setChoices] = useState<(string | null)[]>(() => (scanned ? choicesFor(scanned) : []));
  // What the person typed for blank prices and fees, one entry per line and per fee.
  const [prices, setPrices] = useState<string[]>(() => scanned?.lines.map(() => "") ?? []);
  const [feeAmounts, setFeeAmounts] = useState<string[]>(() => (scanned?.fees ?? []).map(() => ""));
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Scans someone walked away from before confirming; they can be finished here later.
  const waiting = list.receipts.filter((r) => !r.confirmedAt && r.id !== receipt?.id);

  function review(next: Receipt) {
    setReceipt(next);
    setChoices(choicesFor(next));
    setPrices(next.lines.map(() => ""));
    setFeeAmounts((next.fees ?? []).map(() => ""));
    setStatus(null);
  }

  async function scan(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setStatus("Reading the receipt…");
    try {
      const query = memberId ? `?memberId=${memberId}` : "";
      const scanned = await api<Receipt>(`/api/lists/${list.id}/receipts${query}`, { method: "POST", body: await shrink(file) });
      review(scanned);
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  async function confirm() {
    setBusy(true);
    try {
      const body = { itemIds: choices, prices: prices.map(typedCents), feeAmounts: feeAmounts.map(typedCents) };
      onDone(await api<List>(`/api/receipts/${receipt!.id}/confirm`, { method: "POST", body: JSON.stringify(body) }));
      if (onClose) return onClose();
      setReceipt(null);
      setStatus("Done. The matched items are checked off.");
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  // Every amount on the receipt, read or typed (a typed discount is taken off), and whether they reach its total.
  const fees = receipt?.fees ?? [];
  const lineCents = receipt?.lines.map((line, i) => line.priceCents ?? typedCents(prices[i] ?? "")) ?? [];
  const feeCents = fees.map((fee, i) => {
    const typed = typedCents(feeAmounts[i] ?? "");
    return fee.amountCents ?? (typed !== null && fee.kind === "discount" ? -typed : typed);
  });
  const amounts = [...lineCents, ...feeCents];
  const badTyping = amounts.some((cents) => Number.isNaN(cents));
  const blanks = amounts.filter((cents) => cents === null).length;
  const sum = amounts.reduce<number>((total, cents) => total + (cents ?? 0), 0);
  // The sales tax rate this receipt shows, as money.receipt_tax_rate works it out: tax over lines less discounts.
  // Once confirmed, it becomes the list's rate for PayPal payments and estimates (decision 80).
  const taxCents = feeCents.filter((_, i) => fees[i].kind === "tax");
  const subtotal = lineCents.reduce<number>((total, cents) => total + (cents ?? 0), 0) + feeCents.reduce<number>((total, cents, i) => total + (fees[i].kind === "discount" ? (cents ?? 0) : 0), 0);
  const taxKnown = taxCents.length > 0 && !taxCents.some((cents) => cents === null || Number.isNaN(cents)) && !lineCents.some((cents) => cents === null || Number.isNaN(cents));
  const receiptRate = taxKnown && subtotal > 0 ? Math.min(Math.floor((taxCents.reduce<number>((t, c) => t + (c ?? 0), 0) * 20000 + subtotal) / (2 * subtotal)), 2500) : null;

  const typedInput = (label: string, value: string, set: (value: string) => void) => (
    <input
      aria-label={label}
      inputMode="decimal"
      placeholder="0.00"
      className={`h-11 w-28 rounded-[1.25rem] bg-surface-2 px-3 text-right tabular-nums ${Number.isNaN(typedCents(value)) ? "outline outline-money" : ""}`}
      value={value}
      onChange={(e) => set(e.target.value)}
    />
  );

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium lg:text-xl">{scanned ? "Check the receipt" : "Scan a receipt"}</h2>
      {!scanned && !memberId && <p className="text-base text-muted-on-bg">Join above first, so the receipt counts as yours.</p>}
      {!scanned && (
        <label className={`${buttonAi} has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-text ${busy || !memberId ? "cursor-not-allowed opacity-40" : "cursor-pointer"}`}>
          Take a photo of the receipt
          <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only" onChange={scan} disabled={busy || !memberId} />
        </label>
      )}

      {!scanned && waiting.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-base text-muted-on-bg">Scanned but not confirmed yet:</p>
          {waiting.map((r) => (
            <div key={r.id} className={`${card} flex items-center justify-between gap-3 text-base`}>
              <span className="tabular-nums">
                {new Date(r.createdAt).toLocaleDateString(undefined, { day: "numeric", month: "short" })} · {r.lines.length} lines
                {r.totalCents !== null && ` · ${usd(r.totalCents)}`}
              </span>
              <button type="button" onClick={() => review(r)} disabled={busy} className={buttonGlass}>
                Finish checking
              </button>
            </div>
          ))}
        </div>
      )}

      {status && (
        <p role="status" className={`${card} text-base`}>
          {status}
        </p>
      )}

      {receipt && (
        <>
          <ul className="flex flex-col gap-2">
            {receipt.lines.map((line, index) => (
              <li key={index} className={`${card} flex flex-col gap-2 text-base`}>
                <span className="flex items-center justify-between gap-2">
                  <span className="font-mono">{line.text}</span>
                  {line.priceCents !== null ? (
                    <span className="tabular-nums">{usd(line.priceCents)}</span>
                  ) : (
                    typedInput(`Price of ${line.text}`, prices[index] ?? "", (value) => setPrices(prices.map((p, i) => (i === index ? value : p))))
                  )}
                </span>
                {line.priceCents === null && (
                  <span className="text-[0.8125rem] text-money">The price couldn&apos;t be read. Type it from the receipt, or leave it blank if you can&apos;t tell.</span>
                )}
                {line.priceCents !== null && line.lowConfidence && <span className="text-[0.8125rem] text-money">Hard to read: check this line</span>}
                <select
                  aria-label={`List item for ${line.text}`}
                  className="h-11 rounded-[1.25rem] bg-surface-2 px-3"
                  value={choices[index] ?? ""}
                  onChange={(e) => setChoices(choices.map((c, i) => (i === index ? e.target.value || null : c)))}
                >
                  <option value="">Not on the list (extra)</option>
                  {open.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
          {fees.length > 0 && (
            <>
              <h3 className="text-base font-medium">Tax and fees</h3>
              <ul className="flex flex-col gap-2">
                {fees.map((fee, index) => (
                  <li key={index} className={`${card} flex flex-col gap-2 text-base`}>
                    <span className="flex items-center justify-between gap-2">
                      <span>
                        {FEE_KINDS[fee.kind]}
                        {fee.name.toLowerCase() !== FEE_KINDS[fee.kind].toLowerCase() && <span className="font-mono text-muted"> · {fee.name}</span>}
                      </span>
                      {fee.amountCents !== null ? (
                        <span className="tabular-nums">{usd(fee.amountCents)}</span>
                      ) : (
                        typedInput(`Amount of ${fee.name}`, feeAmounts[index] ?? "", (value) => setFeeAmounts(feeAmounts.map((a, i) => (i === index ? value : a))))
                      )}
                    </span>
                    {fee.amountCents === null && (
                      <span className="text-[0.8125rem] text-money">
                        The amount couldn&apos;t be read. Type it{fee.kind === "discount" && " (without a minus)"}, or leave it blank if you can&apos;t tell.
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {receiptRate !== null && (
                <p className="text-[0.8125rem] text-muted">
                  That&apos;s {percent(receiptRate)} sales tax. Once you confirm, PayPal payments and estimates on this list use your receipts&apos; rate.
                </p>
              )}
            </>
          )}
          {receipt.totalCents !== null && (
            <p className={`text-base tabular-nums ${!blanks && sum !== receipt.totalCents ? "font-medium text-text" : "text-muted-on-bg"}`}>
              {blanks > 0
                ? `Receipt total ${usd(receipt.totalCents)}. ${blanks} amount${blanks === 1 ? " is" : "s are"} still blank.`
                : sum === receipt.totalCents
                  ? `Adds up to the receipt total, ${usd(receipt.totalCents)}.`
                  : `These add up to ${usd(sum)}, but the receipt total is ${usd(receipt.totalCents)}. Check the prices against the receipt.`}
            </p>
          )}
          {badTyping && <p className="text-base font-medium text-text">Type amounts like 4.50.</p>}
          <button
            type="button"
            onClick={confirm}
            disabled={busy || badTyping}
            className={button}
          >
            Confirm and check off
          </button>
          {onClose && (
            // The scan is kept unconfirmed, so it can still be finished from the Receipts tab.
            <button type="button" onClick={onClose} disabled={busy} className="self-center text-[0.9375rem] font-medium text-muted">
              Not now, finish it later in Receipts
            </button>
          )}
        </>
      )}
    </section>
  );
}
