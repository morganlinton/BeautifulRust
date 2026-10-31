# The backend-rust stack (framework digest)

Source: this digest is written for the axum + tokio + sqlx (Postgres) backend
stack, following a vertical-slicing, hexagonal-architecture crate workspace
(see the facta backend-rust guides: hexagonal architecture, vertical slicing,
dependency rules). It is the Rust analogue of what a Bevy digest does for game
code: name the conventions to leave alone, and the bugs that pass every lint.

## What changes from the general rules

These rules from `SKILL.md` **do not apply** to framework-managed code:

- **"Application error handling: `anyhow` or `eyre` is the right tool"** — wrong
  inside the stack: one `core::Error` enum (`thiserror`) crosses every ring, and
  each adapter maps foreign errors (`sqlx::Error`, `reqwest::Error`) into it at
  its own boundary. `anyhow` appears only in the composition root's boot path
  (`Config::from_env`), where failing fast with a message is the contract.
- **"Application code stays concrete; no speculative generality"** — the port
  seam is the sanctioned exception: use-case services hold `Arc<dyn Trait>`, not
  a concrete `Pg*` type and not a generic `S: Repository` parameter. The trait
  object is the contract that lets every crate's tests inject the mock from
  `<app>-ports` (feature `mock`).
- **"Write `async fn` rather than `fn -> impl Future`, except in traits"** and
  **"library code doesn't assume a runtime"** — in this stack the exception is
  the norm: ports are `#[async_trait]` traits (bare `async fn` in a trait is not
  dyn-compatible) held behind `Arc<dyn ...>`, and the `Send + Sync + 'static`
  bound is load-bearing — it is what makes a port shareable across tokio tasks.
  The composition root owns the runtime (`axum::serve`); slices never call
  `block_on`.
- **"Reach for `Rc`/`Arc` only when shared ownership is part of the design"** —
  here it is the design: every service is `#[derive(Clone)]` over `Arc<dyn Trait>`
  fields, `Arc<PgPool>` flows through `AppState`, and adapters take the pool by
  clone (cheap — inner `Arc`). Write `Arc::clone(&x)` so cheap clones stay
  visible (`clone_on_ref_ptr`).
- **"Up to two optional parameters: inherent constructors; beyond that, a
  builder"** — wiring is not construction: don't hand-roll a DI graph in a
  slice. The composition root's `AppState::from_env` (production) and
  `with_repos` (tests) are the whole object graph; no service locator, no
  import-time wiring, no re-wiring inside slices.

## Layout: hexagonal + vertical slicing

- **Rings:** `<app>-api` (composition root, knows everything) -> slices
  (`<app>-<scope>`, one capability per crate) -> `ports` (`<app>-ports`: traits
  in `domain/`, `Pg*` adapters in `adapters/`, mocks in `mock/`) -> `core`
  (`<app>-core`: typed IDs, value objects, one `Error` enum — depends on
  nothing). Infra adapters (`<app>-mailer`, `<app>-warden`) and clients
  (`<app>-sdk`, `-cli`) also depend on core only, never on the root.
- **Slices don't depend on each other.** A new feature is a new slice (a new
  crate); shared behavior moves down into `ports`/`core`, not sideways. The one
  orchestrator (`<app>-loom`) composes slices.
- **Port signatures are pure-domain:** no `sqlx::Error`, no `PgRow`, no
  `reqwest::Response` in a trait method; a private `*Row` struct `#[derive(FromRow)]`
  with `into_domain()` stays inside the adapter.
- **SQL lives only in `ports/src/adapters/`**, written as `query_as!` (verified
  against the committed `.sqlx/` offline cache), and every migration is a paired
  `NNNN_name.up.sql` + `.down.sql` run by the root on boot.
- **Enforced, not remembered:** Cargo rejects a cycle but not a direction, so
  the ring rules live in `[workspace.lints]` (`unsafe_code = "forbid"`, clippy
  `-D warnings`) and in review; each member's `[dependencies]` edge list is the
  graph. Rust has no import-linter — the Cargo.toml edges are the contract.

## Quiet failure modes that every lint passes

These are the bugs the machine checks cannot see:

1. **Blocking work inside async** — `std::fs`, `std::thread::sleep`, or a CPU
   loop inside an `async fn` (an axum handler, a `#[async_trait]` port, a loom
   worker) stalls the tokio worker thread for every task sharing it; the symptom
   is tail latency, not an error. `tokio::task::spawn_blocking` for the calls,
   `yield_now()` for short CPU bursts, never `block_on` on the executor.
2. **Transactions held across awaits on unrelated I/O** — the adapter opens a
   transaction for a multi-statement write and commits atomically; holding it
   while awaiting an HTTP call pins a pooled `PgPool` connection for the whole
   round trip. Pool exhaustion surfaces as latency and a `readyz` flip, not an
   error message.
