// Crate versions from the crates.io sparse index, the same files cargo reads:
// https://doc.rust-lang.org/cargo/reference/registry-index.html

export const INDEX_URL = "https://index.crates.io";
export const USER_AGENT =
  "beautiful-rust-mcp (https://github.com/morganlinton/BeautifulRust)";
const NAME_RE = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const RECENT_VERSIONS = 10;
const MAX_INDEX_BYTES = 8 * 1024 * 1024;
const TIMEOUT_MS = 8000;
// Seconds Cloudflare keeps an index file at the edge before asking again.
const CACHE_TTL = 300;

interface IndexLine {
  vers: string;
  yanked: boolean;
  rust_version?: string | null;
  pubtime?: string | null;
  features?: Record<string, unknown>;
  features2?: Record<string, unknown>;
}

export interface VersionInfo {
  version: string;
  yanked: boolean;
  rustVersion: string | null;
  published: string | null;
}

export interface CrateAnswer {
  name: string;
  found: boolean;
  latest: VersionInfo | null;
  latestFeatures: string[];
  latestPrerelease: VersionInfo | null;
  recent: VersionInfo[];
  totalVersions: number;
  yankedVersions: number;
  url: string | null;
}

export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

export class CrateLookupError extends Error {}

export function isValidCrateName(name: string): boolean {
  return NAME_RE.test(name);
}

/** The index path for a crate: `serde` is `se/rd/serde`, `syn` is `3/s/syn`. */
export function indexPath(name: string): string {
  const lower = name.toLowerCase();
  if (lower.length <= 2) {
    return `${lower.length}/${lower}`;
  }
  if (lower.length === 3) {
    return `3/${lower[0]}/${lower}`;
  }
  return `${lower.slice(0, 2)}/${lower.slice(2, 4)}/${lower}`;
}

export async function lookupCrate(name: string, fetcher: Fetcher): Promise<CrateAnswer> {
  if (!isValidCrateName(name)) {
    throw new CrateLookupError(`"${name}" is not a valid crate name`);
  }
  // crates.io treats - and _ as the same name, but the index file uses the
  // spelling the crate was published with.
  const spellings = [...new Set([name, name.replaceAll("-", "_"), name.replaceAll("_", "-")])];
  for (const spelling of spellings) {
    const text = await fetchIndex(spelling, fetcher);
    if (text !== null) {
      return summarize(text);
    }
  }
  return notFound(name);
}

async function fetchIndex(name: string, fetcher: Fetcher): Promise<string | null> {
  let response: Response;
  try {
    response = await fetcher(`${INDEX_URL}/${indexPath(name)}`, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(TIMEOUT_MS),
      // Workers-only: cache at the edge. Other runtimes ignore it.
      cf: { cacheTtl: CACHE_TTL, cacheEverything: true },
    } as RequestInit);
  } catch (error) {
    throw new CrateLookupError(`crates.io index unreachable: ${String(error)}`);
  }
  if (response.status === 404 || response.status === 410 || response.status === 451) {
    return null;
  }
  if (!response.ok) {
    throw new CrateLookupError(`crates.io index returned HTTP ${response.status}`);
  }
  const text = await response.text();
  if (text.length > MAX_INDEX_BYTES) {
    throw new CrateLookupError("crates.io index file is unexpectedly large");
  }
  return text;
}

export function summarize(indexText: string): CrateAnswer {
  const lines: (IndexLine & { name: string })[] = indexText
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line));
  if (lines.length === 0) {
    throw new CrateLookupError("crates.io index file is empty");
  }
  const name = lines[lines.length - 1].name;
  const sorted = [...lines].sort((a, b) => compareSemver(b.vers, a.vers));
  const live = sorted.filter((line) => !line.yanked);
  const stable = live.find((line) => !isPrerelease(line.vers)) ?? null;
  const pre = live.find((line) => isPrerelease(line.vers)) ?? null;
  const newerPre = pre && (!stable || compareSemver(pre.vers, stable.vers) > 0) ? pre : null;
  const latestLine = stable ?? newerPre;
  return {
    name,
    found: true,
    latest: stable ? info(stable) : null,
    latestFeatures: latestLine
      ? Object.keys({ ...latestLine.features, ...latestLine.features2 }).sort()
      : [],
    latestPrerelease: newerPre ? info(newerPre) : null,
    recent: sorted.slice(0, RECENT_VERSIONS).map(info),
    totalVersions: lines.length,
    yankedVersions: lines.length - live.length,
    url: `https://crates.io/crates/${name}`,
  };
}

function notFound(name: string): CrateAnswer {
  return {
    name,
    found: false,
    latest: null,
    latestFeatures: [],
    latestPrerelease: null,
    recent: [],
    totalVersions: 0,
    yankedVersions: 0,
    url: null,
  };
}

function info(line: IndexLine): VersionInfo {
  return {
    version: line.vers,
    yanked: line.yanked,
    rustVersion: line.rust_version ?? null,
    published: line.pubtime ?? null,
  };
}

function isPrerelease(version: string): boolean {
  return version.split("+")[0].includes("-");
}

/** SemVer 2.0.0 precedence; build metadata is ignored. */
export function compareSemver(a: string, b: string): number {
  const [coreA, preA] = splitVersion(a);
  const [coreB, preB] = splitVersion(b);
  for (let i = 0; i < 3; i++) {
    const diff = (coreA[i] ?? 0) - (coreB[i] ?? 0);
    if (diff !== 0) {
      return Math.sign(diff);
    }
  }
  if (preA.length === 0 || preB.length === 0) {
    return Math.sign(preB.length - preA.length);
  }
  for (let i = 0; i < Math.max(preA.length, preB.length); i++) {
    const x = preA[i];
    const y = preB[i];
    if (x === undefined || y === undefined) {
      return x === undefined ? -1 : 1;
    }
    const nx = /^\d+$/.test(x);
    const ny = /^\d+$/.test(y);
    if (nx && ny) {
      const diff = Number(x) - Number(y);
      if (diff !== 0) {
        return Math.sign(diff);
      }
    } else if (nx !== ny) {
      return nx ? -1 : 1;
    } else if (x !== y) {
      return x < y ? -1 : 1;
    }
  }
  return 0;
}

function splitVersion(version: string): [number[], string[]] {
  const withoutBuild = version.split("+")[0];
  const dash = withoutBuild.indexOf("-");
  const core = dash === -1 ? withoutBuild : withoutBuild.slice(0, dash);
  const pre = dash === -1 ? [] : withoutBuild.slice(dash + 1).split(".");
  return [core.split(".").map(Number), pre];
}
