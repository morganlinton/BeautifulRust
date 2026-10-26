---
type: llm
focus: trace
weight: 1
---

The port is proportionate: it does not reimplement the source language's string or number semantics, it adds no public API beyond the original's operations plus standard trait impls and accessors Rust callers expect (Debug, Clone, Display, Error, FromStr, Default, IntoIterator, len/is_empty), and its code lines in src/ (excluding tests, comments, and doc comments) are under one and a half times the code lines of config.c
