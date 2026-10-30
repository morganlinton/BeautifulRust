# Privacy policy

Beautiful Rust is a set of agent skills: Markdown instructions and reference text that
your coding agent reads. It applies to the Claude Code plugin, the ChatGPT / Codex
plugin, and copies installed by hand.

- **It collects no data.** The skills contain no code that runs on install, no
  analytics, and no telemetry. The author receives nothing about you, your code, or how
  you use the skills.
- **It makes no network requests.** The skills do not contact any server, including the
  author's.
- **Your agent may run local tools.** When a Rust toolchain is installed, the skills ask
  your agent to run `cargo fmt`, `cargo clippy`, `cargo test`, and similar cargo
  commands in your project. These run on your computer under your agent's normal
  permissions. Cargo can download crates your project depends on and runs your
  project's build scripts, as it always does.
- **Your agent's provider handles your conversations.** Whatever you share with Claude,
  ChatGPT, Codex, or another agent is covered by that provider's privacy policy, not
  this one.

Questions go to [GitHub issues](https://github.com/morganlinton/BeautifulRust/issues).
This policy changes only through commits to this file, which keep its full history.
