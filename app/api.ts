export type Member = { id: string; name: string };
export type Item = {
  id: string;
  name: string;
  quantity: number;
  estPriceCents: number | null;
  priceCents: number | null;
  claimedBy: string | null;
  boughtBy: string | null;
  checkedAt: string | null;
  orderId: string | null;
  receiptId: string | null;
};
export type ReceiptLine = { text: string; priceCents: number; lowConfidence: boolean; itemId: string | null };
export type Receipt = { id: string; lines: ReceiptLine[]; totalCents: number | null; extras: { name: string; priceCents: number }[] };
export type List = { id: string; title: string; budgetCents: number | null; members: Member[]; items: Item[]; receipts: Receipt[] };

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
};

/** JSON in, JSON out. A Blob body is sent as-is with its own type (receipt photos). */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = init?.body instanceof Blob ? { "Content-Type": init.body.type } : init?.body ? { "Content-Type": "application/json" } : undefined;
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const code = (await res.json().catch(() => null))?.error ?? res.statusText;
    throw new Error(MESSAGES[code] ?? code);
  }
  return res.json();
}
