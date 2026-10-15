"use client";

import Link from "next/link";
import { useParams, usePathname, useSearchParams } from "next/navigation";
import { createContext, use, useEffect, useState } from "react";
import { api, rememberList, type List, type Member } from "../../api";

type Capture = { orderId: string; status: string };
type Ctx = {
  list: List;
  setList: (list: List | ((current: List) => List)) => void;
  me: string | null;
  memberName: (id: string | null) => string | undefined;
  setStatus: (status: string | null) => void;
};

const ListContext = createContext<Ctx | null>(null);
export const useList = () => use(ListContext)!;

export const button = "h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40";
export const outline = "h-14 rounded-full border-2 border-foreground text-xl font-medium disabled:opacity-40";
export const field = "h-14 rounded-lg border border-zinc-300 px-4 text-xl dark:border-zinc-700 dark:bg-zinc-950";
export const card = "rounded-lg border border-zinc-200 px-4 py-3 text-lg dark:border-zinc-800";

const TABS = [
  ["", "Progress"],
  ["/items", "Items"],
  ["/money", "Money"],
  ["/receipts", "Receipts"],
  ["/settle", "Settle up"],
] as const;

// Who "you" are on a list is remembered in this browser only; there are no accounts (decision 6).
const memberKey = (listId: string) => `heylist:member:${listId}`;
function storedMember(listId: string): string | null {
  try {
    return localStorage.getItem(memberKey(listId));
  } catch {
    return null;
  }
}

// Loads the list once for all its pages, and shows the title, tabs and join form above each one.
// PayPal sends the buyer back here with ?token=<order id>&PayerID=... after approval, or only ?token= after a cancel.
export function ListProvider({ children }: { children: React.ReactNode }) {
  const { id: listId } = useParams<{ id: string }>();
  const pathname = usePathname();
  const params = useSearchParams();
  const orderId = params.get("token");
  const approved = params.has("PayerID");

  const [list, setListState] = useState<List | null>(null);
  // Set on join, for browsers where localStorage is unavailable.
  const [joined, setJoined] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    rememberList(listId);
    // The first load only fills an empty page: if a join or a change already set a newer list, a slow
    // response (dev compile, Strict Mode's second run) must not overwrite it.
    const load = () => api<List>(`/api/lists/${encodeURIComponent(listId)}`).then((loaded) => setListState((current) => (current?.id === loaded.id ? current : loaded)));
    if (!orderId || !approved) {
      load().catch((e) => setStatus(`Could not load the list: ${e.message}`));
      return;
    }
    // Capture is idempotent on the backend, so a repeat (Strict Mode, refresh) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(
        (result) =>
          setStatus(
            result.status === "COMPLETED" ? "Paid. Those items are checked off." : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`,
          ),
        (e) => setStatus(`Payment could not be confirmed: ${e.message}`),
      )
      .then(load)
      .catch((e) => setStatus(`Could not load the list: ${e.message}`));
  }, [listId, orderId, approved]);

  async function join(e: React.FormEvent) {
    e.preventDefault();
    try {
      const member = await api<Member>(`/api/lists/${list!.id}/members`, { method: "POST", body: JSON.stringify({ name }) });
      try {
        localStorage.setItem(memberKey(list!.id), member.id);
      } catch {}
      setJoined(member.id);
      setListState({ ...list!, members: [...list!.members.filter((m) => m.id !== member.id), member] });
    } catch (err) {
      setStatus(`Could not add you: ${(err as Error).message}`);
    }
  }

  // A remembered member who is no longer on the list doesn't count.
  const remembered = joined ?? (list ? storedMember(list.id) : null);
  const me = list?.members.some((member) => member.id === remembered) ? remembered : null;
  const message = status ?? (orderId ? (approved ? "Confirming your payment…" : "Payment cancelled.") : null);
  const base = `/lists/${listId}`;

  return (
    <div className="flex w-full flex-col gap-6">
      <Link href="/" className="text-lg underline-offset-4 hover:underline">
        ← HeyList
      </Link>
      <h1 className="text-3xl font-semibold">{list?.title ?? "Loading…"}</h1>

      <nav className="-mx-1 flex gap-1 overflow-x-auto" aria-label="List pages">
        {TABS.map(([path, label]) => {
          const active = pathname === base + path;
          return (
            <Link
              key={path}
              href={base + path}
              aria-current={active ? "page" : undefined}
              className={`shrink-0 rounded-full px-4 py-2 text-lg ${active ? "bg-foreground text-background" : "hover:bg-zinc-100 dark:hover:bg-zinc-900"}`}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {message && (
        <p role="status" className="rounded-lg bg-zinc-100 p-4 text-lg dark:bg-zinc-900">
          {message}
        </p>
      )}

      {list && (
        <>
          {me ? (
            <p className="text-lg opacity-70">
              You are {list.members.find((m) => m.id === me)?.name}. People: {list.members.map((m) => m.name).join(", ")}
            </p>
          ) : (
            <form onSubmit={join} className="flex gap-2">
              <input className={`${field} min-w-0 flex-1`} value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" aria-label="Your name" maxLength={40} required />
              <button type="submit" className={`${button} px-6`}>
                Join
              </button>
            </form>
          )}
          <ListContext
            value={{
              list,
              setList: (next) => setListState((current) => (typeof next === "function" ? next(current!) : next)),
              me,
              memberName: (id) => list.members.find((m) => m.id === id)?.name,
              setStatus,
            }}
          >
            {children}
          </ListContext>
        </>
      )}
    </div>
  );
}
