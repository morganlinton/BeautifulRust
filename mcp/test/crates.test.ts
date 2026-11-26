import assert from "node:assert/strict";
import { test } from "node:test";
import {
  compareRustVersion,
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
  assert.equal(answer.latestCompatible, null);
  assert.equal(answer.rustVersionQuery, null);
});

test("compares rust versions numerically, with a missing patch as 0", () => {
  assert.equal(compareRustVersion("1.70", "1.70.0"), 0);
  assert.ok(compareRustVersion("1.9", "1.10") < 0);
});

test("picks the newest release a toolchain can build", () => {
  const at172 = summarize(INDEX, { rustVersion: "1.72" });
  assert.equal(at172.latestCompatible?.version, "1.0.0");
  assert.equal(at172.rustVersionQuery, "1.72");
  assert.equal(summarize(INDEX, { rustVersion: "1.74.0" }).latestCompatible?.version, "1.0.1");
  // 0.9.0 has no rust-version, which cargo treats as compatible. The newer betas are not releases.
  assert.equal(summarize(INDEX, { rustVersion: "1.60" }).latestCompatible?.version, "0.9.0");
  // 1.1.0 is yanked and sorts above 1.0.1; it must not win.
  assert.equal(summarize(INDEX, { rustVersion: "1.90" }).latestCompatible?.version, "1.0.1");
});

test("skips yanked releases and pre-releases when nothing else qualifies", () => {
  const answer = summarize(
    [line("1.2.0", { rust_version: "1.80" }), line("1.1.0", { yanked: true }), line("2.0.0-rc.1")].join("\n"),
    { rustVersion: "1.70" },
  );
  assert.equal(answer.latestCompatible, null);
  assert.equal(answer.rustVersionQuery, "1.70");
  assert.equal(answer.oldestLiveRustVersion, "1.80");
});

test("names the oldest release's rust requirement outside the recent list", () => {
  const versions = [
    line("0.1.0", { rust_version: "1.70" }),
    ...Array.from({ length: 10 }, (_, i) => line(`0.2.${i}`, { rust_version: "1.90" })),
  ].join("\n");
  const answer = summarize(versions, { rustVersion: "1.65" });
  assert.equal(answer.latestCompatible, null);
  assert.equal(answer.oldestLiveRustVersion, "1.70");
  assert.equal(answer.recent.some((v) => v.version === "0.1.0"), false);
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
  const answer = await lookupCrate("nope", async () => new Response("", { status: 404 }), {
    rustVersion: "1.75",
  });
  assert.equal(answer.found, false);
  assert.equal(answer.latestCompatible, null);
  assert.equal(answer.rustVersionQuery, null);
});

test("rejects a rust version that is not a toolchain without fetching", async () => {
  let called = false;
  await assert.rejects(
    lookupCrate("serde", async () => {
      called = true;
      return new Response("");
    }, { rustVersion: "nightly" }),
    CrateLookupError,
  );
  assert.equal(called, false);
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
