---
type: llm
focus: trace
weight: 1
---

Behavior matches the C version on its edge cases: without value trimming a value keeps its leading whitespace, an out-of-range integer is rejected as not a number, case-insensitive mode treats A and a as duplicates, and allow-duplicates keeps the last value with a count of one
