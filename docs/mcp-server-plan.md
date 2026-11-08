# Plan: a Beautiful Rust MCP server

Status: phase 1 is built in `mcp/` and tested locally, not deployed. Written 2026-11-02.
On 2026-11-08 hosting moved from Cloudflare Workers to Vercel (Pro plan), where the
Beautiful Rust website already runs; see [Hosting](#hosting).

## Why

The ChatGPT / Codex Plugins Directory rejected our 1.5.0 upload with "We are not
accepting more skills-only submissions at this time." A plugin that also ships an MCP
server is not skills-only. OpenAI's guidelines also require that a plugin do something
the product can't already do, so the server has to be useful on its own merits, not a
shell that exists to qualify.

The useful gap: in ChatGPT on the web, and anywhere without a Rust toolchain, the skills
can't run `cargo clippy`, can't see current crate versions, and can only quote rules from
memory. The server fills those three holes.

## Two things to know before building

1. **The server must be in the first upload.** OpenAI's submission guide says "Adding an
   MCP server to an existing skills-only plugin is not currently supported. If your
   plugin uses an MCP server, include it in the initial ZIP." The 1.5.0 draft is
   skills-only and unpublished. We delete it and upload a new package that contains the
   server from the start. Whether the name `beautiful-rust` is free again after deleting
   the draft is not documented.
2. **Nothing says remote-MCP submissions are open.** The docs gate only local MCP
   servers ("limited to approved partners"). They also didn't mention the skills-only
   pause we hit. So phase 1 is built small and uploaded first, partly as a test: if the
   portal accepts a plugin with a remote server, phase 2 is worth the larger investment.

## Requirements from OpenAI's docs

| Area | Requirement |
|---|---|
| Hosting | A stable, public HTTPS endpoint, typically ending in `/mcp`. No tunnels. |
| Transport | Streamable HTTP. One MCP server per plugin. |
| Declaration | Root `mcp.json` with `$schema` `https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`, `type: "streamable-http"`, and the `url`. No headers. |
| Auth | `none` is allowed for an anonymous, read-only server. |
| Tools | One operation per tool, unique verb names, descriptions that match behavior, explicit `readOnlyHint` / `destructiveHint` / `openWorldHint` booleans (plan to justify each), and an `outputSchema` for any tool that returns `structuredContent`. |
| Inputs | Minimal inputs, validated on the server. No request IDs or telemetry in responses. Never ask for the chat history. |
| Review | Exactly 5 positive and 3 negative test cases, and a demo recording URL covering the main tools on desktop and mobile. |
| Domain | Serve OpenAI's token at `/.well-known/openai-apps-challenge` on the server's host. |
| Privacy | The policy must list data categories, purposes, recipients, and retention periods. Redact personal data before logging. |
| Limits | Apply timeouts and rate limits to expensive tools. `_meta["openai/subject"]` is an anonymous per-user ID for rate limiting. |
| After approval | OpenAI scans the server daily. Server updates go live without a new ZIP; keep tool names and schemas backward compatible. |

## Phase 1: lookups, no code execution

### Tools

All three are read-only, non-destructive, and anonymous.

**`search_guidance(query, skill?)`** returns the most relevant sections of the skills and
reference digests, each with its heading, the skill or guide it comes from, and the
original source guide. This lets ChatGPT on the web quote a rule exactly, with its
source, instead of paraphrasing.
- Data: the Markdown in `skills/`, split into one chunk per heading, built at deploy
  time. No hand-maintained copy of the rules, so it can't drift from the skills.
- `openWorldHint: false` (bundled data only).

**`explain_lint(lint)`** returns what a rustc or clippy lint catches, its group and
default level, what Beautiful Rust's `lints/lints.toml` sets it to and why (the inline
comment), and the fix it suggests.
- Data: generated at deploy time from the pinned toolchain. `clippy-driver -W help`
  lists all 840 clippy lints with group and default level, and `cargo clippy --explain
  <lint>` gives the full text. Clippy's online `lints.json` now returns 404, so we don't
  depend on it. The `lints.toml` level and comment are parsed from the repo.
- `openWorldHint: false`.

**`get_crate_versions(name)`** returns the newest non-yanked version, the newest
pre-release, each version's minimum Rust version (`rust_version`) and publish date, the
feature list of the newest version, and whether the crate exists.
- Data: crates.io's sparse index (`https://index.crates.io/se/rd/serde`), the same
  files cargo reads, one line of JSON per version. Cached at the edge and refreshed
  with `If-None-Match`, so repeated lookups don't reach crates.io.
- `openWorldHint: true` (reads an outside service).
- To verify before building: crates.io's data-access policy (User-Agent and rate
  limits). The page didn't render for automated fetches, so it needs a look in a
  browser.

