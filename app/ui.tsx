"use client";

import { useRef, useState } from "react";
import { type Draft, dollars, parseDollars } from "./lib";

const button = "rounded-2xl px-5 py-4 text-xl font-semibold disabled:opacity-40";
export const primary = `${button} bg-emerald-700 text-white`;
export const secondary = `${button} border-2 border-zinc-300 bg-white`;
export const small = "rounded-xl border border-zinc-300 bg-white px-3 py-2 text-base";
export const input = "w-full rounded-2xl border-2 border-zinc-300 bg-white px-4 py-3 text-xl";
export const card = "rounded-2xl border border-zinc-200 bg-white p-4";

export function Notice({ text }: { text: string }) {
  return text ? (
    <p role="alert" className="rounded-2xl bg-amber-100 p-4 text-lg">
      {text}
    </p>
  ) : null;
}

export function Bar({ part, whole, over }: { part: number; whole: number; over?: boolean }) {
  const percent = whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0;
  return (
    <div className="h-4 w-full overflow-hidden rounded-full bg-zinc-200" role="presentation">
      <div
        className={`h-full ${over ? "bg-red-600" : "bg-emerald-600"}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

/** A dollar amount field. Reports integer cents (or null when empty) when the user leaves it. */
export function PriceInput({
  cents,
  onChange,
  label,
}: {
  cents: number | null;
  onChange: (cents: number | null) => void;
  label: string;
}) {
  return (
    <input
      // The key resets the field when the saved value changes underneath it.
      key={cents ?? "empty"}
      aria-label={label}
      inputMode="decimal"
      placeholder="$"
      className="w-24 rounded-xl border-2 border-zinc-300 bg-white px-3 py-2 text-right text-lg"
      defaultValue={cents === null ? "" : (cents / 100).toFixed(2)}
      onBlur={(event) => {
        const next = parseDollars(event.target.value);
        if (next !== cents) onChange(next);
      }}
    />
  );
}

// The Web Speech API is not in TypeScript's DOM types; this is the part used here.
type Recognition = {
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};
type SpeechWindow = {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

/** The one big talk button. Calls onText with what was said. */
export function TalkButton({ onText, label }: { onText: (text: string) => void; label: string }) {
  const [listening, setListening] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const recognition = useRef<Recognition | null>(null);

  function toggle() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const speech = window as unknown as SpeechWindow;
    const Recognizer = speech.SpeechRecognition ?? speech.webkitSpeechRecognition;
    if (!Recognizer) {
      setUnsupported(true);
      return;
    }
    const recognizer = new Recognizer();
    recognizer.lang = "en-US";
    recognizer.onresult = (event) => {
      const said = Array.from(event.results, (result) => result[0].transcript).join(" ");
      if (said.trim()) onText(said.trim());
    };
    recognizer.onend = () => setListening(false);
    recognizer.onerror = () => setListening(false);
    recognition.current = recognizer;
    recognizer.start();
    setListening(true);
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        aria-pressed={listening}
        className={`size-28 rounded-full text-xl font-bold text-white ${listening ? "bg-red-600" : "bg-emerald-700"}`}
      >
        {listening ? "Stop" : "Talk"}
      </button>
      <p className="text-lg text-zinc-600">{listening ? "Listening…" : label}</p>
      {unsupported && (
        <p role="alert" className="text-lg">
          Voice does not work in this browser. Please type instead.
        </p>
      )}
    </div>
  );
}

/** Items the user can still change before they are saved: every AI suggestion lands here first. */
export function DraftEditor({
  drafts,
  onChange,
}: {
  drafts: Draft[];
  onChange: (drafts: Draft[]) => void;
}) {
  const total = drafts.reduce((sum, draft) => sum + (draft.estPriceCents ?? 0), 0);
  const change = (index: number, patch: Partial<Draft>) =>
    onChange(drafts.map((draft, other) => (other === index ? { ...draft, ...patch } : draft)));

  return (
    <div className="flex flex-col gap-2">
      {drafts.map((draft, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            aria-label="Item name"
            className="min-w-0 flex-1 rounded-xl border-2 border-zinc-300 bg-white px-3 py-2 text-lg"
            value={draft.name}
            onChange={(event) => change(index, { name: event.target.value })}
          />
          <PriceInput
            label={`Price of ${draft.name}`}
            cents={draft.estPriceCents}
            onChange={(estPriceCents) => change(index, { estPriceCents })}
          />
          <button
            type="button"
            aria-label={`Remove ${draft.name}`}
            className={small}
            onClick={() => onChange(drafts.filter((_, other) => other !== index))}
          >
            ✕
          </button>
        </div>
      ))}
      <button
        type="button"
        className={`${small} self-start`}
        onClick={() => onChange([...drafts, { name: "", estPriceCents: null }])}
      >
        + Add an item
      </button>
      <p className="text-lg font-semibold">Estimated total: {dollars(total)}</p>
    </div>
  );
}
