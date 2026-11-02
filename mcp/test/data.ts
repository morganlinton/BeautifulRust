import guidanceJson from "../data/guidance.json" with { type: "json" };
import lintsJson from "../data/lints.json" with { type: "json" };
import type { GuidanceData } from "../src/guidance.ts";
import type { LintData } from "../src/lints.ts";

// Built by scripts/build-mcp-data.py; run `npm run data` first.
export const guidance = guidanceJson as unknown as GuidanceData;
export const lints = lintsJson as unknown as LintData;
