import assert from "node:assert/strict";
import test from "node:test";
import { ITEMS, totalCents } from "./sample-list.ts";

test("sums the selected items in cents", () => {
  assert.equal(totalCents(["sunscreen", "adapter"]), 899 + 1499);
  assert.equal(
    totalCents(ITEMS.map((item) => item.id)),
    ITEMS.reduce((sum, item) => sum + item.priceCents, 0),
  );
});

test("rejects selections that must never be charged", () => {
  assert.throws(() => totalCents([]), /at least one/);
  assert.throws(() => totalCents(["sunscreen", "nope"]), /unknown/);
  assert.throws(() => totalCents(["sunscreen", "sunscreen"]), /twice/);
  assert.throws(() => totalCents("sunscreen"), /at least one/);
  assert.throws(() => totalCents(undefined), /at least one/);
});
