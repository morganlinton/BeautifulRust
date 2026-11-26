import assert from "node:assert/strict";
import { test } from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createServer } from "../src/server.ts";
import { guidance, lints } from "./data.ts";

const SERDE = [
  JSON.stringify({ name: "serde", vers: "1.0.0", yanked: false, features: { std: [] }, rust_version: "1.31" }),
].join("\n");

// The alpha is older and declares a lower MSRV, and the yanked line is newer.
// Neither is a released version the tool can return.
const FLOOR = [
  JSON.stringify({ name: "floor", vers: "0.0.1-alpha.1", yanked: false, features: {}, rust_version: "1.40" }),
  JSON.stringify({ name: "floor", vers: "0.1.0", yanked: false, features: {}, rust_version: "1.70" }),
  JSON.stringify({ name: "floor", vers: "0.2.0", yanked: false, features: {}, rust_version: "1.80" }),
  JSON.stringify({ name: "floor", vers: "9.9.9", yanked: true, features: {}, rust_version: "1.10" }),
].join("\n");

async function connect() {
  const server = createServer({
    guidance,
    lints,
    fetch: async (url) => {
      if (url.endsWith("/serde")) {
        return new Response(SERDE);
      }
      if (url.endsWith("/floor")) {
        return new Response(FLOOR);
      }
      return new Response("", { status: 404 });
    },
  });
  const client = new Client({ name: "test", version: "0.0.0" });
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverSide), client.connect(clientSide)]);
  return client;
}

test("lists three read-only tools with explicit hints", async () => {
  const client = await connect();
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map((t) => t.name).sort(), ["explain_lint", "get_crate_versions", "search_guidance"]);
  for (const tool of tools) {
    assert.equal(tool.annotations?.readOnlyHint, true, tool.name);
    assert.equal(tool.annotations?.destructiveHint, false, tool.name);
    assert.equal(typeof tool.annotations?.openWorldHint, "boolean", tool.name);
    assert.ok(tool.outputSchema, `${tool.name} has no outputSchema`);
  }
});

test("search_guidance returns text and structured results", async () => {
  const client = await connect();
  const result = await client.callTool({ name: "search_guidance", arguments: { query: "bool parameters" } });
  assert.notEqual(result.isError, true);
  const structured = result.structuredContent as { results: unknown[] };
  assert.ok(structured.results.length > 0);
});

test("explain_lint describes the config setting", async () => {
  const client = await connect();
  const result = await client.callTool({ name: "explain_lint", arguments: { lint: "unwrap-used" } });
  const text = (result.content as { type: string; text: string }[])[0].text;
  assert.match(text, /sets it to warn/);
});

test("get_crate_versions answers and reports bad names as tool errors", async () => {
  const client = await connect();
  const ok = await client.callTool({ name: "get_crate_versions", arguments: { name: "serde" } });
  const structured = ok.structuredContent as {
    latest: { version: string };
    latestCompatible: null;
    rustVersionQuery: null;
  };
  assert.equal(structured.latest.version, "1.0.0");
  assert.equal(structured.latestCompatible, null);
  assert.equal(structured.rustVersionQuery, null);
  assert.equal("oldestLiveRustVersion" in (ok.structuredContent as object), false);
  const text = (ok.content as { type: string; text: string }[])[0].text;
  assert.doesNotMatch(text, /Newest for Rust/);
  const bad = await client.callTool({ name: "get_crate_versions", arguments: { name: "not a crate" } });
  assert.equal(bad.isError, true);
});

test("get_crate_versions returns the newest release the toolchain can build", async () => {
  const client = await connect();
  const ok = await client.callTool({
    name: "get_crate_versions",
    arguments: { name: "serde", rust_version: "1.31" },
  });
  assert.notEqual(ok.isError, true);
  assert.equal((ok.structuredContent as { latestCompatible: { version: string } }).latestCompatible.version, "1.0.0");
  const text = (ok.content as { type: string; text: string }[])[0].text;
  assert.match(text, /Newest for Rust 1\.31: 1\.0\.0/);

  const none = await client.callTool({
    name: "get_crate_versions",
    arguments: { name: "floor", rust_version: "1.60" },
  });
  assert.equal((none.structuredContent as { latestCompatible: null; rustVersionQuery: string }).latestCompatible, null);
  assert.equal((none.structuredContent as { rustVersionQuery: string }).rustVersionQuery, "1.60");
  const noneText = (none.content as { type: string; text: string }[])[0].text;
  assert.match(noneText, /No released version supports Rust 1\.60; the oldest live version needs Rust 1\.70/);

  const bad = await client.callTool({
    name: "get_crate_versions",
    arguments: { name: "serde", rust_version: "abc" },
  });
  assert.equal(bad.isError, true);
  const badText = (bad.content as { type: string; text: string }[])[0].text;
  assert.doesNotMatch(badText, /not a Rust version/);
});

test("rejects arguments that break the input schema", async () => {
  const client = await connect();
  const result = await client.callTool({ name: "search_guidance", arguments: { query: "" } });
  assert.equal(result.isError, true);
});
