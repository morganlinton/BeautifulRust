<!--
This review was produced by the rust-review skill, unedited, for the deliberately messy
module in skills/rust-review/evals/review-inventory-module/files/inventory.rs. The agent
copied the module into a throwaway crate (scratch-crate/) to run fmt, clippy, and tests;
that crate is not included here.
-->

# Rust review: `inventory.rs`

`inventory.rs` is an in-memory inventory of named items (quantity, price in cents,
perishable flag). It can add, look up, and restock items, total their value, load them
from a comma-separated file, and print a report. Nothing here is published, but every
item is `pub` and you plan to build on it, so I reviewed it as an internal **library**
module and applied the API-design rules strictly. Edition 2021 is assumed (there is no
`Cargo.toml`). **Verdict: not ready to build on yet.** The logic is small and easy to
follow, but the module panics on ordinary bad input, and two of its public shapes, the
`Rc<RefCell<Inventory>>` return type and the error enum, will be breaking changes to fix
once other code depends on them. **The most important fix:** make `load`/`parse_line`
return errors instead of panicking on a missing file or a malformed number.

**Tools run.** I copied the file into a throwaway crate (`scratch-crate/`) and ran
`cargo fmt --check`, `cargo clippy -- -W clippy::pedantic`, and `cargo test`. The file
compiles. `cargo fmt --check` fails (5 hunks). Plain `cargo clippy` **fails with 6
errors**, because `#![deny(warnings)]` turns ordinary style lints into hard errors (see
finding 7). With `pedantic` there are 19 warnings, folded in below. There are no tests,
so `cargo test` runs 0. `inventory.rs` itself was not modified.

Line numbers refer to `inventory.rs`.

## Must fix

### 1. Loading a file panics on bad input (`inventory.rs:76`, `:77`, `:83`)
**Rule:** Don't panic on expected failures (Effective Rust Item 18; M-PANIC-ON-BUG,
Microsoft Rust Guidelines). Clippy: `unwrap_used`, `missing_panics_doc`.
**Problem:** `load` and `parse_line` already return `Result`, but a missing or
unreadable file (`read_to_string(path).unwrap()`) or a non-numeric quantity or price
(`parse::<i64>().unwrap()`) crashes the whole program instead of returning an error. A
single typo in a data file takes the caller down with it.
**Fix:**
```rust
let text = std::fs::read_to_string(path).map_err(InventoryError::Io)?;            // line 83
let qty: i64 = parts[1].trim().parse().map_err(|e| InventoryError::Parse { field: "qty", source: e })?;   // line 76
let price: i64 = parts[2].trim().parse().map_err(|e| InventoryError::Parse { field: "price", source: e })?; // line 77
```
(The error variants are the ones proposed in finding 4.)

### 2. `total_value` panics on an unknown name, and the arithmetic can overflow (`inventory.rs:54`, `:55`, `:63`)
**Rule:** Don't panic (Effective Rust Item 18); prefer `Option`/`Result` transforms
(Effective Rust Item 3).
**Problem:** `self.items.borrow().get(n).unwrap()` panics if any requested name is not in
the inventory, which is an easy mistake for a caller to make. Separately, `qty *
price_cents` (line 55), `total +=` (line 55), and `item.qty += amount` (line 63) are
unchecked `i64` arithmetic. They panic in debug builds and silently wrap to a wrong (even
negative) value in release builds.
**Fix:**
```rust
pub fn total_value(&self, names: &[String]) -> Result<i64, InventoryError> {
    names.iter().try_fold(0i64, |total, n| {
        let item = self.items.get(n).ok_or_else(|| InventoryError::NotFound(n.clone()))?;
        item.qty
            .checked_mul(item.price_cents)
            .and_then(|v| total.checked_add(v))
            .ok_or(InventoryError::Overflow)
    })
}
// restock, line 63:
item.qty = item.qty.checked_add(amount).ok_or(InventoryError::Overflow)?;
```
If skipping unknown names is the intended behavior, use `filter_map` instead and
document it.

