"use client";

import { useEffect, useRef } from "react";

// What to tell someone whose trip to PayPal's checkout page ended without a payment. Nothing was charged, and nothing
// on the list changed.
export const BACK_FROM_PAYPAL = "The payment wasn't finished: you came back from PayPal before approving it, so nothing was paid. Try again when you're ready.";
export const PAYPAL_DID_NOT_OPEN = "PayPal didn't open, so nothing was paid. Try again.";

// How long the page may still be on screen after being sent to PayPal before it counts as not having gone.
const STALLED_MS = 8000;

/**
 * Sends the page to PayPal's checkout, and calls onBack(message) if the person ends up on this page again without
 * paying, so the button stops saying "Opening PayPal…" and the page says what happened. Two ways that happens:
 * - Back from PayPal's page restores this page from the browser's back/forward cache exactly as it was left, and no
 *   other code runs to reset it (pageshow with persisted).
 * - The navigation never finishes: PayPal is slow and the person presses Stop, or it fails. The page is still here and
 *   visible some seconds later.
 * PayPal's own "Cancel and return" link loads the page fresh (?token= only), which the list page reports as
 * "Payment cancelled."
 */
export function usePayPalRedirect(onBack: (message: string) => void) {
  const leaving = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(onBack);
  useEffect(() => {
    latest.current = onBack;
  });
  useEffect(() => {
    const stop = () => {
      leaving.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
    function shown(e: PageTransitionEvent) {
      if (!e.persisted || !leaving.current) return;
      stop();
      latest.current(BACK_FROM_PAYPAL);
    }
    window.addEventListener("pageshow", shown);
    return () => {
      window.removeEventListener("pageshow", shown);
      stop();
    };
  }, []);
  return (url: string) => {
    leaving.current = true;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      // Hidden means the page is on its way out (or in the back/forward cache, where pageshow reports it): wait.
      if (!leaving.current || document.visibilityState !== "visible") return;
      leaving.current = false;
      latest.current(PAYPAL_DID_NOT_OPEN);
    }, STALLED_MS);
    window.location.assign(url);
  };
}
