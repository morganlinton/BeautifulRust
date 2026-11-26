// Crate versions and direct dependencies from the crates.io sparse index, the
// same files cargo reads:
// https://doc.rust-lang.org/cargo/reference/registry-index.html

export const INDEX_URL = "https://index.crates.io";
export const USER_AGENT =
  "beautiful-rust-mcp (https://github.com/morganlinton/BeautifulRust)";
const NAME_RE = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const RECENT_VERSIONS = 10;
const MAX_INDEX_BYTES = 8 * 1024 * 1024;
const TIMEOUT_MS = 8000;
const NEAREST_VERSIONS = 5;

interface IndexDep {
  name: string;
  req: string;
  features?: unknown;
  optional?: boolean;
  default_features?: boolean;
  target?: string | null;
  kind?: string | null;
  package?: string | null;
}

interface IndexLine {
  name: string;
  vers: string;
  yanked: boolean;
  rust_version?: string | null;
  pubtime?: string | null;
  features?: Record<string, unknown>;
  features2?: Record<string, unknown>;
  deps?: IndexDep[];
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

export interface DependencyInfo {
  name: string;
  /** Real crate name when `name` is a rename; null when the dependency is not renamed. */
  package: string | null;
  req: string;
  kind: "normal" | "build" | "dev";
  optional: boolean;
  defaultFeatures: boolean;
  features: string[];
  target: string | null;
  /** Features of this version that enable this optional dependency. */
  enabledBy: string[];
}

export interface DependencyAnswer {
  name: string;
  found: boolean;
  version: string | null;
  yanked: boolean;
  dependencies: DependencyInfo[];
  features: Record<string, string[]>;
  defaultFeatures: string[];
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
  const lines = await readIndex(name, fetcher);
  if (lines === null) {
    return notFound(name);
  }
  return summarizeLines(lines);
}

export async function lookupDependencies(
  name: string,
  version: string | undefined,
  fetcher: Fetcher,
): Promise<DependencyAnswer> {
  const lines = await readIndex(name, fetcher);
  if (lines === null) {
    return notFoundDependencies(name);
  }
  return dependenciesOf(lines, version);
}

/**
 * Direct dependencies of one index version. `version` is an exact version
 * string; omit it for the newest non-yanked stable release, or the newest
 * pre-release when the crate has no stable release.
 */
export function dependenciesOf(lines: IndexLine[], version?: string): DependencyAnswer {
  if (lines.length === 0) {
    throw new CrateLookupError("crates.io index file is empty");
  }
  const name = lines[lines.length - 1].name;
  const requested = version?.trim() ?? "";
  const chosen =
    requested.length === 0 ? defaultVersion(lines) : (lines.find((line) => line.vers === requested) ?? null);
  if (requested.length > 0 && chosen === null) {
    const nearest = nearestVersions(lines, requested)
      .map((line) => (line.yanked ? `${line.vers} (yanked)` : line.vers))
      .join(", ");
    throw new CrateLookupError(`No version "${requested}" of ${name}. Nearest versions: ${nearest}.`);
  }
  if (chosen === null) {
    return {
      name,
      found: true,
      version: null,
      yanked: false,
      dependencies: [],
      features: {},
      defaultFeatures: [],
      url: `https://crates.io/crates/${name}`,
    };
  }
  const features = featureMap(chosen);
  return {
    name,
    found: true,
    version: chosen.vers,
    yanked: chosen.yanked,
    dependencies: (chosen.deps ?? []).map((dep) => toDependency(dep, features)),
    features,
    defaultFeatures: [...(features.default ?? [])],
    url: `https://crates.io/crates/${name}`,
  };
}

async function readIndex(name: string, fetcher: Fetcher): Promise<IndexLine[] | null> {
  if (!isValidCrateName(name)) {
    throw new CrateLookupError(`"${name}" is not a valid crate name`);
  }
  // crates.io treats - and _ as the same name, but the index file uses the
  // spelling the crate was published with.
  const spellings = [...new Set([name, name.replaceAll("-", "_"), name.replaceAll("_", "-")])];
  for (const spelling of spellings) {
    const text = await fetchIndex(spelling, fetcher);
    if (text !== null) {
      return parseIndex(text);
    }
  }
  return null;
}

async function fetchIndex(name: string, fetcher: Fetcher): Promise<string | null> {
  let response: Response;
  try {
    response = await fetcher(`${INDEX_URL}/${indexPath(name)}`, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
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

function parseIndex(indexText: string): IndexLine[] {
  const lines: IndexLine[] = indexText
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as IndexLine);
  if (lines.length === 0) {
    throw new CrateLookupError("crates.io index file is empty");
  }
  return lines;
}

export function summarize(indexText: string): CrateAnswer {
  return summarizeLines(parseIndex(indexText));
}

function summarizeLines(lines: IndexLine[]): CrateAnswer {
  const name = lines[lines.length - 1].name;
  const { stable, newerPre, sorted, liveCount } = classify(lines);
  const latestLine = stable ?? newerPre;
  return {
    name,
    found: true,
    latest: stable ? info(stable) : null,
    latestFeatures: latestLine ? Object.keys(featureMap(latestLine)) : [],
    latestPrerelease: newerPre ? info(newerPre) : null,
    recent: sorted.slice(0, RECENT_VERSIONS).map(info),
    totalVersions: lines.length,
    yankedVersions: lines.length - liveCount,
    url: `https://crates.io/crates/${name}`,
  };
}

/** Newest non-yanked stable release, else the newest pre-release. */
function defaultVersion(lines: IndexLine[]): IndexLine | null {
  const { stable, newerPre } = classify(lines);
  return stable ?? newerPre;
}

function classify(lines: IndexLine[]): {
  stable: IndexLine | null;
  newerPre: IndexLine | null;
  sorted: IndexLine[];
  liveCount: number;
} {
  const sorted = [...lines].sort((a, b) => compareSemver(b.vers, a.vers));
  const live = sorted.filter((line) => !line.yanked);
  const stable = live.find((line) => !isPrerelease(line.vers)) ?? null;
  const pre = live.find((line) => isPrerelease(line.vers)) ?? null;
  const newerPre = pre && (!stable || compareSemver(pre.vers, stable.vers) > 0) ? pre : null;
  return { stable, newerPre, sorted, liveCount: live.length };
}

function featureMap(line: IndexLine): Record<string, string[]> {
  // `features2` is the current feature syntax and replaces `features` for the same name.
  const merged = new Map<string, string[]>();
  for (const source of [line.features, line.features2]) {
    if (!source) {
      continue;
    }
    for (const [key, value] of Object.entries(source)) {
      merged.set(key, stringList(value));
    }
  }
  const keys = [...merged.keys()].sort();
  return Object.fromEntries(keys.map((key) => [key, merged.get(key) ?? []]));
}

function toDependency(dep: IndexDep, features: Record<string, string[]>): DependencyInfo {
  const optional = dep.optional === true;
  const packageName =
    typeof dep.package === "string" && dep.package.length > 0 && dep.package !== dep.name ? dep.package : null;
  return {
    name: dep.name,
    package: packageName,
    req: dep.req,
    kind: dep.kind === "build" || dep.kind === "dev" ? dep.kind : "normal",
    optional,
    defaultFeatures: dep.default_features !== false,
    features: stringList(dep.features),
    target: typeof dep.target === "string" && dep.target.length > 0 ? dep.target : null,
    enabledBy: optional ? featuresEnabling(dep.name, features) : [],
  };
}

/** Features whose values name this dependency, as `dep:name` or a bare `name`. */
function featuresEnabling(depName: string, features: Record<string, string[]>): string[] {
  const enabledBy: string[] = [];
  for (const [feature, values] of Object.entries(features)) {
    if (values.includes(`dep:${depName}`) || values.includes(depName)) {
      enabledBy.push(feature);
    }
  }
  return enabledBy;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function nearestVersions(lines: IndexLine[], version: string): IndexLine[] {
  return [...lines]
    .sort((a, b) => {
      const diff = versionDistance(version, a.vers) - versionDistance(version, b.vers);
      return diff !== 0 ? diff : compareSemver(b.vers, a.vers);
    })
    .slice(0, NEAREST_VERSIONS);
}

/** Lower is closer. Unparseable versions sort after every real version. */
function versionDistance(requested: string, candidate: string): number {
  const [coreA, preA] = splitVersion(requested);
  const [coreB, preB] = splitVersion(candidate);
  const weights = [1_000_000, 1_000, 1];
  let score = 0;
  for (let i = 0; i < 3; i++) {
    const left = coreA[i] ?? 0;
    const right = coreB[i] ?? 0;
    if (Number.isNaN(left) || Number.isNaN(right)) {
      return Number.MAX_SAFE_INTEGER;
    }
    score += Math.abs(left - right) * weights[i];
  }
  if (preA.join(".") !== preB.join(".")) {
    score += 1;
  }
  return score;
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

function notFoundDependencies(name: string): DependencyAnswer {
  return {
    name,
    found: false,
    version: null,
    yanked: false,
    dependencies: [],
    features: {},
    defaultFeatures: [],
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
