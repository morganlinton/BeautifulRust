<p align="center">
  <img src="assets/banner.png" alt="Pixel art banner: a crab on rocky tide pools at sunset, with waves, sea stacks, and a forested headland, under the title Beautiful Rust and the subtitle Idiomatic Rust, distilled">
</p>

# Beautiful Rust

Three standard [Agent Skills](https://agentskills.io) and a lints config that teach coding
agents to write, review, port, and enforce idiomatic Rust:

- **`rust-best-practices`** loads whenever an agent writes or changes Rust, and steers it
  toward idiomatic, robust, maintainable code.
- **`rust-review`** reviews existing Rust code, a file, a crate, or a diff, and writes a
  prioritized report where every finding cites the rule it breaks and shows the fix.
- **`rust-port`** ports C, C++, Python, Go, or JavaScript to idiomatic Rust with the same
  behavior, porting the original tests first so you can prove the two match.
- **`lints/`** is a drop-in clippy configuration that enforces the machine-checkable rules
  in CI.

They work with Claude Code, OpenAI Codex, GitHub Copilot, Cursor, Gemini CLI, and any other
agent that reads the Agent Skills format. Every code example in the skills compiles on
stable Rust, and every lint in the config was checked against current clippy.

The guidance is distilled from five sources, with a condensed digest of each bundled in
the skill so the agent can consult the original reasoning when it needs to:

- [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html)
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) (official rust-lang checklist)
- [Effective Rust](https://www.lurklurk.org/effective-rust/) by David Drysdale
- [Rust Design Patterns](https://rust-unofficial.github.io/patterns/) (idioms, patterns, anti-patterns)
- [Microsoft Pragmatic Rust Guidelines](https://microsoft.github.io/rust-guidelines/)

Where the sources disagree, the skill picks a side and says why.

## What it changes

Asked for a small semver-parsing library, an agent without the skill produced working
code with public fields, no `# Errors` docs, and `unwrap()` in its doc examples. With the
skill, the same agent kept the fields private, documented failure modes, and wrote doc
examples users can copy safely. Condensed from those two runs:

```rust
// Without the skill
/// A semantic version. The fields are public for convenience.
pub struct Version {
    pub major: u64,
    pub minor: u64,
    pub patch: u64,
    pub pre: Vec<Identifier>,
    pub build: Vec<String>,
}

impl Version {
    /// Parses a version string.
    ///
    /// ```
    /// let v = Version::parse("1.2.3").unwrap();
    /// ```
    pub fn parse(s: &str) -> Result<Version, ParseError> { /* ... */ }
}
```

```rust
// With the skill
/// A semantic version. Equality, hashing, and ordering ignore build metadata.
pub struct Version {
    major: u64,
    minor: u64,
    patch: u64,
    pre: Vec<Identifier>,
    build: Vec<String>,
}

impl Version {
    /// Parses a version string according to SemVer 2.0.0.
    ///
    /// # Errors
    ///
    /// Returns [`ParseVersionError`] if the string is empty, a numeric part has a
    /// leading zero or overflows `u64`, or an identifier contains invalid characters.
    ///
    /// ```
    /// # use semver_lite::Version;
    /// # fn main() -> Result<(), semver_lite::ParseVersionError> {
    /// let v = Version::parse("1.2.3-beta.1")?;
    /// assert_eq!(v.major(), 1);
    /// # Ok(())
    /// # }
    /// ```
    pub fn parse(s: &str) -> Result<Self, ParseVersionError> { /* ... */ }

    /// Returns the major version number.
    pub fn major(&self) -> u64 { self.major }
}
```

Across three test tasks (a library, a CLI, and refactoring a messy module), the skill
passed 29 of 30 checks against 24 of 30 without it. See [Testing the skills](#testing-the-skills).

## Install

Each skill is a folder under `skills/`: `rust-best-practices/`, `rust-review/`, and
`rust-port/`. Every option below puts those folders where your agent looks for skills.
Install all three; the review and port skills lean on the best-practices skill for style.

### Any agent, one command

The [`skills`](https://github.com/vercel-labs/skills) installer supports most agents
(Node 22.20 or later):

```bash
npx skills add morganlinton/BeautifulRust
```

Add `-g` to install for your user instead of the current project, or `-a <agent>` to pick
an agent, such as `-a codex` or `-a cursor`.

### Claude Code

Install it as a plugin so updates arrive with one command:

```bash
claude plugin install beautiful-rust --marketplace morganlinton/BeautifulRust
```

Inside a session, the same thing is:

```
/plugin marketplace add morganlinton/BeautifulRust
/plugin install beautiful-rust@beautiful-rust
```

This installs all three skills. They appear as `/beautiful-rust:rust-best-practices`,
`/beautiful-rust:rust-review`, and `/beautiful-rust:rust-port`, though you rarely need to
call them, since they trigger on their own. To try it for one session without installing, clone the repo
and run `claude --plugin-dir ./BeautifulRust`.

### GitHub Copilot

With GitHub CLI 2.90 or later:

```bash
gh skill install morganlinton/BeautifulRust rust-best-practices
gh skill install morganlinton/BeautifulRust rust-review
gh skill install morganlinton/BeautifulRust rust-port
```

This installs into the current project by default. Add `--scope user` to install for your
user, or `--agent <name>` to install for a different agent.

### Gemini CLI

```bash
gemini skills install https://github.com/morganlinton/BeautifulRust --path skills/rust-best-practices
gemini skills install https://github.com/morganlinton/BeautifulRust --path skills/rust-review
gemini skills install https://github.com/morganlinton/BeautifulRust --path skills/rust-port
```

### OpenAI Codex, Cursor, or anything else: copy the folder

Clone the repo and copy the three skill folders into your agent's skills directory.
Most agents now read the shared `.agents/skills/` location:

```bash
git clone https://github.com/morganlinton/BeautifulRust
mkdir -p ~/.agents/skills
cp -R BeautifulRust/skills/rust-* ~/.agents/skills/
```

| Agent | User directory | Project directory |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| GitHub Copilot | `~/.copilot/skills/` or `~/.agents/skills/` | `.github/skills/` or `.agents/skills/` |
| Cursor | `~/.cursor/skills/` or `~/.agents/skills/` | `.cursor/skills/` or `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` or `~/.agents/skills/` | `.gemini/skills/` or `.agents/skills/` |

Claude Code does not read `.agents/skills/`, so use its own directory or the plugin.
Restart the agent if the skill doesn't show up right away.

### claude.ai

claude.ai takes one zip per skill, with the skill folder as the zip root:

```bash
cd skills
zip -r ../rust-best-practices.zip rust-best-practices -x '*.DS_Store' -x '*/evals/*'
zip -r ../rust-review.zip rust-review -x '*.DS_Store' -x '*/evals/*'
zip -r ../rust-port.zip rust-port -x '*.DS_Store' -x '*/evals/*'
```

Upload each under **Customize > Skills**. Code execution must be enabled first.

## Reviewing existing code

Ask your agent to review a file, crate, or diff, for example "review src/parser.rs" or
"what would you change in this PR". The `rust-review` skill runs `cargo fmt`, `clippy`, and
the tests when a toolchain is available, then writes a report with three tiers: must fix,
should fix, and consider. Every finding gives a `file:line` location, the rule it breaks
with its source (an API Guidelines code such as `C-GETTER`, an Effective Rust item, a
Microsoft guideline, or a clippy lint), and the smallest code change that fixes it. Each
report ends with what the code already does well.

[`examples/review-inventory.md`](examples/review-inventory.md) is a real review the skill
produced for the deliberately messy module in the eval cases.

## Porting code to Rust

Ask your agent to port a module, for example "port parser.c to Rust" or "rewrite this
Python service in Rust". The `rust-port` skill reads the original and its tests, ports the
tests first, designs a Rust API instead of transliterating the original, and verifies with
`cargo test` and `clippy`. It maps each language's habits to their Rust equivalents:
`NULL` and `None` to `Option`, error codes and exceptions to an error enum, out-parameters
to return values, flag ints and magic strings to typed enums and options, and dict
insertion order to an ordered collection instead of a `HashMap` that would silently
reorder output. Each port comes with a `PORTING.md` that maps the old API and tests to the
new ones and lists every deliberate difference.

## Bevy

Bevy calls your systems and builds their arguments, so some general Rust advice is wrong
for them. Taken at face value, the skills would tell an agent to change `Res<Time>` to a
reference, replace `use bevy::prelude::*` with explicit imports, and split a system to
quiet clippy. When a crate depends on `bevy` or `bevy_ecs`, both the writing and review
skills now read [`references/bevy.md`](skills/rust-best-practices/references/bevy.md)
first. It covers Bevy 0.20 and does two things:

- **It names the conventions to leave alone:** system parameters taken by value, the
  Bevy prelude, public fields on plain-data components, and complex query types.
- **It lists the ECS bugs that compile cleanly.** Two queries that can both mutate the
  same component panic with error B0001 on the first frame. A system can read the world
  before another system's `Commands` have applied. Systems that depend on each other may
  have no order between them. A `.single().unwrap()` crashes the game once the player
  dies.

Every behavior in the reference was checked with a test against bevy 0.20.0. Two eval
cases cover it: a review of a combat plugin with two of those bugs planted, and a feature
added to the fixed plugin, which checks that the agent keeps Bevy's conventions.

## Enforcing the rules with clippy

The skills teach the rules; the lints keep them from slipping back in. Copy
[`lints/clippy.toml`](lints/clippy.toml) next to your `Cargo.toml` and paste the `[lints]`
block from [`lints/lints.toml`](lints/lints.toml) into it, then run:

```bash
cargo clippy --all-targets --all-features -- -D warnings
```

It flags `unwrap()` outside tests, `unsafe` blocks without a `// SAFETY:` comment, `#[allow]`
without a reason, any `bool` function parameter, silent lossy `as` casts, missing `# Errors`
and `# Panics` docs, and leftover `dbg!` and `todo!`. Lints marked `[lib]` in the file are
for libraries, and applications can drop them. Bevy crates need four extra allows,
listed in the [Bevy reference](skills/rust-best-practices/references/bevy.md#keep-bevys-conventions),
because the table otherwise flags every idiomatic system signature.

Every lint in the table is proven to fire. [`lints/check/`](lints/check/src/lib.rs) is a small crate
with one deliberate violation per lint, and this script runs clippy on it from the repo
root:

```bash
bash scripts/check-lints.sh
```

It fails if a lint stops firing, if something unexpected fires, or if the check crate's
copy of the table drifts from `lints/lints.toml`. `allow_attributes` and
`allow_attributes_without_reason` need `rust-version = "1.81"` or later, because clippy
switches them off for crates that can't use `#[expect]`.

## What the writing skill covers

`skills/rust-best-practices/SKILL.md` is about 500 lines, organized so an agent can scan
it while coding:

1. Mindset: Rust-shaped code, invalid states unrepresentable, application vs library
2. Pre-handback checklist: fmt, clippy with `-D warnings`, test, doc; lint policy
3. Ownership and borrowing: what to do instead of cloning for the borrow checker
4. Types and API design: naming, newtypes, common traits, builders, visibility, generics vs `dyn`
5. Errors and panics: `Option` vs `Result` vs panic, library vs application error types
6. Everyday idioms: iterators, combinators, `format!`, imports, drop guards
7. Concurrency and async: `Send` assertions, lock discipline, `async fn`, yield points
8. Unsafe and FFI: when it's allowed, `SAFETY:` comments, soundness, bindgen
9. Crates, modules, dependencies: workspace layout, features, semver
10. Documentation and comments
11. Tests
12. Performance, in order
13. Final checklist

`skills/rust-best-practices/references/` holds one digest per source for deeper lookups.

## Layout

```
BeautifulRust/
├── .claude-plugin/
│   ├── plugin.json         plugin manifest
│   └── marketplace.json    lets this repo act as its own marketplace
├── skills/
│   ├── rust-best-practices/   writing skill
│   │   ├── SKILL.md
│   │   ├── references/        one digest per source, plus bevy.md
│   │   └── evals/
│   ├── rust-review/           review skill
│   │   ├── SKILL.md
│   │   └── evals/
│   └── rust-port/             porting skill
│       ├── SKILL.md
│       └── evals/             a C module and a Python module to port
├── lints/
│   ├── lints.toml             [lints] block for Cargo.toml
│   ├── clippy.toml            clippy thresholds
│   └── check/                 one deliberate violation per lint
├── scripts/
│   ├── check-skill.py         validates skills, evals, and manifests
│   ├── check-lints.sh         proves every lint in the table fires
│   ├── check-examples.py      compiles every Rust example in the docs
│   └── examples.json          context that lets fragment examples compile
├── benchmarks/
│   └── cross-agent-2026-10/   Claude Code vs Codex, with and without the skills
├── examples/
│   └── review-inventory.md    a real review report
├── CHANGELOG.md
├── CONTRIBUTING.md
└── README.md
```

## Testing the skills

`skills/rust-best-practices/evals/` holds four test cases in the layout `claude plugin eval`
reads: a library API design task, an application CLI task, and a refactor-this-module task
with an input file. Each case has the prompt, a description of a good result, and one
assertion per file under `graders/`. Run them with and without the skill from the skill
directory:

```bash
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
```

`skills/rust-review/evals/` holds a review case for the same messy module and one for a
Bevy plugin with two ECS bugs planted, and `skills/rust-port/evals/` holds a C module and
a Python module to port, each with its original test suite. The writing skill also has a
Bevy case that adds a feature to a working plugin. Run them the same way from each
skill's directory.

These are real model runs and are billed.

**Across agents.** The [October 2026 benchmark](benchmarks/cross-agent-2026-10/README.md)
ran all eight cases on Claude Code and OpenAI's Codex CLI, with and without the skills,
and graded the results blind:

| | No skills | Skills |
| --- | --- | --- |
| Claude Code (Opus 5.5) | 72/85 (85%) | 80/85 (94%) |
| Codex CLI (default model) | 53/85 (62%) | 76/85 (89%) |

The skills helped Codex more than Claude, and helped reviews most. They hurt in one case:
Claude did worse on the Bevy feature task with them. The benchmark page has the details,
the method, and the caveats. Notably, it was one run per configuration, graded by a
Claude model.

## Updating

Edit the skill, bump `version` in `.claude-plugin/plugin.json`, commit, and push.
Claude Code plugin users pick up the new version with:

```bash
claude plugin update beautiful-rust
```

Anyone who copied the folder or used an installer re-runs the install command. Record
each release in [CHANGELOG.md](CHANGELOG.md).

Validate before pushing. `python3 scripts/check-skill.py` checks skill
frontmatter, links, eval cases, and plugin manifests. Pass `--json` for
machine-readable output. `python3 scripts/check-examples.py` compiles every Rust
block in the skills, reference digests, README, and examples with `cargo check`.

```bash
python3 scripts/check-skill.py
python3 scripts/check-examples.py
claude plugin validate .
```

## Contributing

Issues and pull requests are welcome. Every rule needs a published source; see
[CONTRIBUTING.md](CONTRIBUTING.md) for how to propose a rule, report a review false
positive, or add an eval case.

## Sources and attribution

The guidance in this skill is a synthesis. The five digests in
`skills/rust-best-practices/references/` are paraphrased summaries written for this
project; they restate each source's advice in condensed form and link back to the
original. Read the originals for the full reasoning.

| Source | Author | License |
|---|---|---|
| [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) | Google | CC BY 3.0 |
| [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) | The Rust Project | MIT or Apache-2.0 |
| [Effective Rust](https://www.lurklurk.org/effective-rust/) | David Drysdale, published by O'Reilly | CC BY-NC-ND 4.0 (online edition) |
| [Rust Design Patterns](https://rust-unofficial.github.io/patterns/) | rust-unofficial contributors | MPL-2.0 |
| [Pragmatic Rust Guidelines](https://microsoft.github.io/rust-guidelines/) | Microsoft | MIT |

The skill text, the digests, the banner, and the generator script in this repository
are MIT licensed (see [LICENSE](LICENSE)). The crab is a crab, not the Rust mascot.

## License

MIT. See [LICENSE](LICENSE).
