import { supabase } from "./auth";

// userId is set for someone who joined logged in; null for a guest.
export type Member = { id: string; name: string; userId: string | null };
export type Item = {
  id: string;
  name: string;
  // A condition or an amount to check, kept from the request ("only if nobody has one").
  note: string | null;
  quantity: number;
  estPriceCents: number | null;
  priceCents: number | null;
  claimedBy: string | null;
  boughtBy: string | null;
  checkedAt: string | null;
  orderId: string | null;
  receiptId: string | null;
  // A real product chosen from a store search (Channel3, decision 50); its price is estPriceCents.
  product: Product | null;
};
export type Product = { productId: string; title: string; store: string; url: string; imageUrl: string | null; priceCents: number };
export type ReceiptLine = { text: string; priceCents: number; lowConfidence: boolean; itemId: string | null };
export type Receipt = {
  id: string;
  memberId: string | null;
  lines: ReceiptLine[];
  totalCents: number | null;
  extras: { name: string; priceCents: number }[];
  confirmedAt: string | null;
  createdAt: string;
};
// COMPLETED is proof of purchase; PENDING means PayPal hasn't settled the payment yet (its items are held).
export type Order = {
  id: string; memberId: string | null; itemIds: string[]; totalCents: number; status: "COMPLETED" | "PENDING";
  // Charges given back because a single item had already been checked off when the payment went through (decision 39).
  refunds: Record<string, { refundId: string; cents: number; status: string }>;
  createdAt: string;
};
export type Invoice = { id: string; debtorId: string | null; creditorId: string | null; amountCents: number; status: string; payUrl: string | null };
export type List = {
  id: string;
  title: string;
  kind: string;
  budgetCents: number | null;
  createdAt: string;
  finishedAt: string | null;
  members: Member[];
  items: Item[];
  receipts: Receipt[];
  orders: Order[];
  invoices: Invoice[];
};

// List IDs this browser has opened, newest first. There are no accounts (decision 6), so this is what History shows.
const SEEN = "heylist:lists";
export function seenLists(): string[] {
  try {
    return JSON.parse(localStorage.getItem(SEEN) ?? "[]");
  } catch {
    return [];
  }
}
export function rememberList(id: string) {
  try {
    localStorage.setItem(SEEN, JSON.stringify([id, ...seenLists().filter((seen) => seen !== id)].slice(0, 50)));
  } catch {}
}

// What an item's status rests on. Each label says only what that evidence shows: a PayPal capture proves the
// payment, not that the item arrived; a hand tick is someone's word.
export function proofLabel(item: Item, orders: Order[]): string | null {
  if (item.orderId) return "Paid with PayPal";
  if (item.receiptId) return "On a receipt";
  if (item.checkedAt) return "Marked bought by hand";
  if (orders.some((order) => order.status === "PENDING" && order.itemIds.includes(item.id))) return "Payment pending at PayPal";
  return null;
}

// Said after a capture: how much came back for items someone had already bought.
export const refundNote = (cents: number) => (cents > 0 ? ` ${usd(cents)} was refunded for items someone had already bought.` : "");

export const usd = (cents: number) => `$${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;

// Readable messages for the backend's error codes; anything else shows the code itself.
const MESSAGES: Record<string, string> = {
  AI_UNAVAILABLE: "The list helper is not answering right now. Try again in a moment.",
  UNREADABLE_IMAGE: "That photo could not be read. Try again with the whole receipt flat and in focus.",
  NO_LINES_FOUND: "No items were found on that receipt.",
  SCANNING_UNAVAILABLE: "Receipt scanning is not available right now.",
  MATCHING_UNAVAILABLE: "Receipt matching is not available right now.",
  NO_MEMBERS: "Add at least one person first.",
  TOO_MANY_REQUESTS: "That was done a lot just now. Please wait a while and try again.",
  RECEIPT_TOO_LONG: "That receipt is too long to match in one go.",
  PAYMENT_PENDING: "A payment for one of those items is still pending at PayPal.",
  ORDER_NOT_PENDING: "That payment is no longer pending. Reload the page to see it.",
  MARKET_UNAVAILABLE: "Store search is not available right now. Try again in a moment.",
  PRODUCT_NOT_FOUND: "That product is no longer available. Search again.",
  ITEM_CHECKED: "That item has already been bought.",
  NOT_YOURS: "That person joined with an account. Only they can do this, logged in.",
  NAME_TAKEN: "Someone with an account already uses that name on this list. Pick another, or log in if it's you.",
};

/** JSON in, JSON out. A Blob body is sent as-is with its own type (receipt photos). A failure throws an Error
 * with the readable message, and the backend's error code (or the HTTP status text) as `code`. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = init?.body instanceof Blob ? { "Content-Type": init.body.type } : init?.body ? { "Content-Type": "application/json" } : {};
  const token = (await supabase.auth.getSession()).data.session?.access_token;
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const code = (await res.json().catch(() => null))?.error ?? res.statusText;
    throw Object.assign(new Error(MESSAGES[code] ?? code), { code });
  }
  return res.json();
}