### Hosting

**Vercel (chosen 2026-11-08).** One Vercel Function on the Pro plan ($20/month), in the
same account as the website. It runs the MCP SDK's Web-standard streamable HTTP
transport, statelessly. Why Vercel over Cloudflare: the website and `beautifulrust.dev`
already live there, so the DNS doesn't move and there's one account. Hobby (free) is for
non-commercial use only, so the server runs on Pro to be safe.

How it's built and deployed:

- `npm run build` builds the data (it needs a Rust toolchain with clippy) and bundles
  `src/` with esbuild into `build/server.mjs`. `api/index.mjs`, the function, only
  re-exports that bundle, so Vercel never compiles our TypeScript.
- Vercel's build machines have no Rust, so deploys are prebuilt: `npm run deploy` runs
  `vercel build` locally and uploads the output with `vercel deploy --prebuilt`.
- `vercel.json` rewrites every path to the function, which routes `/mcp`,
  `/.well-known/openai-apps-challenge`, and `/` itself.
- crates.io answers are cached in memory for five minutes per warm instance (Fluid
  compute reuses instances), in place of Cloudflare's edge cache.
- The domain is `mcp.beautifulrust.dev`, added to the Vercel project.

The comparison that first picked Cloudflare, kept for reference:

| | Free plan | Paid plan |
|---|---|---|
| Price | $0 | $5/month minimum |
| Requests | 100,000 per day | 10 million/month included, then $0.30 per million |
| CPU per request | 10 ms | 30 s default (up to 5 min) |

The free plan should hold for launch traffic. The risk is the 10 ms CPU limit on
`search_guidance`; ranking a prebuilt index of a few hundred chunks should fit, and the
paid plan removes the question. Phase 2 needs the paid plan anyway.

### Code layout

```
mcp/
├── api/index.mjs          the Vercel Function; re-exports build/server.mjs
├── src/index.ts           request router: MCP handler and the challenge route
├── src/search.ts          ranking over the guidance index
├── src/crates.ts          sparse-index fetch and parse
├── src/cache.ts           in-memory cache for crates.io answers
├── data/                  generated at deploy time, not committed
├── test/                  unit tests per tool, plus MCP protocol tests
├── scripts/bundle.mjs     esbuild bundle of src/ and data/
└── vercel.json
scripts/build-mcp-data.py  skills -> guidance index; toolchain + lints.toml -> lint catalog
mcp.json                   plugin declaration for OpenAI
```

CI builds the data, type-checks, and runs the tests on every pull request. A deploy job
on `main` could later publish the function with a Vercel token stored as an Actions
secret; for now Morgan deploys from a Mac with `npm run deploy`.

## Phase 2: `check_rust`

### The tool

**`check_rust(files, edition?, crate_type?)`** runs `cargo check` and `cargo clippy`
with Beautiful Rust's lints on a snippet or a small crate. It returns each diagnostic
with its file, line, lint name, and message, and where one exists, the Beautiful Rust
rule behind it (from the same mapping `explain_lint` uses). It can also run the
crate's tests, with `run_tests: true`.

- Read-only toward the user's environment: `readOnlyHint: true`,
  `destructiveHint: false`, `openWorldHint: false` (the sandbox has no network).
- Inputs: up to 10 files, 64 KB total, a `Cargo.toml` limited to an allowlist of
  dependencies.

### The sandbox

User code runs in a throwaway container with no network.

- **Image:** a slim Rust image with the same pinned toolchain as the lint catalog,
  clippy, and an allowlist of popular crates (for example serde, thiserror, anyhow,
  regex, itertools, tokio) vendored and prebuilt. Then a check only compiles the user's
  code, and nothing is downloaded at check time.
- **Limits:** a 30 s wall-clock timeout, capped memory and disk, output truncated to a
  fixed size, one job per container at a time, and a per-user rate limit keyed on
  `openai/subject` (for example 20 checks per hour).
- **Why "check" first:** `cargo check` and `cargo clippy` mostly don't run user code,
  but build scripts and proc macros do, and `run_tests` runs it directly. Treat every
  job as hostile code, which is what the no-network, throwaway container is for.

### Hosting options

With phase 1 on Vercel, **Vercel Sandbox** is now the natural first choice: throwaway
microVMs in the same account, with a firewall that can block all network access. Its
pricing changed several times in 2026, so the cost estimate below (made for Cloudflare)
needs redoing before phase 2.


