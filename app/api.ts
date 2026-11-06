import { supabase } from "./auth";
import type { Split } from "./split";

// userId is set for someone who joined logged in; null for a guest. hasEmail: their PayPal email for settle-up
// payments is known (the email itself stays on the server).
export type Member = { id: string; name: string; userId: string | null; hasEmail: boolean };
export type Item = {
  id: string;
  name: string;
  // A condition or an amount to check, kept from the request ("only if nobody has one").
  note: string | null;
  quantity: number;
  estPriceCents: number | null;
  priceCents: number | null;
  // The receipt couldn't read the price, so the buyer typed it: self-reported, like a hand tick (decision 57).
  priceTyped: boolean;
  claimedBy: string | null;
  boughtBy: string | null;
  checkedAt: string | null;
  // Already had when the list was made: checked off, not bought.
  owned: boolean;
  orderId: string | null;
  receiptId: string | null;
  // A real product chosen from a store search (Channel3, decision 50); its price is estPriceCents.
  product: Product | null;
  // The store a market price came from (decisions 73-75), e.g. "walmart.com"; null for a guess.
  priceStore: string | null;
  // Where estPriceCents came from (decision 49): paid before, a store product chosen before, a store's price today,
  // or the AI's guess. null for an item priced by hand or before sources were saved.
  priceSource: "paid" | "store" | "market" | "estimate" | null;
};

// "walmart.com" -> "Walmart", shown under a store's price.
const STORE_NAMES: Record<string, string> = { "walmart.com": "Walmart", "target.com": "Target", "kroger.com": "Kroger" };
export const storeName = (domain: string) => STORE_NAMES[domain] ?? domain;

/** How an open item's price is shown: "~" only for a guess, and the label under it (the store, "paid before", "AI guess"). */
export function priceShown(item: Pick<Item, "product" | "priceStore" | "priceSource">): { approx: boolean; label: string | null } {
  if (item.product) return { approx: false, label: null };
  if (item.priceStore) return { approx: false, label: storeName(item.priceStore) };
  if (item.priceSource === "paid") return { approx: false, label: "paid before" };
  if (item.priceSource === "store") return { approx: false, label: "store price" };
  // A guess says so, as on the review screen; a price with no source (typed in, or saved before sources were) is just "~".
  return { approx: true, label: item.priceSource === "estimate" ? "AI guess" : null };
}
export type Product = { productId: string; title: string; store: string; url: string; imageUrl: string | null; priceCents: number };
// priceCents is null where the photo's price couldn't be read surely; typed marks one the person typed in.
// discountCents (positive) is a discount printed under the line and already taken off priceCents (issue 17).
export type ReceiptLine = { text: string; priceCents: number | null; lowConfidence: boolean; itemId: string | null; typed?: boolean; discountCents?: number; discountName?: string };
// What a receipt charged besides its items. A discount's amountCents is negative; null means it couldn't be read.
export type ReceiptFee = { kind: "tax" | "tip" | "service" | "delivery" | "discount" | "other"; name: string; amountCents: number | null; typed?: boolean };
export type Receipt = {
  id: string;
  memberId: string | null;
  lines: ReceiptLine[];
  // Missing on a receipt scanned before fees were read.
  fees?: ReceiptFee[];
  totalCents: number | null;
  extras: { name: string; priceCents: number | null }[];
  confirmedAt: string | null;
  createdAt: string;
};
// COMPLETED is proof of purchase; PENDING means PayPal hasn't settled the payment yet (its items are held).
export type Order = {
  id: string; memberId: string | null; itemIds: string[]; totalCents: number; status: "COMPLETED" | "PENDING";
  // The sales tax charged on each item, all units (decision 80); totalCents includes it. Missing on older orders.
  taxes?: Record<string, number>;
  // Charges given back because a single item had already been checked off when the payment went through (decision 39).
  refunds: Record<string, { refundId: string; cents: number; status: string }>;
  createdAt: string;
};
// A settle-up payment sent with PayPal straight to the person owed (decision 60); id is the PayPal order ID.
export type Settlement = { id: string; debtorId: string | null; creditorId: string | null; amountCents: number; status: "COMPLETED" | "PENDING"; capturedAt: string | null };
export type List = {
  id: string;
  title: string;
  kind: string;
  budgetCents: number | null;
  // The sales tax rate someone typed on Money, in basis points (825 is 8.25%); null when none.
  taxRateBp: number | null;
  // The rate checkouts charge and estimates use (decision 80): the list's receipts' rate, else the typed one, else 0.
  // Missing on a list saved in this browser before tax was counted.
  tax?: { rateBp: number; source: "receipts" | "set" | null };
  createdAt: string;
  finishedAt: string | null;
  members: Member[];
  items: Item[];
  receipts: Receipt[];
  orders: Order[];
  // Missing on a list saved in this browser before settle-up payments existed.
  settlements?: Settlement[];
  // Missing on a list saved in this browser before it was sent with the list.
  split?: Split;
};

