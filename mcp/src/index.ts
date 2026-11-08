import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import guidanceJson from "../data/guidance.json" with { type: "json" };
import lintsJson from "../data/lints.json" with { type: "json" };
import { cachingFetcher } from "./cache.ts";
import type { GuidanceData } from "./guidance.ts";
import type { LintData } from "./lints.ts";
import { createServer, SERVER_VERSION } from "./server.ts";

const guidance = guidanceJson as unknown as GuidanceData;
const lints = lintsJson as unknown as LintData;
const MAX_BODY_BYTES = 64 * 1024;
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept, Mcp-Protocol-Version, Mcp-Session-Id",
  "Access-Control-Expose-Headers": "Mcp-Session-Id",
};
// Shared by every request this instance serves.
const crateFetch = cachingFetcher((url, init) => fetch(url, init), {
  ttlMs: 5 * 60 * 1000,
  maxBytes: 64 * 1024 * 1024,
});

export interface Env {
  /** The token OpenAI asks the plugin's domain to serve. */
  OPENAI_APPS_CHALLENGE?: string;
}

/** Routes one request. vercel.json rewrites every path to this function. */
export async function handleRequest(request: Request, env: Env): Promise<Response> {
  const { pathname } = new URL(request.url);
  if (pathname === "/mcp") {
    return withCors(await handleMcp(request));
  }
  if (pathname === "/.well-known/openai-apps-challenge" && env.OPENAI_APPS_CHALLENGE) {
    return new Response(env.OPENAI_APPS_CHALLENGE, {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
  if (pathname === "/" && request.method === "GET") {
    return new Response(
      `Beautiful Rust MCP server ${SERVER_VERSION}\n` +
        "Connect an MCP client to /mcp (streamable HTTP).\n" +
        "https://github.com/morganlinton/BeautifulRust\n",
      { headers: { "Content-Type": "text/plain; charset=utf-8" } },
    );
  }
  return new Response("Not found\n", { status: 404 });
}

// The Web-standard handler shape Vercel Functions run.
export default {
  fetch(request: Request): Promise<Response> {
    return handleRequest(request, { OPENAI_APPS_CHALLENGE: process.env.OPENAI_APPS_CHALLENGE });
  },
};

async function handleMcp(request: Request): Promise<Response> {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }
  // Stateless: every POST gets a fresh server, and there is no stream to
  // resume or session to delete.
  if (request.method !== "POST") {
    return new Response("Method not allowed\n", { status: 405, headers: { Allow: "POST" } });
  }
  const server = createServer({ guidance, lints, fetch: crateFetch });
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
    maxRequestBodySize: MAX_BODY_BYTES,
  });
  await server.connect(transport);
  return transport.handleRequest(request);
}

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    headers.set(key, value);
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}
