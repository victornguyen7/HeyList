export type Item = { id: string; name: string; priceCents: number };

export const ITEMS: Item[] = [
  { id: "sunscreen", name: "Sunscreen", priceCents: 899 },
  { id: "adapter", name: "Travel adapter", priceCents: 1499 },
  { id: "toothbrush", name: "Toothbrush", priceCents: 349 },
];

export function totalCents(itemIds: unknown): number {
  if (!Array.isArray(itemIds) || itemIds.length === 0) {
    throw new Error("Select at least one item");
  }
  if (new Set(itemIds).size !== itemIds.length) {
    throw new Error("An item was selected twice");
  }
  return itemIds.reduce((sum: number, id) => {
    const item = ITEMS.find((candidate) => candidate.id === id);
    if (!item) throw new Error(`unknown item: ${String(id)}`);
    return sum + item.priceCents;
  }, 0);
}
