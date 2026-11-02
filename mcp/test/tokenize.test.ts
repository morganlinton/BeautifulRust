import assert from "node:assert/strict";
import { test } from "node:test";
import { tokenize } from "../src/tokenize.ts";
import { guidance } from "./data.ts";

test("matches the Python tokenizer that built the index", () => {
  assert.ok(guidance.tokenizerSamples.length > 0, "guidance.json has no samples");
  for (const sample of guidance.tokenizerSamples) {
    assert.deepEqual(tokenize(sample.text), sample.tokens, sample.text);
  }
});
