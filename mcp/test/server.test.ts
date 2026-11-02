import assert from "node:assert/strict";
import { test } from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createServer } from "../src/server.ts";
import { guidance, lints } from "./data.ts";

const SERDE = [
  JSON.stringify({ name: "serde", vers: "1.0.0", yanked: false, features: { std: [] }, rust_version: "1.31" }),
].join("\n");

async function connect() {
  const server = createServer({
    guidance,
    lints,
    fetch: async (url) =>
      url.endsWith("/serde") ? new Response(SERDE) : new Response("", { status: 404 }),
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
  assert.equal((ok.structuredContent as { latest: { version: string } }).latest.version, "1.0.0");
  const bad = await client.callTool({ name: "get_crate_versions", arguments: { name: "not a crate" } });
  assert.equal(bad.isError, true);
});

test("rejects arguments that break the input schema", async () => {
  const client = await connect();
  const result = await client.callTool({ name: "search_guidance", arguments: { query: "" } });
  assert.equal(result.isError, true);
});
