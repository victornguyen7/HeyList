"use client";

import { useEffect, useRef, useState } from "react";
import { payPayPal, payVenmo } from "./ui";

// PayPal and, where the buyer can use it, Venmo, from the JS SDK v6 (decision 67). Payment happens in PayPal's pop-up
// on this page. The orders are still made and captured by HeyList's backend from its own prices (decision 21); the
// buttons only replace the trip to PayPal's page and back. Until the SDK is ready, or if it can't load or nothing is
// eligible, the children (the redirect checkout) show instead.
// The buttons are drawn in the soft glass style (Figma "Pay buttons") and start the SDK's payment session on click,
// in place of the SDK's fixed-width yellow and blue <paypal-button> and <venmo-button>.
// Pay Later (decision 78): where PayPal says this buyer and amount qualify, a third button pays the same order in
// instalments, and PayPal's own message under the buttons says what that would be ("Pay in 4…"). The order is the
// same PayPal order as the PayPal button's; PayPal pays HeyList in full, so nothing about capture or the split
// changes.

// What the backend's order routes know: Pay Later is a PayPal order.
type Method = "paypal" | "venmo";
type Button = Method | "paylater";
type SessionOptions = { onApprove: (data: { orderId: string }) => Promise<void>; onCancel?: () => void; onError?: (error: Error) => void };
type Session = { start: (options: { presentationMode: "auto" }, order: Promise<{ orderId: string }>) => Promise<void> };
type Instance = {
  findEligibleMethods: (options: { currencyCode: string; amount?: string }) => Promise<Eligible>;
  createPayPalOneTimePaymentSession: (options: SessionOptions) => Session;
  createVenmoOneTimePaymentSession: (options: SessionOptions) => Session;
  createPayLaterOneTimePaymentSession: (options: SessionOptions) => Session;
  createPayPalMessages: () => unknown;
};
type Eligible = { isEligible: (method: string) => boolean; getDetails: (method: string) => { productCode?: string; countryCode?: string } | undefined };

declare global {
  interface Window {
    paypal?: { createInstance: (options: { clientId: string; components: string[]; pageType?: string }) => Promise<Instance> };
  }
}

// PayPal's Pay Later message, a web component the SDK defines once createPayPalMessages() has run.
declare module "react" {
  // eslint-disable-next-line @typescript-eslint/no-namespace -- how React's types take a custom element
  namespace JSX {
    interface IntrinsicElements {
      "paypal-message": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        "auto-bootstrap"?: boolean;
        amount?: string;
        "currency-code"?: string;
        "text-color"?: string;
        "logo-type"?: string;
      };
    }
  }
}

// Sandbox only (decision 17), like the backend.
const SDK_URL = "https://www.sandbox.paypal.com/web-sdk/v6/core";
let loading: Promise<Instance | null> | null = null;

/** The SDK, loaded once per visit. null when there's no client ID or it can't load; a later call tries again. */
function sdk(): Promise<Instance | null> {
  const clientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID;
  if (!clientId) return Promise.resolve(null);
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SDK_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("The PayPal SDK did not load"));
    document.head.appendChild(script);
  })
    .then(() => window.paypal!.createInstance({ clientId, components: ["paypal-payments", "venmo-payments", "paypal-messages"], pageType: "checkout" }))
    .then((instance) => {
      // Defines <paypal-message>; a failure here only loses the message, never the buttons.
      try {
        instance.createPayPalMessages();
      } catch {}
      return instance;
    })
    .catch(() => {
      loading = null;
      return null;
    });
  return loading;
}

export function PayPalButtons({
  createOrder,
  onApproved,
  onError,
  amountCents,
  children,
}: {
  /** Asks the backend for an order and returns its ID; throws (after saying why) when it can't. */
  createOrder: (method: Method) => Promise<string>;
  /** Captures the approved order. */
  onApproved: (orderId: string) => Promise<void>;
  onError: (message: string) => void;
  /** What the order will charge. Pay Later's eligibility and message depend on it; without it there's no Pay Later. */
  amountCents?: number;
  children: React.ReactNode;
}) {
  const [sessions, setSessions] = useState<Partial<Record<Button, Session>> | null>(null);
  const amount = amountCents ? (amountCents / 100).toFixed(2) : undefined;
  // The latest callbacks, for sessions made once.
  const handlers = useRef({ createOrder, onApproved, onError });
  useEffect(() => {
    handlers.current = { createOrder, onApproved, onError };
  });

  useEffect(() => {
    let live = true;
    sdk()
      .then(async (instance) => {
        if (!instance) return;
        const eligible = await instance.findEligibleMethods({ currencyCode: "USD", ...(amount ? { amount } : {}) });
        const options: SessionOptions = {
          onApprove: ({ orderId }) => handlers.current.onApproved(orderId),
          onCancel: () => handlers.current.onError("Payment cancelled."),
          onError: (error) => handlers.current.onError(`PayPal couldn't finish the payment: ${error.message}`),
        };
        const found: Partial<Record<Button, Session>> = {};
        if (eligible.isEligible("paypal")) found.paypal = instance.createPayPalOneTimePaymentSession(options);
        // Venmo: US buyers, in USD, where PayPal says this buyer can use it.
        if (eligible.isEligible("venmo")) found.venmo = instance.createVenmoOneTimePaymentSession(options);
        // Pay Later: only for a known amount PayPal says qualifies, with the product it offers (as PayPal's v6 sample).
        const later = amount && eligible.isEligible("paylater") ? eligible.getDetails("paylater") : undefined;
        if (later?.productCode && later.countryCode) found.paylater = instance.createPayLaterOneTimePaymentSession(options);
        if (live && (found.paypal || found.venmo)) setSessions(found);
      })
      .catch(() => {
        // Eligibility failed: the redirect checkout stays.
      });
    return () => {
      live = false;
    };
    // Again when the amount changes: Pay Later may start or stop qualifying.
  }, [amount]);

  if (!sessions) return <>{children}</>;

  function start(button: Button) {
    // The order is asked for at the click, as PayPal's sample does, so the pop-up opens at once.
    const order = handlers.current.createOrder(button === "venmo" ? "venmo" : "paypal").then((orderId) => ({ orderId }));
    sessions![button]!.start({ presentationMode: "auto" }, order).catch(() => {
      // createOrder already said what went wrong; anything else comes through onError.
    });
  }

  return (
    <div className="flex flex-wrap gap-2.5">
      {sessions.paypal && (
        <button type="button" onClick={() => start("paypal")} className={`${payPayPal} flex-1`}>
          Pay with PayPal
        </button>
      )}
      {sessions.venmo && (
        <button type="button" onClick={() => start("venmo")} className={`${payVenmo} flex-1`}>
          Venmo
        </button>
      )}
      {sessions.paylater && (
        <button type="button" onClick={() => start("paylater")} className={`${payVenmo} basis-full`}>
          Pay Later
        </button>
      )}
      {/* PayPal's own wording and terms for this amount; it draws nothing where Pay Later isn't offered. */}
      {sessions.paylater && amount && (
        <paypal-message auto-bootstrap amount={amount} currency-code="USD" text-color="MONOCHROME" logo-type="MONOGRAM" className="block basis-full text-center" />
      )}
    </div>
  );
}
