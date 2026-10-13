"use client";

import { useState } from "react";
import { type Item, type ListState, api, dollars } from "../../lib";
import { Bar, Notice, PriceInput, card, input, secondary, small } from "../../ui";
import type { PageProps } from "./progress";

const nameOf = (list: ListState, id: string | null) =>
  list.members.find((member) => member.id === id)?.name ?? "Someone";

/** One change against the backend, then a reload; returns a message to show if it failed. */
function useChange(refresh: () => Promise<void>) {
  const [notice, setNotice] = useState("");
  async function change(action: () => Promise<unknown>) {
    setNotice("");
    try {
      await action();
      await refresh();
    } catch (error) {
      setNotice(
        error instanceof Error && error.message === "ITEM_PAID"
          ? "This item was paid with PayPal, so it cannot be changed."
          : "That could not be saved. Please try again.",
      );
    }
  }
  return { notice, setNotice, change };
}

export function ItemsPage({ list, me, refresh, lastPaid }: PageProps & { lastPaid: Record<string, number> }) {
  const { notice, setNotice, change } = useChange(refresh);
  const patch = (item: Item, body: object) => change(() => api(`/items/${item.id}`, { method: "PATCH", body }));

  return (
    <>
      <Notice text={notice} />
      {list.items.length === 0 && <p className="text-xl">No items yet. Add some on the Progress page.</p>}
      <ul className="flex flex-col gap-3">
        {list.items.map((item) => {
          const remembered = lastPaid[item.name.trim().toLowerCase()];
          return (
            <li key={item.id} className={`${card} flex flex-col gap-2`}>
              <div className="flex items-center justify-between gap-2">
                <p className={`text-xl font-semibold ${item.checkedAt ? "line-through" : ""}`}>{item.name}</p>
                <span
                  className={`rounded-full px-3 py-1 text-base ${item.checkedAt ? "bg-emerald-100" : "bg-zinc-200"}`}
                >
                  {item.checkedAt ? "Done" : "Open"}
                </span>
              </div>

              {item.checkedAt ? (
                <>
                  <div className="flex items-center justify-between gap-2 text-lg">
                    <span>{item.boughtBy ? `${nameOf(list, item.boughtBy)} paid` : "Paid"}</span>
                    {item.orderId ? (
                      <span>{dollars(item.priceCents ?? 0)}</span>
                    ) : (
                      <PriceInput
                        label={`Price paid for ${item.name}`}
                        cents={item.priceCents}
                        onChange={(priceCents) => patch(item, { checked: true, memberId: item.boughtBy, priceCents })}
                      />
                    )}
                  </div>
                  {/* The proof: the PayPal order, or the receipt photo. */}
                  {item.orderId && <p className="text-base text-zinc-600">Proof: PayPal order {item.orderId}</p>}
                  {item.receiptId && (
                    <a
                      className="text-base underline"
                      href={`/api/receipts/${item.receiptId}/image`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Proof: see the receipt
                    </a>
                  )}
                  {!item.orderId && (
                    <button type="button" className={`${small} self-start`} onClick={() => patch(item, { checked: false })}>
                      Not done after all
                    </button>
                  )}
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-2 text-lg">
                    <span>Suggested price</span>
                    <PriceInput
                      label={`Suggested price of ${item.name}`}
                      cents={item.estPriceCents}
                      onChange={(estPriceCents) => patch(item, { estPriceCents })}
                    />
                  </div>
                  {remembered !== undefined && (
                    <p className="text-base text-zinc-600">Last time you paid {dollars(remembered)} for this.</p>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    {item.claimedBy ? (
                      <>
                        <span className="text-lg">{nameOf(list, item.claimedBy)} will buy this</span>
                        {item.claimedBy === me && (
                          <button type="button" className={small} onClick={() => patch(item, { claimedBy: null })}>
                            Let someone else
                          </button>
                        )}
                      </>
                    ) : (
                      <button
                        type="button"
                        className={small}
                        onClick={() =>
                          me ? patch(item, { claimedBy: me }) : setNotice("Add your name at the top first.")
                        }
                      >
                        I&apos;ll buy this
                      </button>
                    )}
                    <button
                      type="button"
                      className={small}
                      onClick={() => change(() => api(`/items/${item.id}`, { method: "DELETE" }))}
                    >
                      Remove
                    </button>
                  </div>
                </>
              )}
            </li>
          );
        })}
      </ul>
      {list.members.length > 1 && list.items.some((item) => !item.checkedAt && !item.claimedBy) && (
        <button
          type="button"
          className={secondary}
          onClick={() => change(() => api(`/lists/${list.id}/assign`, { method: "POST" }))}
        >
          Share out the unclaimed items
        </button>
      )}
    </>
  );
}

export function MoneyPage({ list, refresh }: PageProps) {
  const { notice, change } = useChange(refresh);
  const { spentCents, extrasCents, perPerson } = list.money;
  const total = spentCents + extrasCents;
  const toBuy = list.items
    .filter((item) => !item.checkedAt)
    .reduce((sum, item) => sum + (item.estPriceCents ?? 0), 0);
  const over = list.budgetCents !== null && total > list.budgetCents;
  const extras = list.receipts.flatMap((receipt) => receipt.extras);

  return (
    <>
      <Notice text={notice} />
      <section className={`${card} flex flex-col gap-3`}>
        <div className="flex items-center justify-between gap-2 text-xl font-semibold">
          Budget
          <PriceInput
            label="Budget"
            cents={list.budgetCents}
            onChange={(budgetCents) =>
              change(() => api(`/lists/${list.id}`, { method: "PATCH", body: { budgetCents } }))
            }
          />
        </div>
        {list.budgetCents !== null && <Bar part={total} whole={list.budgetCents} over={over} />}
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-lg">
          <dt>Spent on list items</dt>
          <dd className="text-right">{dollars(spentCents)}</dd>
          <dt>Extras (not on the list)</dt>
          <dd className="text-right">{dollars(extrasCents)}</dd>
          <dt className="font-semibold">Spent so far</dt>
          <dd className="text-right font-semibold">{dollars(total)}</dd>
          <dt>Still to buy (estimate)</dt>
          <dd className="text-right">{dollars(toBuy)}</dd>
          {list.budgetCents !== null && (
            <>
              <dt className={over ? "font-semibold text-red-700" : ""}>{over ? "Over budget by" : "Left in budget"}</dt>
              <dd className={`text-right ${over ? "font-semibold text-red-700" : ""}`}>
                {dollars(Math.abs(list.budgetCents - total))}
              </dd>
            </>
          )}
        </dl>
      </section>

      {extras.length > 0 && (
        <section className={`${card} flex flex-col gap-1`}>
          <h2 className="text-xl font-semibold">
            {extras.length} extras, {dollars(extrasCents)}
          </h2>
          {extras.map((extra, index) => (
            <p key={index} className="flex justify-between gap-2 text-lg">
              <span className="min-w-0 truncate">{extra.name}</span>
              <span>{extra.priceCents === null ? "" : dollars(extra.priceCents)}</span>
            </p>
          ))}
        </section>
      )}

      <section className={`${card} flex flex-col gap-1`}>
        <h2 className="text-xl font-semibold">Each person</h2>
        {perPerson.length === 0 && <p className="text-lg">Nobody has joined yet.</p>}
        {perPerson.map((person) => (
          <p key={person.memberId} className="flex justify-between gap-2 text-lg">
            <span>{nameOf(list, person.memberId)}</span>
            <span>
              {dollars(person.spentCents)}
              {person.extrasCents > 0 && ` + ${dollars(person.extrasCents)} extras`}
            </span>
          </p>
        ))}
      </section>
    </>
  );
}

export function ReceiptsPage({ list }: PageProps) {
  const when = (iso: string) => new Date(iso).toLocaleDateString();

  return (
    <>
      {list.receipts.length + list.orders.length === 0 && (
        <p className="text-xl">No proof yet. Scan a receipt or pay with PayPal on the Progress page.</p>
      )}

      {list.orders.map((order) => (
        <section key={order.id} className={`${card} flex flex-col gap-1`}>
          <h2 className="flex justify-between gap-2 text-xl font-semibold">
            <span>PayPal order</span>
            <span>{dollars(order.totalCents)}</span>
          </h2>
          <p className="text-base text-zinc-600">
            {order.id} · {when(order.capturedAt)}
            {order.memberId && ` · ${nameOf(list, order.memberId)}`}
          </p>
          {list.items
            .filter((item) => item.orderId === order.id)
            .map((item) => (
              <p key={item.id} className="flex justify-between gap-2 text-lg">
                <span>{item.name}</span>
                <span>{dollars(item.priceCents ?? 0)}</span>
              </p>
            ))}
        </section>
      ))}

      {list.receipts.map((receipt) => (
        <section key={receipt.id} className={`${card} flex flex-col gap-1`}>
          <h2 className="flex justify-between gap-2 text-xl font-semibold">
            <span>Receipt</span>
            <span>{receipt.totalCents === null ? "" : dollars(receipt.totalCents)}</span>
          </h2>
          <p className="text-base text-zinc-600">
            {when(receipt.createdAt)}
            {receipt.memberId && ` · ${nameOf(list, receipt.memberId)}`}
          </p>
          {/* A plain <img>: the photo is private and served by the backend, so next/image cannot optimise it. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api/receipts/${receipt.id}/image`}
            alt="Photo of the receipt"
            loading="lazy"
            className="my-2 max-h-96 w-full rounded-xl object-contain"
          />
          {list.items
            .filter((item) => item.receiptId === receipt.id)
            .map((item) => (
              <p key={item.id} className="flex justify-between gap-2 text-lg">
                <span>{item.name}</span>
                <span>{item.priceCents === null ? "" : dollars(item.priceCents)}</span>
              </p>
            ))}
          {receipt.extras.map((extra, index) => (
            <p key={index} className="flex justify-between gap-2 text-lg text-zinc-600">
              <span className="min-w-0 truncate">Extra: {extra.name}</span>
              <span>{extra.priceCents === null ? "" : dollars(extra.priceCents)}</span>
            </p>
          ))}
        </section>
      ))}
    </>
  );
}

export function SettlePage({ list, refresh }: PageProps) {
  const { notice, change } = useChange(refresh);
  const { owes } = list.money;

  return (
    <>
      <Notice text={notice} />
      {list.members.length < 2 ? (
        <p className="text-xl">Share this list first. When others join and buy things, you can settle up here.</p>
      ) : owes.length === 0 ? (
        <p className="text-xl">Everyone is even. Nobody owes anything.</p>
      ) : (
        <p className="text-lg text-zinc-600">
          What was spent on list items is split equally between {list.members.length} people. Extras are not split.
        </p>
      )}

      {owes.map((owed) => (
        <section key={`${owed.from}-${owed.to}`} className={`${card} flex flex-col gap-2`}>
          <p className="text-xl font-semibold">
            {nameOf(list, owed.from)} owes {nameOf(list, owed.to)} {dollars(owed.amountCents)}
          </p>
        </section>
      ))}

      {list.members.length > 0 && (
        <section className={`${card} flex flex-col gap-3`}>
          <h2 className="text-xl font-semibold">Emails for PayPal invoices</h2>
          {list.members.map((member) => (
            <label key={member.id} className="flex flex-col gap-1 text-lg">
              {member.name}
              <input
                key={member.email ?? "none"}
                type="email"
                className={input}
                placeholder="name@example.com"
                defaultValue={member.email ?? ""}
                onBlur={(event) => {
                  const email = event.target.value.trim();
                  if (email && email !== member.email) {
                    void change(() =>
                      api(`/lists/${list.id}/members`, { body: { name: member.name, email } }),
                    );
                  }
                }}
              />
            </label>
          ))}
        </section>
      )}
    </>
  );
}
