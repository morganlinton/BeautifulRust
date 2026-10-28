---
type: llm
focus: trace
weight: 1
---

REVIEW.md flags that apply_hits has two queries that both take &mut Health (With<Player> and With<Enemy>), which Bevy rejects as conflicting access (error B0001), so ArenaPlugin panics when the system is first run; ranks it as a must-fix; and fixes it with Without filters that make the queries disjoint or with a ParamSet
