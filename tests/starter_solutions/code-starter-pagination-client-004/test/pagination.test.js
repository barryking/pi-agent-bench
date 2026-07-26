import assert from "node:assert/strict";
import test from "node:test";

import { fetchAllPages } from "../src/client.js";

test("collects nextCursor pages and passes the signal", async () => {
  const signal = new AbortController().signal;
  const calls = [];
  const items = await fetchAllPages(async request => {
    calls.push(request);
    return request.cursor === null
      ? { items: [1], nextCursor: "next" }
      : { items: [2], nextCursor: null };
  }, { signal });
  assert.deepEqual(items, [1, 2]);
  assert.ok(calls.every(call => call.signal === signal));
});

test("rejects a repeated cursor and maxPages overflow", async () => {
  await assert.rejects(() => fetchAllPages(async () => ({
    items: [],
    nextCursor: "repeated"
  })));
  await assert.rejects(() => fetchAllPages(async () => ({
    items: [],
    nextCursor: String(Math.random())
  }), { maxPages: 1 }));
});
