"use client";

import { useState } from "react";
import { api, usd, type Item, type List, type Receipt, type ReceiptFee } from "./api";
import { button, buttonAi, buttonGlass, card } from "./ui";

// Phone photos are often larger than the backend's 5 MB limit; 2000 px is plenty for Textract to read a receipt.
async function shrink(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 2000 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not read the photo"))), "image/jpeg", 0.85),
  );
}

// "4.50" -> 450; "" -> null (nothing typed); anything else -> NaN. Whole cents, no floats.
function typedCents(text: string): number | null {
  const found = text.trim().replace(/^\$/, "").match(/^(\d{0,7})(?:\.(\d{1,2}))?$/);
  if (!text.trim()) return null;
  if (!found || (!found[1] && !found[2])) return NaN;
  return Number(found[1] || 0) * 100 + Number((found[2] ?? "").padEnd(2, "0"));
}

const FEE_KINDS: Record<ReceiptFee["kind"], string> = { tax: "Tax", tip: "Tip", service: "Service charge", delivery: "Delivery", discount: "Discount", other: "Fee" };

// Take a photo of a receipt, check what the AI matched, then confirm to check those items off.
// A price or fee the photo couldn't be read for surely is left blank for the person to type, never guessed (decision 57).
// capture="environment" opens the back camera on phones; on a computer it is a file picker.
export function ReceiptScan({ list, memberId, onDone }: { list: List; memberId: string | null; onDone: (list: List) => void }) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [choices, setChoices] = useState<(string | null)[]>([]);
  // What the person typed for blank prices and fees, one entry per line and per fee.
  const [prices, setPrices] = useState<string[]>([]);
  const [feeAmounts, setFeeAmounts] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const open: Item[] = list.items.filter((item) => !item.checkedAt);
  // Scans someone walked away from before confirming; they can be finished here later.
  const waiting = list.receipts.filter((r) => !r.confirmedAt && r.id !== receipt?.id);

  function review(next: Receipt) {
    setReceipt(next);
    // An item checked off since the scan can't be chosen any more; its line starts as an extra.
    setChoices(next.lines.map((line) => (open.some((item) => item.id === line.itemId) ? line.itemId : null)));
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

  const typedInput = (label: string, value: string, set: (value: string) => void) => (
    <input
      aria-label={label}
      inputMode="decimal"
      placeholder="0.00"
      className={`h-11 w-28 rounded-[20px] bg-surface-2 px-3 text-right tabular-nums ${Number.isNaN(typedCents(value)) ? "outline outline-money" : ""}`}
      value={value}
      onChange={(e) => set(e.target.value)}
    />
  );

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium lg:text-xl">Scan a receipt</h2>
      {!memberId && <p className="text-base text-muted-on-bg">Join above first, so the receipt counts as yours.</p>}
      <label className={`${buttonAi} cursor-pointer has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-text ${busy || !memberId ? "pointer-events-none opacity-40" : ""}`}>
        Take a photo of the receipt
        <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only" onChange={scan} disabled={busy || !memberId} />
      </label>

      {waiting.length > 0 && (
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
          <p className="text-base text-muted-on-bg">Check each line, change any that are wrong, then confirm.</p>
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
                  <span className="text-[13px] text-money">The price couldn&apos;t be read. Type it from the receipt, or leave it blank if you can&apos;t tell.</span>
                )}
                {line.priceCents !== null && line.lowConfidence && <span className="text-[13px] text-money">Hard to read: check this line</span>}
                <select
                  aria-label={`List item for ${line.text}`}
                  className="h-11 rounded-[20px] bg-surface-2 px-3"
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
              <p className="text-base text-muted-on-bg">Tax, tip and other fees. They&apos;re shared like the list items they were charged on.</p>
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
                      <span className="text-[13px] text-money">
                        The amount couldn&apos;t be read. Type it{fee.kind === "discount" && " (without a minus)"}, or leave it blank if you can&apos;t tell.
                      </span>
                    )}
                  </li>
                ))}
              </ul>
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
        </>
      )}
    </section>
  );
}
