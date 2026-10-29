"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { api, rememberMember, usd, type List } from "./api";
import { Brand, button, card, chip, row } from "./ui";

// priceSource (decision 49): paid = what people paid for it before, store = a store product chosen for it, estimate = the AI's guess.
type Suggestion = {
  title: string;
  kind: string;
  items: { name: string; quantity: number; estPriceCents: number | null; note: string | null; priceSource?: "paid" | "store" | "estimate" | null }[];
};
const sourceLabel = { paid: "paid before", store: "store price", estimate: "AI guess" };

// Idea chips (Figma "Ideas"): each fills the prompt with an example to start from.
const IDEAS = [
  ["Trip", "Weekend camping trip for 3 friends, $150 budget", "text-list"],
  ["Party", "Birthday party for 10 kids at home, $100 budget", "text-money"],
  ["Groceries", "Weekly groceries for 2 adults", "text-list"],
  ["Move-in", "Moving into a new flat with 2 roommates, $300 budget", "text-ai"],
] as const;

// Whole dollars without ".00", as in the design's budget card ("$186 of $200 budget").
const dollars = (cents: number) => (cents % 100 === 0 ? `$${cents / 100}` : usd(cents));

// The budget is said in the sentence ("..., $200 budget"), as in the design; it only counts next to the word "budget".
function budgetIn(text: string): number | undefined {
  const match = text.match(/\$\s?(\d[\d,]*(?:\.\d{1,2})?)\s*budget|budget\s*(?:of\s*)?\$\s?(\d[\d,]*(?:\.\d{1,2})?)/i);
  const dollars = Number((match?.[1] ?? match?.[2] ?? "").replaceAll(",", ""));
  return dollars > 0 ? Math.round(dollars * 100) : undefined;
}

// Voice input with the browser's own speech recognition (decision 13); the mic only shows where it exists.
type Recognition = { lang: string; start(): void; onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void; onend: () => void };
const recognitionClass = () => {
  const w = window as unknown as Record<string, (new () => Recognition) | undefined>;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};

// How long a call took, in whole seconds (at least 1), for "AI made 12 items in 3 seconds".
async function timed<T>(call: () => Promise<T>): Promise<[T, number]> {
  const started = Date.now();
  const result = await call();
  return [result, Math.max(1, Math.round((Date.now() - started) / 1000))];
}