| Option | Fit | Price |
|---|---|---|
| Cloudflare Sandbox SDK / Containers (first pick before the move) | Same account and Worker as phase 1. Each sandbox is "a microVM with its own kernel and network", and internet access can be turned off. Scheduling is in public beta. | Workers Paid ($5/mo). Includes 375 vCPU-minutes, 25 GiB-hours of memory, and 200 GB-hours of disk per month. Then $0.000020 per vCPU-second, $0.0000025 per GiB-second, $0.00000007 per GB-second. |
| E2B | A managed code sandbox. Easy API; a second vendor and account. | $0.000014 per vCPU-second and $0.0000045 per GiB-second. Free tier is a one-time $100 credit; Pro is $150/month plus usage. |
| Fly.io Machines | Per-second billing, more setup, no free tier. | About $0.0000052/s for shared-cpu-2x with 2 GB. |
| Self-hosted Rust Playground | Open source (MIT/Apache) with a working `/clippy` endpoint, but needs a Docker host, so it doesn't fit Workers or Fly Machines. | Cost of a VM. |
| Public play.rust-lang.org API | Not an option: no published terms for third-party use, and no control over limits. | — |

Unverified: Cloudflare container cold-start time, and whether the Rust image with
vendored crates fits the instance disk (12 GB on the 1 vCPU, 6 GiB size).

### Cost estimate

Assumption: an average check keeps a 1 vCPU, 6 GiB container busy for about 10 seconds,
including warm-up.

| | Per check | 1,000 checks/day (≈30,000/month) |
|---|---|---|
| CPU | 10 vCPU-s × $0.000020 = $0.0002 | about $6 |
| Memory | 60 GiB-s × $0.0000025 = $0.00015 | about $4.50 |
| Disk and egress | negligible | under $1 |
| **Total** | **about $0.0004** | **about $11/month on top of $5** |

The included amounts cover roughly the first 2,000 checks a month. Containers left idle
between checks still bill for memory, so the sleep timeout matters. A spending alert and
a global daily cap on checks keep a traffic spike from becoming a bill.

## Privacy

`PRIVACY.md` needs a section for the server:

- **What it receives:** search terms, lint and crate names, and, in phase 2, the code
  submitted for checking.
- **What happens to it:** used only to answer that request. Code exists only inside the
  throwaway container and is deleted when the check ends. Nothing is sold or shared.
- **Logs:** request metadata only (tool name, duration, result status, and a hash of the
  anonymous user ID for rate limiting), kept 30 days. No code or query text is logged.
- **Recipients:** Vercel as the host. `get_crate_versions` asks crates.io for public
  index files and sends nothing about the user.

## Claude Code

Claude Code plugins can declare an HTTP MCP server too, so the same server can ship in
`.claude-plugin/plugin.json`. Claude Code users usually have cargo locally, so
`check_rust` matters less for them, but `get_crate_versions` and `explain_lint` still help.
Make it opt-in, since some users won't want code sent to a server.

## Review cases

Positive (prompt → tools → expected behavior):

1. "What's the latest version of serde, and what Rust version does it need?" →
   `get_crate_versions` → names the newest non-yanked version and its `rust_version`.
2. "What does clippy's unwrap_used lint catch, and does Beautiful Rust turn it on?" →
   `explain_lint` → describes the lint, says it's set to warn, and gives the reason.
3. "What does Beautiful Rust say about bool parameters?" → `search_guidance` → quotes
   the rule (use an enum) and cites the Google Rust Style Guide.
4. "Check this Rust function with clippy." (a function using `unwrap()` on user input) →
   `check_rust` → reports `unwrap_used` at the right line and the rule behind it.
5. "Port this Python function to Rust and make sure it passes clippy." →
   `check_rust` → returns Rust code that the tool reports clean.

Negative (the tools should not be called):

1. "Write a Python script that renames files in a folder."
2. "Publish my crate to crates.io."
3. "What's the weather in Los Angeles?"

## Build order

1. Confirm crates.io's data-access policy in a browser, and pick the domain (for example
   a subdomain of the Beautiful Rust website) and the hosting account (Vercel, decided).
2. Build phase 1: the data script, the function, tests, and the challenge route. Deploy.
3. Update `PRIVACY.md`, add `mcp.json`, bump the plugin to 1.6.0, and add the review
   cases to `plugin.json`.
4. Delete the 1.5.0 draft, upload the new ZIP, and see whether the portal accepts it. If
   it shows another blocking finding, stop here and ask OpenAI before building phase 2.
5. Build phase 2: the sandbox image, `check_rust`, limits, spending alerts, and load
   tests. Deploy it as a server update.
6. Record the demo (desktop and mobile), complete the review form, and submit.

## Decisions for you

- **Domain** for the server, for example `mcp.<website domain>`.
- **Hosting account:** decided: Vercel Pro ($20/month), shared with the website.
- **Monthly spending cap** for phase 2, which sets the daily check limit.
- **Crate allowlist** for `check_rust`.
- **Submission timing:** upload after phase 1 as a test (recommended), or wait and
  submit once with both phases.
