---
type: llm
focus: trace
weight: 1
---

If REVIEW.md mentions clippy's type_complexity warning on stun_wounded's query, it recommends a crate-level allow (as Bevy's own workspace does) or a type alias, not splitting the system or wrapping the query in a custom SystemParam only to silence the lint; passes if the warning is not mentioned
