import assert from "node:assert/strict";
import { test } from "node:test";
import { cachingFetcher } from "../src/cache.ts";

function counting(status = 200, body = "index") {
  const calls: string[] = [];
  const fetcher = async (url: string) => {
    calls.push(url);
    return new Response(body, { status });
  };
  return { calls, fetcher };
}

test("serves repeat lookups from memory until they expire", async () => {
  let clock = 0;
  const { calls, fetcher } = counting();
  const cached = cachingFetcher(fetcher, { ttlMs: 1000, maxBytes: 1024, now: () => clock });
  assert.equal(await (await cached("https://x/a", {})).text(), "index");
  assert.equal(await (await cached("https://x/a", {})).text(), "index");
  assert.equal(calls.length, 1);
  clock = 1001;
  await cached("https://x/a", {});
  assert.equal(calls.length, 2);
});

test("remembers that a crate doesn't exist", async () => {
  const { calls, fetcher } = counting(404, "");
  const cached = cachingFetcher(fetcher, { ttlMs: 1000, maxBytes: 1024 });
  assert.equal((await cached("https://x/nope", {})).status, 404);
  assert.equal((await cached("https://x/nope", {})).status, 404);
  assert.equal(calls.length, 1);
});

test("never caches server errors", async () => {
  const { calls, fetcher } = counting(503, "busy");
  const cached = cachingFetcher(fetcher, { ttlMs: 1000, maxBytes: 1024 });
  assert.equal((await cached("https://x/a", {})).status, 503);
  await cached("https://x/a", {});
  assert.equal(calls.length, 2);
});

test("evicts the least recently used entry when over budget", async () => {
  const { calls, fetcher } = counting(200, "12345");
  const cached = cachingFetcher(fetcher, { ttlMs: 1000, maxBytes: 10 });
  await cached("https://x/a", {});
  await cached("https://x/b", {});
  await cached("https://x/a", {}); // a is now the most recent
  await cached("https://x/c", {}); // evicts b
  await cached("https://x/a", {});
  await cached("https://x/b", {});
  assert.deepEqual(calls, ["https://x/a", "https://x/b", "https://x/c", "https://x/b"]);
});
