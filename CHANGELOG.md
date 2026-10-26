# Changelog

All notable changes to this project are listed here. Versions follow
[Semantic Versioning](https://semver.org/), and the version lives in
`.claude-plugin/plugin.json`.

## [Unreleased]

- `lints/check/` and `scripts/check-lints.sh` prove every lint in `lints/lints.toml`
  fires, and fail if a lint goes quiet or the table drifts. Contributed by
  @mvanhorn.
- `lints/lints.toml` adds `redundant_clone`, `rc_buffer`, `string_add`, and
  `wildcard_imports`, and allows `module_inception` and `enum_glob_use`, from the same
  contribution. It now notes that the two suppression lints need Rust 1.81 or later.
- `scripts/check-skill.py` checks skill frontmatter, links, eval cases, and
  plugin manifests. CI runs it on push and pull request.

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

[Unreleased]: https://github.com/morganlinton/BeautifulRust/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/morganlinton/BeautifulRust/releases/tag/v1.0.0
