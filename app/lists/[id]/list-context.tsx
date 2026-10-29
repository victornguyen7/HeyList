"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, use, useEffect, useRef, useState } from "react";
import { api, cachedLists, cacheLists, captureMessage, memberKey, rememberList, rememberMember, type Capture, type List, type Member } from "../../api";
import { accountName, supabase, useSession } from "../../auth";
import { listChanged, onListChanged } from "../../realtime";
import { Avatar, button, card } from "../../ui";

type Ctx = {
  list: List;
  setList: (list: List | ((current: List) => List)) => void;
  me: string | null;
  memberName: (id: string | null) => string | undefined;
  setStatus: (status: string | null) => void;
  // Join as this name, or take back the guest member who already has it (a reminder link opened on a new phone).
  joinAs: (name: string) => Promise<void>;
  // Figma "Join card", or null once you've joined. Progress shows it where the pay card goes; Receipts above the scan.
  joinCard: React.ReactNode;
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

// Who "you" are on a list: for a guest, remembered in this browser only; logged in, the member with your account.
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
  // The saved copy shown while the fresh list loads; kept across effect runs so the load knows to replace it.
  const saved = useRef<List | null>(null);
  // Set on join, for browsers where localStorage is unavailable.
  const [joined, setJoined] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const session = useSession();
  const savedName = accountName(session);

  useEffect(() => {
    rememberList(listId);
    // The copy saved in this browser shows at once; the fresh load then replaces it.
    const cached = cachedLists().find((copy) => copy.id === listId);
    if (cached && saved.current?.id !== listId) {
      saved.current = cached;
      setListState((current) => (current?.id === listId ? current : cached));
    }
    // The fresh load fills an empty page or replaces the saved copy: if a join or a change already set a newer
    // list, a slow response (dev compile, Strict Mode's second run) must not overwrite it.
    const load = () =>
      api<List>(`/api/lists/${encodeURIComponent(listId)}`).then((loaded) => {
        cacheLists([loaded]);
        setListState((current) => (current?.id === loaded.id && current !== saved.current ? current : loaded));
      });
    if (!orderId || !approved) {
      load().catch((e) => setStatus(`Could not load the list: ${e.message}`));
      return;
    }
    // Capture is idempotent on the backend for a while, so a repeat (Strict Mode) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(
        (result) => setStatus(captureMessage(result)),
        (e) => setStatus(`Payment could not be confirmed: ${e.message}`),
      )
      // Drop ?token=&PayerID= so a reload or a shared link doesn't capture again after PayPal's idempotency
      // window, which would report a failure for an order already paid. The effect then runs again and loads the list.
      // Stays on the tab PayPal sent them back to (Settle up for a settle-up payment).
      .then(() => {
        listChanged(listId);
        router.replace(pathname, { scroll: false });
      });
  }, [listId, orderId, approved, router, pathname]);

  // Someone else's change, or coming back to the tab, reloads the list. Pings that arrive together cause one load.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const reload = () => {
      clearTimeout(timer);
      timer = setTimeout(
        () =>
          api<List>(`/api/lists/${encodeURIComponent(listId)}`)
            .then((loaded) => {
              cacheLists([loaded]);
              setListState(loaded);
            })
            .catch(() => {}),
        300,
      );
    };
    const onVisible = () => document.visibilityState === "visible" && reload();
    const stop = onListChanged(listId, reload);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(timer);
      stop();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [listId]);

  // Logged in with a saved name, the backend fills it in; otherwise the typed name is sent (and saved on the account).
  async function join(e: React.FormEvent) {
    e.preventDefault();
    await joinAs(savedName ? null : name);
  }

  async function joinAs(asName: string | null) {
    try {
      const member = await api<Member>(`/api/lists/${list!.id}/members`, { method: "POST", body: JSON.stringify(asName ? { name: asName } : {}) });
      if (session && !savedName) await supabase.auth.updateUser({ data: { name: member.name } });
      rememberMember(list!.id, member.id);
      setJoined(member.id);
      setListState({ ...list!, members: [...list!.members.filter((m) => m.id !== member.id), member] });
      listChanged(list!.id);
    } catch (err) {
      setStatus(`Could not add you: ${(err as Error).message}`);
    }
  }

  // A remembered member who is no longer on the list doesn't count.
  const remembered = joined ?? (list ? storedMember(list.id) : null);
  const me =
    list?.members.find((member) => session && member.userId === session.user.id)?.id ??
    // A remembered member who joined with an account only counts while logged in as it (found above).
    (list?.members.some((member) => member.id === remembered && !member.userId) ? remembered : null);
  const message = status ?? (orderId ? (approved ? "Confirming your payment…" : "Payment cancelled.") : null);
  const base = `/lists/${listId}`;
  // Joining is needed to claim, pay, tick and scan: the form shows where those happen (issue 34).
  const joinHere = pathname === base || pathname === `${base}/receipts`;

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
    <button type="button" onClick={share} className="glass shrink-0 rounded-[18px] bg-surface-2 px-3.5 py-2 text-sm font-medium whitespace-nowrap lg:px-5 lg:py-[13px]">
      Share link
    </button>
  );

  // The header (Figma v2): on the website the title has its own row with Share link beside it, and the tabs sit on
  // the row below, so a long title wraps instead of squeezing the tabs onto two lines.
  return (
    <div className="flex w-full flex-col gap-3.5 lg:gap-7">
      <div className="flex items-center justify-between lg:hidden">
        <Link href="/" className="text-base font-medium text-muted">
          ← Lists
        </Link>
        {shareButton}
      </div>

      <header className="flex flex-col gap-2 lg:gap-3">
        <Link href="/" className="hidden text-[15px] text-muted lg:block">
          ← My lists
        </Link>
        <div className="flex items-end justify-between gap-6">
          <h1 className="min-w-0 text-[32px] tracking-[-0.015em] break-words lg:text-[48px] lg:leading-tight lg:font-medium">{list?.title ?? "Loading…"}</h1>
          <span className="hidden lg:block">{shareButton}</span>
        </div>
        <div className="flex items-center justify-between gap-6">
          {list && list.members.length > 0 ? (
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="flex shrink-0 pr-2.5">
                {list.members.map((m) => (
                  <Avatar key={m.id} name={m.name} ring />
                ))}
              </span>
              <span className="text-sm font-medium text-muted">
                {list.members.length} {list.members.length === 1 ? "person" : "people"}
                {me ? ` · you are ${list.members.find((m) => m.id === me)?.name}` : " · you haven't joined"}
              </span>
            </div>
          ) : (
            <span />
          )}
          {/* Website tabs (Figma "Web tabs"): the active one is a raised frosted pill. */}
          <nav className="glass hidden shrink-0 gap-1 rounded-full p-[5px] lg:flex" aria-label="List pages">
            {tabs.map((tab) => (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={tab.active ? "page" : undefined}
                className={`rounded-full px-5 py-2.5 text-[15px] whitespace-nowrap ${tab.active ? "bg-surface-2 font-medium shadow-[0_4px_14px_0_rgb(30_40_60/0.1)]" : "text-muted hover:text-text"}`}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {message && (
        <p role="status" className={`${card} text-base whitespace-pre-line`}>
          {message}
        </p>
      )}

      {list && (
        <>
          {!me && !joinHere && (
            <Link href={base} className="text-[15px] text-ai underline underline-offset-4">
              Join this list to take part
            </Link>
          )}
          <ListContext
            value={{
              list,
              // Pages call this after a change they made, so the other open pages are told.
              setList: (next) => {
                setListState((current) => (typeof next === "function" ? next(current!) : next));
                listChanged(list.id);
              },
              me,
              memberName: (id) => list.members.find((m) => m.id === id)?.name,
              setStatus,
              joinAs,
              joinCard: me ? null : (
                <form onSubmit={join} className={`${card} flex flex-col gap-3 border-ai/35`}>
                  <span className="flex flex-col gap-0.5">
                    <span className="text-[17px] font-medium">Join this list</span>
                    <span className="text-sm text-muted">to claim, tick off and pay for items</span>
                  </span>
                  {savedName ? (
                    <button type="submit" className={button}>
                      Join as {savedName}
                    </button>
                  ) : (
                    <>
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
                        <button type="submit" className={`${button} px-7`}>
                          Join
                        </button>
                      </div>
                      {!session && (
                        <Link href={`/login?next=${encodeURIComponent(base)}`} className="text-[13px] text-ai">
                          Or log in with email, so you don&apos;t type your name next time
                        </Link>
                      )}
                    </>
                  )}
                </form>
              ),
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
