import { useSyncExternalStore } from "react";

// The shapes the backend returns. Money is always integer cents.
export type Item = {
  id: string;
  name: string;
  estPriceCents: number | null;
  priceCents: number | null;
  claimedBy: string | null;
  boughtBy: string | null;
  checkedAt: string | null;
  receiptId: string | null;
  orderId: string | null;
  photoPath: string | null;
};
export type Member = { id: string; name: string; email: string | null };
export type Extra = { name: string; priceCents: number | null };
export type Receipt = {
  id: string;
  memberId: string | null;
  totalCents: number | null;
  extras: Extra[];
  createdAt: string;
};
export type Order = {
  id: string;
  memberId: string | null;
  itemIds: string[];
  totalCents: number;
  capturedAt: string;
};
export type Invoice = {
  id: string;
  debtorId: string | null;
  creditorId: string | null;
  amountCents: number;
  status: string;
  payUrl: string | null;
};
export type Owed = { from: string; to: string; amountCents: number };
export type ListState = {
  id: string;
  title: string;
  kind: string;
  budgetCents: number | null;
  finishedAt: string | null;
  members: Member[];
  items: Item[];
  receipts: Receipt[];
  orders: Order[];
  invoices: Invoice[];
  money: {
    spentCents: number;
    extrasCents: number;
    perPerson: { memberId: string; spentCents: number; extrasCents: number }[];
    owes: Owed[];
  };
};
export type History = {
  lists: {
    id: string;
    title: string;
    kind: string;
    createdAt: string;
    finishedAt: string | null;
    spentCents: number;
    itemCount: number;
    doneCount: number;
  }[];
  byKind: Record<string, number>;
  byMonth: Record<string, number>;
  lastPaidCents: Record<string, number>;
};
// An item the user has not saved yet: typed, spoken, or suggested by the AI.
export type Draft = { name: string; estPriceCents: number | null };

export const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export function parseDollars(text: string): number | null {
  const amount = Number(text.replace(/[$,\s]/g, ""));
  return text.trim() && Number.isFinite(amount) && amount >= 0 ? Math.round(amount * 100) : null;
}

/** Calls the backend. Throws an Error whose message is the backend's error code. */
export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; image?: Blob } = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: options.method ?? (options.body !== undefined || options.image ? "POST" : "GET"),
    headers: options.image
      ? { "Content-Type": options.image.type }
      : options.body !== undefined
        ? { "Content-Type": "application/json" }
        : undefined,
    body: options.image ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  });
  if (response.status === 204) return undefined as T;
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error ?? "SERVER_ERROR");
  return result;
}

/** Shrinks a phone photo to a JPEG at most 1600px on its long side, so the upload is small. */
export async function shrink(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("IMAGE"))), "image/jpeg", 0.85),
  );
}

// What this browser remembers. There are no accounts, so this is all "you" means.
export const NAME_KEY = "heylist-name";
export const LISTS_KEY = "heylist-lists";
export const memberKey = (listId: string) => `heylist-member-${listId}`;

const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** A localStorage value that re-renders when it changes. Null on the server and when unset. */
export function useStored(key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => localStorage.getItem(key),
    () => null,
  );
}

export function store(key: string, value: string) {
  localStorage.setItem(key, value);
  listeners.forEach((listener) => listener());
}

export function knownLists(): string[] {
  try {
    const ids = JSON.parse(localStorage.getItem(LISTS_KEY) ?? "[]");
    return Array.isArray(ids) ? ids : [];
  } catch {
    return [];
  }
}

export function rememberList(id: string) {
  const ids = knownLists();
  if (!ids.includes(id)) store(LISTS_KEY, JSON.stringify([id, ...ids].slice(0, 50)));
}
