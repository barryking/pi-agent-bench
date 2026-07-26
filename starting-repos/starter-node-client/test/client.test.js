import assert from "node:assert/strict";
import test from "node:test";

import { fetchFirstPage } from "../src/client.js";

test("fetchFirstPage requests the initial cursor", async () => {
  const calls = [];
  const page = await fetchFirstPage(async request => {
    calls.push(request);
    return { items: ["one"], nextCursor: "next" };
  });

  assert.deepEqual(page, { items: ["one"], nextCursor: "next" });
  assert.equal(calls[0].cursor, null);
});
