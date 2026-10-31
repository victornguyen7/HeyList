"use client";

import { useEffect, useRef, useState } from "react";
import { payPayPal, payVenmo } from "./ui";

// PayPal and, where the buyer can use it, Venmo, from the JS SDK v6 (decision 67). Payment happens in PayPal's pop-up
// on this page. The orders are still made and captured by HeyList's backend from its own prices (decision 21); the
// buttons only replace the trip to PayPal's page and back. Until the SDK is ready, or if it can't load or nothing is
// eligible, the children (the redirect checkout) show instead.
// The buttons are drawn in the soft glass style (Figma "Pay buttons") and start the SDK's payment session on click,
// in place of the SDK's fixed-width yellow and blue <paypal-button> and <venmo-button>.

type Method = "paypal" | "venmo";
type SessionOptions = { onApprove: (data: { orderId: string }) => Promise<void>; onCancel?: () => void; onError?: (error: Error) => void };
type Session = { start: (options: { presentationMode: "auto" }, order: Promise<{ orderId: string }>) => Promise<void> };
type Instance = {
  findEligibleMethods: (options: { currencyCode: string }) => Promise<{ isEligible: (method: string) => boolean }>;
  createPayPalOneTimePaymentSession: (options: SessionOptions) => Session;
  createVenmoOneTimePaymentSession: (options: SessionOptions) => Session;
};

declare global {
  interface Window {
    paypal?: { createInstance: (options: { clientId: string; components: string[]; pageType?: string }) => Promise<Instance> };
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
    .then(() => window.paypal!.createInstance({ clientId, components: ["paypal-payments", "venmo-payments"], pageType: "checkout" }))
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
  children,
}: {
  /** Asks the backend for an order and returns its ID; throws (after saying why) when it can't. */
  createOrder: (method: Method) => Promise<string>;
  /** Captures the approved order. */
  onApproved: (orderId: string) => Promise<void>;
  onError: (message: string) => void;
  children: React.ReactNode;
}) {
  const [sessions, setSessions] = useState<Partial<Record<Method, Session>> | null>(null);
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
        const eligible = await instance.findEligibleMethods({ currencyCode: "USD" });
        const options: SessionOptions = {
          onApprove: ({ orderId }) => handlers.current.onApproved(orderId),
          onCancel: () => handlers.current.onError("Payment cancelled."),
          onError: (error) => handlers.current.onError(`PayPal couldn't finish the payment: ${error.message}`),
        };
        const found: Partial<Record<Method, Session>> = {};
        if (eligible.isEligible("paypal")) found.paypal = instance.createPayPalOneTimePaymentSession(options);
        // Venmo: US buyers, in USD, where PayPal says this buyer can use it.
        if (eligible.isEligible("venmo")) found.venmo = instance.createVenmoOneTimePaymentSession(options);
        if (live && (found.paypal || found.venmo)) setSessions(found);
      })
      .catch(() => {
        // Eligibility failed: the redirect checkout stays.
      });
    return () => {
      live = false;
    };
  }, []);

  if (!sessions) return <>{children}</>;

  function start(method: Method) {
    // The order is asked for at the click, as PayPal's sample does, so the pop-up opens at once.
    const order = handlers.current.createOrder(method).then((orderId) => ({ orderId }));
    sessions![method]!.start({ presentationMode: "auto" }, order).catch(() => {
      // createOrder already said what went wrong; anything else comes through onError.
    });
  }

  return (
    <div className="flex gap-2.5">
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
    </div>
  );
}
