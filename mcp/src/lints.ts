export interface BeautifulRustSetting {
  level: string;
  reason?: string;
  librariesOnly?: boolean;
}

export interface Lint {
  name: string;
  tool: "rustc" | "clippy";
  defaultLevel: string;
  summary: string;
  groups?: string[];
  explanation?: string;
  beautifulRust?: BeautifulRustSetting;
}

export interface LintData {
  toolchain: { rustc: string; clippy: string };
  lints: Record<string, Lint>;
  groups: Record<string, { members: number; beautifulRust?: BeautifulRustSetting }>;
}

export interface LintAnswer {
  found: boolean;
  lint: string | null;
  tool: "rustc" | "clippy" | null;
  defaultLevel: string | null;
  groups: string[];
  summary: string | null;
  explanation: string | null;
  beautifulRust: {
    level: string;
    setBy: string;
    reason: string | null;
    librariesOnly: boolean;
  } | null;
  suggestions: string[];
  toolchain: string;
}

/** `unwrap-used`, `clippy::unwrap_used`, and `#[warn(clippy::unwrap_used)]` all name one lint. */
export function normalizeLintName(input: string): string {
  const inner = input.trim().match(/^#!?\[\w+\((.+)\)\]$/)?.[1] ?? input;
  return inner.trim().toLowerCase().replaceAll("-", "_").replace(/^clippy\s*::\s*/, "clippy::");
}

export function explainLint(data: LintData, input: string): LintAnswer {
  const name = normalizeLintName(input);
  const lint = data.lints[name] ?? data.lints[`clippy::${name}`];
  const toolchain = data.toolchain.clippy;
  if (!lint) {
    return {
      found: false,
      lint: null,
      tool: null,
      defaultLevel: null,
      groups: [],
      summary: null,
      explanation: null,
      beautifulRust: null,
      suggestions: suggest(data, name),
      toolchain,
    };
  }
  return {
    found: true,
    lint: lint.name,
    tool: lint.tool,
    defaultLevel: lint.defaultLevel,
    groups: lint.groups ?? [],
    summary: lint.summary,
    explanation: lint.explanation ?? null,
    beautifulRust: beautifulRustSetting(data, lint),
    suggestions: [],
    toolchain,
  };
}

/** The lint's own entry in lints.toml wins over a group that turns it on. */
function beautifulRustSetting(data: LintData, lint: Lint): LintAnswer["beautifulRust"] {
  if (lint.beautifulRust) {
    return {
      level: lint.beautifulRust.level,
      setBy: lint.name,
      reason: lint.beautifulRust.reason ?? null,
      librariesOnly: lint.beautifulRust.librariesOnly ?? false,
    };
  }
  for (const group of lint.groups ?? []) {
    const setting = data.groups[group]?.beautifulRust;
    if (setting) {
      return {
        level: setting.level,
        setBy: group,
        reason: setting.reason ?? null,
        librariesOnly: setting.librariesOnly ?? false,
      };
    }
  }
  return null;
}

/** Up to five lint names that share the most words with the input. */
function suggest(data: LintData, name: string): string[] {
  const words = new Set(name.replace(/^clippy::/, "").split("_").filter(Boolean));
  if (words.size === 0) {
    return [];
  }
  const scored: { name: string; score: number }[] = [];
  for (const candidate of Object.keys(data.lints)) {
    const parts = candidate.replace(/^clippy::/, "").split("_");
    const score = parts.filter((p) => words.has(p)).length;
    if (score > 0) {
      scored.push({ name: candidate, score: score / parts.length });
    }
  }
  scored.sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
  return scored.slice(0, 5).map((s) => s.name);
}
