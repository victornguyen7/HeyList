import type { DetailedHTMLProps, HTMLAttributes } from "react";

export interface PayPalSession {
  start(
    options: { presentationMode: "auto" },
    order: Promise<{ orderId: string }>,
  ): Promise<void>;
}

interface PayPalSdk {
  findEligibleMethods(options: {
    currencyCode: string;
  }): Promise<{ isEligible(method: string): boolean }>;
  createPayPalOneTimePaymentSession(callbacks: {
    onApprove(data: { orderId: string }): Promise<void>;
    onCancel(): void;
    onError(error: unknown): void;
  }): PayPalSession;
}

declare global {
  interface Window {
    paypal: {
      createInstance(options: {
        clientId: string;
        components: string[];
        pageType: string;
      }): Promise<PayPalSdk>;
    };
  }
}

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "paypal-button": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        type?: string;
      };
    }
  }
}
