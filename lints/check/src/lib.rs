//! Deliberate violations of `lints/lints.toml`, one per lint that is set to warn.
//!
//! Each expect-marker comment names a lint and marks the line it must fire on. A marker on a
//! line by itself applies to the next code line, so a line that trips several
//! lints carries several markers above it. `scripts/check-lints.sh` fails if a
//! marked lint stays quiet or if anything unmarked fires. Code that uses an
//! allowed lint (such as `expect`) appears without a marker to prove it stays
//! quiet.

use std::rc::Rc;

/// A parse failure.
#[derive(Debug)]
pub struct ParseError;

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "parse error")
    }
}

impl std::error::Error for ParseError {}

// ---------------------------------------------------------------- [lints.rust]

/// A public type without `Debug`.
pub struct Silent; // expect: missing_debug_implementations

mod internal {
    /// An item that should not be `pub`.
    pub fn unused_export() {} // expect: unreachable_pub
}

/// Touches the private module so it is not dead.
pub fn touch_internal() {
    internal::unused_export();
}

pub fn undocumented() {} // expect: missing_docs

/// Reads `slot`.
///
/// # Safety
///
/// `slot` must be valid for reads.
#[must_use]
pub unsafe fn read_slot(slot: *const u32) -> u32 {
    *slot // expect: unsafe_op_in_unsafe_fn
}

/// Writes a formatter without naming its lifetime.
///
/// # Errors
///
/// Returns an error if the formatter fails.
// expect: rust_2018_idioms
pub fn write_hidden(f: &mut std::fmt::Formatter) -> std::fmt::Result {
    f.write_str("hidden")
}

// --------------------------------------------------------------------- panics

fn unwrap_value(value: Option<i32>) -> i32 {
    value.unwrap() // expect: clippy::unwrap_used
}

/// Calls `unwrap` on `value`.
///
/// # Panics
///
/// Panics if `value` is `None`.
#[must_use]
pub fn take_or_panic(value: Option<i32>) -> i32 {
    unwrap_value(value)
}

/// Calls `expect` with a reason, which the table allows.
///
/// # Panics
///
/// Panics if `value` is `None`.
#[must_use]
pub fn take_or_expect(value: Option<i32>) -> i32 {
    value.expect("value must be present")
}

/// Panics inside a function that returns `Result`.
///
/// # Errors
///
/// Never; it panics instead.
///
/// # Panics
///
/// Always.
// expect: clippy::panic_in_result_fn
pub fn parse_or_panic(_input: &str) -> Result<(), ParseError> {
    panic!("not implemented");
}

/// Parses `input`.
// expect: clippy::missing_errors_doc
pub fn parse_input(_input: &str) -> Result<(), ParseError> {
    Err(ParseError)
}

/// Panics on purpose.
// expect: clippy::missing_panics_doc
pub fn boom() {
    panic!("boom");
}

// --------------------------------------------------------------- suppressions

/// Suppresses a lint without a reason, using `allow` instead of `expect`.
// expect: clippy::allow_attributes
// expect: clippy::allow_attributes_without_reason
#[allow(clippy::needless_pass_by_value)]
pub fn takes_owned(text: String) -> usize {
    text.len()
}

// --------------------------------------------------------------------- unsafe

/// Reads a local through a raw pointer.
#[must_use]
pub fn read_local() -> u32 {
    let value = 1_u32;
    let slot = std::ptr::addr_of!(value);
    unsafe { *slot } // expect: clippy::undocumented_unsafe_blocks
}

/// Does two unsafe operations in one block.
///
/// # Safety
///
/// `a` and `b` must be valid for reads.
#[must_use]
pub unsafe fn read_two(a: *const u32, b: *const u32) -> u32 {
    // SAFETY: the caller guarantees both pointers are valid for reads.
    // expect: clippy::multiple_unsafe_ops_per_block
    unsafe { *a + *b }
}

// ------------------------------------------------------------------- API shape

/// Takes a single `bool`; lints/clippy.toml lowers the threshold so one is enough.
#[must_use]
// expect: clippy::fn_params_excessive_bools
pub fn render(verbose: bool) -> &'static str {
    if verbose {
        "long"
    } else {
        "short"
    }
}

/// Carries four boolean flags.
#[derive(Debug)]
// expect: clippy::struct_excessive_bools
pub struct Flags {
    /// Flag a.
    pub a: bool,
    /// Flag b.
    pub b: bool,
    /// Flag c.
    pub c: bool,
    /// Flag d.
    pub d: bool,
}

/// Clones an `Rc` with method syntax.
#[must_use]
pub fn share(text: &Rc<str>) -> Rc<str> {
    text.clone() // expect: clippy::clone_on_ref_ptr
}

/// Clones a local `String` instead of moving it.
#[must_use]
pub fn clone_text() -> String {
    let text = String::from("label");
    text.clone() // expect: clippy::redundant_clone
}

/// Holds an `Rc<String>`.
#[derive(Debug)]
pub struct SharedText {
    text: Rc<String>, // expect: clippy::rc_buffer
}

impl SharedText {
    /// Wraps a `String` in `Rc`.
    #[must_use]
    pub fn from_text(text: String) -> Self {
        Self {
            text: Rc::new(text),
        }
    }

    /// Returns the wrapped text.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.text
    }
}

// --------------------------------------------------------------------- idioms

/// Concatenates with `+`.
#[must_use]
pub fn join_label(prefix: String) -> String {
    prefix + "-suffix" // expect: clippy::string_add
}

/// Imports a module with a glob.
pub fn glob_sink() {
    use std::io::*; // expect: clippy::wildcard_imports
    let mut buf = [0_u8; 1];
    drop(empty().read(&mut buf));
}

/// Doubles `n` without `#[must_use]`, which the table allows.
pub fn double(n: u32) -> u32 {
    n.saturating_mul(2)
}

// ------------------------------------------------------- leftovers and output

/// Leaves a `dbg!` behind.
#[must_use]
pub fn traced(n: u32) -> u32 {
    dbg!(n) // expect: clippy::dbg_macro
}

/// Leaves a `todo!` behind.
///
/// # Panics
///
/// Always, until implemented.
pub fn unfinished() {
    todo!() // expect: clippy::todo
}

/// Prints to stdout from library code.
pub fn shout() {
    println!("hello"); // expect: clippy::print_stdout
}

/// Prints to stderr from library code.
pub fn complain() {
    eprintln!("oops"); // expect: clippy::print_stderr
}

// ---------------------------------------------------------------------- casts

/// Narrows a `u64` with `as`.
#[must_use]
pub fn narrow(n: u64) -> u32 {
    // expect: clippy::as_conversions
    // expect: clippy::cast_possible_truncation
    n as u32
}

/// Reinterprets a signed value as unsigned with `as`.
#[must_use]
pub fn unsign(n: i32) -> u32 {
    // expect: clippy::as_conversions
    // expect: clippy::cast_sign_loss
    n as u32
}
