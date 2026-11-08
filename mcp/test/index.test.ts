import assert from "node:assert/strict";
import { test } from "node:test";
import { handleRequest } from "../src/index.ts";

const BASE = "https://mcp.example.dev";

async function json(response: Response): Promise<any> {
  return response.json();
}

function mcpRequest(body: unknown): Request {
  return new Request(`${BASE}/mcp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify(body),
  });
}

test("answers MCP initialize and tools/list with CORS headers", async () => {
  const init = await handleRequest(
    mcpRequest({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "t", version: "0" } },
    }),
    {},
  );
  assert.equal(init.status, 200);
  assert.equal(init.headers.get("Access-Control-Allow-Origin"), "*");
  assert.equal((await json(init)).result.serverInfo.name, "beautiful-rust");

  const list = await handleRequest(mcpRequest({ jsonrpc: "2.0", id: 2, method: "tools/list" }), {});
  const names = (await json(list)).result.tools.map((t: { name: string }) => t.name).sort();
  assert.deepEqual(names, ["explain_lint", "get_crate_versions", "search_guidance"]);
});

test("rejects GET on /mcp", async () => {
  const response = await handleRequest(new Request(`${BASE}/mcp`), {});
  assert.equal(response.status, 405);
});

test("serves OpenAI's domain token only when it is set", async () => {
  const path = `${BASE}/.well-known/openai-apps-challenge`;
  assert.equal((await handleRequest(new Request(path), {})).status, 404);
  const response = await handleRequest(new Request(path), { OPENAI_APPS_CHALLENGE: "token-123" });
  assert.equal(await response.text(), "token-123");
});

test("describes itself at / and 404s elsewhere", async () => {
  assert.match(await (await handleRequest(new Request(`${BASE}/`), {})).text(), /Beautiful Rust MCP server/);
  assert.equal((await handleRequest(new Request(`${BASE}/nope`), {})).status, 404);
});
