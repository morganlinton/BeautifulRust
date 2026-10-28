---
type: llm
focus: trace
weight: 1
---

REVIEW.md flags that spawn_wave and check_wave_cleared have no ordering between them, and that because spawn_wave's Commands are deferred, check_wave_cleared can run after it in the same frame, see no enemies, and start another wave (double spawns or a skipped wave number); it recommends an explicit order such as (check_wave_cleared, spawn_wave).chain() or .before/.after
