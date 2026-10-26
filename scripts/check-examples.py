#!/usr/bin/env python3
"""Check that every Rust code block in the skills and docs compiles.

Most examples are fragments: a few statements, a method without its impl, or a
type that refers to another type defined elsewhere. scripts/examples.json gives
each fragment the code it needs to compile (a per-file prelude and a per-block
template) or a reason to skip it, so the markdown the agent reads stays as is.

The blocks are compiled together as one generated crate with no dependencies,
using `cargo check`. Errors are reported against the markdown line.

Stdlib only, Python 3.9+. Exit 1 on any error, 2 if cargo is unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HARNESS = Path("scripts") / "examples.json"
DOC_GLOBS = (
    "README.md",
    "CONTRIBUTING.md",
    "examples/*.md",
    "skills/*/SKILL.md",
    "skills/*/references/*.md",
)
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`\s]*)")
# A function body that is only a placeholder, e.g. `fn f() -> bool { /* ... */ }`.
FN_PLACEHOLDER_RE = re.compile(r"(\)\s*(?:->\s*[^{;]+?)?)\{\s*/\*\s*\.\.\.\s*\*/\s*\}")
CODE = "{code}"
ALLOWS = (
    "#![allow(dead_code, unused, unreachable_code, clippy::all)]\n"
)


@dataclass(frozen=True)
class Problem:
    path: str
    line: int
    level: str
    message: str


@dataclass
class Block:
    path: str
    line: int  # line of the first code line in the markdown file
    index: int  # 1-based position among the file's rust blocks
    code: str
    skip: Optional[str] = None
    prelude: str = ""
    template: str = CODE
    lines: Dict[int, Tuple[str, int]] = field(default_factory=dict)


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def format_problem(problem: Problem) -> str:
    prefix = "warning: " if problem.level == "warning" else ""
    return "%s:%d: %s%s" % (problem.path, problem.line, prefix, problem.message)


def summary_line(problems: Sequence[Problem], checked: int, skipped: int) -> str:
    errors = sum(1 for p in problems if p.level == "error")
    err_word = "error" if errors == 1 else "errors"
    return "%d %s, %d blocks compiled, %d skipped" % (errors, err_word, checked, skipped)


def doc_files(root: Path) -> List[Path]:
    found = set()
    for pattern in DOC_GLOBS:
        for path in root.glob(pattern):
            if path.is_file() and "evals" not in path.parts:
                found.add(path)
    return sorted(found)


def find_blocks(root: Path, path: Path) -> List[Block]:
    """Return the ```rust blocks in one markdown file."""
    blocks: List[Block] = []
    lines = path.read_text(encoding="utf-8").split("\n")
    fence: Optional[str] = None
    is_rust = False
    start = 0
    body: List[str] = []
    for number, text in enumerate(lines, 1):
        match = FENCE_RE.match(text)
        if fence is None:
            if match:
                fence = match.group(2)
                lang = match.group(3).split(",")[0]
                is_rust = lang == "rust"
                start = number + 1
                body = []
            continue
        if match and match.group(2).startswith(fence[0]) and len(match.group(2)) >= len(fence) and not match.group(3):
            if is_rust:
                blocks.append(
                    Block(
                        path=rel(root, path),
                        line=start,
                        index=len(blocks) + 1,
                        code=textwrap.dedent("\n".join(body)),
                    )
                )
            fence = None
            continue
        body.append(text)
    return blocks


def as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def first_code_line(code: str) -> str:
    for text in code.split("\n"):
        if text.strip():
            return text.strip()
    return ""


def apply_harness(
    root: Path, blocks: List[Block], harness: Dict[str, Any]
) -> List[Problem]:
    """Attach preludes, templates, and skips. Report harness drift."""
    problems: List[Problem] = []
    files = harness.get("files", {})
    by_path: Dict[str, List[Block]] = {}
    for block in blocks:
        by_path.setdefault(block.path, []).append(block)
    harness_path = HARNESS.as_posix()
    for path, entry in files.items():
        if path not in by_path:
            problems.append(
                Problem(harness_path, 1, "error", "%s: file has no rust blocks or does not exist" % path)
            )
            continue
        for key, spec in (entry.get("blocks") or {}).items():
            try:
                index = int(key)
            except ValueError:
                problems.append(Problem(harness_path, 1, "error", "%s: block key %r is not a number" % (path, key)))
                continue
            if index < 1 or index > len(by_path[path]):
                problems.append(
                    Problem(harness_path, 1, "error", "%s: no rust block #%d (file has %d)" % (path, index, len(by_path[path])))
                )
                continue
            block = by_path[path][index - 1]
            expected = (spec.get("first_line") or "").strip()
            actual = first_code_line(block.code)
            if expected != actual:
                problems.append(
                    Problem(
                        block.path,
                        block.line,
                        "error",
                        "rust block #%d does not match %s (expected first line %r, found %r); "
                        "blocks were added, moved, or edited, so update the harness" % (index, harness_path, expected, actual),
                    )
                )
                block.skip = "harness out of date"
                continue
            if "skip" in spec:
                reason = str(spec.get("skip") or "").strip()
                if not reason:
                    problems.append(Problem(block.path, block.line, "error", "rust block #%d: skip needs a reason" % index))
                block.skip = reason or "no reason"
                continue
            template = as_text(spec.get("template")) or CODE
            if CODE not in template:
                problems.append(
                    Problem(harness_path, 1, "error", "%s block #%d: template has no {code}" % (path, index))
                )
                template = CODE
            block.template = template
        prelude = as_text(entry.get("prelude"))
        for block in by_path[path]:
            block.prelude = prelude
    return problems


def normalize(code: str) -> str:
    """Give placeholder function bodies a body that type-checks."""
    return FN_PLACEHOLDER_RE.sub(lambda m: m.group(1) + "{ todo!() }", code)


def render(block: Block, harness_label: str) -> str:
    """Build one module's source and record where each line came from."""
    out: List[str] = []
    origin: List[Tuple[str, int]] = []

    def add(text: str, where: Tuple[str, int]) -> None:
        for piece in text.split("\n"):
            out.append(piece)
            origin.append(where)

    add(ALLOWS.rstrip("\n"), (harness_label, 1))
    if block.prelude:
        add(block.prelude, (harness_label, 1))
    before, _, after = block.template.partition(CODE)
    if before:
        add(before.rstrip("\n"), (harness_label, 1))
    for offset, piece in enumerate(normalize(block.code).split("\n")):
        out.append(piece)
        origin.append((block.path, block.line + offset))
    if after:
        add(after.lstrip("\n"), (harness_label, 1))
    block.lines = {number: where for number, where in enumerate(origin, 1)}
    return "\n".join(out) + "\n"


def build_crate(crate: Path, blocks: List[Block]) -> Dict[str, Block]:
    (crate / "src").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "examples-check"\nversion = "0.0.0"\nedition = "2021"\n'
        "publish = false\n\n[lib]\npath = \"src/lib.rs\"\n\n[workspace]\n",
        encoding="utf-8",
    )
    lib: List[str] = []
    modules: Dict[str, Block] = {}
    for number, block in enumerate(blocks, 1):
        name = "ex_%03d" % number
        lib.append("mod %s;" % name)
        (crate / "src" / (name + ".rs")).write_text(render(block, HARNESS.as_posix()), encoding="utf-8")
        modules["src/%s.rs" % name] = block
    (crate / "src" / "lib.rs").write_text("\n".join(lib) + "\n", encoding="utf-8")
    return modules


def map_errors(output: str, modules: Dict[str, Block]) -> List[Problem]:
    """Turn cargo's JSON messages into problems at markdown lines."""
    problems: List[Problem] = []
    seen = set()
    for raw in output.splitlines():
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        diag = msg.get("message") or {}
        if diag.get("level") not in ("error", "error: internal compiler error"):
            continue
        spans = diag.get("spans") or []
        primary = next((s for s in spans if s.get("is_primary")), spans[0] if spans else None)
        text = diag.get("message", "").strip()
        code = (diag.get("code") or {}).get("code")
        if code:
            text = "%s [%s]" % (text, code)
        where = ("examples-check", 1)
        if primary:
            block = modules.get(primary.get("file_name", ""))
            if block is not None:
                where = block.lines.get(primary.get("line_start", 1), (block.path, block.line))
                if where[0] != block.path:
                    text = "%s (in the harness code for %s rust block #%d)" % (text, block.path, block.index)
        key = (where, text)
        if key in seen:
            continue
        seen.add(key)
        problems.append(Problem(where[0], where[1], "error", text))
    return problems


def run_cargo(crate: Path) -> Tuple[int, str, str]:
    result = subprocess.run(
        ["cargo", "check", "--quiet", "--all-targets", "--message-format=json"],
        cwd=crate,
        capture_output=True,
        text=True,
        env=None,
    )
    return result.returncode, result.stdout, result.stderr


def load_harness(root: Path) -> Tuple[Dict[str, Any], List[Problem]]:
    path = root / HARNESS
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {}, [Problem(HARNESS.as_posix(), getattr(exc, "lineno", 1), "error", "invalid JSON: %s" % exc)]
    if not isinstance(data, dict):
        return {}, [Problem(HARNESS.as_posix(), 1, "error", "top level must be an object")]
    return data, []


def check_repo(root: Path) -> Tuple[List[Problem], int, int]:
    """Return (problems, compiled block count, skipped block count)."""
    root = Path(root)
    harness, problems = load_harness(root)
    blocks: List[Block] = []
    for path in doc_files(root):
        blocks.extend(find_blocks(root, path))
    problems.extend(apply_harness(root, blocks, harness))
    to_check = [b for b in blocks if b.skip is None]
    skipped = len(blocks) - len(to_check)
    if not to_check:
        return problems, 0, skipped
    with tempfile.TemporaryDirectory(prefix="examples-check.") as tmp:
        crate = Path(tmp) / "crate"
        modules = build_crate(crate, to_check)
        status, stdout, stderr = run_cargo(crate)
        found = map_errors(stdout, modules)
        if status != 0 and not found:
            tail = stderr.strip().splitlines()[-1:] or ["cargo check failed"]
            found = [Problem("examples-check", 1, "error", tail[0])]
        problems.extend(found)
    return problems, len(to_check), skipped


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every Rust code block in the skills and docs compiles."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="print findings as JSON",
    )
    args = parser.parse_args(argv)
    if shutil.which("cargo") is None:
        sys.stderr.write("check-examples: cargo not found on PATH\n")
        return 2
    problems, checked, skipped = check_repo(Path(args.root))
    errors = sum(1 for p in problems if p.level == "error")
    if args.as_json:
        json.dump(
            {
                "ok": errors == 0,
                "error_count": errors,
                "compiled": checked,
                "skipped": skipped,
                "summary": summary_line(problems, checked, skipped),
                "problems": [asdict(p) for p in problems],
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        for problem in problems:
            sys.stdout.write(format_problem(problem) + "\n")
        sys.stdout.write(summary_line(problems, checked, skipped) + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
