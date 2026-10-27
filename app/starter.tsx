"use client";

import { useState } from "react";
import { api, usd, type List } from "./api";

type Suggestion = { title: string; kind: string; items: { name: string; quantity: number; estPriceCents: number | null }[] };

const button = "h-14 rounded-full bg-accent text-xl font-medium text-white disabled:opacity-40";
const field = "h-14 rounded-3xl glass px-4 text-xl";

// Describe the situation, review the AI's starting list, untick what you don't need, then create it.
// Nothing is saved until "Create list" (decision 5).
export function Starter({ onCreated }: { onCreated: (list: List) => void }) {
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [dropped, setDropped] = useState<Set<number>>(new Set());
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function suggest(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const dollars = Number(budget);
      const budgetCents = budget && dollars > 0 ? Math.round(dollars * 100) : undefined;
      setSuggestion(await api<Suggestion>("/api/lists/suggest", { method: "POST", body: JSON.stringify({ description, budgetCents }) }));
      setDropped(new Set());
    } catch (err) {
      setStatus((err as Error).message);
    }
    setBusy(false);
  }

  async function create() {
    if (!suggestion) return;
    setBusy(true);
    try {
      const items = suggestion.items.filter((_, index) => !dropped.has(index));
      const budgetCents = Number(budget) > 0 ? Math.round(Number(budget) * 100) : undefined;
      onCreated(await api<List>("/api/lists", { method: "POST", body: JSON.stringify({ ...suggestion, items, budgetCents }) }));
    } catch (err) {
      setStatus(`Could not create the list: ${(err as Error).message}`);
      setBusy(false);
    }
  }

  const kept = suggestion?.items.filter((_, index) => !dropped.has(index)) ?? [];
  const total = kept.reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0);

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={suggest} className="flex flex-col gap-3">
        <label className="flex flex-col gap-2 text-lg">
          What is the list for?
          <input
            className={field}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Weekend camping trip for 3 friends"
            maxLength={500}
            required
          />
        </label>
        <label className="flex flex-col gap-2 text-lg">
          Budget in dollars (optional)
          <input className={field} value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" placeholder="150" />
        </label>
        <button type="submit" disabled={busy || !description.trim()} className={button}>
          {busy && !suggestion ? "Making your list…" : suggestion ? "Try again" : "Make my list"}
        </button>
      </form>

      {status && (
        <p role="status" className="glass rounded-3xl p-4 text-lg">
          {status}
        </p>
      )}

      {suggestion && (
        <>
          <h2 className="text-2xl font-medium">{suggestion.title}</h2>
          <p className="text-lg">Untick anything you don&apos;t need.</p>
          <ul className="flex flex-col gap-2">
            {suggestion.items.map((item, index) => (
              <li key={index}>
                <label className="flex min-h-14 cursor-pointer items-center gap-4 rounded-3xl glass px-4 text-xl">
                  <input
                    type="checkbox"
                    className="size-6"
                    checked={!dropped.has(index)}
                    onChange={() => {
                      const next = new Set(dropped);
                      if (!next.delete(index)) next.add(index);
                      setDropped(next);
                    }}
                  />
                  <span className="flex-1">
                    {item.name}
                    {item.quantity > 1 && <span className="opacity-60"> × {item.quantity}</span>}
                  </span>
                  <span className="tabular-nums">{item.estPriceCents ? usd(item.estPriceCents * item.quantity) : "—"}</span>
                </label>
              </li>
            ))}
          </ul>
          <p className="text-lg tabular-nums">Estimated total: {usd(total)}</p>
          {/* The AI is asked to stay within the budget but doesn't always; the check is done here, in code (decision 10). */}
          {Number(budget) > 0 && total > Math.round(Number(budget) * 100) && (
            <p role="status" className="text-lg text-amber-700">
              That is {usd(total - Math.round(Number(budget) * 100))} over your budget. Untick a few items to fit.
            </p>
          )}
          <button type="button" onClick={create} disabled={busy || kept.length === 0} className={button}>
            Create list with {kept.length} items
          </button>
        </>
      )}
    </div>
  );
}