// Sales tax (decision 80), in whole cents like the backend's money.tax_of: to the nearest cent, half up.
export const taxOf = (cents: number, rateBp: number) => Math.floor((cents * rateBp + 5000) / 10000);
// 825 -> "8.25%", 800 -> "8%".
export const percent = (rateBp: number) => `${(rateBp / 100).toFixed(2).replace(/\.?0+$/, "")}%`;
/** The tax a PayPal checkout charges on these items: per unit, times the quantity, as the backend sends it to PayPal. */
export const itemsTax = (items: Pick<Item, "estPriceCents" | "quantity">[], rateBp: number) =>
  items.reduce((sum, item) => sum + taxOf(item.estPriceCents ?? 0, rateBp) * item.quantity, 0);

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
    // Opening a list again brings it back, also one the account joined (issue 26).
    localStorage.setItem(HIDDEN, JSON.stringify(hiddenLists().filter((hidden) => hidden !== id)));
  } catch {}
}

// Lists taken off Home and History in this browser. The account's lists (GET /api/me/lists) come back from the
// server every time, so they are hidden here rather than only forgotten.
const HIDDEN = "heylist:hidden";
export function hiddenLists(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HIDDEN) ?? "[]");
  } catch {
    return [];
  }
}

// Who "you" are on a list: for a guest, remembered in this browser only (list-context.tsx reads it).
export const memberKey = (listId: string) => `heylist:member:${listId}`;
export function rememberMember(listId: string, memberId: string) {
  try {
    localStorage.setItem(memberKey(listId), memberId);
  } catch {}
}

// The last copy of each list this browser loaded, shown at once on the next visit while a fresh one loads
// (Home, History, a list's own pages). A per-browser convenience only: it can be missing or blocked, and the
// fresh copy always replaces it.
const CACHE = "heylist:lists-cache";
export function cachedLists(): List[] {
  try {
    return JSON.parse(localStorage.getItem(CACHE) ?? "[]") ?? [];
  } catch {
    return [];
  }
}
// Takes a list off this browser's Home and History, with its saved copy. The list itself stays for everyone on the
// link; opening the link again brings it back.
export function forgetList(id: string) {
  try {
    localStorage.setItem(SEEN, JSON.stringify(seenLists().filter((seen) => seen !== id)));
    localStorage.setItem(CACHE, JSON.stringify(cachedLists().filter((list) => list.id !== id)));
    localStorage.setItem(HIDDEN, JSON.stringify([id, ...hiddenLists().filter((hidden) => hidden !== id)].slice(0, 200)));
  } catch {}
}
export function cacheLists(lists: List[]) {
  const ids = new Set(lists.map((list) => list.id));
  try {
    localStorage.setItem(CACHE, JSON.stringify([...lists, ...cachedLists().filter((list) => !ids.has(list.id))].slice(0, 50)));
  } catch {}
}

// What an item's status rests on. Each label says only what that evidence shows: a PayPal capture proves the
// payment, not that the item arrived; a hand tick is someone's word.
export function proofLabel(item: Item, orders: Order[]): string | null {
  if (item.orderId) return "Paid with PayPal";
  if (item.receiptId) return "On a receipt";
  if (item.owned) return "Already had";
  if (item.checkedAt) return "Marked bought by hand";
  if (orders.some((order) => order.status === "PENDING" && order.itemIds.includes(item.id))) return "Payment pending at PayPal";
  return null;
}

// Said after a capture: how much came back for items someone had already bought.
export const refundNote = (cents: number) => (cents > 0 ? ` ${usd(cents)} was refunded for items someone had already bought.` : "");

// What a capture came back with. settlement is set when the order was a settle-up payment, not list items.
export type Capture = { orderId: string; status: string; refundedCents: number; settlement?: boolean };

