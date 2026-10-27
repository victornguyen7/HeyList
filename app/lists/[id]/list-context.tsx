"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, use, useEffect, useState } from "react";
import { api, refundNote, rememberList, type List, type Member } from "../../api";
import { Avatar, button, card } from "../../ui";

type Capture = { orderId: string; status: string; refundedCents: number };
type Ctx = {
  list: List;
  setList: (list: List | ((current: List) => List)) => void;
  me: string | null;
  memberName: (id: string | null) => string | undefined;
  setStatus: (status: string | null) => void;
};

const ListContext = createContext<Ctx | null>(null);
export const useList = () => use(ListContext)!;

export { button, buttonAi, buttonGlass as outline, card, field, row } from "../../ui";

// Tabs, with the colour each one takes when active on the phone tab bar (Figma "Tab bar").
const TABS = [
  ["", "Progress", "text-list"],
  ["/items", "Items", "text-list"],
  ["/money", "Money", "text-money"],
  ["/receipts", "Receipts", "text-ai"],
  ["/settle", "Settle up", "text-money"],
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
  const router = useRouter();
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
    // Capture is idempotent on the backend for a while, so a repeat (Strict Mode) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(
        (result) =>
          setStatus(
            result.status === "COMPLETED"
              ? `Paid. Those items are checked off.${refundNote(result.refundedCents)}`
              : result.status === "PENDING"
                ? "PayPal is still processing this payment. The items are held as pending until it goes through."
                : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`,
          ),
        (e) => setStatus(`Payment could not be confirmed: ${e.message}`),
      )
      // Drop ?token=&PayerID= so a reload or a shared link doesn't capture again after PayPal's idempotency
      // window, which would report a failure for an order already paid. The effect then runs again and loads the list.
      .then(() => router.replace(`/lists/${listId}`, { scroll: false }));
  }, [listId, orderId, approved, router]);

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

  async function share() {
    const url = `${window.location.origin}${base}`;
    try {
      if (navigator.share) await navigator.share({ title: list?.title, url });
      else {
        await navigator.clipboard.writeText(url);
        setStatus("Link copied. Anyone with it can join this list.");
      }
    } catch {
      // Closing the share sheet is not an error.
    }
  }

  const tabs = TABS.map(([path, label, color]) => ({ href: base + path, label, color, active: pathname === base + path }));
  const shareButton = (
    <button type="button" onClick={share} className="glass rounded-[18px] bg-surface-2 px-3.5 py-2 text-sm font-medium lg:px-5 lg:py-[13px]">
      Share link
    </button>
  );

  return (
    <div className="flex w-full flex-col gap-3.5 lg:gap-7">
      <div className="flex items-center justify-between lg:hidden">
        <Link href="/" className="text-base font-medium text-muted">
          ← Lists
        </Link>
        {shareButton}
      </div>

      <header className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-2.5">
          <Link href="/" className="hidden text-[15px] text-muted lg:block">
            ← My lists
          </Link>
          <h1 className="text-[32px] tracking-[-0.015em] lg:text-[48px] lg:font-medium">{list?.title ?? "Loading…"}</h1>
          {list && list.members.length > 0 && (
            <div className="flex items-center gap-2.5">
              <span className="flex pr-2.5">
                {list.members.map((m) => (
                  <Avatar key={m.id} name={m.name} ring />
                ))}
              </span>
              <span className="text-sm font-medium text-muted">
                {list.members.length} {list.members.length === 1 ? "person" : "people"}
                {me && ` · you are ${list.members.find((m) => m.id === me)?.name}`}
              </span>
            </div>
          )}
        </div>
        {/* Website tabs (Figma "Web tabs"): the active one is a raised frosted pill. */}
        <div className="hidden items-center gap-3 lg:flex">
          <nav className="glass flex gap-1 rounded-full p-[5px]" aria-label="List pages">
            {tabs.map((tab) => (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={tab.active ? "page" : undefined}
                className={`rounded-full px-5 py-2.5 text-[15px] ${tab.active ? "bg-surface-2 font-medium shadow-[0_4px_14px_0_rgb(30_40_60/0.1)]" : "text-muted hover:text-text"}`}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
          {shareButton}
        </div>
      </header>

      {message && (
        <p role="status" className={`${card} text-base`}>
          {message}
        </p>
      )}

      {list && (
        <>
          {!me && (
            <form onSubmit={join} className={`${card} flex flex-col gap-3 sm:flex-row sm:items-center`}>
              <span className="text-base font-medium sm:flex-1">Join to claim, tick off and pay for items</span>
              <div className="flex gap-2">
                <input
                  className="h-12 min-w-0 flex-1 rounded-[20px] bg-bg px-4 text-base"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  aria-label="Your name"
                  maxLength={40}
                  required
                />
                <button type="submit" className={button}>
                  Join
                </button>
              </div>
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

      {/* Phone tab bar (Figma "Tab bar"): floating at the bottom, a dot over the active tab. */}
      <nav
        className="glass fixed inset-x-4 bottom-4 z-10 flex h-[68px] items-center justify-between rounded-[34px] bg-surface-2 px-[18px] shadow-[0_10px_15px_rgb(30_40_60/0.1)] lg:hidden"
        aria-label="List pages"
      >
        {tabs.map((tab) => (
          <Link key={tab.href} href={tab.href} aria-current={tab.active ? "page" : undefined} className={`flex flex-col items-center gap-[5px] text-[13px] font-medium ${tab.active ? tab.color : "text-muted"}`}>
            <span className={`size-1.5 rounded-full ${tab.active ? "bg-current" : ""}`} />
            {tab.label === "Settle up" ? "Settle" : tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
