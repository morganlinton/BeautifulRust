<p align="center">
  <img src="assets/banner.png" alt="Pixel art banner: a crab on a rocky shore at sunset, under the title Beautiful Rust and the subtitle Idiomatic Rust, distilled">
</p>

# Beautiful Rust

A standard [Agent Skill](https://agentskills.io), `rust-best-practices`, that teaches
coding agents to write idiomatic, robust, maintainable Rust. It works with Claude Code,
OpenAI Codex, GitHub Copilot, Cursor, Gemini CLI, and any other agent that reads the Agent
Skills format. Once installed, it loads whenever a task involves Rust, cargo, crates, the
borrow checker, clippy, or `.rs` files.

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
passed 29 of 30 checks against 24 of 30 without it. See [Testing the skill](#testing-the-skill).

## Install

The skill is the folder `skills/rust-best-practices/`. Every option below puts that folder
where your agent looks for skills.

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

The skill then appears as `/beautiful-rust:rust-best-practices`. You rarely need to call it,
since it triggers on its own. To try it for one session without installing, clone the repo
and run `claude --plugin-dir ./BeautifulRust`.

### GitHub Copilot

With GitHub CLI 2.90 or later:

```bash
gh skill install morganlinton/BeautifulRust rust-best-practices
```

This installs into the current project by default. Add `--scope user` to install for your
user, or `--agent <name>` to install for a different agent.

### Gemini CLI

```bash
gemini skills install https://github.com/morganlinton/BeautifulRust --path skills/rust-best-practices
```

### OpenAI Codex, Cursor, or anything else: copy the folder

Clone the repo and copy `skills/rust-best-practices/` into your agent's skills directory.
Most agents now read the shared `.agents/skills/` location:

```bash
git clone https://github.com/morganlinton/BeautifulRust
mkdir -p ~/.agents/skills
cp -R BeautifulRust/skills/rust-best-practices ~/.agents/skills/
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

claude.ai takes a zip of the skill folder, with the folder as the zip root:

```bash
cd skills && zip -r ../rust-best-practices.zip rust-best-practices -x '*.DS_Store' -x 'rust-best-practices/evals/*'
```

Upload it under **Customize > Skills**. Code execution must be enabled first.

## What the skill covers

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

## Enforce it with lints

The skill's rules hold only while the compiler enforces them. Copy
`skills/rust-best-practices/assets/lints.toml` into your `Cargo.toml` as `[lints]`,
or into a workspace as `[workspace.lints]` with `lints.workspace = true` on each
crate.

The table sets `clippy::pedantic` to `warn` (priority -1) and then allows the few
pedantic lints this skill disagrees with. It never uses `deny(warnings)`.

Prove the mapping from the repository root:

```bash
bash scripts/check-lints.sh
```

The script fails if a listed lint stops firing, if clippy reports anything else,
or if the check crate's `Cargo.toml` drifts from `assets/lints.toml`.

## Layout

```
BeautifulRust/
├── .claude-plugin/
│   ├── plugin.json         plugin manifest
│   └── marketplace.json    lets this repo act as its own marketplace
├── scripts/
│   └── check-lints.sh      proves the [lints] table still fires
├── skills/
│   └── rust-best-practices/
│       ├── SKILL.md
│       ├── assets/
│       │   ├── lints.toml      copy-paste [lints.rust] / [lints.clippy]
│       │   └── lints-check/    tiny crate with one violation per lint
│       └── references/
│           ├── google-rust-style-guide.md
│           ├── rust-api-guidelines.md
│           ├── effective-rust.md
│           ├── rust-design-patterns.md
│           └── microsoft-rust-guidelines.md
└── README.md
```

## Testing the skill

`skills/rust-best-practices/evals/` holds three test cases in the layout `claude plugin eval`
reads: a library API design task, an application CLI task, and a refactor-this-module task
with an input file. Each case has the prompt, a description of a good result, and one
assertion per file under `graders/`. Run them with and without the skill from the skill
directory:

```bash
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
```

These are real model runs and are billed. In the last comparison the skill passed 29 of
30 assertions against 24 of 30 without it, at roughly a third more tokens per task.

## Updating

Edit the skill, bump `version` in `.claude-plugin/plugin.json`, commit, and push.
Claude Code plugin users pick up the new version with:

```bash
claude plugin update beautiful-rust
```

Anyone who copied the folder or used an installer re-runs the install command. Record
each release in [CHANGELOG.md](CHANGELOG.md).

Validate before pushing:

```bash
claude plugin validate .
```

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