### 3. The "no negative quantity or price" rule is only enforced in one of four places (`inventory.rs:17-20`, `:43`, `:63`, `:71-79`)
**Rule:** Enforce validity with types or constructors (C-VALIDATE, Rust API Guidelines);
fields private by default (C-STRUCT-PRIVATE, Rust API Guidelines).
**Problem:** `add_item` rejects negative values, but `load`/`parse_line` accept them,
`restock` accepts a negative `amount` that can drive `qty` below zero, and `Item`'s
fields are `pub`, so any caller can set `qty = -5` directly. Code built on this module
can't rely on the invariant. Two related silent-data problems in the same parser: any
perishable value other than exactly `"true"` (such as `"TRUE"` or `"yes"`) quietly
becomes `false` (line 78), and a duplicate name in the file silently overwrites the
earlier line (line 90).
**Fix:** let the type carry the rule and validate in one place.
```rust
pub struct Item {
    name: String,
    qty: u32,          // or u64: negative is unrepresentable
    price_cents: u64,
    perishable: bool,
}
// parse_line, line 78:
let perishable: bool = parts[3].trim().parse()
    .map_err(|_| InventoryError::InvalidField { field: "perishable", value: parts[3].trim().to_owned() })?;
```
Add accessor methods (`qty()`, `price_cents()`) for reading the private fields. If you
keep a signed `amount` in `restock` for removals, use `checked_add_signed` and return an
error on underflow.

### 4. The error type gives callers nothing to act on (`inventory.rs:6-13`)
**Rule:** Errors implement `std::error::Error` and carry context (C-GOOD-ERR, Rust API
Guidelines; Effective Rust Item 4).
**Problem:** `InventoryError` has no `Display` or `std::error::Error` impl, so it can't
be used with `?` into `Box<dyn Error>`/`anyhow` or printed for a user. Its variants carry
no data: `NotFound` doesn't say which item, `Parse` doesn't say which line or field, and
`Io` is never constructed (the I/O error is unwrapped instead). `Invalid` doesn't say
which value. `Other(String)` is never used. Changing the variants later is a breaking
change for every `match` on them.
**Fix (with `thiserror`, or hand-write `Display` and `Error`):**
```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum InventoryError {
    #[error("item `{0}` not found")]
    NotFound(String),
    #[error("invalid {field}: {value}")]
    InvalidField { field: &'static str, value: String },
    #[error("expected 4 comma-separated fields, found {found}")]
    WrongFieldCount { found: usize },
    #[error("could not parse {field}")]
    Parse { field: &'static str, #[source] source: std::num::ParseIntError },
    #[error("could not read inventory file")]
    Io(#[from] std::io::Error),
    #[error("arithmetic overflow")]
    Overflow,
}
```
Have `load` wrap per-line errors with the line number (for example a
`Line { line: usize, source: Box<InventoryError> }` variant) so a bad file points at the
bad line.

### 5. `Rc<RefCell<...>>` in the public API, twice (`inventory.rs:24`, `:28`, `:82`)
**Rule:** Keep `Rc`, `Arc`, and `RefCell` out of public APIs (M-AVOID-WRAPPERS,
Microsoft Rust Guidelines); choose the mutation granularity you need (Effective Rust
Item 8).
**Problem:** `new()` and `load()` return `Rc<RefCell<Inventory>>`, and the inventory
wraps its map in a second `Rc<RefCell<...>>`. Callers are forced into shared, single-
threaded ownership (`Rc` is not `Send`, so this can never go to another thread or an
async task). Borrow errors move from compile time to runtime panics, and every call site
needs `inv.borrow()`. All mutating methods take `&self`, which hides mutation. Removing
this later changes every signature.
**Fix:** a plain struct with `&mut self` mutators. Callers who truly need sharing can
wrap it themselves.
```rust
#[derive(Debug, Default)]
pub struct Inventory {
    items: HashMap<String, Item>,
}

impl Inventory {
    pub fn new() -> Self { Self::default() }
    pub fn add_item(&mut self, /* ... */) -> Result<(), InventoryError> { /* ... */ }
    pub fn restock(&mut self, name: &str, amount: u32) -> Result<(), InventoryError> { /* ... */ }
    pub fn load(path: impl AsRef<std::path::Path>) -> Result<Self, InventoryError> { /* ... */ }
}
```

