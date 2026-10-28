---
type: llm
focus: trace
weight: 1
---

REVIEW.md flags that player.single().unwrap() in contact_damage panics when there is no player (for example after apply_hits despawns a dead player) and recommends Single, an early return with let-else, or returning Result from the system
