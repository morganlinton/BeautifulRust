import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { CrateLookupError, lookupCrate, type CrateAnswer, type Fetcher } from "./crates.ts";
import { SKILLS, searchGuidance, type GuidanceData } from "./guidance.ts";
import { explainLint, type LintAnswer, type LintData } from "./lints.ts";

export const SERVER_NAME = "beautiful-rust";
export const SERVER_VERSION = "0.1.0";

export interface Deps {
  guidance: GuidanceData;
  lints: LintData;
  fetch: Fetcher;
}

const versionInfo = z.object({
  version: z.string(),
  yanked: z.boolean(),
  rustVersion: z.string().nullable(),
  published: z.string().nullable(),
});

const settingSchema = z
  .object({
    level: z.string(),
    setBy: z.string(),
    reason: z.string().nullable(),
    librariesOnly: z.boolean(),
  })
  .nullable();

/** Every tool reads data and changes nothing, so all share these hints. */
const lookupHints = (openWorld: boolean) => ({
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: openWorld,
});

export function createServer(deps: Deps): McpServer {
  const server = new McpServer(
    { name: SERVER_NAME, version: SERVER_VERSION },
    {
      instructions:
        "Beautiful Rust's guidance for idiomatic Rust, drawn from the Google Rust Style " +
        "Guide, the Rust API Guidelines, Effective Rust, Rust Design Patterns, and " +
        "Microsoft's Pragmatic Rust Guidelines, plus clippy lint explanations and " +
        "current crate versions.",
    },
  );

  server.registerTool(
    "search_guidance",
    {
      title: "Search Beautiful Rust guidance",
      description:
        "Search Beautiful Rust's Rust guidance (writing, review, and porting skills, and " +
        "digests of five published Rust style guides). Returns the most relevant sections " +
        "verbatim, each with a link and, for digests, the original guide it summarizes. " +
        "Use it to quote or cite a Rust rule, for example on error types, panics, bool " +
        "parameters, or unsafe code.",
      inputSchema: {
        query: z.string().min(1).max(200).describe("What to look up, in plain words"),
        skill: z
          .enum(SKILLS)
          .optional()
          .describe("Limit results to one skill's guidance"),
        limit: z.number().int().min(1).max(8).optional().describe("Sections to return (default 4)"),
      },
      outputSchema: {
        results: z.array(
          z.object({
            section: z.string(),
            skill: z.string(),
            file: z.string(),
            url: z.string(),
            source: z.string().nullable(),
            sourceUrl: z.string().nullable(),
            text: z.string(),
            truncated: z.boolean(),
          }),
        ),
      },
      annotations: lookupHints(false),
    },
    async ({ query, skill, limit }) => {
      const results = searchGuidance(deps.guidance, query, { skill, limit: limit ?? 4 });
      const text =
        results.length === 0
          ? `No Beautiful Rust guidance matches "${query}".`
          : results
              .map((r) => {
                const cite = r.source ? ` (from ${r.source})` : "";
                return `## ${r.section}${cite}\n${r.url}\n\n${r.text}`;
              })
              .join("\n\n---\n\n");
      return { content: [{ type: "text", text }], structuredContent: { results } };
    },
  );

  server.registerTool(
    "explain_lint",
    {
      title: "Explain a Rust lint",
      description:
        "Explain a rustc or clippy lint: what it catches, why, its default level and " +
        "groups, and how Beautiful Rust's recommended lints config sets it. Accepts " +
        "names like clippy::unwrap_used, unwrap-used, or missing_docs.",
      inputSchema: {
        lint: z.string().min(1).max(120).describe("The lint name"),
      },
      outputSchema: {
        found: z.boolean(),
        lint: z.string().nullable(),
        tool: z.enum(["rustc", "clippy"]).nullable(),
        defaultLevel: z.string().nullable(),
        groups: z.array(z.string()),
        summary: z.string().nullable(),
        explanation: z.string().nullable(),
        beautifulRust: settingSchema,
        suggestions: z.array(z.string()),
        toolchain: z.string(),
      },
      annotations: lookupHints(false),
    },
    async ({ lint }) => {
      const answer = explainLint(deps.lints, lint);
      return {
        content: [{ type: "text", text: describeLint(lint, answer) }],
        structuredContent: { ...answer },
      };
    },
  );

  server.registerTool(
    "get_crate_versions",
    {
      title: "Get crate versions",
      description:
        "Look up a Rust crate on crates.io: the newest version that isn't yanked, a newer " +
        "pre-release if there is one, each version's minimum supported Rust version and " +
        "publish date, and the newest version's features. Use it before adding or " +
        "upgrading a dependency so Cargo.toml names a version that exists.",
      inputSchema: {
        name: z.string().min(1).max(64).describe("The crate name, for example serde"),
      },
      outputSchema: {
        name: z.string(),
        found: z.boolean(),
        latest: versionInfo.nullable(),
        latestFeatures: z.array(z.string()),
        latestPrerelease: versionInfo.nullable(),
        recent: z.array(versionInfo),
        totalVersions: z.number(),
        yankedVersions: z.number(),
        url: z.string().nullable(),
      },
      annotations: lookupHints(true),
    },
    async ({ name }) => {
      let answer: CrateAnswer;
      try {
        answer = await lookupCrate(name.trim(), deps.fetch);
      } catch (error) {
        if (error instanceof CrateLookupError) {
          return { content: [{ type: "text", text: error.message }], isError: true };
        }
        throw error;
      }
      return {
        content: [{ type: "text", text: describeCrate(answer) }],
        structuredContent: { ...answer },
      };
    },
  );

  return server;
}

