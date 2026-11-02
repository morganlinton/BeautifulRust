#!/usr/bin/env python3
"""Build the data files the MCP server bundles.

- mcp/data/guidance.json: every section of the skills and reference digests,
  with a BM25 index, for search_guidance.
- mcp/data/lints.json: every rustc and clippy lint from the installed
  toolchain, with clippy's full explanation and the level and reason from
  lints/lints.toml, for explain_lint.

The output is generated, not committed: CI and deploys rebuild it, so it can't
drift from the skills or the lints config. Needs cargo, rustc, and
clippy-driver on PATH. Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/morganlinton/BeautifulRust/blob/main"

# The tokenizer is mirrored in mcp/src/tokenize.ts. guidance.json carries
# sample outputs so the TypeScript tests can prove the two still agree.
TOKEN_RE = re.compile(r"[a-z0-9_]+")
STOPWORDS = frozenset(
    "a an and are as at be by do does for from how i if in is it its of on or "
    "should that the this to use what when which why with you your".split()
)
TOKENIZER_SAMPLES = (
    "Should library errors use thiserror or anyhow?",
    "clippy::unwrap_used and Box<dyn Error> in public APIs",
    "Panics, asserts, and expect() messages",
)
HEADING_WEIGHT = 3

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SOURCE_RE = re.compile(r"^Sources?:(.*?)(?:\n\s*\n|\Z)", re.M | re.S)
URL_RE = re.compile(r"https?://[^\s)>\]]+")
LINT_LINE_RE = re.compile(r"^\s*(\S+)\s+(allow|warn|deny|forbid|expect)\s+(.*)$")
LINTS_TOML_RE = re.compile(r"^([a-z0-9_]+)\s*=\s*(.+?)\s*(?:#\s*(.*))?$")


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for raw in TOKEN_RE.findall(text.lower()):
        parts = [raw]
        if "_" in raw:
            parts.extend(p for p in raw.split("_") if p)
        for token in parts:
            if len(token) < 2 or token in STOPWORDS:
                continue
            if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
                token = token[:-1]
            tokens.append(token)
    return tokens


def github_slug(heading: str, seen: Dict[str, int]) -> str:
    """The anchor GitHub gives a heading, including -1, -2 for repeats."""
    text = re.sub(r"`([^`]*)`", r"\1", heading).lower()
    slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    count = seen.get(slug, 0)
    seen[slug] = count + 1
    return slug if count == 0 else "%s-%d" % (slug, count)


def strip_frontmatter(text: str) -> Tuple[str, int]:
    if not text.startswith("---\n"):
        return text, 0
    end = text.find("\n---\n", 4)
    if end == -1:
        return text, 0
    return text[end + 5 :], text[: end + 5].count("\n")


def split_sections(path: Path) -> List[Dict[str, Any]]:
    text, offset = strip_frontmatter(path.read_text(encoding="utf-8"))
    sections: List[Dict[str, Any]] = []
    stack: List[Tuple[int, str]] = []
    seen: Dict[str, int] = {}
    current: Optional[Dict[str, Any]] = None
    in_fence = False
    for i, line in enumerate(text.splitlines(), offset + 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = {
                "heading": title,
                "trail": [t for _, t in stack],
                "anchor": github_slug(title, seen),
                "line": i,
                "lines": [],
            }
            sections.append(current)
        elif current is not None:
            current["lines"].append(line)
    for section in sections:
        section["text"] = "\n".join(section.pop("lines")).strip()
    return [s for s in sections if s["text"]]


def source_of(path: Path, text: str) -> Optional[Dict[str, str]]:
    """The guide a reference digest summarizes, from its title and Source line."""
    if path.parent.name != "references":
        return None
    title_match = re.search(r"^# (.+)$", text, re.M)
    if not title_match:
        return None
    name = re.sub(r"\s*\(digest\)\s*$", "", title_match.group(1)).strip()
    source = {"name": name}
    paragraph = SOURCE_RE.search(text)
    url_match = URL_RE.search(paragraph.group(1)) if paragraph else None
    if url_match:
        source["url"] = url_match.group(0).rstrip(".,;")
    return source


def build_guidance(root: Path) -> Dict[str, Any]:
    files = sorted(root.glob("skills/*/SKILL.md")) + sorted(
        root.glob("skills/*/references/*.md")
    )
    chunks: List[Dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        skill = path.relative_to(root / "skills").parts[0]
        source = source_of(path, path.read_text(encoding="utf-8"))
        for section in split_sections(path):
            counts: Dict[str, int] = {}
            body = tokenize(section["text"])
            heading = tokenize(" ".join(section["trail"])) * HEADING_WEIGHT
            for token in body + heading:
                counts[token] = counts.get(token, 0) + 1
            chunk = {
                "id": "%s#%s" % (rel, section["anchor"]),
                "skill": skill,
                "file": rel,
                "heading": section["heading"],
                "trail": section["trail"],
                "url": "%s/%s#%s" % (REPO_URL, rel, section["anchor"]),
                "text": section["text"],
                "terms": counts,
                "length": len(body) + len(heading),
            }
            if source:
                chunk["source"] = source
            chunks.append(chunk)
    df: Dict[str, int] = {}
    for chunk in chunks:
        for term in chunk["terms"]:
            df[term] = df.get(term, 0) + 1
    total = sum(c["length"] for c in chunks)
    return {
        "chunks": chunks,
        "df": df,
        "avgLength": total / len(chunks) if chunks else 0,
        "tokenizerSamples": [
            {"text": t, "tokens": tokenize(t)} for t in TOKENIZER_SAMPLES
        ],
    }


def run(cmd: Sequence[str]) -> str:
    return subprocess.run(
        list(cmd), capture_output=True, text=True, check=True
    ).stdout


def parse_lint_help(text: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    """Lints and lint groups from `clippy-driver -W help`."""
    lints: Dict[str, Dict[str, Any]] = {}
    groups: Dict[str, List[str]] = {}
    mode = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Lint checks"):
            mode = "lints"
            continue
        if stripped.startswith("Lint groups"):
            mode = "groups"
            continue
        if not stripped or stripped.startswith("name ") or set(stripped) <= {"-", " "}:
            continue
        if mode == "lints":
            match = LINT_LINE_RE.match(line)
            if match:
                name = match.group(1).replace("-", "_")
                lints[name] = {
                    "name": name,
                    "tool": "clippy" if name.startswith("clippy::") else "rustc",
                    "defaultLevel": match.group(2),
                    "summary": match.group(3).strip(),
                }
        elif mode == "groups":
            parts = stripped.split(None, 1)
            if len(parts) == 2 and parts[0] != "warnings":
                group = parts[0].replace("-", "_")
                members = [m.strip().replace("-", "_") for m in parts[1].split(",")]
                groups[group] = [m for m in members if m]
    return lints, groups


def parse_lints_toml(path: Path) -> Dict[str, Dict[str, Any]]:
    """Level and inline reason for each lint in lints/lints.toml."""
    config: Dict[str, Dict[str, Any]] = {}
    table = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            table = stripped.strip("[]")
            continue
        if table not in ("lints.rust", "lints.clippy") or stripped.startswith("#"):
            continue
        match = LINTS_TOML_RE.match(stripped)
        if not match:
            continue
        name, value, comment = match.groups()
        level_match = re.search(r'"(allow|warn|deny|forbid)"', value)
        if not level_match:
            continue
        key = ("clippy::" + name) if table == "lints.clippy" else name
        entry: Dict[str, Any] = {"level": level_match.group(1)}
        if comment:
            entry["reason"] = comment.strip()
            if "[lib]" in comment:
                entry["librariesOnly"] = True
                entry["reason"] = comment.replace("[lib]", "").strip()
        config[key] = entry
    return config


def explain(name: str) -> str:
    try:
        return run(["cargo", "clippy", "--explain", name.split("::", 1)[1]]).strip()
    except subprocess.CalledProcessError:
        return ""


def build_lints(root: Path, jobs: int) -> Dict[str, Any]:
    lints, groups = parse_lint_help(run(["clippy-driver", "-W", "help"]))
    for group, members in groups.items():
        for member in members:
            if member in lints:
                lints[member].setdefault("groups", []).append(group)
    config = parse_lints_toml(root / "lints" / "lints.toml")
    for name, entry in config.items():
        if name in lints:
            lints[name]["beautifulRust"] = entry
        elif name not in groups:
            raise SystemExit("lints.toml names %s, which the toolchain doesn't know" % name)
    clippy = sorted(n for n in lints if n.startswith("clippy::"))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name, text in zip(clippy, pool.map(explain, clippy)):
            if text:
                lints[name]["explanation"] = text
    group_config = {g: config[g] for g in groups if g in config}
    return {
        "toolchain": {
            "rustc": run(["rustc", "--version"]).strip(),
            "clippy": run(["cargo", "clippy", "--version"]).strip(),
        },
        "lints": dict(sorted(lints.items())),
        "groups": {
            g: {"members": len(m), **({"beautifulRust": group_config[g]} if g in group_config else {})}
            for g, m in sorted(groups.items())
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root")
    parser.add_argument(
        "--out", type=Path, help="output directory (default: mcp/data under the root)"
    )
    parser.add_argument(
        "--jobs", type=int, default=8, help="parallel `cargo clippy --explain` calls"
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    out = args.out or root / "mcp" / "data"
    out.mkdir(parents=True, exist_ok=True)
    guidance = build_guidance(root)
    try:
        lints = build_lints(root, args.jobs)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("build-mcp-data: needs a Rust toolchain with clippy: %s" % exc, file=sys.stderr)
        return 1
    for name, data in (("guidance.json", guidance), ("lints.json", lints)):
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    print(
        "Wrote %d guidance sections and %d lints (%s) to %s"
        % (len(guidance["chunks"]), len(lints["lints"]), lints["toolchain"]["clippy"], out)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
