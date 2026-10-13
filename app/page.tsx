"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  type Draft,
  type ListState,
  type Member,
  NAME_KEY,
  api,
  dollars,
  memberKey,
  rememberList,
  store,
  useStored,
} from "./lib";
import { DraftEditor, Notice, PriceInput, TalkButton, input, primary, secondary } from "./ui";

// What the AI suggested, while the user is still confirming or editing it. Nothing is saved yet.
type Suggestion = { title: string; kind: string; budgetCents: number | null; items: Draft[] };

export default function Home() {
  const router = useRouter();
  const savedName = useStored(NAME_KEY);
  const [sentence, setSentence] = useState("");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function suggest(said: string) {
    if (!said.trim() || busy) return;
    setSentence(said);
    setBusy(true);
    setNotice("");
    try {
      setSuggestion(await api<Suggestion>("/ai/list", { body: { sentence: said.trim() } }));
    } catch {
      // Without the AI the user can still build the list by hand.
      setSuggestion({ title: said.trim().slice(0, 120), kind: "other", budgetCents: null, items: [] });
      setNotice("We could not suggest items just now. You can add them yourself below.");
    }
    setBusy(false);
  }

  async function save() {
    if (!suggestion || busy) return;
    const items = suggestion.items.filter((item) => item.name.trim());
    if (!suggestion.title.trim()) {
      setNotice("Please give the list a name.");
      return;
    }
    setBusy(true);
    try {
      const list = await api<ListState>("/lists", { body: { ...suggestion, items } });
      rememberList(list.id);
      const who = (name ?? savedName ?? "").trim();
      if (who) {
        const member = await api<Member>(`/lists/${list.id}/members`, { body: { name: who } });
        store(NAME_KEY, who);
        store(memberKey(list.id), member.id);
      }
      router.push(`/l/${list.id}`);
    } catch {
      setNotice("The list could not be saved. Please try again.");
      setBusy(false);
    }
  }

  if (suggestion) {
    const total = suggestion.items.reduce((sum, item) => sum + (item.estPriceCents ?? 0), 0);
    const over = suggestion.budgetCents !== null && total > suggestion.budgetCents;
    return (
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-5 p-5">
        <h1 className="text-3xl font-bold">Is this right?</h1>
        <p className="text-lg text-zinc-600">Change anything you like, then save.</p>
        <Notice text={notice} />

        <label className="flex flex-col gap-1 text-lg font-semibold">
          List name
          <input
            className={input}
            value={suggestion.title}
            onChange={(event) => setSuggestion({ ...suggestion, title: event.target.value })}
          />
        </label>
        <div className="flex items-center justify-between gap-3 text-lg font-semibold">
          Budget
          <PriceInput
            label="Budget"
            cents={suggestion.budgetCents}
            onChange={(budgetCents) => setSuggestion({ ...suggestion, budgetCents })}
          />
        </div>

        <DraftEditor
          drafts={suggestion.items}
          onChange={(items) => setSuggestion({ ...suggestion, items })}
        />
        {suggestion.budgetCents !== null && (
          <p className={`text-lg ${over ? "font-semibold text-red-700" : "text-zinc-600"}`}>
            {over
              ? `That is ${dollars(total - suggestion.budgetCents)} over your budget.`
              : `${dollars(suggestion.budgetCents - total)} of your budget is left.`}
          </p>
        )}

        <label className="flex flex-col gap-1 text-lg font-semibold">
          Your name (so others know who bought what)
          <input
            className={input}
            value={name ?? savedName ?? ""}
            onChange={(event) => setName(event.target.value)}
          />
        </label>

        <button type="button" className={primary} disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save list"}
        </button>
        <button type="button" className={secondary} disabled={busy} onClick={() => setSuggestion(null)}>
          Start over
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 p-5">
      <header>
        <h1 className="text-4xl font-bold">HeyList</h1>
        <p className="text-xl text-zinc-600">Simple checklists with money built in.</p>
      </header>

      <TalkButton onText={suggest} label="Tap and say what the list is for" />

      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void suggest(sentence);
        }}
      >
        <label className="flex flex-col gap-1 text-lg font-semibold">
          Or type it
          <textarea
            className={input}
            rows={2}
            placeholder="Move-in list for 3 roommates, $300 budget"
            value={sentence}
            onChange={(event) => setSentence(event.target.value)}
          />
        </label>
        <button type="submit" className={primary} disabled={busy || !sentence.trim()}>
          {busy ? "Making your list…" : "Make my list"}
        </button>
      </form>
      <Notice text={notice} />

      <Link href="/history" className={`${secondary} text-center`}>
        Your lists
      </Link>
    </main>
  );
}