## Should fix

### 6. Double lookups, check-then-unwrap, and clone-to-mutate (`inventory.rs:35-36`, `:61-64`)
**Rule:** Prefer `Option` transforms over check-then-unwrap (Effective Rust Item 3);
avoid clones that exist only to satisfy the borrow checker (Rust Design Patterns,
anti-patterns).
**Problem:** `get_item` looks the key up twice. `restock` looks it up twice, clones the
whole `Item`, edits the clone, and re-inserts it with a cloned key. This is three hash
lookups and two allocations to bump a number.
**Fix:**
```rust
pub fn get(&self, name: &str) -> Option<&Item> {
    self.items.get(name)
}

pub fn restock(&mut self, name: &str, amount: u32) -> Result<(), InventoryError> {
    let item = self.items.get_mut(name).ok_or_else(|| InventoryError::NotFound(name.to_owned()))?;
    item.qty = item.qty.checked_add(amount).ok_or(InventoryError::Overflow)?;
    Ok(())
}
```
Returning `Option<&Item>` lets the caller decide whether to clone. Renaming `get_item`
to `get` follows the `HashMap::get` convention (C-GETTER).

### 7. `#![deny(warnings)]` already breaks `cargo clippy` (`inventory.rs:1`)
**Rule:** Don't put `#![deny(warnings)]` in source (Rust Design Patterns, anti-patterns;
Effective Rust Item 29).
**Problem:** Clippy currently fails on this file with 6 errors, all minor style lints
(`redundant_field_names` at lines 46 and 79, `ptr_arg` at 71, `needless_bool` at 78,
`len_zero` at 86, `needless_borrow` at 98). Each new Rust release can add a lint and break
the build the same way. In a module file (not the crate root) the inner attribute also
quietly applies to just this module.
**Fix:** delete line 1 and enforce warnings in CI instead:
```bash
cargo clippy --all-targets -- -D warnings
```

### 8. `&String` and `&Vec<T>` parameters (`inventory.rs:34`, `:51`, `:60`, `:71`, `:82`)
**Rule:** Accept borrowed slices, not references to owned containers (clippy `ptr_arg`;
C-GENERIC, Rust API Guidelines).
**Problem:** Callers holding a `&str` or a string literal must allocate a `String` just to
call `get_item`, `restock`, or `parse_line`, as `load` itself does on line 89
(`&line.to_string()`). `total_value` can't accept an array or a slice of a `Vec`.
**Fix:**
```rust
pub fn get(&self, name: &str) -> Option<&Item>
pub fn total_value(&self, names: &[String]) -> Result<i64, InventoryError>
pub fn restock(&mut self, name: &str, amount: u32) -> Result<(), InventoryError>
pub fn parse_line(line: &str) -> Result<Item, InventoryError>
pub fn load(path: impl AsRef<std::path::Path>) -> Result<Self, InventoryError>
```
`load` then becomes `Inventory::parse_line(line)?` with no allocation.

### 9. `report` output order is random (`inventory.rs:97`)
**Rule:** Don't let `HashMap` iteration order leak into output (BeautifulRust review
checklist; Effective Rust Item 10).
**Problem:** Iterating a `HashMap` produces a different order on each run, so the report
can't be diffed, snapshot-tested, or read consistently.
**Fix:** store items in a `BTreeMap<String, Item>` (sorted by name, same API), or sort
before printing:
```rust
let items = self.items.borrow();
let mut entries: Vec<_> = items.iter().collect();
entries.sort_by(|a, b| a.0.cmp(b.0));
```

