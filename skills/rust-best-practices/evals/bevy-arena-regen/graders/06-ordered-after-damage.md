---
type: llm
focus: trace
weight: 1
---

The regeneration system has an explicit order relative to the damage systems: it is in the same chain as apply_hits or ordered with .after(...) on apply_hits or contact_damage, so a hit landing this frame resets the pause before regeneration runs, rather than depending on an ambiguous order
