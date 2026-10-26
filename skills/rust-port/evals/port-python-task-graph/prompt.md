---
tags: [rust-port]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Can you port taskgraph.py to Rust? I want an idiomatic Rust library crate with the same behavior, and port test_taskgraph.py too so we know it matches. Put the crate in the current directory (Cargo.toml, src/lib.rs) and add a PORTING.md with notes for the reviewer.

Input files: taskgraph.py, test_taskgraph.py