### 10. No tests and no docs (whole file)
**Rule:** Document public interfaces with `# Errors`/`# Panics` sections (Effective Rust
Item 27; clippy `missing_errors_doc`, `missing_panics_doc`); write tests for logic
(Effective Rust Item 30).
**Problem:** None of the 11 public items has a doc comment, and nothing is tested. Clippy
pedantic flags 4 functions missing `# Errors` and 5 missing `# Panics`. The parser is
exactly where tests pay off: the panics in finding 1 and the `"TRUE"` case in finding 3
would have shown up in the first test.
**Fix:** start with a few parser tests:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_line_reads_valid_line() {
        let item = Inventory::parse_line("apple, 3, 50, true").unwrap();
        assert_eq!(item.name, "apple");
        assert_eq!(item.qty, 3);
    }

    #[test]
    fn parse_line_rejects_bad_number() {
        assert!(Inventory::parse_line("apple, three, 50, true").is_err());
    }
}
```

## Consider

### 11. Positional `bool` and look-alike `i64` parameters (`inventory.rs:42`, `:95`)
**Rule:** Don't pass a `bool` where meaning is ambiguous (C-CUSTOM-TYPE, Rust API
Guidelines).
**Problem:** `add_item("milk".into(), 4, 199, true)` and `report(true)` don't say what
`true` means, and `qty` and `price` are both `i64`, so they can be swapped without a
compiler error.
**Fix:** take an `Item` (or a builder) in `add_item`, and use an enum for the report:
```rust
pub enum ReportDetail { Summary, Verbose }
pub fn report(&self, detail: ReportDetail) -> String
```

### 12. Missing standard traits on `Item` (`inventory.rs:15`)
**Rule:** Public types implement `Debug` and the common traits (C-COMMON-TRAITS,
C-DEBUG, Rust API Guidelines; M-PUBLIC-DEBUG).
**Problem:** `Item` derives only `Clone`, so it can't be printed with `{:?}` or compared
in tests with `assert_eq!`. `Inventory` has no `Debug` either.
**Fix:**
```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Item { /* ... */ }
```

### 13. String building with `+` and leftover clippy nits (`inventory.rs:46`, `:78`, `:79`, `:86`, `:98`, `:100`)
**Rule:** Google Rust Style Guide (formatting); clippy `redundant_field_names`,
`needless_bool`, `len_zero`, `needless_borrow`.
**Problem:** `s = s + &k + ": " + ...` is hard to read and allocates for every
`to_string()`. The rest are small idiom slips: `qty: qty`, `if x { true } else { false }`,
`len() == 0`. Run `cargo fmt` too, since it currently reports 5 hunks.
**Fix:**
```rust
use std::fmt::Write as _;
writeln!(s, "{k}: {}", v.qty).unwrap(); // writing to a String can't fail
if verbose {
    writeln!(s, "  price={} perishable={}", v.price_cents, v.is_perishable).unwrap();
}
// line 46/79: Item { name, qty, price_cents: price, is_perishable: perishable }
// line 78:    let perishable = parts[3].trim() == "true";   (but see finding 3)
// line 86:    if line.trim().is_empty() {
```

## What's already good

- Prices are stored as integer cents (`price_cents: i64`), not floating point, which
  avoids rounding errors in money.
- `add_item` validates its inputs and returns an error instead of panicking. That is the
  right pattern; it just needs to be applied everywhere (finding 3).
- `parse_line` checks the field count before indexing, so `parts[1..3]` can't go out of
  bounds, and it trims whitespace around each field.
- `Inventory.items` is private and `load` skips blank lines, so the storage can change
  (findings 5 and 9) without touching callers once the signatures are fixed.

## Suggested lints

This code has no `Cargo.toml` and no `[lints]` table. Adding the BeautifulRust lints
config (`lints/lints.toml` and `lints/clippy.toml` from
https://github.com/morganlinton/BeautifulRust) to the crate this module goes into would
make clippy flag most of the mechanical issues above automatically, as warnings rather
than build-breaking errors. From this review it would have caught:

- the `unwrap()` calls on lines 36, 54, 62, 76, 77, and 83 (`unwrap_used`, finding 1 and 2),
- the missing `Debug` on `Item` and `Inventory` and the missing docs
  (`missing_debug_implementations`, `missing_docs`, `missing_errors_doc`, findings 10 and 12),
- the `&String` parameter on `parse_line` and the panics with no `# Panics` doc
  (`ptr_arg`, `missing_panics_doc`, findings 1 and 8).
