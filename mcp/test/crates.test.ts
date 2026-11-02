import assert from "node:assert/strict";
import { test } from "node:test";
import {
  compareSemver,
  CrateLookupError,
  indexPath,
  lookupCrate,
  summarize,
  type Fetcher,
} from "../src/crates.ts";

const line = (vers: string, extra: Record<string, unknown> = {}) =>
  JSON.stringify({ name: "demo_crate", vers, yanked: false, features: {}, ...extra });

const INDEX = [
  line("0.9.0"),
  line("1.0.0", { rust_version: "1.70", pubtime: "2026-01-01T00:00:00Z", features: { std: [] } }),
  line("1.1.0", { yanked: true }),
  line("1.0.1", { rust_version: "1.74", features: { std: [] }, features2: { "dep:serde": [] } }),
  line("2.0.0-beta.2"),
  line("2.0.0-beta.10"),
].join("\n");

test("builds index paths like cargo", () => {
  assert.equal(indexPath("a"), "1/a");
  assert.equal(indexPath("ab"), "2/ab");
  assert.equal(indexPath("syn"), "3/s/syn");
  assert.equal(indexPath("Serde"), "se/rd/serde");
});

test("orders versions by SemVer precedence", () => {
  const sorted = ["1.0.0", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "0.9.9", "1.0.0+build"]
    .sort(compareSemver);
  assert.deepEqual(sorted, ["0.9.9", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.0+build"]);
});

test("picks the newest live version and a newer pre-release", () => {
  const answer = summarize(INDEX);
  assert.equal(answer.latest?.version, "1.0.1");
  assert.equal(answer.latest?.rustVersion, "1.74");
  assert.equal(answer.latestPrerelease?.version, "2.0.0-beta.10");
  assert.deepEqual(answer.latestFeatures, ["dep:serde", "std"]);
  assert.equal(answer.totalVersions, 6);
  assert.equal(answer.yankedVersions, 1);
  assert.equal(answer.recent[0].version, "2.0.0-beta.10");
  assert.ok(answer.recent.some((v) => v.version === "1.1.0" && v.yanked));
});

test("tries the other spelling of - and _", async () => {
  const requested: string[] = [];
  const fetcher: Fetcher = async (url) => {
    requested.push(url);
    return url.endsWith("/demo_crate")
      ? new Response(INDEX)
      : new Response("", { status: 404 });
  };
  const answer = await lookupCrate("demo-crate", fetcher);
  assert.equal(answer.found, true);
  assert.equal(answer.name, "demo_crate");
  assert.deepEqual(requested, [
    "https://index.crates.io/de/mo/demo-crate",
    "https://index.crates.io/de/mo/demo_crate",
  ]);
});

test("reports a missing crate", async () => {
  const answer = await lookupCrate("nope", async () => new Response("", { status: 404 }));
  assert.equal(answer.found, false);
});

test("rejects invalid names without fetching", async () => {
  let called = false;
  await assert.rejects(
    lookupCrate("../etc/passwd", async () => {
      called = true;
      return new Response("");
    }),
    CrateLookupError,
  );
  assert.equal(called, false);
});

test("surfaces index errors", async () => {
  await assert.rejects(
    lookupCrate("serde", async () => new Response("", { status: 503 })),
    /HTTP 503/,
  );
});
