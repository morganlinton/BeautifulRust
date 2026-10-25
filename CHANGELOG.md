# Changelog

All notable changes to this project are listed here. Versions follow
[Semantic Versioning](https://semver.org/), and the version lives in
`.claude-plugin/plugin.json`.

## [Unreleased]

- Copy-paste `[lints]` table for the skill's compiler and clippy rules, a check
  crate that proves each lint fires, and `scripts/check-lints.sh`.
- README: install instructions for agents other than Claude Code, since the skill
  is a standard Agent Skill.
- README: a before/after example of what the skill changes.
- Added this changelog.

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

[Unreleased]: https://github.com/morganlinton/BeautifulRust/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/morganlinton/BeautifulRust/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/morganlinton/BeautifulRust/releases/tag/v1.0.0