function describeLint(input: string, answer: LintAnswer): string {
  if (!answer.found) {
    const hint = answer.suggestions.length > 0 ? ` Did you mean: ${answer.suggestions.join(", ")}?` : "";
    return `No lint named "${input}" in ${answer.toolchain}.${hint}`;
  }
  const lines = [
    `${answer.lint} (${answer.tool}, ${answer.defaultLevel} by default` +
      (answer.groups.length > 0 ? `, in ${answer.groups.join(", ")})` : ")"),
    answer.summary ?? "",
  ];
  const setting = answer.beautifulRust;
  if (setting) {
    const via = setting.setBy === answer.lint ? "" : ` through ${setting.setBy}`;
    const scope = setting.librariesOnly ? " for libraries" : "";
    const why = setting.reason ? `: ${setting.reason}` : "";
    lines.push(`Beautiful Rust's lints config sets it to ${setting.level}${via}${scope}${why}.`);
  } else {
    lines.push("Beautiful Rust's lints config leaves it at the default.");
  }
  if (answer.explanation) {
    lines.push("", answer.explanation);
  }
  return lines.join("\n");
}

function describeCrate(answer: CrateAnswer): string {
  if (!answer.found) {
    return `No crate named "${answer.name}" on crates.io.`;
  }
  const lines: string[] = [];
  const msrv = (v: { rustVersion: string | null }) =>
    v.rustVersion ? `, needs Rust ${v.rustVersion}` : "";
  if (answer.latest) {
    lines.push(`${answer.name} ${answer.latest.version}${msrv(answer.latest)} (${answer.url})`);
  } else {
    lines.push(`${answer.name} has no released version that isn't yanked.`);
  }
  if (answer.latestPrerelease) {
    lines.push(`Newer pre-release: ${answer.latestPrerelease.version}${msrv(answer.latestPrerelease)}`);
  }
  if (answer.latestFeatures.length > 0) {
    lines.push(`Features: ${answer.latestFeatures.join(", ")}`);
  }
  lines.push(
    `Recent versions: ${answer.recent
      .map((v) => (v.yanked ? `${v.version} (yanked)` : v.version))
      .join(", ")}`,
  );
  return lines.join("\n");
}
