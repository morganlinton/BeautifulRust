# Privacy policy

Beautiful Rust is a set of agent skills: Markdown instructions and reference text that
your coding agent reads. It applies to the Claude Code plugin, the ChatGPT / Codex
plugin, and copies installed by hand. The ChatGPT / Codex plugin also connects to an MCP
server, described [below](#the-mcp-server).

- **It collects no data.** The skills contain no code that runs on install, no
  analytics, and no telemetry. The author receives nothing about you, your code, or how
  you use the skills.
- **The skills make no network requests.** The skills themselves do not contact any
  server, including the author's.
- **Your agent may run local tools.** When a Rust toolchain is installed, the skills ask
  your agent to run `cargo fmt`, `cargo clippy`, `cargo test`, and similar cargo
  commands in your project. These run on your computer under your agent's normal
  permissions. Cargo can download crates your project depends on and runs your
  project's build scripts, as it always does.
- **Your agent's provider handles your conversations.** Whatever you share with Claude,
  ChatGPT, Codex, or another agent is covered by that provider's privacy policy, not
  this one.

## The MCP server

The ChatGPT / Codex plugin also connects to a remote MCP server at
`https://mcp.beautifulrust.dev/mcp`. It has three read-only tools that look up Beautiful
Rust's rules, explain Rust lints, and read crate versions from crates.io. It needs no
account and no sign-in.

- **What it receives:** only the inputs of each tool call: a search phrase and an
  optional skill name, a lint name, or a crate name. It never asks for your code, files,
  or chat history.
- **What it does with them:** answers that one request. The server stores nothing, sets
  no cookies, and does not build a profile of you. Nothing is sold or shared for
  advertising.
- **Logs:** the server's own code writes no logs. Vercel, which hosts the server,
  processes each request (including your IP address) to deliver it and protect against
  abuse, under the [Vercel privacy policy](https://vercel.com/legal/privacy-policy).
- **Recipients:** Vercel, as the host. For crate lookups, the server fetches public
  index files from crates.io by crate name and sends nothing about you. Answers from
  crates.io are kept in the server's memory for five minutes.
- **Retention:** request inputs are kept only for the time it takes to answer. Cached
  crates.io index files contain only public crate data.

Questions go to [GitHub issues](https://github.com/morganlinton/BeautifulRust/issues).
This policy changes only through commits to this file, which keep its full history.
