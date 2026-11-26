import assert from "node:assert/strict";
import { test } from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createServer } from "../src/server.ts";
import { guidance, lints } from "./data.ts";

const SERDE = [
  JSON.stringify({
    name: "serde",
    vers: "1.0.0",
    yanked: false,
    rust_version: "1.31",
    features: { default: ["std"], std: [] },
    features2: { derive: ["dep:serde_derive"] },
    deps: [
      {
        name: "serde_derive",
        req: "^1.0",
        features: [],
        optional: true,
        default_features: true,
        target: null,
        kind: "normal",
      },
      {
        name: "serde_core",
        req: "^1.0",
        features: ["alloc"],
        optional: false,
        default_features: false,
        target: null,
        kind: "normal",
        package: "serde",
      },
      {
        name: "libc",
        req: "^0.2",
        features: [],
        optional: false,
        default_features: true,
        target: "cfg(unix)",
        kind: "normal",
      },
    ],
  }),
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

test("lists four read-only tools with explicit hints", async () => {
  const client = await connect();
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map((t) => t.name).sort(), [
    "explain_lint",
    "get_crate_dependencies",
    "get_crate_versions",
    "search_guidance",
  ]);
  for (const tool of tools) {
    assert.equal(tool.annotations?.readOnlyHint, true, tool.name);
    assert.equal(tool.annotations?.destructiveHint, false, tool.name);
    assert.equal(typeof tool.annotations?.openWorldHint, "boolean", tool.name);
    assert.ok(tool.outputSchema, `${tool.name} has no outputSchema`);
  }
  const dependencies = tools.find((tool) => tool.name === "get_crate_dependencies");
  assert.equal(dependencies?.annotations?.openWorldHint, true);
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

test("get_crate_dependencies returns the dependency list", async () => {
  const client = await connect();
  const ok = await client.callTool({ name: "get_crate_dependencies", arguments: { name: "serde" } });
  assert.notEqual(ok.isError, true);
  const answer = ok.structuredContent as {
    version: string;
    dependencies: { name: string; package: string | null; optional: boolean; enabledBy: string[] }[];
  };
  assert.equal(answer.version, "1.0.0");
  assert.ok(Array.isArray(answer.dependencies));
  assert.equal(answer.dependencies[0]?.name, "serde_derive");
  assert.deepEqual(answer.dependencies[0]?.enabledBy, ["derive"]);
  assert.equal(answer.dependencies[1]?.package, "serde");
  const text = (ok.content as { type: string; text: string }[])[0].text;
  assert.match(text, /^serde 1\.0\.0 \(normal: 3\)/);
  assert.match(text, /optional, via feature "derive"/);
  assert.match(text, /package serde/);
  assert.match(text, /target `cfg\(unix\)`/);

  const bad = await client.callTool({ name: "get_crate_dependencies", arguments: { name: "not a crate" } });
  assert.equal(bad.isError, true);
  const missing = await client.callTool({
    name: "get_crate_dependencies",
    arguments: { name: "serde", version: "9.9.9" },
  });
  assert.equal(missing.isError, true);
  const missingText = (missing.content as { type: string; text: string }[])[0].text;
  assert.match(missingText, /Nearest versions: 1\.0\.0/);
});

test("rejects arguments that break the input schema", async () => {
  const client = await connect();
  const result = await client.callTool({ name: "search_guidance", arguments: { query: "" } });
  assert.equal(result.isError, true);
});
