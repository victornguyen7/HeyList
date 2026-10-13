"use client";

import Script from "next/script";
import { useRef, useState } from "react";
import type { PayPalSession } from "../../paypal";
import { type Draft, type Extra, type ListState, api, dollars, shrink } from "../../lib";
import { Bar, DraftEditor, Notice, PriceInput, TalkButton, card, input, primary, secondary, small } from "../../ui";

export type PageProps = { list: ListState; me: string | null; refresh: () => Promise<void> };

// What the AI read off a receipt, while the user is still confirming it. Nothing is checked off yet.
type Scan = {
  imagePath: string;
  totalCents: number | null;
  matches: { itemId: string; line: string; priceCents: number | null }[];
  extras: Extra[];
};

export default function Progress({ list, me, refresh, clientId }: PageProps & { clientId: string }) {
  const [ticked, setTicked] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);
  const session = useRef<PayPalSession | null>(null);
  // The items in the order being paid, so changing ticks mid-payment cannot change what is cleared.
  const pending = useRef<string[]>([]);

  const open = list.items.filter((item) => !item.checkedAt);
  const done = list.items.filter((item) => item.checkedAt);
  const chosen = open.filter((item) => ticked.includes(item.id));
  // For display only. The backend looks the prices up and computes what is charged.
  const chosenTotal = chosen.reduce((sum, item) => sum + (item.estPriceCents ?? 0), 0);
  const payable = chosen.length > 0 && chosen.every((item) => item.estPriceCents);
  const nameOf = (id: string | null) => list.members.find((member) => member.id === id)?.name;

  /** Runs one change against the backend, then reloads the list. */
  async function run(label: string, action: () => Promise<unknown>, failed: string) {
    setBusy(label);
    setNotice("");
    try {
      await action();
      await refresh();
    } catch {
      setNotice(failed);
    }
    setBusy("");
  }

  const addItems = (items: Draft[]) =>
    run(
      "Adding…",
      async () => {
        await api(`/lists/${list.id}/items`, { body: { items: items.filter((item) => item.name.trim()) } });
        setDrafts(null);
        setText("");
      },
      "The items could not be added. Please try again.",
    );

  // Voice: the AI splits what was said into items, and the user confirms them before they are added.
  async function heard(said: string) {
    setBusy("Listening to that…");
    setNotice("");
    try {
      const { items } = await api<{ items: Draft[] }>("/ai/items", { body: { text: said } });
      if (items.length) setDrafts(items);
      else setNotice("We did not catch any items. Please try again.");
    } catch {
      // Without the AI, what was said becomes one item the user can fix.
      setDrafts([{ name: said.slice(0, 120), estPriceCents: null }]);
    }
    setBusy("");
  }

  const markDone = () =>
    run(
      "Saving…",
      async () => {
        for (const item of chosen) {
          await api(`/items/${item.id}`, {
            method: "PATCH",
            body: { checked: true, memberId: me, priceCents: item.estPriceCents },
          });
        }
        setTicked([]);
      },
      "That could not be saved. Please try again.",
    );

  // Receipt: the AI reads the photo and proposes matches; the user confirms before anything is checked off.
  async function photographed(file: File | undefined) {
    if (!file) return;
    setBusy("Reading the receipt…");
    setNotice("");
    try {
      const image = await shrink(file);
      setScan(await api<Scan>(`/lists/${list.id}/receipts/scan`, { image }));
    } catch {
      setNotice("We could not read that receipt. Please try another photo.");
    }
    setBusy("");
  }

  const saveScan = (confirmed: Scan) =>
    run(
      "Saving…",
      async () => {
        await api(`/lists/${list.id}/receipts`, { body: { ...confirmed, memberId: me } });
        setScan(null);
        setTicked([]);
      },
      "The receipt could not be saved. Please try again.",
    );

  async function onApprove({ orderId }: { orderId: string }) {
    // A capture that fails here may still have gone through at PayPal, so this never says "not charged".
    const unconfirmed =
      "The payment could not be confirmed. Please check your PayPal account before trying again.";
    try {
      const result = await api<{ status: string }>(`/orders/${orderId}/capture`, { method: "POST" });
      if (result.status === "COMPLETED") {
        setTicked((current) => current.filter((id) => !pending.current.includes(id)));
        setNotice("");
      } else {
        setNotice(unconfirmed);
      }
    } catch (error) {
      setNotice(
        error instanceof Error && error.message === "INSTRUMENT_DECLINED"
          ? "Your payment method was declined. Please try another payment method."
          : unconfirmed,
      );
    }
    await refresh();
  }

  async function initPayPal() {
    try {
      const sdk = await window.paypal.createInstance({
        clientId,
        components: ["paypal-payments"],
        pageType: "checkout",
      });
      const methods = await sdk.findEligibleMethods({ currencyCode: "USD" });
      if (!methods.isEligible("paypal")) return;
      session.current = sdk.createPayPalOneTimePaymentSession({
        onApprove,
        onCancel: () => setNotice("The payment was cancelled. You can try again when you are ready."),
        onError: (error) => {
          console.error(error);
          setNotice("The payment did not go through. Please try again.");
        },
      });
      setReady(true);
    } catch (error) {
      console.error(error);
    }
  }

  async function pay() {
    if (!session.current || !payable) return;
    setNotice("");
    pending.current = chosen.map((item) => item.id);
    try {
      // start() must receive the promise itself, not a function, and must run inside the click.
      // Only item IDs are sent; the server looks up the prices (decision 23).
      await session.current.start(
        { presentationMode: "auto" },
        api<{ orderId: string }>(`/lists/${list.id}/orders`, {
          body: { itemIds: pending.current, memberId: me },
        }),
      );
    } catch (error) {
      console.error(error);
      setNotice("The payment did not go through. Please try again.");
    }
  }

  function toggle(id: string) {
    setTicked((current) => (current.includes(id) ? current.filter((other) => other !== id) : [...current, id]));
  }

  if (scan) {
    const itemName = (id: string) => list.items.find((item) => item.id === id)?.name ?? "";
    const extrasTotal = scan.extras.reduce((sum, extra) => sum + (extra.priceCents ?? 0), 0);
    return (
      <>
        <h2 className="text-2xl font-bold">Is this right?</h2>
        <p className="text-lg text-zinc-600">We read your receipt. Fix anything that is wrong, then confirm.</p>
        <Notice text={notice} />

        <section className="flex flex-col gap-2">
          <h3 className="text-xl font-semibold">On your list ({scan.matches.length})</h3>
          {scan.matches.length === 0 && <p className="text-lg">Nothing on the receipt matched your list.</p>}
          {scan.matches.map((match, index) => (
            <div key={match.itemId} className={`${card} flex items-center gap-2`}>
              <div className="min-w-0 flex-1">
                <p className="text-xl">{itemName(match.itemId)}</p>
                <p className="truncate text-base text-zinc-600">{match.line}</p>
                <button
                  type="button"
                  className="text-base underline"
                  onClick={() =>
                    setScan({
                      ...scan,
                      matches: scan.matches.filter((_, other) => other !== index),
                      extras: [...scan.extras, { name: match.line, priceCents: match.priceCents }],
                    })
                  }
                >
                  Not this item
                </button>
              </div>
              <PriceInput
                label={`Price of ${itemName(match.itemId)}`}
                cents={match.priceCents}
                onChange={(priceCents) =>
                  setScan({
                    ...scan,
                    matches: scan.matches.map((other, at) => (at === index ? { ...other, priceCents } : other)),
                  })
                }
              />
            </div>
          ))}
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-xl font-semibold">
            {scan.extras.length} not on the list, {dollars(extrasTotal)}
          </h3>
          {scan.extras.map((extra, index) => (
            <div key={index} className={`${card} flex items-center gap-2`}>
              <p className="min-w-0 flex-1 truncate text-lg">{extra.name}</p>
              <span className="text-lg">{extra.priceCents === null ? "" : dollars(extra.priceCents)}</span>
              <button
                type="button"
                aria-label={`Remove ${extra.name}`}
                className={small}
                onClick={() => setScan({ ...scan, extras: scan.extras.filter((_, other) => other !== index) })}
              >
                ✕
              </button>
            </div>
          ))}
        </section>

        {scan.totalCents !== null && <p className="text-xl font-semibold">Receipt total: {dollars(scan.totalCents)}</p>}
        <button type="button" className={primary} disabled={Boolean(busy)} onClick={() => saveScan(scan)}>
          {busy || "Confirm"}
        </button>
        <button type="button" className={secondary} disabled={Boolean(busy)} onClick={() => setScan(null)}>
          Cancel
        </button>
      </>
    );
  }

  if (drafts) {
    return (
      <>
        <h2 className="text-2xl font-bold">Add these?</h2>
        <DraftEditor drafts={drafts} onChange={setDrafts} />
        <Notice text={notice} />
        <button type="button" className={primary} disabled={Boolean(busy)} onClick={() => addItems(drafts)}>
          {busy || "Add to the list"}
        </button>
        <button type="button" className={secondary} disabled={Boolean(busy)} onClick={() => setDrafts(null)}>
          Cancel
        </button>
      </>
    );
  }

  return (
    <>
      {clientId && (
        <Script src="https://www.sandbox.paypal.com/web-sdk/v6/core" onReady={() => void initPayPal()} />
      )}

      <section className="flex flex-col gap-1">
        <p className="text-xl font-semibold">
          {done.length} of {list.items.length} done
        </p>
        <Bar part={done.length} whole={list.items.length} />
      </section>

      <ul className="flex flex-col gap-2">
        {open.map((item) => (
          <li key={item.id}>
            <label className={`${card} flex items-center gap-4 text-xl`}>
              <input
                type="checkbox"
                className="size-7"
                checked={ticked.includes(item.id)}
                onChange={() => toggle(item.id)}
              />
              <span className="min-w-0 flex-1">
                {item.name}
                {item.claimedBy && (
                  <span className="block text-base text-zinc-600">{nameOf(item.claimedBy)} will buy this</span>
                )}
              </span>
              {item.estPriceCents !== null && <span>{dollars(item.estPriceCents)}</span>}
            </label>
          </li>
        ))}
        {done.map((item) => (
          <li key={item.id} className={`${card} flex items-center gap-4 text-xl`}>
            <input type="checkbox" className="size-7" checked disabled aria-label={`${item.name}, done`} />
            <span className="min-w-0 flex-1">
              <span className="line-through">{item.name}</span>
              <span className="block text-base text-zinc-600">
                {item.orderId ? "Paid with PayPal" : item.receiptId ? "On a receipt" : "Done"}
                {nameOf(item.boughtBy) && ` · ${nameOf(item.boughtBy)}`}
              </span>
            </span>
            {item.priceCents !== null && <span>{dollars(item.priceCents)}</span>}
          </li>
        ))}
      </ul>

      <Notice text={notice} />
      {busy && <p className="text-xl" aria-live="polite">{busy}</p>}

      {chosen.length > 0 && (
        <section className={`${card} flex flex-col gap-3 border-2 border-emerald-700`}>
          <p className="text-xl font-semibold" aria-live="polite">
            {chosen.length} ticked{chosenTotal > 0 && ` · ${dollars(chosenTotal)}`}
          </p>
          <button type="button" className={secondary} disabled={Boolean(busy)} onClick={markDone}>
            I have these
          </button>
          {payable ? (
            <paypal-button type="pay" className="paypal-gold w-full" hidden={!ready} onClick={pay} />
          ) : (
            <p className="text-lg text-zinc-600">To pay with PayPal, every ticked item needs a price (see Items).</p>
          )}
        </section>
      )}

      <label className={`${secondary} text-center`}>
        Scan a receipt
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={Boolean(busy)}
          onChange={(event) => {
            void photographed(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </label>

      <section className="flex flex-col gap-3">
        <TalkButton onText={heard} label="Tap and say what to add" />
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (text.trim()) void addItems([{ name: text.trim(), estPriceCents: null }]);
          }}
        >
          <input
            className={input}
            aria-label="Add an item"
            placeholder="Add an item"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <button type="submit" className={primary} disabled={Boolean(busy) || !text.trim()}>
            Add
          </button>
        </form>
      </section>

      <button
        type="button"
        className={secondary}
        disabled={Boolean(busy)}
        onClick={() =>
          run(
            "Saving…",
            () => api(`/lists/${list.id}`, { method: "PATCH", body: { finished: !list.finishedAt } }),
            "That could not be saved. Please try again.",
          )
        }
      >
        {list.finishedAt ? "Finished · tap to reopen" : "Finish this list"}
      </button>
    </>
  );
}
