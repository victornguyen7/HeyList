"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  type History,
  type ListState,
  type Member,
  NAME_KEY,
  api,
  dollars,
  knownLists,
  memberKey,
  rememberList,
  store,
  useStored,
} from "../../lib";
import { Bar, Notice, input, primary, small } from "../../ui";
import { ItemsPage, MoneyPage, ReceiptsPage, SettlePage } from "./pages";
import Progress from "./progress";

const TABS = [
  ["progress", "Progress"],
  ["items", "Items"],
  ["money", "Money"],
  ["receipts", "Receipts"],
  ["settle", "Settle up"],
] as const;

export default function ListView({ listId, clientId }: { listId: string; clientId: string }) {
  const tab = useSearchParams().get("tab") ?? "progress";
  const me = useStored(memberKey(listId));
  const savedName = useStored(NAME_KEY);
  const [list, setList] = useState<ListState | null>(null);
  const [missing, setMissing] = useState(false);
  const [lastPaid, setLastPaid] = useState<Record<string, number>>({});
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");

  // Promise chains, not async functions: the effects below call these, and the React lint rule
  // only allows setState there from inside a callback.
  const refresh = useCallback(
    () =>
      api<ListState>(`/lists/${listId}`).then(
        (next) => {
          setList(next);
          rememberList(listId);
        },
        (error) => {
          // A network blip keeps the last list on screen; only a missing list replaces it.
          if (error instanceof Error && error.message === "LIST_NOT_FOUND") setMissing(true);
        },
      ),
    [listId],
  );

  // Shared lists stay current by re-fetching, not Supabase Realtime (decision 55).
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  // Price memory: what this browser's other lists last paid for an item of the same name.
  useEffect(() => {
    api<History>(`/history?ids=${knownLists().join(",")}`)
      .then((history) => setLastPaid(history.lastPaidCents))
      .catch(() => {});
  }, []);

  const join = useCallback(
    (who: string) =>
      api<Member>(`/lists/${listId}/members`, { body: { name: who } })
        .then((member) => {
          store(NAME_KEY, who);
          store(memberKey(listId), member.id);
          return refresh();
        })
        .catch(() => setNotice("Your name could not be saved. Please try again.")),
    [listId, refresh],
  );

  // Someone who already gave their name on another list joins this one without being asked again.
  useEffect(() => {
    if (list && !me && savedName) void join(savedName);
  }, [list, me, savedName, join]);

  async function share() {
    const url = `${window.location.origin}/l/${listId}`;
    if (navigator.share) {
      await navigator.share({ title: list?.title, url }).catch(() => {});
    } else {
      await navigator.clipboard.writeText(url);
      setNotice("Link copied. Send it to anyone; they do not need an account.");
    }
  }

  if (missing) {
    return (
      <>
        <p className="text-xl">This list does not exist. Check the link, or start a new one.</p>
        <Link href="/" className={`${primary} text-center`}>
          Start a list
        </Link>
      </>
    );
  }
  if (!list) return <p className="text-xl">Loading the list…</p>;

  const spent = list.money.spentCents + list.money.extrasCents;
  const over = list.budgetCents !== null && spent > list.budgetCents;
  const pageProps = { list, me, refresh };

  return (
    <>
      <header className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-3xl font-bold">{list.title}</h1>
          <button type="button" className={small} onClick={share}>
            Share
          </button>
        </div>
        {/* Money stays in view on every page, not on a side page. */}
        <div className="flex flex-col gap-1">
          <p className={`text-xl font-semibold ${over ? "text-red-700" : ""}`}>
            Spent {dollars(spent)}
            {list.budgetCents !== null && ` of ${dollars(list.budgetCents)}`}
          </p>
          {list.budgetCents !== null && <Bar part={spent} whole={list.budgetCents} over={over} />}
        </div>
      </header>

      {!me && !savedName && (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) void join(name.trim());
          }}
        >
          <input
            className={input}
            aria-label="Your name"
            placeholder="Your name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" className={primary}>
            Join
          </button>
        </form>
      )}
      <Notice text={notice} />

      <nav className="flex flex-wrap gap-2" aria-label="Pages">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-current={tab === key ? "page" : undefined}
            className={`rounded-full px-4 py-2 text-lg font-semibold ${
              tab === key ? "bg-emerald-700 text-white" : "bg-zinc-200"
            }`}
            // pushState keeps this component (and the PayPal session) mounted across pages.
            onClick={() => window.history.pushState(null, "", `?tab=${key}`)}
          >
            {label}
          </button>
        ))}
        <Link href="/history" className="rounded-full bg-zinc-200 px-4 py-2 text-lg font-semibold">
          History
        </Link>
      </nav>

      {/* Progress stays mounted so a PayPal payment in flight survives a look at another page. */}
      <div hidden={tab !== "progress"} className="flex flex-col gap-5">
        <Progress {...pageProps} clientId={clientId} />
      </div>
      {tab === "items" && <ItemsPage {...pageProps} lastPaid={lastPaid} />}
      {tab === "money" && <MoneyPage {...pageProps} />}
      {tab === "receipts" && <ReceiptsPage {...pageProps} />}
      {tab === "settle" && <SettlePage {...pageProps} />}
    </>
  );
}
