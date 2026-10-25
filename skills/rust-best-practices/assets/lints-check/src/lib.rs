//! Deliberate violations of the skill's lint table, one per mapped lint.

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

/// A public type without `Debug`.
pub struct Silent; // expect: missing_debug_implementations

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

mod internal {
    /// An item that should not be `pub`.
    pub fn unused_export() {} // expect: unreachable_pub
}

/// Touches the private module so it is not dead.
pub fn touch_internal() {
    internal::unused_export();
}

pub fn undocumented() {} // expect: missing_docs

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

fn expect_value(value: Option<i32>) -> i32 {
    value.expect("value must be present") // expect: clippy::expect_used
}

/// Calls `expect` on `value`.
///
/// # Panics
///
/// Panics if `value` is `None`.
#[must_use]
pub fn take_or_expect(value: Option<i32>) -> i32 {
    expect_value(value)
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

/// Accepts four boolean switches.
#[must_use]
// expect: clippy::fn_params_excessive_bools
pub fn configure(verbose: bool, sorted: bool, strict: bool, dry_run: bool) -> bool {
    verbose && sorted && strict && dry_run
}

/// Doubles `n`.
// expect: clippy::must_use_candidate
pub fn double(n: u32) -> u32 {
    n.saturating_mul(2)
}

/// Clones a local `String` instead of moving it.
#[must_use]
pub fn clone_text() -> String {
    let text = String::from("label");
    text.clone() // expect: clippy::redundant_clone
}

/// Reads `slot`.
///
/// # Safety
///
/// `slot` must be valid for reads.
#[must_use]
pub unsafe fn read_slot(slot: *const u32) -> u32 {
    *slot // expect: unsafe_op_in_unsafe_fn
}

/// Reads a local through a raw pointer.
#[must_use]
pub fn read_local() -> u32 {
    let value = 1_u32;
    let slot = std::ptr::addr_of!(value);
    unsafe { *slot } // expect: clippy::undocumented_unsafe_blocks
}

/// Imports a module with a glob.
pub fn glob_sink() {
    use std::io::*; // expect: clippy::wildcard_imports
    let mut buf = [0_u8; 1];
    drop(empty().read(&mut buf));
}

/// Concatenates with `+`.
#[must_use]
pub fn join_label(prefix: String) -> String {
    prefix + "-suffix" // expect: clippy::string_add
}
