import { tokenize } from "./tokenize.ts";

export interface GuidanceChunk {
  id: string;
  skill: string;
  file: string;
  heading: string;
  trail: string[];
  url: string;
  text: string;
  terms: Record<string, number>;
  length: number;
  source?: { name: string; url?: string };
}

export interface GuidanceData {
  chunks: GuidanceChunk[];
  df: Record<string, number>;
  avgLength: number;
  tokenizerSamples: { text: string; tokens: string[] }[];
}

export interface GuidanceResult {
  section: string;
  skill: string;
  file: string;
  url: string;
  source: string | null;
  sourceUrl: string | null;
  text: string;
  truncated: boolean;
}

export const SKILLS = ["rust-best-practices", "rust-review", "rust-port"] as const;
export type Skill = (typeof SKILLS)[number];

const K1 = 1.2;
const B = 0.75;
// Long sections are cut here; the result's url links to the full text.
export const MAX_SECTION_CHARS = 3000;

/** Ranks guidance sections against a query with BM25. */
export function searchGuidance(
  data: GuidanceData,
  query: string,
  options: { skill?: Skill; limit: number },
): GuidanceResult[] {
  const terms = [...new Set(tokenize(query))];
  const total = data.chunks.length;
  const scored: { chunk: GuidanceChunk; score: number }[] = [];
  for (const chunk of data.chunks) {
    if (options.skill && chunk.skill !== options.skill) {
      continue;
    }
    let score = 0;
    for (const term of terms) {
      const tf = chunk.terms[term];
      if (!tf) {
        continue;
      }
      const df = data.df[term] ?? 0;
      const idf = Math.log(1 + (total - df + 0.5) / (df + 0.5));
      const norm = tf + K1 * (1 - B + (B * chunk.length) / data.avgLength);
      score += (idf * tf * (K1 + 1)) / norm;
    }
    if (score > 0) {
      scored.push({ chunk, score });
    }
  }
  scored.sort((a, b) => b.score - a.score || a.chunk.id.localeCompare(b.chunk.id));
  return scored.slice(0, options.limit).map(({ chunk }) => toResult(chunk));
}

function toResult(chunk: GuidanceChunk): GuidanceResult {
  const truncated = chunk.text.length > MAX_SECTION_CHARS;
  return {
    section: chunk.trail.join(" > "),
    skill: chunk.skill,
    file: chunk.file,
    url: chunk.url,
    source: chunk.source?.name ?? null,
    sourceUrl: chunk.source?.url ?? null,
    text: truncated ? `${chunk.text.slice(0, MAX_SECTION_CHARS)}…` : chunk.text,
    truncated,
  };
}
