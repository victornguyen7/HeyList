"use client";

import Script from "next/script";
import { useRef, useState } from "react";
import type { PayPalSession } from "./paypal";

export type Item = { id: string; name: string; priceCents: number };

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

async function createOrder(itemIds: string[]): Promise<{ orderId: string }> {
  const response = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ itemIds }),
  });
  if (!response.ok) throw new Error(`Create order failed: ${response.status}`);
  return response.json();
}

export default function CheckoutList({ clientId, items }: { clientId: string; items: Item[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  // Item ID -> the PayPal order that paid for it. The order is the proof.
  const [paid, setPaid] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);
  const session = useRef<PayPalSession | null>(null);
  // The items in the order being paid, so changing ticks mid-payment cannot change what is marked paid.
  const pending = useRef<string[]>([]);

  async function onApprove({ orderId }: { orderId: string }) {
    // A capture that fails here may still have gone through at PayPal, so this never says "not charged".
    const unconfirmed =
      "The payment could not be confirmed. Please check your PayPal account before trying again.";
    try {
      const response = await fetch(`/api/orders/${orderId}/capture`, { method: "POST" });
      const result = await response.json();
      if (response.ok && result.status === "COMPLETED") {
        const items = pending.current;
        setPaid((current) => ({
          ...current,
          ...Object.fromEntries(items.map((id) => [id, orderId])),
        }));
        setSelected((current) => current.filter((id) => !items.includes(id)));
        setNotice("");
      } else if (result.error === "INSTRUMENT_DECLINED") {
        setNotice("Your payment method was declined. Please try another payment method.");
      } else {
        setNotice(unconfirmed);
      }
    } catch (error) {
      console.error(error);
      setNotice(unconfirmed);
    }
  }

  async function initPayPal() {
    try {
      const sdk = await window.paypal.createInstance({
        clientId,
        components: ["paypal-payments"],
        pageType: "checkout",
      });
      const methods = await sdk.findEligibleMethods({ currencyCode: "USD" });
      if (!methods.isEligible("paypal")) {
        setNotice("PayPal is not available here.");
        return;
      }
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
      setNotice("PayPal could not be loaded. Please refresh the page.");
    }
  }

  async function pay() {
    if (!session.current || selected.length === 0) return;
    setNotice("");
    pending.current = selected;
    try {
      // start() must receive the promise itself, not a function, and must run inside the click.
      await session.current.start({ presentationMode: "auto" }, createOrder(selected));
    } catch (error) {
      console.error(error);
      setNotice("The payment did not go through. Please try again.");
    }
  }

  // For display only. The backend computes the amount that is charged.
  const total = items
    .filter((item) => selected.includes(item.id))
    .reduce((sum, item) => sum + item.priceCents, 0);

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((other) => other !== id) : [...current, id],
    );
  }

  return (
    <>
      <Script src="https://www.sandbox.paypal.com/web-sdk/v6/core" onReady={() => void initPayPal()} />

      <ul className="flex flex-col gap-3">
        {items.map((item) => {
          const orderId = paid[item.id];
          return (
            <li key={item.id}>
              <label className="flex items-center gap-4 rounded-2xl border border-black/10 p-4 text-xl dark:border-white/15">
                <input
                  type="checkbox"
                  className="size-7"
                  checked={Boolean(orderId) || selected.includes(item.id)}
                  disabled={Boolean(orderId)}
                  onChange={() => toggle(item.id)}
                />
                <span className="flex-1">
                  <span className={orderId ? "line-through" : ""}>{item.name}</span>
                  {orderId && (
                    <span className="block text-base text-zinc-600 dark:text-zinc-400">
                      Paid with PayPal · order {orderId}
                    </span>
                  )}
                </span>
                <span>{dollars(item.priceCents)}</span>
              </label>
            </li>
          );
        })}
      </ul>

      <p className="text-xl font-semibold" aria-live="polite">
        {selected.length > 0 ? `Total: ${dollars(total)}` : "Tick the items you want to buy."}
      </p>

      <paypal-button
        type="pay"
        className="paypal-gold w-full"
        hidden={!ready || selected.length === 0}
        onClick={pay}
      />

      {notice && (
        <p role="alert" className="text-lg text-red-700 dark:text-red-400">
          {notice}
        </p>
      )}
    </>
  );
}
