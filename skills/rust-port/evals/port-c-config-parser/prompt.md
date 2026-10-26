---
tags: [rust-port]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

We're moving our config parser from C to Rust. Port config.h and config.c to an idiomatic Rust library crate with the same behavior, and port the tests in test_config.c too. Put the crate in the current directory (Cargo.toml, src/lib.rs) and add a PORTING.md with notes for the reviewer.

Input files: config.h, config.c, test_config.c
