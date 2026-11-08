import type { Fetcher } from "./crates.ts";

// An in-memory cache for crates.io index files. Vercel's Fluid compute reuses a
// warm instance across requests, so repeated lookups of the same crate stay off
// crates.io for `ttlMs`. Each instance keeps its own cache; a cold start begins
// empty.

export interface CacheOptions {
  /** How long an answer stays fresh. */
  ttlMs: number;
  /** Upper bound on cached body bytes; the least recently used go first. */
  maxBytes: number;
  /** Clock, for tests. */
  now?: () => number;
}

interface Entry {
  expires: number;
  status: number;
  body: string;
}

/** Statuses worth remembering: a found crate, or one that doesn't exist. */
const CACHEABLE = new Set([200, 404, 410, 451]);

export function cachingFetcher(inner: Fetcher, options: CacheOptions): Fetcher {
  const entries = new Map<string, Entry>();
  const now = options.now ?? Date.now;
  let bytes = 0;

  const remove = (url: string) => {
    const entry = entries.get(url);
    if (entry) {
      bytes -= entry.body.length;
      entries.delete(url);
    }
  };

  return async (url, init) => {
    const hit = entries.get(url);
    if (hit && hit.expires > now()) {
      // Move to the back of the Map, which keeps least recently used first.
      entries.delete(url);
      entries.set(url, hit);
      return new Response(hit.body, { status: hit.status });
    }
    remove(url);
    const response = await inner(url, init);
    if (!CACHEABLE.has(response.status)) {
      return response;
    }
    const body = await response.text();
    if (body.length <= options.maxBytes) {
      entries.set(url, { expires: now() + options.ttlMs, status: response.status, body });
      bytes += body.length;
      for (const oldest of entries.keys()) {
        if (bytes <= options.maxBytes) {
          break;
        }
        remove(oldest);
      }
    }
    return new Response(body, { status: response.status });
  };
}