3. **`query_as!` drift and unpaired migrations** — with `DATABASE_URL` set,
   sqlx checks queries against the live schema, so a local build "passes" while
   the committed `.sqlx/` cache goes stale; CI builds offline and fails, or
   schema and queries drift anyway. After every SQL edit: `just sqlx-prepare`,
   commit `.sqlx/`, and ship the `.down.sql` pair — a `.up.sql` without its
   inverse has no deterministic rollback.
4. **`Error::Internal(detail)` text leaking to clients** — the adapter maps
   `sqlx` text into the error's detail field; the handler's `IntoResponse`
   match must return a generic message and log the detail server-side with the
   request id. Putting the internal string into the response body is a leak,
   and so is a 500 that should have been a 404 or 409.
5. **Config read mid-request** — `Config::from_env()` validates on boot: a
   missing or malformed var fails the deploy, not a request. Reading env (or
   anything else) after startup fails at request time; pass `Arc<Config>`
   through `AppState`.
6. **tracing without a subscriber** — `tracing::info!` compiles and emits
   nothing when no subscriber is installed, or when the worker binary's main
   never configured the `env-filter`. Install the subscriber once per binary
   (`<app>-api` and the `<app>-worker` alike) and let `tower-http`'s
   TraceLayer inject the request id; without it, spans never reach the log.
7. **Axum extractor misuse** — a body-consuming extractor (`Json<T>`) must be
   the last handler parameter and there can be only one per handler; doing I/O
   or calling a service inside an extractor hides the failure from the router's
   error path. Extractors translate the request; the handler validates at the
   HTTP boundary and maps `core::Error` to a status.
8. **A leaf slice depending on a sibling slice** — compiles clean (Cargo
   rejects cycles only), passes clippy, and six months later the god-object is
   back. New features are crates; shared behavior is a lower ring, or the
   `<app>-loom` orchestrator calls both slices.
9. **`tokio::spawn` for work that must survive a restart** — a spawn dies with
   the process on deploy. Anything durable goes through the `<app>-loom`
   outbox/janitor worker; a best-effort spawn says so at the call site.
10. **Unbounded broker channels** — SSE/WS fan-out that queues into an
    unbounded `mpsc` holds memory for a slow client forever. Bound every
    channel and drop a consumer after N pending; batch deltas before broadcast.

## Lint allowances this stack needs

When a repo uses the stack, its `[workspace.lints]` goes on top of the
BeautifulRust base config (`lints/lints.toml` + `lints/clippy.toml`):

- The broad groups go on first at `priority = -1`: `clippy::all`,
  `clippy::pedantic`, and — the stack-specific addition — `clippy::nursery`,
  all at `warn`, enforced with `cargo clippy --all-targets -- -D warnings`.
- `unsafe_code = "forbid"` replaces the base config's warning-level unsafe
  hygiene: a `forbid` is a wall no attribute can reopen.
- `missing_errors_doc = "allow"` where the base config warns: every port
  method returns `core::Result<T>`, so per-method `# Errors` docs are noise;
  the one `Error` enum carries the failure surface, documented once.
- `too_long_first_doc_paragraph = "allow"` — nursery-only noise on
  two-sentence module docs.
- Already allowed by the base config but worth keeping in the workspace table:
  `module_name_repetitions` (a trait named `WidgetRepository` living in
  `<app>-ports`) and `must_use_candidate`.
- Suppressions stay narrow and expiring: `#[expect(lint, reason = "...")]` on
  the smallest item that needs it. A blanket `#![allow(clippy::...)]` at a
  crate root that covers an architecture gate is itself a review finding.

## Verification the stack needs beyond the checker

- `just ci` runs the composite gate: fmt-check + `cargo clippy --all-targets
  -- -D warnings` + `cargo check` + `cargo nextest run --workspace`.
- Compile-test the contracts instead of only reading them:
  - The trait seam verifies itself: every use-case's unit tests inject only
    the mock from `<app>-ports` (`mock` feature), so a slice that depends on a
    concrete `Pg*` adapter cannot test against the mock.
  - Domain purity is mechanical: `<app>-core` depends on nothing, so CI can
    assert its `Cargo.toml` carries no `[dependencies]` edges — a one-line
    check that replaces remembering "zero I/O".
  - A cycle fails the build; a forbidden direction (a leaf slice depending on
    a sibling) does not — that edge is review's to catch.
- `.sqlx/` freshness is part of the contract: `just sqlx-prepare` after any SQL
  edit, the committed cache, paired migrations.
- In the BeautifulRust repo itself, `scripts/check-lints.sh` proves the
  `[lints]` table actually fires: every suppression must still be reachable.