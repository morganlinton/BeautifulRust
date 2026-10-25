#!/usr/bin/env bash
# Prove the skill's [lints] table fires: every // expect: lint in the check
# crate must report on its marked line, nothing else may report, and the
# table in assets/lints.toml must match the check crate's Cargo.toml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TABLE="$ROOT/skills/rust-best-practices/assets/lints.toml"
CRATE="$ROOT/skills/rust-best-practices/assets/lints-check"
SRC="$CRATE/src/lib.rs"
MANIFEST="$CRATE/Cargo.toml"

if ! command -v cargo >/dev/null 2>&1; then
  echo "check-lints: cargo not found on PATH" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "check-lints: python3 not found on PATH" >&2
  exit 1
fi
if ! cargo clippy --version >/dev/null 2>&1; then
  echo "check-lints: cargo clippy is not available" >&2
  exit 1
fi

TARGET="$(mktemp -d "${TMPDIR:-/tmp}/lints-check.XXXXXX")"
JSON="$(mktemp "${TMPDIR:-/tmp}/lints-check-json.XXXXXX")"
trap 'rm -rf "$TARGET" "$JSON"' EXIT

export CARGO_TERM_COLOR=never
set +e
cargo clippy --manifest-path "$MANIFEST" --target-dir "$TARGET" --message-format=json \
  >"$JSON" 2>"$TARGET/clippy.err"
CLIPPY_STATUS=$?
set -e

python3 - "$TABLE" "$MANIFEST" "$SRC" "$JSON" "$CLIPPY_STATUS" "$TARGET/clippy.err" <<'PY'
import json
import re
import sys
from pathlib import Path

table_path, manifest_path, src_path, json_path, status_s, err_path = sys.argv[1:]
clippy_status = int(status_s)

table = Path(table_path).read_text()
manifest = Path(manifest_path).read_text()
src = Path(src_path).read_text()
err = Path(err_path).read_text() if Path(err_path).exists() else ""

failed = False

if table not in manifest:
    print("lints table drifted: assets/lints.toml is not byte-identical in the check crate Cargo.toml")
    failed = True

rule_for = {}
last_rule = ""
for line in table.splitlines():
    stripped = line.strip()
    if stripped.startswith("# §"):
        last_rule = stripped[2:].strip()
        continue
    m = re.match(r"^([A-Za-z0-9_]+)\s*=", stripped)
    if m and last_rule:
        name = m.group(1)
        rule_for[name] = last_rule
        rule_for[name.replace("_", "-")] = last_rule
        rule_for[f"clippy::{name}"] = last_rule


def hyphen_to_underscore(name: str) -> str:
    if name.startswith("clippy::"):
        return "clippy::" + name[len("clippy::") :].replace("-", "_")
    return name.replace("-", "_")


def add_aliases(names: set[str], raw: str) -> None:
    if not raw:
        return
    n = hyphen_to_underscore(raw)
    names.add(n)
    if n.startswith("clippy::"):
        names.add(n[len("clippy::") :])
    elif not n.startswith("E") and n[:1].isalpha():
        names.add(f"clippy::{n}")


W_NOTE = re.compile(r"-W ([A-Za-z0-9_:-]+)")
EXPECT = re.compile(r"// expect:\s*(\S+)")


def collect_lint_names(message: dict) -> set[str]:
    names: set[str] = set()
    code = message.get("code")
    code_str = code.get("code") if isinstance(code, dict) else code
    if isinstance(code_str, str) and not re.fullmatch(r"E\d+", code_str):
        add_aliases(names, code_str)
    blobs = [message.get("message") or "", message.get("rendered") or ""]
    for child in message.get("children") or []:
        blobs.append(child.get("message") or "")
        blobs.append(child.get("rendered") or "")
    for blob in blobs:
        for match in W_NOTE.finditer(blob):
            add_aliases(names, match.group(1))
    return names


def primary_span(message: dict) -> dict:
    spans = message.get("spans") or []
    for span in spans:
        if span.get("is_primary"):
            return span
    return spans[0] if spans else {}


src_lines = src.splitlines()


def marked_line(line_no: int) -> int:
    """Same-line expects mark that line; a comment-only expect marks the next code line."""
    code = EXPECT.sub("", src_lines[line_no - 1]).strip()
    if code:
        return line_no
    for j in range(line_no, len(src_lines)):
        stripped = src_lines[j].strip()
        if stripped and not stripped.startswith("//"):
            return j + 1
    return line_no


expects: list[tuple[int, str]] = []
for i, line in enumerate(src_lines, start=1):
    match = EXPECT.search(line)
    if match:
        expects.append((marked_line(i), match.group(1)))

if not expects:
    print("no // expect: comments found in the check crate")
    failed = True

fired: list[tuple[int, set[str], str, str]] = []
for line in Path(json_path).read_text().splitlines():
    if not line.strip():
        continue
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        continue
    if obj.get("reason") != "compiler-message":
        continue
    message = obj.get("message") or {}
    level = message.get("level")
    if level not in ("warning", "error"):
        continue
    span = primary_span(message)
    file_name = span.get("file_name") or ""
    if file_name and Path(file_name).name != "lib.rs":
        continue
    line_no = span.get("line_start")
    names = collect_lint_names(message)
    text = (message.get("message") or "").split("\n")[0]
    fired.append((line_no, names, level, text))

if clippy_status != 0 and not any(level == "error" for _, _, level, _ in fired):
    print(f"cargo clippy exited {clippy_status} without compiler diagnostics")
    if err.strip():
        print(err.strip())
    failed = True

unmatched_expects = []
matched_fired = set()
rows = []

for line_no, expected in expects:
    want = set()
    add_aliases(want, expected)
    hit = None
    for idx, (fline, names, level, text) in enumerate(fired):
        if idx in matched_fired:
            continue
        if fline == line_no and (names & want):
            hit = (idx, names, text)
            break
    rule = rule_for.get(expected) or rule_for.get(expected.split("::")[-1]) or ""
    if hit is None:
        unmatched_expects.append((line_no, expected))
        rows.append((rule, expected, "MISSING"))
        failed = True
    else:
        matched_fired.add(hit[0])
        rows.append((rule, expected, "fired"))

unexpected = []
for idx, (fline, names, level, text) in enumerate(fired):
    if idx in matched_fired:
        continue
    label = sorted(names)[0] if names else (level or "unknown")
    unexpected.append((fline, label, text))
    failed = True

width_rule = max((len(r[0]) for r in rows), default=4)
width_lint = max((len(r[1]) for r in rows), default=4)
width_rule = max(width_rule, 4)
width_lint = max(width_lint, 4)
print(f"{'rule'.ljust(width_rule)}  {'lint'.ljust(width_lint)}  status")
print(f"{'-' * width_rule}  {'-' * width_lint}  ------")
for rule, lint, status in rows:
    print(f"{rule.ljust(width_rule)}  {lint.ljust(width_lint)}  {status}")

if unmatched_expects:
    print()
    print("expected lints that did not fire on their marked line:")
    for line_no, expected in unmatched_expects:
        print(f"  src/lib.rs:{line_no}: {expected}")

if unexpected:
    print()
    print("unexpected diagnostics:")
    for fline, label, text in unexpected:
        print(f"  src/lib.rs:{fline}: {label}: {text}")

if failed:
    sys.exit(1)

print()
print(f"{len(rows)} expected lints fired; table matches {table_path}")
PY
