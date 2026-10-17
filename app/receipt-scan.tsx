"use client";

import { useState } from "react";
import { api, usd, type Item, type List, type Receipt } from "./api";

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

// Take a photo of a receipt, check what the AI matched, then confirm to check those items off.
// capture="environment" opens the back camera on phones; on a computer it is a file picker.
export function ReceiptScan({ list, memberId, onDone }: { list: List; memberId: string | null; onDone: (list: List) => void }) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [choices, setChoices] = useState<(string | null)[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const open: Item[] = list.items.filter((item) => !item.checkedAt);

  async function scan(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setStatus("Reading the receipt…");
    try {
      const query = memberId ? `?memberId=${memberId}` : "";
      const scanned = await api<Receipt>(`/api/lists/${list.id}/receipts${query}`, { method: "POST", body: await shrink(file) });
      setReceipt(scanned);
      setChoices(scanned.lines.map((line) => line.itemId));
      setStatus(null);
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  async function confirm() {
    setBusy(true);
    try {
      onDone(await api<List>(`/api/receipts/${receipt!.id}/confirm`, { method: "POST", body: JSON.stringify({ itemIds: choices }) }));
      setReceipt(null);
      setStatus("Done. The matched items are checked off.");
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-2xl font-bold">Scan a receipt</h2>
      {!memberId && <p className="text-lg">Add your name above first, so the receipt counts as yours.</p>}
      <label
        className={`flex h-14 cursor-pointer items-center justify-center rounded-2xl border-2 border-line bg-card text-xl font-bold ${busy || !memberId ? "pointer-events-none opacity-40" : ""}`}
      >
        Take a photo of the receipt
        <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only" onChange={scan} disabled={busy || !memberId} />
      </label>

      {status && (
        <p role="status" className="rounded-2xl bg-chip p-4 text-lg">
          {status}
        </p>
      )}

      {receipt && (
        <>
          <p className="text-lg">Check each line, change any that are wrong, then confirm.</p>
          <ul className="flex flex-col gap-2">
            {receipt.lines.map((line, index) => (
              <li key={index} className="flex flex-col gap-2 rounded-2xl border border-line bg-card p-4 text-lg">
                <span className="flex justify-between gap-2">
                  <span className="font-mono">{line.text}</span>
                  <span className="tabular-nums">{usd(line.priceCents)}</span>
                </span>
                {line.lowConfidence && <span className="text-base text-amber-700 dark:text-amber-400">Hard to read: check this line</span>}
                <select
                  aria-label={`List item for ${line.text}`}
                  className="h-12 rounded-2xl border-2 border-line bg-card px-2"
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
          <button
            type="button"
            onClick={confirm}
            disabled={busy}
            className="h-14 rounded-2xl bg-accent text-xl font-bold text-white disabled:opacity-40"
          >
            Confirm and check off
          </button>
        </>
      )}
    </section>
  );
}
