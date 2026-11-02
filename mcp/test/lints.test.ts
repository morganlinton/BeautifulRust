import assert from "node:assert/strict";
import { test } from "node:test";
import { explainLint, normalizeLintName } from "../src/lints.ts";
import { lints } from "./data.ts";

test("normalizes the ways people write a lint name", () => {
  for (const input of ["clippy::unwrap_used", "unwrap-used", "Clippy::Unwrap_Used", "#[warn(clippy::unwrap_used)]"]) {
    const name = normalizeLintName(input);
    assert.ok(name === "clippy::unwrap_used" || name === "unwrap_used", `${input} -> ${name}`);
    assert.equal(explainLint(lints, input).lint, "clippy::unwrap_used", input);
  }
});

test("reports Beautiful Rust's own setting and reason", () => {
  const answer = explainLint(lints, "unwrap_used");
  assert.equal(answer.found, true);
  assert.equal(answer.defaultLevel, "allow");
  assert.equal(answer.beautifulRust?.level, "warn");
  assert.equal(answer.beautifulRust?.setBy, "clippy::unwrap_used");
  assert.match(answer.beautifulRust?.reason ?? "", /expect/);
  assert.match(answer.explanation ?? "", /What it does/);
});

test("credits the group that turns a lint on", () => {
  const inherited = Object.values(lints.lints).find(
    (l) => l.groups?.includes("clippy::pedantic") && !l.beautifulRust,
  );
  assert.ok(inherited, "expected a pedantic lint without its own setting");
  const answer = explainLint(lints, inherited.name);
  assert.equal(answer.beautifulRust?.setBy, "clippy::pedantic");
  assert.equal(answer.beautifulRust?.level, "warn");
});

test("an explicit allow beats the group", () => {
  const answer = explainLint(lints, "clippy::must_use_candidate");
  assert.equal(answer.beautifulRust?.setBy, "clippy::must_use_candidate");
  assert.equal(answer.beautifulRust?.level, "allow");
});

test("marks library-only lints", () => {
  const answer = explainLint(lints, "missing_docs");
  assert.equal(answer.tool, "rustc");
  assert.equal(answer.beautifulRust?.librariesOnly, true);
});

test("suggests close names for an unknown lint", () => {
  const answer = explainLint(lints, "unwrap_usage");
  assert.equal(answer.found, false);
  assert.ok(answer.suggestions.includes("clippy::unwrap_used"), answer.suggestions.join(", "));
});
