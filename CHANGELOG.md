# Changelog

All notable changes to this project are listed here. Versions follow
[Semantic Versioning](https://semver.org/), and the version lives in
`.claude-plugin/plugin.json`.

## [Unreleased]

### Added

- **Bevy support.** `skills/rust-best-practices/references/bevy.md` covers Bevy 0.20.
  It says which general rules don't apply to systems: by-value system parameters, the
  Bevy prelude, public fields on plain-data components, and complex query types. It
  lists the ECS bugs that compile cleanly: conflicting queries (B0001), deferred
  `Commands`, systems with no order between them, and unwrapped `single()`. It also
  gives the four lint allows a Bevy crate needs on top of `lints/lints.toml`. Every
  behavior it describes was confirmed with a test on bevy 0.20.0. Both the writing and
  review skills read it when a crate depends on `bevy`. Proposed by @millionart in #5.
- **Two Bevy eval cases.** `rust-review/evals/review-bevy-arena` plants a query conflict
  and an ordering bug in a combat plugin whose tests pass, alongside valid Bevy patterns
  the review should leave alone. `rust-best-practices/evals/bevy-arena-regen` adds a
  feature to the fixed plugin and checks that Bevy's conventions survive. Both pin
  `bevy = "=0.20.0"` and ship a `Cargo.lock`.
- **A cross-agent benchmark.** `benchmarks/cross-agent-2026-10/` ran all eight eval cases
  on Claude Code and Codex CLI, with and without the skills, and graded them blind. The
  skills raised Codex from 53/85 to 76/85 and Claude from 72/85 to 80/85. The page
  includes every assertion result, the harness, and the caveats, including one case
  where the skills made Claude worse.
- **Every Rust example is compiled.** `scripts/check-examples.py` compiles each Rust
  code block in the skills, the reference digests, the README, and `examples/` with
  `cargo check`, and reports errors at the markdown line. `scripts/examples.json` holds
  the surrounding code that fragments need to compile, or the reason a block is
  skipped. CI runs it on every push and pull request. Contributed by @tmchow in #4.

### Changed

- The glob-import rule in both skills allows a framework's documented prelude, such as
  `use bevy::prelude::*`. Clippy's `wildcard_imports` already exempts these.
- Both skills now cover `impl Into<T>` parameters and collected return values, from the
  Google Rust Style Guide's "Accepting Into" and "Iterators vs. owned collections in
  return types". Application code takes `String` or `&str` rather than
  `impl Into<String>`, and library code returns an iterator instead of collecting into
  a `Vec`. `rust-review` flags both, with Google's exceptions for owned results.

### Fixed

- The Errors section paired `get` with `get_unchecked` as a fallible API and its
  panicking twin, but an out-of-bounds `get_unchecked` is undefined behavior, not a
  panic. It now pairs indexing (`v[i]`, which panics) with `v.get(i)`. Reported and
  fixed by @DylanCosto in #3 and #6.

## [1.4.0] - 2026-10-26

The first release with outside contributions. Thanks to @mvanhorn for both.

### Added

- **A skill checker in CI.** `scripts/check-skill.py` validates every skill's
  frontmatter, links, eval cases, and the plugin manifests, using only Python's
  standard library. It runs on every push and pull request. Contributed by @mvanhorn.
- **Proof that every lint fires.** `lints/check/` is a crate with one deliberate
  violation for each of the 28 lints set to warn, and `scripts/check-lints.sh` runs clippy
  on it. It fails if a lint goes quiet, if something unexpected fires, or if the check
  crate's copy of the table drifts from `lints/lints.toml`. CI now runs it too.
  Contributed by @mvanhorn.
- **Four more lints** in `lints/lints.toml`: `redundant_clone`, `rc_buffer`,
  `string_add`, and `wildcard_imports`. `module_inception` and `enum_glob_use` are now
  allowed, matching rules the skill already states.

### Fixed

- `allow_attributes` and `allow_attributes_without_reason` are silently disabled by
  clippy for crates whose `rust-version` is below 1.81. The lints config and README now
  say so.

### Changed

- `rust-best-practices` is back under the 500-line guidance, with no rules removed.
- CI uses `actions/checkout@v7` and runs with read-only permissions.

## [1.3.0] - 2026-10-25

### Added

- **`rust-port` skill.** Ports C, C++, Python, Go, JavaScript, or TypeScript to
  idiomatic Rust with the same behavior. It ports the original tests first, maps each
  language's habits to Rust (`NULL` and `None` to `Option`, error codes and exceptions to
  error enums, flag ints and magic strings to typed values), keeps the port proportionate
  instead of reimplementing the source language's runtime, and writes a `PORTING.md`
  with API and test mappings and every deliberate difference.
- Two eval cases for it: a C config parser and a Python task scheduler, each with its
  original test suite. With the skill, the ports passed 22 of 22 checks; without it, 19
  of 22. Both configurations ported correctly. The skill's ports were the ones that
  stayed proportionate: the baseline Python port was 5.8 times the original's size and
  reimplemented Python's string and integer parsing; the skill's was 3.1 times, with none.
- `CONTRIBUTING.md` and issue templates for proposing a rule and reporting a review false
  positive.

## [1.2.0] - 2026-10-25

### Added

- **`rust-review` skill.** Point your agent at a file, crate, or diff and get a
  prioritized review: must fix, should fix, and consider. Every finding cites a
  `file:line` location, the rule it breaks with its source, and the smallest code change
  that fixes it. It runs fmt, clippy, and tests when a toolchain is available.
  On the inventory eval it passed 11 of 12 checks against 7 of 12 without the skill;
  the difference was rule citations, code fixes, and line references.
- **Drop-in lints** in `lints/`: a `[lints]` block for `Cargo.toml` and a `clippy.toml`.
  They make clippy enforce the machine-checkable rules, including no `unwrap()` outside
  tests, `// SAFETY:` on every unsafe block, reasons on every suppression, and no `bool`
  parameters. Every lint name was verified against clippy 0.1.99.
- An example review report in `examples/review-inventory.md`.
- A new painted README banner.
- An eval case for the review skill under `skills/rust-review/evals/`.
- README install instructions for agents other than Claude Code, since both skills are
  standard Agent Skills, and a before/after example of what the writing skill changes.
- This changelog.

### Verified

- Every Rust code example in the skills, the reference digests, and the README now
  compiles on stable Rust 1.99.

### Changed

- `rust-best-practices` points to the lints config when a project has no `[lints]` table.

## [1.1.0] - 2026-10-24

Tightened the skill based on a with/without comparison on three realistic tasks.
With the skill, 29 of 30 assertions passed; without it, 24 of 30.

- `bool` parameters are out of public and shared signatures. Use a two-variant
  enum or two methods instead. An existing `bool` is a smell to remove when refactoring.
- New section on refactoring someone else's code: fix every smell on the list, keep
  public behavior identical, show before and after for any signature you change, and
  flag quirks instead of silently fixing them.
- A hand-written `Ord` must come with matching `PartialEq` and `Hash`.
- Added three eval cases under `skills/rust-best-practices/evals/` and a Testing
  section in the README.

## [1.0.0] - 2026-10-23

First release.

- The `rust-best-practices` skill, distilled from the Google Rust Style Guide, the
  Rust API Guidelines, Effective Rust, Rust Design Patterns, and Microsoft's
  Pragmatic Rust Guidelines, with one reference digest per source.
- Packaged as a Claude Code plugin that is its own marketplace.
- MIT license, source attribution, and a plugin icon.

[Unreleased]: https://github.com/morganlinton/BeautifulRust/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/morganlinton/BeautifulRust/releases/tag/v1.0.0
