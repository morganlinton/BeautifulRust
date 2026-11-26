import assert from "node:assert/strict";
import { test } from "node:test";
import { cachingFetcher } from "../src/cache.ts";
import {
  compareSemver,
  CrateLookupError,
  dependenciesOf,
  indexPath,
  lookupCrate,
  lookupDependencies,
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

// JSON.parse keeps the fixture loosely typed: index lines carry extra fields.
const dependencyLine = (vers: string, extra: Record<string, unknown> = {}) =>
  JSON.parse(
    JSON.stringify({
      name: "demo_crate",
      vers,
      yanked: false,
      features: {},
      deps: [],
      ...extra,
    }),
  );

const DEPENDENCIES = [
  dependencyLine("1.0.0", {
    deps: [{ name: "old", req: "^0.1", kind: "normal" }],
  }),
  dependencyLine("1.2.0", {
    yanked: true,
    deps: [{ name: "only_yanked", req: "^9", kind: "normal" }],
  }),
  dependencyLine("1.1.0", {
    features: {
      default: ["std"],
      derive: ["serde_derive"],
      json: ["serde_json"],
      bytes_extra: ["dep:bytes"],
    },
    features2: {
      derive: ["dep:serde_derive"],
      bytes: ["dep:bytes"],
    },
    deps: [
      {
        name: "serde_renamed",
        req: "^1.0",
        features: ["derive"],
        optional: false,
        default_features: true,
        target: null,
        kind: "normal",
        package: "serde",
      },
      {
        name: "serde_derive",
        req: "^1.0",
        features: [],
        optional: true,
        default_features: true,
        kind: "normal",
      },
      {
        name: "serde_json",
        req: "^1.0",
        optional: true,
        kind: "normal",
      },
      {
        name: "bytes",
        req: "^1",
        optional: true,
        kind: "normal",
      },
      {
        name: "libc",
        req: "^0.2",
        optional: false,
        default_features: true,
        target: "cfg(unix)",
        kind: "normal",
      },
      { name: "itoa", req: "^1.0" },
      {
        name: "cc",
        req: "^1.0",
        optional: false,
        default_features: false,
        kind: "build",
      },
      {
        name: "criterion",
        req: "^0.5",
        optional: false,
        default_features: true,
        kind: "dev",
      },
      {
        name: "same",
        req: "^1",
        package: "same",
        kind: "normal",
      },
    ],
  }),
];

test("default dependency version skips a yanked newer release", () => {
  const answer = dependenciesOf(DEPENDENCIES);
  assert.equal(answer.version, "1.1.0");
  assert.equal(answer.yanked, false);
  assert.equal(answer.found, true);
  assert.ok(!answer.dependencies.some((dep) => dep.name === "only_yanked"));
  assert.equal(answer.url, "https://crates.io/crates/demo_crate");
});

test("explicit version reads that line, including a yanked one", () => {
  const older = dependenciesOf(DEPENDENCIES, "1.0.0");
  assert.equal(older.version, "1.0.0");
  assert.deepEqual(older.dependencies.map((dep) => dep.name), ["old"]);

  const yanked = dependenciesOf(DEPENDENCIES, "1.2.0");
  assert.equal(yanked.version, "1.2.0");
  assert.equal(yanked.yanked, true);
  assert.equal(yanked.dependencies[0].name, "only_yanked");
});

test("unknown version lists up to five nearest versions", () => {
  assert.throws(
    () => dependenciesOf(DEPENDENCIES, "1.0.9"),
    (error: unknown) => {
      assert.ok(error instanceof CrateLookupError);
      assert.equal(
        error.message,
        'No version "1.0.9" of demo_crate. Nearest versions: 1.0.0, 1.1.0, 1.2.0 (yanked).',
      );
      return true;
    },
  );

  const many = ["0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0"].map((vers) => dependencyLine(vers));
  assert.throws(
    () => dependenciesOf(many, "0.0.1"),
    (error: unknown) => {
      assert.ok(error instanceof CrateLookupError);
      assert.match(error.message, /0\.1\.0, 0\.2\.0, 0\.3\.0, 0\.4\.0, 0\.5\.0/);
      assert.doesNotMatch(error.message, /0\.6\.0/);
      return true;
    },
  );
});

test("renamed dependency reports its real package", () => {
  const answer = dependenciesOf(DEPENDENCIES);
  const renamed = answer.dependencies.find((dep) => dep.name === "serde_renamed");
  assert.equal(renamed?.package, "serde");
  assert.deepEqual(renamed?.features, ["derive"]);
  assert.equal(renamed?.kind, "normal");
  const same = answer.dependencies.find((dep) => dep.name === "same");
  assert.equal(same?.package, null);
});

test("optional dependency lists the feature that enables it", () => {
  const answer = dependenciesOf(DEPENDENCIES);
  assert.deepEqual(answer.features.derive, ["dep:serde_derive"]);
  assert.deepEqual(answer.features.json, ["serde_json"]);
  assert.deepEqual(answer.defaultFeatures, ["std"]);

  const derived = answer.dependencies.find((dep) => dep.name === "serde_derive");
  assert.equal(derived?.optional, true);
  assert.deepEqual(derived?.enabledBy, ["derive"]);

  const json = answer.dependencies.find((dep) => dep.name === "serde_json");
  assert.deepEqual(json?.enabledBy, ["json"]);

  const bytes = answer.dependencies.find((dep) => dep.name === "bytes");
  assert.deepEqual(bytes?.enabledBy, ["bytes", "bytes_extra"]);

  const renamed = answer.dependencies.find((dep) => dep.name === "serde_renamed");
  assert.deepEqual(renamed?.enabledBy, []);
});

test("maps kind, target, and default features", () => {
  const answer = dependenciesOf(DEPENDENCIES);
  const libc = answer.dependencies.find((dep) => dep.name === "libc");
  assert.equal(libc?.target, "cfg(unix)");
  assert.equal(libc?.kind, "normal");

  const itoa = answer.dependencies.find((dep) => dep.name === "itoa");
  assert.equal(itoa?.kind, "normal");
  assert.equal(itoa?.optional, false);
  assert.equal(itoa?.defaultFeatures, true);
  assert.equal(itoa?.target, null);
  assert.deepEqual(itoa?.features, []);

  const cc = answer.dependencies.find((dep) => dep.name === "cc");
  assert.equal(cc?.kind, "build");
  assert.equal(cc?.defaultFeatures, false);

  const criterion = answer.dependencies.find((dep) => dep.name === "criterion");
  assert.equal(criterion?.kind, "dev");
});

test("uses a pre-release only when every stable release is yanked or absent", () => {
  const newerPre = dependenciesOf([
    dependencyLine("1.0.0", { deps: [{ name: "stable_dep", req: "^1", kind: "normal" }] }),
    dependencyLine("2.0.0-rc.1", { deps: [{ name: "pre_dep", req: "^1", kind: "normal" }] }),
  ]);
  assert.equal(newerPre.version, "1.0.0");

  const onlyPre = dependenciesOf([
    dependencyLine("1.0.0-alpha.1", { deps: [{ name: "old", req: "^1", kind: "normal" }] }),
    dependencyLine("1.0.0-alpha.10", { deps: [{ name: "new", req: "^1", kind: "normal" }] }),
    dependencyLine("0.9.0", { yanked: true }),
  ]);
  assert.equal(onlyPre.version, "1.0.0-alpha.10");
  assert.equal(onlyPre.dependencies[0].name, "new");

  const allYanked = dependenciesOf([dependencyLine("1.0.0", { yanked: true })]);
  assert.equal(allYanked.found, true);
  assert.equal(allYanked.version, null);
  assert.deepEqual(allYanked.dependencies, []);
});

test("dependency lookup tries the other spelling of - and _", async () => {
  const text = JSON.stringify(dependencyLine("1.0.0"));
  const requested: string[] = [];
  const answer = await lookupDependencies("demo-crate", undefined, async (url) => {
    requested.push(url);
    return url.endsWith("/demo_crate") ? new Response(text) : new Response("", { status: 404 });
  });
  assert.equal(answer.found, true);
  assert.equal(answer.version, "1.0.0");
  assert.deepEqual(requested, [
    "https://index.crates.io/de/mo/demo-crate",
    "https://index.crates.io/de/mo/demo_crate",
  ]);
});

test("reports a missing crate's dependencies without fetching an invalid name", async () => {
  const missing = await lookupDependencies("nope", undefined, async () => new Response("", { status: 404 }));
  assert.equal(missing.found, false);
  assert.equal(missing.version, null);
  assert.equal(missing.url, null);

  let called = false;
  await assert.rejects(
    lookupDependencies("not a crate", undefined, async () => {
      called = true;
      return new Response("");
    }),
    CrateLookupError,
  );
  assert.equal(called, false);
});

test("version and dependency lookups share one index fetch", async () => {
  const text = DEPENDENCIES.map((line) => JSON.stringify(line)).join("\n");
  let calls = 0;
  const fetcher = cachingFetcher(
    async (url) => {
      calls += 1;
      return url.endsWith("/demo_crate") ? new Response(text) : new Response("", { status: 404 });
    },
    { ttlMs: 60_000, maxBytes: 1_000_000, now: () => 0 },
  );
  const versions = await lookupCrate("demo_crate", fetcher);
  const deps = await lookupDependencies("demo_crate", undefined, fetcher);
  assert.equal(versions.latest?.version, "1.1.0");
  assert.equal(deps.version, "1.1.0");
  assert.equal(calls, 1);
});
