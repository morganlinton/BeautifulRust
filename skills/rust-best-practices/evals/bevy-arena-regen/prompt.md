---
tags: [rust-best-practices, bevy]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Add health regeneration to the arena crate. Entities with a regen component should slowly regain health up to a maximum, and regeneration should pause for 3 seconds after the entity takes a hit. Wire it into ArenaPlugin and add tests. The existing tests need to keep passing.

Input files: Cargo.toml, Cargo.lock, src/lib.rs, tests/arena.rs
