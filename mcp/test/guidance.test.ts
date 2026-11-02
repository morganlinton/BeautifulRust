import assert from "node:assert/strict";
import { test } from "node:test";
import { MAX_SECTION_CHARS, searchGuidance } from "../src/guidance.ts";
import { guidance } from "./data.ts";

test("finds the bool parameter rule", () => {
  const results = searchGuidance(guidance, "bool parameters", { limit: 4 });
  assert.ok(results.length > 0);
  assert.ok(
    results.some((r) => r.text.includes("bool") && r.text.includes("enum")),
    results.map((r) => r.section).join("\n"),
  );
});

test("cites the original guide for digest sections", () => {
  const results = searchGuidance(guidance, "accessor naming set_foo take_foo", { limit: 4 });
  const digest = results.find((r) => r.source !== null);
  assert.ok(digest, "expected a reference digest in the results");
  assert.match(digest.sourceUrl ?? "", /^https:\/\//);
});

test("links every result to its heading on GitHub", () => {
  for (const r of searchGuidance(guidance, "unsafe SAFETY comment", { limit: 8 })) {
    assert.match(r.url, /^https:\/\/github\.com\/morganlinton\/BeautifulRust\/blob\/main\/skills\/.+#.+$/);
  }
});

test("filters by skill", () => {
  const results = searchGuidance(guidance, "error handling", { skill: "rust-review", limit: 8 });
  assert.ok(results.length > 0);
  assert.ok(results.every((r) => r.skill === "rust-review"));
});

test("truncates long sections", () => {
  const results = searchGuidance(guidance, "rust", { limit: 8 });
  for (const r of results) {
    assert.ok(r.text.length <= MAX_SECTION_CHARS + 1);
  }
});

test("returns nothing for an unrelated query", () => {
  assert.deepEqual(searchGuidance(guidance, "zzqx flibbertigibbet", { limit: 4 }), []);
});