/** What to tell the payer after a capture, whether they came back from PayPal's page or approved in a pop-up. */
export const captureMessage = (result: Capture) =>
  result.status === "COMPLETED"
    ? result.settlement
      ? "Paid. The money went to their PayPal account, and Settle up is updated."
      : `Paid. Those items are checked off.${refundNote(result.refundedCents)}`
    : result.status === "PENDING"
      ? result.settlement
        ? "PayPal is still processing this payment. It counts once it goes through."
        : "PayPal is still processing this payment. The items are held as pending until it goes through."
      : `Payment is ${result.status.toLowerCase()}; items stay unchecked for now.`;

export const usd = (cents: number) =>
  `${cents < 0 ? "−" : ""}$${Math.floor(Math.abs(cents) / 100).toLocaleString("en-US")}.${String(Math.abs(cents) % 100).padStart(2, "0")}`;

// Readable messages for the backend's error codes; anything else gets a general message, with the code still on the error.
const MESSAGES: Record<string, string> = {
  AI_UNAVAILABLE: "The list helper is not answering right now. Try again in a moment.",
  UNREADABLE_IMAGE: "That photo could not be read. Try again with the whole receipt flat and in focus.",
  UNREADABLE_LIST: "That photo could not be read. Try again with the whole page flat, in good light and in focus.",
  NO_LINES_FOUND: "No items were found on that receipt.",
  NO_ITEMS_FOUND: "No items were found in that photo. Try again closer to the list, or type it instead.",
  SCANNING_UNAVAILABLE: "Reading photos is not available right now. Try again in a moment.",
  MATCHING_UNAVAILABLE: "Receipt matching is not available right now.",
  NO_MEMBERS: "Add at least one person first.",
  TOO_MANY_REQUESTS: "That was done a lot just now. Please wait a while and try again.",
  RECEIPT_TOO_LONG: "That receipt is too long to match in one go.",
  PAYMENT_PENDING: "A payment for one of those items is still pending at PayPal.",
  ORDER_NOT_PENDING: "That payment is no longer pending. Reload the page to see it.",
  MARKET_UNAVAILABLE: "Store search is not available right now. Try again in a moment.",
  PRODUCT_NOT_FOUND: "That product is no longer available. Search again.",
  PRICE_CHANGED: "A store price changed since it was chosen, or the store stopped selling it. Check the new total, then pay again.",
  ITEM_CHECKED: "That item has already been bought.",
  SPLIT_CHANGED: "The amounts changed since this page loaded. Check the new amount, then pay again.",
  EMAIL_NEEDED: "Type the PayPal email of the person you're paying.",
  PAYEE_NOT_ACCEPTED: "PayPal can't send money to that email. Check it with them and try again.",
  NOT_YOURS: "That person joined with an account. Only they can do this, logged in.",
  NAME_TAKEN: "Someone with an account already uses that name on this list. Pick another, or log in if it's you.",
  LIST_NOT_FOUND: "This list doesn't exist any more. Check the link with whoever shared it.",
  ITEM_NOT_FOUND: "That item is no longer on the list. Reload the page to see the latest.",
  ITEM_PAID: "That item was paid for with PayPal, so it can't be changed.",
  ORDER_NOT_FOUND: "That payment couldn't be found. Reload the page to see the latest.",
  RECEIPT_NOT_FOUND: "That receipt couldn't be found. Reload the page to see the latest.",
  RECEIPT_CONFIRMED: "That receipt was already confirmed. Reload the page to see the latest.",
  IMAGE_TOO_LARGE: "That photo is too large. Try a smaller one.",
  UNSUPPORTED_IMAGE: "That file can't be read. Use a JPEG or PNG photo.",
  PAYPAL_ERROR: "PayPal isn't answering right now. Try again in a moment.",
  INVALID_BODY: "Something in that wasn't valid. Check it and try again.",
};

/** JSON in, JSON out. A Blob body is sent as-is with its own type (receipt photos). A failure throws an Error
 * with the readable message, and the backend's error code (or the HTTP status text) as `code`. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = init?.body instanceof Blob ? { "Content-Type": init.body.type } : init?.body ? { "Content-Type": "application/json" } : {};
  const token = (await supabase.auth.getSession()).data.session?.access_token;
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers }).catch(() => {
    throw Object.assign(new Error("HeyList can't be reached. Check your connection and try again."), { code: "NETWORK" });
  });
  if (!res.ok) {
    // data is the whole error body, for errors that carry more than a code (PRICE_CHANGED's new prices).
    const data = await res.json().catch(() => null);
    const code = data?.error ?? res.statusText;
    throw Object.assign(new Error(MESSAGES[code] ?? "That didn't work. Try again in a moment."), { code, data });
  }
  // 204: nothing to read, as after deleting an item.
  return res.status === 204 ? (undefined as T) : res.json();
}