// Describe the situation, review the AI's starting list (drop, rename, change amounts, add what's missing),
// then create it. Nothing is saved until "create list" (decision 5).
export function Starter({ onCreated, side }: { onCreated: (list: List) => void; side?: React.ReactNode }) {
  const [description, setDescription] = useState("");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [dropped, setDropped] = useState<Set<number>>(new Set());
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [extra, setExtra] = useState("");
  const canListen = useSyncExternalStore(
    () => () => {},
    () => Boolean(recognitionClass()),
    () => false,
  );
  const budgetCents = budgetIn(description);

  function listen() {
    const Recognition = recognitionClass();
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = navigator.language;
    recognition.onresult = (e) => setDescription(e.results[0][0].transcript);
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  }

  function change(index: number, values: Partial<Suggestion["items"][number]>) {
    setSuggestion((current) => current && { ...current, items: current.items.map((item, i) => (i === index ? { ...item, ...values } : item)) });
  }

  async function suggest(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const [suggested, took] = await timed(() => api<Suggestion>("/api/lists/suggest", { method: "POST", body: JSON.stringify({ description, budgetCents }) }));
      setSuggestion(suggested);
      setSeconds(took);
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
      // An emptied name means the item isn't wanted.
      const items = suggestion.items.filter((item, index) => !dropped.has(index) && item.name.trim()).map((item) => ({ ...item, name: item.name.trim() }));
      onCreated(await api<List>("/api/lists", { method: "POST", body: JSON.stringify({ ...suggestion, items, budgetCents }) }));
    } catch (err) {
      setStatus(`Could not create the list: ${(err as Error).message}`);
      setBusy(false);
    }
  }

  // A ready-made trip with Ann and Ben, so one person can try sharing, paying and settling up (phase 8B).
  async function trySample() {
    setBusy(true);
    try {
      const { list, memberId } = await api<{ list: List; memberId: string }>("/api/lists/sample", { method: "POST" });
      rememberMember(list.id, memberId);
      onCreated(list);
    } catch (err) {
      setStatus(`Could not open the sample: ${(err as Error).message}`);
      setBusy(false);
    }
  }

  const message = status && (
    <p role="status" className={`${card} text-base`}>
      {status}
    </p>
  );

  if (!suggestion) {
    return (
      <div className="flex flex-col gap-10 lg:flex-row lg:gap-10">
        <div className="flex min-w-0 flex-1 flex-col gap-5 lg:gap-7 lg:pt-10">
          <div className="flex items-center justify-between lg:hidden">
            <Brand />
            <Link href="/history" className="text-base font-medium text-muted">
              History
            </Link>
          </div>
          <h1 className="text-[34px] tracking-[-0.015em] lg:text-[60px] lg:font-medium lg:tracking-[-0.02em]">What are we planning?</h1>
          <p className="hidden text-[19px] leading-normal text-muted lg:block">
            Describe the situation. HeyList drafts the list, you keep what you need,
            <br />
            and everyone sees who paid for what.
          </p>

          <form onSubmit={suggest} className={`${card} flex flex-col gap-4 lg:gap-5 lg:p-7`}>
            <span className="flex items-center gap-2 text-sm font-medium text-ai">
              {/* eslint-disable-next-line @next/next/no-img-element -- 18px design asset */}
              <img src="/ui/sparkle.svg" alt="" width={18} height={18} />
              Describe it, AI builds the list
            </span>
            <div className="flex items-center gap-3 rounded-[20px] bg-bg py-2.5 pr-2.5 pl-[18px]">
              <textarea
                className="min-h-[52px] min-w-0 flex-1 resize-none bg-transparent text-lg font-medium outline-none placeholder:text-muted lg:text-[22px]"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Camping at Big Sur with 4 friends, $200 budget"
                aria-label="What is the list for?"
                rows={2}
                maxLength={500}
                required
              />
              {canListen && (
                <button
                  type="button"
                  onClick={listen}
                  disabled={listening}
                  aria-label={listening ? "Listening…" : "Say it instead"}
                  className={`flex size-[52px] shrink-0 items-center justify-center rounded-full bg-ai ${listening ? "animate-pulse" : ""}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- 24px design asset */}
                  <img src="/ui/mic.svg" alt="" width={24} height={24} />
                </button>
              )}
            </div>
            {budgetCents !== undefined && <span className="text-sm text-muted">Budget: {usd(budgetCents)}</span>}
            <button type="submit" disabled={busy || !description.trim()} className={`${button} w-full lg:w-[168px]`}>
              {busy ? "Making your list…" : "Make my list"}
            </button>
          </form>
          {message}

          <div className="flex flex-wrap gap-2">
            {IDEAS.map(([label, example, color]) => (
              <button key={label} type="button" onClick={() => setDescription(example)} className={`${chip} ${color}`}>
                {label}
              </button>
            ))}
          </div>
          <button type="button" onClick={trySample} disabled={busy} className="self-start text-[15px] text-muted underline underline-offset-4">
            New here? See how it works with a sample trip
          </button>
        </div>
        {side && <aside className="flex flex-col gap-5 lg:w-[440px] lg:shrink-0 lg:pt-10">{side}</aside>}
      </div>
    );
  }

  const kept = suggestion.items.filter((item, index) => !dropped.has(index) && item.name.trim());
  const total = kept.reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0);

  return (
    <div className="flex flex-col gap-5 lg:mx-auto lg:w-full lg:max-w-[760px]">
      <button type="button" onClick={() => setSuggestion(null)} className="self-start text-base font-medium text-muted">
        ← Back
      </button>
      <span className={`${chip} flex items-center gap-1.5 self-start px-3 py-[7px] text-[13px] text-ai`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- design asset */}
        <img src="/ui/sparkle.svg" alt="" width={16} height={16} />
        AI made {suggestion.items.length} items in {seconds} {seconds === 1 ? "second" : "seconds"}
      </span>
      <h1 className="text-[32px] tracking-[-0.015em] lg:text-[48px] lg:font-medium">{suggestion.title}</h1>

      {/* The AI is asked to stay within the budget but doesn't always; the check is done here, in code (decision 10). */}
      <div className={`${card} flex flex-col gap-2.5`}>
        <div className="flex items-end justify-between">
          <span className="flex items-baseline gap-1.5 whitespace-nowrap">
            <span className="text-[30px] tracking-[-0.015em] text-money tabular-nums">{dollars(total)}</span>
            <span className="text-[15px] font-medium text-muted">{budgetCents !== undefined ? `of ${dollars(budgetCents)} budget` : "estimated"}</span>
          </span>
          {budgetCents !== undefined && (
            <span className="text-sm font-medium whitespace-nowrap">{total <= budgetCents ? `${dollars(budgetCents - total)} left` : `${dollars(total - budgetCents)} over`}</span>
          )}
        </div>
        {budgetCents !== undefined && (
          <div className="h-2.5 overflow-hidden rounded-[5px] bg-surface-2">
            <div className="h-full rounded-[5px] bg-money" style={{ width: `${Math.min(100, (total / budgetCents) * 100)}%` }} />
          </div>
        )}
      </div>
      {budgetCents !== undefined && total > budgetCents && <p className="text-base text-money">Tap the circle on a few items to drop them and fit the budget.</p>}

      <p className="text-[15px] text-muted">Tap anything to change it. Tap a circle to drop that item.</p>
      <ul className="flex flex-col gap-2.5">
        {suggestion.items.map((item, index) => {
          const off = dropped.has(index);
          return (
            <li key={index} className={`${row} ${off ? "opacity-50" : ""}`}>
              <label className="flex shrink-0 cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only"
                  aria-label={`Drop ${item.name}`}
                  checked={off}
                  onChange={() => {
                    const next = new Set(dropped);
                    if (!next.delete(index)) next.add(index);
                    setDropped(next);
                  }}
                />
                <span className={`size-7 rounded-full border-2 border-muted ${off ? "bg-muted" : ""}`} />
              </label>
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <input
                  className={`w-full bg-transparent text-[17px] font-medium outline-none ${off ? "line-through" : ""}`}
                  aria-label="Item name"
                  value={item.name}
                  maxLength={120}
                  onChange={(e) => change(index, { name: e.target.value })}
                />
                <span className="flex items-center gap-2 text-[13px] text-muted">
                  <button type="button" aria-label={`One fewer ${item.name}`} disabled={item.quantity <= 1} onClick={() => change(index, { quantity: item.quantity - 1 })} className="px-1 disabled:opacity-30">
                    −
                  </button>
                  <span aria-live="polite" className="tabular-nums">
                    ×{item.quantity}
                  </span>
                  <button type="button" aria-label={`One more ${item.name}`} disabled={item.quantity >= 99} onClick={() => change(index, { quantity: item.quantity + 1 })} className="px-1 disabled:opacity-30">
                    +
                  </button>
                  {item.note && <span className="truncate text-money">· {item.note}</span>}
                </span>
              </span>
              <span className="flex shrink-0 flex-col items-end text-base font-medium tabular-nums">
                {item.estPriceCents ? `${item.priceSource === "estimate" ? "~" : ""}${usd(item.estPriceCents * item.quantity)}` : "—"}
                {item.estPriceCents && item.priceSource ? <span className="text-[13px] font-normal text-muted">{sourceLabel[item.priceSource]}</span> : null}
              </span>
            </li>
          );
        })}
      </ul>
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!extra.trim()) return;
          setSuggestion({ ...suggestion, items: [...suggestion.items, { name: extra.trim(), quantity: 1, estPriceCents: null, note: null }] });
          setExtra("");
        }}
      >
        <input
          className="min-w-0 flex-1 bg-transparent text-base font-medium text-ai outline-none placeholder:text-ai"
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          placeholder="+ Add an item"
          aria-label="Add an item"
          maxLength={120}
        />
        {extra.trim() && (
          <button type="submit" className="text-base font-medium text-ai">
            Add
          </button>
        )}
      </form>
      {message}

      {/* Pinned to the bottom of the phone screen over a fade, as in the design; in the page flow on the website. */}
      <div className="fixed inset-x-0 bottom-0 bg-gradient-to-b from-transparent via-bg/90 via-45% to-bg px-8 pt-16 pb-10 lg:static lg:bg-none lg:p-0">
        <button type="button" onClick={create} disabled={busy || kept.length === 0} className={`${button} mx-auto w-full max-w-[760px] lg:w-auto`}>
          {busy ? "Creating…" : `Looks good, create list (${kept.length})`}
        </button>
      </div>
    </div>
  );
}
