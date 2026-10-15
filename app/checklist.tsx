"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, usd, type Item, type List, type Member } from "./api";
import { ReceiptScan } from "./receipt-scan";
import { SplitPanel } from "./split";
import { Starter } from "./starter";

type Capture = { orderId: string; status: string };

const button = "h-14 rounded-full bg-foreground text-xl font-medium text-background disabled:opacity-40";

// Who "you" are on a list is remembered in this browser only; there are no accounts (decision 6).
const memberKey = (listId: string) => `heylist:member:${listId}`;
function storedMember(listId: string): string | null {
  try {
    return localStorage.getItem(memberKey(listId));
  } catch {
    return null;
  }
}

// The list page. The list ID lives in the URL (?list=), which is also where PayPal sends the buyer back,
// adding ?token=<order id>&PayerID=... after approval, or only ?token= after a cancel.
export function Checklist() {
  const router = useRouter();
  const params = useSearchParams();
  const listId = params.get("list");
  const orderId = params.get("token");
  const approved = params.has("PayerID");

  const [list, setList] = useState<List | null>(null);
  // Set on join, for browsers where localStorage is unavailable.
  const [joined, setJoined] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!listId) return;
    // The first load only fills an empty page: if a join or a change already set a newer list, a slow
    // response (dev compile, Strict Mode's second run) must not overwrite it.
    const load = () => api<List>(`/api/lists/${encodeURIComponent(listId)}`).then((loaded) => setList((current) => (current?.id === loaded.id ? current : loaded)));
    if (!orderId || !approved) {
      load().catch((e) => setStatus(`Could not load the list: ${e.message}`));
      return;
    }
    // Capture is idempotent on the backend, so a repeat (Strict Mode, refresh) returns the same result.
    api<Capture>(`/api/orders/${encodeURIComponent(orderId)}/capture`, { method: "POST" })
      .then(
        (result) =>
          setStatus(
            result.status === "COMPLETED"
              ? "Paid. Those items are checked off."
              : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`,
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
      setList({ ...list!, members: [...list!.members.filter((m) => m.id !== member.id), member] });
    } catch (err) {
      setStatus(`Could not add you: ${(err as Error).message}`);
    }
  }

  async function patchItem(item: Item, change: object) {
    try {
      const saved = await api<Item>(`/api/items/${item.id}`, { method: "PATCH", body: JSON.stringify(change) });
      setList((current) => current && { ...current, items: current.items.map((i) => (i.id === saved.id ? saved : i)) });
    } catch (err) {
      setStatus(`Could not save that change: ${(err as Error).message}`);
    }
  }

  async function assign() {
    try {
      setList(await api<List>(`/api/lists/${list!.id}/assign`, { method: "POST" }));
    } catch (err) {
      setStatus((err as Error).message);
    }
  }

  function toggle(id: string) {
    const next = new Set(selected);
    if (!next.delete(id)) next.add(id);
    setSelected(next);
  }

  async function pay() {
    setBusy(true);
    setStatus(null);
    try {
      const { approveUrl } = await api<{ approveUrl: string }>(`/api/lists/${list!.id}/orders`, {
        method: "POST",
        body: JSON.stringify({ itemIds: [...selected], memberId: me }),
      });
      window.location.assign(approveUrl);
    } catch (e) {
      setStatus(`Could not start checkout: ${(e as Error).message}`);
      setBusy(false);
    }
  }

  if (!listId) {
    return (
      <div className="flex w-full flex-col gap-6">
        <h1 className="text-3xl font-semibold">HeyList</h1>
        <Starter onCreated={(created) => router.push(`/?list=${created.id}`)} />
      </div>
    );
  }

  // A remembered member who is no longer on the list doesn't count.
  const remembered = joined ?? (list ? storedMember(list.id) : null);
  const me = list?.members.some((member) => member.id === remembered) ? remembered : null;
  const message = status ?? (orderId ? (approved ? "Confirming your payment…" : "Payment cancelled.") : null);
  const items = list?.items ?? [];
  const members = list?.members ?? [];
  const memberName = (id: string | null) => members.find((m) => m.id === id)?.name;
  const done = items.filter((item) => item.checkedAt).length;
  const total = items
    .filter((item) => selected.has(item.id) && !item.checkedAt)
    .reduce((sum, item) => sum + (item.estPriceCents ?? 0) * item.quantity, 0);

  return (
    <div className="flex w-full flex-col gap-6">
      <h1 className="text-3xl font-semibold">{list?.title ?? "HeyList"}</h1>

      {message && (
        <p role="status" className="rounded-lg bg-zinc-100 p-4 text-lg dark:bg-zinc-900">
          {message}
        </p>
      )}

      {list && (
        <>
          <progress className="h-3 w-full" value={done} max={items.length || 1} aria-label={`${done} of ${items.length} done`} />

          {me ? (
            <p className="text-lg">You are {memberName(me)}. People: {members.map((m) => m.name).join(", ")}</p>
          ) : (
            <form onSubmit={join} className="flex gap-2">
              <input
                className="h-14 flex-1 rounded-lg border border-zinc-300 px-4 text-xl dark:border-zinc-700 dark:bg-zinc-950"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                aria-label="Your name"
                maxLength={40}
                required
              />
              <button type="submit" className="h-14 rounded-full bg-foreground px-6 text-xl font-medium text-background">
                Join
              </button>
            </form>
          )}

          <ul className="flex flex-col gap-2">
            {items.map((item) => {
              const isDone = Boolean(item.checkedAt);
              const priced = item.estPriceCents !== null;
              return (
                <li key={item.id} className="flex flex-col gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-xl dark:border-zinc-800">
                  <div className="flex min-h-12 items-center gap-4">
                    <label className="flex flex-1 cursor-pointer items-center gap-4">
                      <input
                        type="checkbox"
                        className="size-6"
                        checked={isDone || selected.has(item.id)}
                        disabled={isDone || !priced || busy}
                        onChange={() => toggle(item.id)}
                      />
                      <span className={isDone ? "line-through opacity-60" : ""}>{item.name}</span>
                    </label>
                    {!isDone && (
                      <span className="flex items-center gap-2">
                        <button
                          type="button"
                          aria-label={`One fewer ${item.name}`}
                          disabled={busy || item.quantity <= 1}
                          onClick={() => patchItem(item, { quantity: item.quantity - 1 })}
                          className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                        >
                          −
                        </button>
                        <span aria-live="polite" className="w-6 text-center tabular-nums">
                          {item.quantity}
                        </span>
                        <button
                          type="button"
                          aria-label={`One more ${item.name}`}
                          disabled={busy || item.quantity >= 99}
                          onClick={() => patchItem(item, { quantity: item.quantity + 1 })}
                          className="size-10 rounded-full border border-zinc-300 dark:border-zinc-700"
                        >
                          +
                        </button>
                      </span>
                    )}
                    <span className="tabular-nums">
                      {isDone ? usd(item.priceCents ?? 0) : priced ? usd(item.estPriceCents! * item.quantity) : "—"}
                    </span>
                  </div>
                  {isDone ? (
                    <span className="text-base opacity-70">
                      {item.orderId ? "Paid with PayPal" : item.receiptId ? "On a receipt" : "Checked off"}
                      {memberName(item.boughtBy) && ` by ${memberName(item.boughtBy)}`}
                    </span>
                  ) : (
                    members.length > 0 && (
                      <select
                        aria-label={`Who buys ${item.name}`}
                        className="h-11 rounded-lg border border-zinc-300 px-2 text-lg dark:border-zinc-700 dark:bg-zinc-950"
                        value={item.claimedBy ?? ""}
                        onChange={(e) => patchItem(item, { claimedBy: e.target.value || null })}
                      >
                        <option value="">Nobody yet</option>
                        {members.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name} buys it
                          </option>
                        ))}
                      </select>
                    )
                  )}
                </li>
              );
            })}
          </ul>

          {members.length > 0 && items.some((item) => !item.checkedAt && !item.claimedBy) && (
            <button type="button" onClick={assign} className="h-14 rounded-full border-2 border-foreground text-xl font-medium">
              Share out the rest evenly
            </button>
          )}

          <button type="button" onClick={pay} disabled={total === 0 || busy} className={button}>
            {busy ? "Opening PayPal…" : `Pay ${usd(total)} with PayPal`}
          </button>

          <ReceiptScan list={list} memberId={me} onDone={setList} />
          <SplitPanel list={list} />
        </>
      )}
    </div>
  );
}
