#!/usr/bin/env python3
"""Check skill frontmatter, links, eval cases, and plugin manifests.

Stdlib only, Python 3.9+. Exit 1 on any error. Warnings do not fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ALLOWED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=['\"]([^'\"]+)['\"]", re.I)
REF_DEF_RE = re.compile(r"^[ \t]*\[([^\]]+)\]:\s+(\S+)", re.M)
REF_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9._-])references/([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)"
)
FILES_REF_RE = re.compile(
    r"(?<![/\w])files/([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)"
)
GRADER_NAME_RE = re.compile(r"^(\d+)-.+\.md$")
HEADING_RE = re.compile(r"^## \[([^\]]+)\]")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

MAX_NAME = 64
MAX_DESC = 1024
MAX_COMPAT = 500
MAX_BODY_LINES = 500

# The portable plugin.json read by Codex and the ChatGPT / Codex Plugins
# Directory. Limits are from developers.openai.com/plugins/deploy/submission.
PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PORTABLE_KEYS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
PORTABLE_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
OPENAI_TEXT_LIMITS = (
    ("displayName", 30),
    ("shortDescription", 30),
    ("longDescription", 4000),
    ("developerName", 80),
    ("category", 80),
)
OPENAI_URL_KEYS = ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL")
OPENAI_ICON_KEYS = ("composerIcon", "logo", "composerIconDark", "logoDark")
OPENAI_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_OPENAI_IMAGE_BYTES = 5 * 1024 * 1024
MIN_ICON_SIDE = 48
MAX_CAPABILITIES = 20
MAX_CAPABILITY = 120
MAX_PROMPTS = 3
MAX_PROMPT = 128


@dataclass(frozen=True)
class Problem:
    path: str
    line: int
    level: str
    message: str


class YamlError(Exception):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.message = message


class YamlParser:
    """Small YAML subset: maps, lists, quoted scalars, | and > blocks."""

    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.i = 0
        self.locs: Dict[Tuple[str, ...], int] = {}

    def parse(self) -> Tuple[Any, Dict[Tuple[str, ...], int]]:
        self._skip_empty()
        if self.i >= len(self.lines):
            return None, self.locs
        indent = self._indent(self.lines[self.i])
        value = self._parse_value(indent, ())
        self._skip_empty()
        if self.i < len(self.lines):
            raise YamlError(self.i + 1, "unexpected extra YAML content")
        return value, self.locs

    def _skip_empty(self) -> None:
        while self.i < len(self.lines) and self._is_empty(self.lines[self.i]):
            self.i += 1

    @staticmethod
    def _is_empty(line: str) -> bool:
        stripped = line.strip()
        return stripped == "" or stripped.startswith("#")

    def _indent(self, line: str) -> int:
        n = 0
        for ch in line:
            if ch == " ":
                n += 1
            elif ch == "\t":
                raise YamlError(self.i + 1, "tabs are not allowed in YAML indent")
            else:
                break
        return n

    def _parse_value(self, indent: int, path: Tuple[str, ...]) -> Any:
        self._skip_empty()
        if self.i >= len(self.lines):
            return None
        line = self.lines[self.i]
        ind = self._indent(line)
        if ind != indent:
            raise YamlError(self.i + 1, "unexpected indent")
        content = line[ind:]
        if content.startswith("- ") or content == "-":
            return self._parse_seq(indent, path)
        return self._parse_map(indent, path)

    def _parse_seq(self, indent: int, path: Tuple[str, ...]) -> List[Any]:
        items: List[Any] = []
        index = 0
        while True:
            self._skip_empty()
            if self.i >= len(self.lines):
                break
            line = self.lines[self.i]
            ind = self._indent(line)
            if ind < indent:
                break
            if ind != indent:
                raise YamlError(self.i + 1, "unexpected indent")
            content = line[ind:]
            if not (content.startswith("- ") or content == "-"):
                break
            line_no = self.i + 1
            rest = "" if content == "-" else content[2:]
            self.i += 1
            item_path = path + (str(index),)
            self.locs[item_path] = line_no
            rest = rest.strip()
            if rest == "":
                self._skip_empty()
                if self.i < len(self.lines) and self._indent(self.lines[self.i]) > indent:
                    items.append(
                        self._parse_value(self._indent(self.lines[self.i]), item_path)
                    )
                else:
                    items.append(None)
            else:
                items.append(self._parse_scalar(rest, line_no))
            index += 1
        return items

    def _parse_map(self, indent: int, path: Tuple[str, ...]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        while True:
            self._skip_empty()
            if self.i >= len(self.lines):
                break
            line = self.lines[self.i]
            ind = self._indent(line)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError(self.i + 1, "unexpected indent")
            content = line[ind:]
            if content.startswith("- ") or content == "-":
                raise YamlError(self.i + 1, "expected a mapping key")
            key, rest = self._split_key(content, self.i + 1)
            if key in result:
                raise YamlError(self.i + 1, "duplicate key %s" % key)
            line_no = self.i + 1
            self.locs[path + (key,)] = line_no
            self.i += 1
            rest = rest.strip()
            if rest in ("|", "|-", "|+", ">", ">-", ">+"):
                result[key] = self._parse_block(indent, rest)
            elif rest == "":
                self._skip_empty()
                if self.i < len(self.lines) and not self._is_empty(self.lines[self.i]):
                    next_ind = self._indent(self.lines[self.i])
                    if next_ind > indent:
                        result[key] = self._parse_value(next_ind, path + (key,))
                        continue
                result[key] = None
            else:
                result[key] = self._parse_scalar(rest, line_no)
        return result

    def _split_key(self, content: str, line_no: int) -> Tuple[str, str]:
        in_s = in_d = False
        for i, ch in enumerate(content):
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == ":" and not in_s and not in_d:
                nxt = content[i + 1 : i + 2]
                if nxt in ("", " ", "\t"):
                    return content[:i].strip(), content[i + 1 :]
        raise YamlError(line_no, "missing ':' in mapping entry")

    def _parse_block(self, key_indent: int, marker: str) -> str:
        folded = marker[0] == ">"
        chomp = marker[1:] if len(marker) > 1 else ""
        chunks: List[Optional[str]] = []
        content_indent: Optional[int] = None
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if line.strip() == "":
                chunks.append("")
                self.i += 1
                continue
            if self._is_empty(line) and line.lstrip().startswith("#") and content_indent is None:
                break
            ind = self._indent(line)
            if ind <= key_indent:
                break
            if content_indent is None:
                content_indent = ind
            if ind < content_indent:
                break
            chunks.append(line[content_indent:])
            self.i += 1
        while chunks and chunks[-1] == "":
            chunks.pop()
        lines = [c if c is not None else "" for c in chunks]
        if folded:
            text = _fold_block(lines)
        else:
            text = "\n".join(lines)
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n"
        return text + ("\n" if text else "")

    def _parse_scalar(self, raw: str, line_no: int) -> Any:
        raw = _strip_comment(raw)
        if raw == "" or raw == "~" or raw == "null":
            return None
        if raw in ("true", "True", "TRUE"):
            return True
        if raw in ("false", "False", "FALSE"):
            return False
        if raw.startswith("[") and raw.endswith("]"):
            return self._parse_flow_seq(raw[1:-1], line_no)
        if raw.startswith("{") and raw.endswith("}"):
            return self._parse_flow_map(raw[1:-1], line_no)
        if raw[0] in "'\"":
            return _parse_quoted(raw, line_no)
        if re.fullmatch(r"-?(0|[1-9]\d*)", raw):
            return int(raw)
        return raw


    def _parse_flow_seq(self, inner: str, line_no: int) -> List[Any]:
        if inner.strip() == "":
            return []
        return [self._parse_scalar(part.strip(), line_no) for part in _split_flow(inner)]

    def _parse_flow_map(self, inner: str, line_no: int) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if inner.strip() == "":
            return result
        for part in _split_flow(inner):
            key, rest = self._split_key(part.strip(), line_no)
            result[key] = self._parse_scalar(rest.strip(), line_no)
        return result


def _fold_block(lines: List[str]) -> str:
    paragraphs: List[str] = []
    current: List[str] = []
    for line in lines:
        if line == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
            else:
                paragraphs.append("")
        elif line[:1] in " \t":
            if current:
                paragraphs.append(" ".join(current))
                current = []
            paragraphs.append(line)
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n".join(paragraphs)


def _strip_comment(raw: str) -> str:
    in_s = in_d = False
    for i, ch in enumerate(raw):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            if i == 0 or raw[i - 1].isspace():
                return raw[:i].rstrip()
    return raw.rstrip()


def _split_flow(inner: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    in_s = in_d = False
    depth = 0
    for ch in inner:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch in "[{" and not in_s and not in_d:
            depth += 1
        elif ch in "]}" and not in_s and not in_d and depth:
            depth -= 1
        if ch == "," and not in_s and not in_d and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def _parse_quoted(raw: str, line_no: int) -> str:
    quote = raw[0]
    if quote not in "'\"" or len(raw) < 2 or raw[-1] != quote:
        raise YamlError(line_no, "unterminated quoted string")
    inner = raw[1:-1]
    if quote == "'":
        return inner.replace("''", "'")
    out: List[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(inner):
            break
        nxt = inner[i + 1]
        mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}
        out.append(mapping.get(nxt, nxt))
        i += 2
    return "".join(out)


def parse_yaml(text: str) -> Tuple[Any, Dict[Tuple[str, ...], int]]:
    return YamlParser(text).parse()


def split_frontmatter(text: str) -> Tuple[Optional[str], str, int]:
    if not text.startswith("---"):
        return None, text, 1
    rest = text[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        return None, text, 1
    match = re.search(r"(?m)^---[ \t]*\r?$", rest)
    if not match:
        return None, text, 1
    fm = rest[: match.start()]
    body = rest[match.end() :]
    if body.startswith("\r\n"):
        body = body[2:]
    elif body.startswith("\n"):
        body = body[1:]
    fm_lines = fm.splitlines()
    body_start = 2 + len(fm_lines) + 1
    return fm, body, body_start


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def format_problem(problem: Problem) -> str:
    prefix = "warning: " if problem.level == "warning" else ""
    return "%s:%d: %s%s" % (problem.path, problem.line, prefix, problem.message)


def summary_line(problems: Sequence[Problem]) -> str:
    errors = sum(1 for p in problems if p.level == "error")
    warnings = sum(1 for p in problems if p.level == "warning")
    err_word = "error" if errors == 1 else "errors"
    warn_word = "warning" if warnings == 1 else "warnings"
    return "%d %s, %d %s" % (errors, err_word, warnings, warn_word)


class Checker:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.problems: List[Problem] = []

    def add(
        self,
        path: Path,
        line: int,
        message: str,
        level: str = "error",
    ) -> None:
        self.problems.append(
            Problem(rel(self.root, path), max(1, line), level, message)
        )

    def check(self) -> List[Problem]:
        plugin = self.root / ".claude-plugin" / "plugin.json"
        market = self.root / ".claude-plugin" / "marketplace.json"
        changelog = self.root / "CHANGELOG.md"
        readme = self.root / "README.md"
        name, version = self._check_plugin_files(plugin, market)
        if version:
            self._check_changelog(changelog, version)
        portable = self.root / "plugin.json"
        if portable.is_file():
            self._check_portable_plugin(portable, name, version)
        skills = self._skill_dirs()
        if not skills:
            self.add(self.root / "skills", 1, "no SKILL.md found under skills/")
        if readme.is_file():
            readme_text = self._read(readme)
            if readme_text is not None:
                self._check_doc_links(readme, readme_text, skills)
        else:
            self.add(readme, 1, "missing file")
        for skill_dir in skills:
            self._check_skill(skill_dir)
        self.problems.sort(key=lambda p: (p.path, p.line, p.level, p.message))
        return self.problems

    def _skill_dirs(self) -> List[Path]:
        base = self.root / "skills"
        if not base.is_dir():
            return []
        found = []
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                found.append(child)
        return found

    def _read(self, path: Path) -> Optional[str]:
        if not path.is_file():
            self.add(path, 1, "missing file")
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.add(path, 1, "cannot read file: %s" % exc)
            return None
        if text.startswith("\ufeff"):
            text = text[1:]
        return text

    def _load_yaml(self, path: Path, text: str) -> Tuple[Any, Dict[Tuple[str, ...], int]]:
        try:
            return parse_yaml(text)
        except YamlError as exc:
            self.add(path, exc.line, "YAML: %s" % exc.message)
            return None, {}

    def _load_frontmatter(
        self, path: Path, text: str
    ) -> Tuple[Optional[Dict[str, Any]], Dict[Tuple[str, ...], int], str, int]:
        fm_text, body, body_start = split_frontmatter(text)
        if fm_text is None:
            self.add(path, 1, "missing YAML frontmatter")
            return None, {}, body, 1
        data, locs = self._load_yaml(path, fm_text)
        if data is None:
            return None, {}, body, body_start
        if not isinstance(data, dict):
            self.add(path, 1, "frontmatter must be a mapping")
            return None, {}, body, body_start
        shifted = {}
        for key, line in locs.items():
            shifted[key] = line + 1
        return data, shifted, body, body_start

    def _loc(
        self, locs: Dict[Tuple[str, ...], int], *keys: str, default: int = 1
    ) -> int:
        return locs.get(keys, default)

    def _check_plugin_files(
        self, plugin_path: Path, market_path: Path
    ) -> Tuple[Optional[str], Optional[str]]:
        plugin = self._load_json(plugin_path)
        market = self._load_json(market_path)
        version = None
        plugin_name = None
        if isinstance(plugin, dict):
            plugin_name = plugin.get("name")
            if not isinstance(plugin_name, str) or not plugin_name.strip():
                self.add(plugin_path, 1, "missing name")
                plugin_name = None
            version = plugin.get("version")
            if not isinstance(version, str) or not version.strip():
                self.add(plugin_path, 1, "missing version")
                version = None
            elif not SEMVER_RE.match(version):
                self.add(
                    plugin_path,
                    _json_key_line(plugin_path, "version"),
                    "version %r is not semver" % version,
                )
        if isinstance(market, dict) and plugin_name:
            market_name = market.get("name")
            if market_name != plugin_name:
                self.add(
                    market_path,
                    _json_key_line(market_path, "name"),
                    "plugin name %r does not match %r in plugin.json"
                    % (market_name, plugin_name),
                )
            plugins = market.get("plugins")
            if not isinstance(plugins, list) or not plugins:
                self.add(market_path, 1, "missing plugins list")
            else:
                for i, entry in enumerate(plugins):
                    if not isinstance(entry, dict):
                        self.add(market_path, 1, "plugins[%d] must be a mapping" % i)
                        continue
                    entry_name = entry.get("name")
                    if entry_name != plugin_name:
                        self.add(
                            market_path,
                            1,
                            "plugin name %r does not match %r in plugin.json"
                            % (entry_name, plugin_name),
                        )
        return plugin_name, version if isinstance(version, str) else None

    def _check_portable_plugin(
        self, path: Path, name: Optional[str], version: Optional[str]
    ) -> None:
        data = self._load_json(path)
        if not isinstance(data, dict):
            if data is not None:
                self.add(path, 1, "must be a JSON object")
            return
        for key in sorted(set(data) - PORTABLE_KEYS):
            self.add(
                path, _json_key_line(path, key), "key %r is not in the schema" % key
            )
        if data.get("$schema") != PORTABLE_SCHEMA:
            self.add(
                path,
                _json_key_line(path, "$schema"),
                "$schema must be %s" % PORTABLE_SCHEMA,
            )
        portable_name = data.get("name")
        if not isinstance(portable_name, str) or not PORTABLE_NAME_RE.match(
            portable_name
        ):
            self.add(
                path, _json_key_line(path, "name"), "name %r is not valid" % portable_name
            )
        elif name and portable_name != name:
            self.add(
                path,
                _json_key_line(path, "name"),
                "name %r does not match %r in .claude-plugin/plugin.json"
                % (portable_name, name),
            )
        if version and data.get("version") != version:
            self.add(
                path,
                _json_key_line(path, "version"),
                "version %r does not match %r in .claude-plugin/plugin.json"
                % (data.get("version"), version),
            )
        extensions = data.get("extensions")
        openai = extensions.get("com.openai") if isinstance(extensions, dict) else None
        if not isinstance(openai, dict):
            self.add(path, 1, "missing extensions.com.openai")
            return
        interface = openai.get("interface")
        if not isinstance(interface, dict):
            self.add(path, 1, "missing extensions.com.openai.interface")
            return
        self._check_openai_interface(path, interface)

    def _check_openai_interface(self, path: Path, interface: Dict[str, Any]) -> None:
        # Unknown interface keys: the top-level gate (PORTABLE_KEYS) stops at the
        # top level; OpenAI's submission review is strict one level deeper.
        known_interface_keys = (
            {key for key, _ in OPENAI_TEXT_LIMITS}
            | set(OPENAI_URL_KEYS)
            | {"capabilities", "defaultPrompt", "brandColor", "brandColorDark"}
            | set(OPENAI_ICON_KEYS)
        )
        for key in sorted(set(interface) - known_interface_keys):
            self.add(
                path, _json_key_line(path, key),
                "key %r is not in the schema" % key,
            )
        for key, limit in OPENAI_TEXT_LIMITS:
            value = interface.get(key)
            if not isinstance(value, str) or not value.strip():
                self.add(path, 1, "interface.%s is required" % key)
            elif len(value) > limit:
                self.add(
                    path,
                    _json_key_line(path, key),
                    "interface.%s is %d characters; the limit is %d"
                    % (key, len(value), limit),
                )
        for key in OPENAI_URL_KEYS:
            value = interface.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not value.startswith("https://"):
                self.add(
                    path,
                    _json_key_line(path, key),
                    "interface.%s must be an HTTPS URL" % key,
                )
        capabilities = interface.get("capabilities")
        if not isinstance(capabilities, list):
            self.add(path, 1, "interface.capabilities must be a list")
        else:
            if len(capabilities) > MAX_CAPABILITIES:
                self.add(
                    path,
                    _json_key_line(path, "capabilities"),
                    "interface.capabilities has %d items; the limit is %d"
                    % (len(capabilities), MAX_CAPABILITIES),
                )
            for item in capabilities:
                if not isinstance(item, str) or len(item) > MAX_CAPABILITY:
                    self.add(
                        path,
                        _json_key_line(path, "capabilities"),
                        "each capability must be a string of at most %d characters"
                        % MAX_CAPABILITY,
                    )
        prompts = interface.get("defaultPrompt")
        if prompts is not None:
            if isinstance(prompts, str):
                prompts = [prompts]
            if (
                not isinstance(prompts, list)
                or len(prompts) > MAX_PROMPTS
                or len(set(map(str, prompts))) != len(prompts)
                or any(not isinstance(p, str) or len(p) > MAX_PROMPT for p in prompts)
            ):
                self.add(
                    path,
                    _json_key_line(path, "defaultPrompt"),
                    "interface.defaultPrompt must be up to %d unique strings of at "
                    "most %d characters" % (MAX_PROMPTS, MAX_PROMPT),
                )
        for key in ("brandColor", "brandColorDark"):
            value = interface.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not HEX_COLOR_RE.match(value):
                self.add(
                    path, _json_key_line(path, key), "interface.%s must be #RRGGBB" % key
                )
        for key in OPENAI_ICON_KEYS:
            value = interface.get(key)
            if value is None:
                if key in ("composerIcon", "logo"):
                    self.add(path, 1, "interface.%s is required" % key)
                continue
            self._check_openai_icon(path, key, value)

    def _check_openai_icon(self, path: Path, key: str, value: Any) -> None:
        line = _json_key_line(path, key)
        if not isinstance(value, str) or not value.startswith("./"):
            self.add(path, line, "interface.%s must be a ./ path in the plugin" % key)
            return
        image = (path.parent / value).resolve()
        if path.parent.resolve() not in image.parents or not image.is_file():
            self.add(path, line, "interface.%s: %s not found" % (key, value))
            return
        if image.suffix.lower() not in OPENAI_IMAGE_SUFFIXES:
            self.add(path, line, "interface.%s must be PNG, JPEG, WebP, or SVG" % key)
        if image.stat().st_size > MAX_OPENAI_IMAGE_BYTES:
            self.add(path, line, "interface.%s is larger than 5 MiB" % key)
        size = _png_size(image)
        if size is not None:
            width, height = size
            if width != height or width < MIN_ICON_SIDE:
                self.add(
                    path,
                    line,
                    "interface.%s is %dx%d; icons must be square and at least %dpx"
                    % (key, width, height, MIN_ICON_SIDE),
                )

    def _load_json(self, path: Path) -> Any:
        text = self._read(path)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            self.add(path, exc.lineno or 1, "JSON: %s" % exc.msg)
            return None

    def _check_changelog(self, path: Path, version: str) -> None:
        text = self._read(path)
        if text is None:
            return
        has_unreleased = False
        has_version = False
        unreleased_line = 1
        version_line = 1
        for i, line in enumerate(text.splitlines(), 1):
            match = HEADING_RE.match(line.strip())
            if not match:
                continue
            label = match.group(1)
            if label == "Unreleased":
                has_unreleased = True
                unreleased_line = i
            elif label == version:
                has_version = True
                version_line = i
        if not has_unreleased and not has_version:
            self.add(
                path,
                1,
                "needs an [Unreleased] section or a [%s] entry" % version,
            )
        links: Dict[str, Tuple[str, int]] = {}
        for i, line in enumerate(text.splitlines(), 1):
            match = re.match(r"^\[([^\]]+)\]:\s+(\S+)", line)
            if match:
                links[match.group(1)] = (match.group(2), i)
        if has_unreleased:
            if "Unreleased" not in links:
                self.add(
                    path,
                    unreleased_line,
                    "[Unreleased] compare link is missing",
                )
            elif version not in links["Unreleased"][0]:
                self.add(
                    path,
                    links["Unreleased"][1],
                    "compare links do not reference version %s" % version,
                )
        if has_version:
            if version not in links:
                self.add(
                    path,
                    version_line,
                    "compare link for [%s] is missing" % version,
                )
            elif version not in links[version][0]:
                self.add(
                    path,
                    links[version][1],
                    "compare links do not reference version %s" % version,
                )

    def _check_skill(self, skill_dir: Path) -> None:
        skill_md = skill_dir / "SKILL.md"
        text = self._read(skill_md)
        if text is None:
            return
        data, locs, body, body_start = self._load_frontmatter(skill_md, text)
        mentioned_refs: List[Path] = []
        if data is not None:
            extra = sorted(set(data) - ALLOWED_FRONTMATTER)
            if extra:
                self.add(
                    skill_md,
                    self._loc(locs, extra[0]),
                    "unknown frontmatter key%s: %s"
                    % ("s" if len(extra) > 1 else "", ", ".join(extra)),
                )
            if "name" not in data:
                self.add(skill_md, 1, "missing name")
            else:
                name = data["name"]
                line = self._loc(locs, "name")
                if not isinstance(name, str) or not name.strip():
                    self.add(skill_md, line, "name must be a non-empty string")
                else:
                    if len(name) > MAX_NAME:
                        self.add(
                            skill_md,
                            line,
                            "name exceeds %d characters (%d)" % (MAX_NAME, len(name)),
                        )
                    if not NAME_RE.match(name):
                        self.add(
                            skill_md,
                            line,
                            "name %r must be lowercase letters, digits, and hyphens"
                            % name,
                        )
                    if name != skill_dir.name:
                        self.add(
                            skill_md,
                            line,
                            "name %r must equal the folder name %r"
                            % (name, skill_dir.name),
                        )
            if "description" not in data:
                self.add(skill_md, 1, "missing description")
            else:
                desc = data["description"]
                line = self._loc(locs, "description")
                if not isinstance(desc, str) or not desc.strip():
                    self.add(skill_md, line, "description must be a non-empty string")
                elif len(desc) > MAX_DESC:
                    self.add(
                        skill_md,
                        line,
                        "description exceeds %d characters (%d)"
                        % (MAX_DESC, len(desc)),
                    )
            if "compatibility" in data:
                compat = data["compatibility"]
                line = self._loc(locs, "compatibility")
                if not isinstance(compat, str):
                    self.add(skill_md, line, "compatibility must be a string")
                elif len(compat) > MAX_COMPAT:
                    self.add(
                        skill_md,
                        line,
                        "compatibility exceeds %d characters (%d)"
                        % (MAX_COMPAT, len(compat)),
                    )
        body_lines = body.splitlines()
        if len(body_lines) > MAX_BODY_LINES:
            self.add(
                skill_md,
                body_start,
                "SKILL.md body has %d lines (spec guidance is %d)"
                % (len(body_lines), MAX_BODY_LINES),
                level="warning",
            )
        mentioned_refs.extend(self._check_doc_links(skill_md, text, [skill_dir]))
        self._check_orphans(skill_dir, mentioned_refs)
        self._check_evals(skill_dir)

    def _reference_hit(
        self, target: Path, skill_dirs: Sequence[Path]
    ) -> Optional[Path]:
        resolved = target.resolve()
        for skill_dir in skill_dirs:
            ref_root = (skill_dir / "references").resolve()
            if resolved.is_relative_to(ref_root):
                return resolved
        return None

    def _check_relative_url(
        self,
        path: Path,
        url: str,
        line: int,
        skill_dirs: Sequence[Path],
        resolved_refs: List[Path],
    ) -> None:
        target = (path.parent / url).resolve()
        if not target.is_file():
            self.add(path, line, "broken link %s" % url)
            return
        hit = self._reference_hit(target, skill_dirs)
        if hit is not None:
            resolved_refs.append(hit)

    def _check_doc_links(
        self, path: Path, text: str, skill_dirs: Sequence[Path]
    ) -> List[Path]:
        resolved_refs: List[Path] = []
        for match in MD_LINK_RE.finditer(text):
            url = _normalize_url(match.group(1))
            if not url or not _is_relative(url):
                continue
            self._check_relative_url(
                path,
                url,
                text[: match.start()].count("\n") + 1,
                skill_dirs,
                resolved_refs,
            )
        for match in IMG_SRC_RE.finditer(text):
            url = _normalize_url(match.group(1))
            if not url or not _is_relative(url):
                continue
            self._check_relative_url(
                path,
                url,
                text[: match.start()].count("\n") + 1,
                skill_dirs,
                resolved_refs,
            )
        for match in REF_DEF_RE.finditer(text):
            url = _normalize_url(match.group(2))
            if not url or not _is_relative(url):
                continue
            self._check_relative_url(
                path,
                url,
                text[: match.start()].count("\n") + 1,
                skill_dirs,
                resolved_refs,
            )
        for match in REF_MENTION_RE.finditer(text):
            mention = "references/" + match.group(1)
            line = text[: match.start()].count("\n") + 1
            found = None
            candidates = [path.parent / mention]
            candidates.extend(sd / mention for sd in skill_dirs)
            for cand in candidates:
                if cand.is_file():
                    found = cand.resolve()
                    break
            if found is None:
                self.add(path, line, "broken link %s" % mention)
            else:
                resolved_refs.append(found)
        return resolved_refs

    def _check_orphans(
        self, skill_dir: Path, mentioned: Sequence[Path]
    ) -> None:
        ref_dir = skill_dir / "references"
        if not ref_dir.is_dir():
            return
        mentioned_set = {p.resolve() for p in mentioned}
        for child in sorted(ref_dir.rglob("*")):
            if not child.is_file():
                continue
            if child.resolve() not in mentioned_set:
                self.add(
                    child,
                    1,
                    "orphan reference %s; not linked from SKILL.md"
                    % child.relative_to(skill_dir).as_posix(),
                )

    def _check_evals(self, skill_dir: Path) -> None:
        evals = skill_dir / "evals"
        if not evals.is_dir():
            return
        for case_dir in sorted(p for p in evals.iterdir() if p.is_dir()):
            self._check_eval_case(case_dir)

    def _check_eval_case(self, case_dir: Path) -> None:
        case_yaml = case_dir / "case.yaml"
        prompt = case_dir / "prompt.md"
        graders_dir = case_dir / "graders"
        text = self._read(case_yaml)
        scaffold = None
        if text is not None:
            data, locs = self._load_yaml(case_yaml, text)
            if isinstance(data, dict):
                for key in ("schema_version", "name", "expected_outcome"):
                    if key not in data or data[key] in (None, ""):
                        self.add(
                            case_yaml,
                            self._loc(locs, key, default=1),
                            "missing %s" % key,
                        )
                name = data.get("name")
                if isinstance(name, str) and name != case_dir.name:
                    self.add(
                        case_yaml,
                        self._loc(locs, "name"),
                        "name %r must equal the folder name %r"
                        % (name, case_dir.name),
                    )
                context = data.get("context")
                if isinstance(context, dict):
                    scaffold = context.get("scaffold_script")
            elif data is not None:
                self.add(case_yaml, 1, "case.yaml must be a mapping")
        prompt_text = self._read(prompt)
        if prompt_text is not None:
            pdata, plocs, body, _ = self._load_frontmatter(prompt, prompt_text)
            if isinstance(pdata, dict):
                for key in ("tags", "max_turns", "timeout_seconds"):
                    if key not in pdata or pdata[key] in (None, ""):
                        self.add(
                            prompt,
                            self._loc(plocs, key, default=1),
                            "missing %s" % key,
                        )
        if not graders_dir.is_dir():
            self.add(graders_dir, 1, "missing graders directory")
        else:
            self._check_graders(graders_dir)
        script_name = scaffold if isinstance(scaffold, str) else None
        script_path = case_dir / script_name if script_name else case_dir / "place-files.sh"
        if script_name and not script_path.is_file():
            self.add(case_dir / script_name, 1, "missing file")
        elif script_path.is_file():
            self._check_place_files(script_path, case_dir / "files")

    def _check_graders(self, graders_dir: Path) -> None:
        files = sorted(p for p in graders_dir.iterdir() if p.is_file())
        if not files:
            self.add(graders_dir, 1, "no grader files")
            return
        numbers: List[int] = []
        for path in files:
            match = GRADER_NAME_RE.match(path.name)
            if not match:
                self.add(
                    path,
                    1,
                    "grader filename must be NN-slug.md with a leading number",
                )
                continue
            numbers.append(int(match.group(1), 10))
            self._check_grader_file(path)
        if not numbers:
            return
        expected = list(range(1, max(numbers) + 1))
        if sorted(numbers) != expected:
            found = ", ".join("%02d" % n for n in sorted(numbers))
            self.add(
                graders_dir,
                1,
                "grader numbers are not contiguous (found %s)" % found,
            )

    def _check_grader_file(self, path: Path) -> None:
        text = self._read(path)
        if text is None:
            return
        data, locs, body, _ = self._load_frontmatter(path, text)
        if not isinstance(data, dict):
            return
        for key in ("type", "focus", "weight"):
            if key not in data or data[key] in (None, ""):
                self.add(path, self._loc(locs, key, default=1), "missing %s" % key)
        if not body.strip():
            self.add(path, 1, "grader body is empty")

    def _check_place_files(self, script: Path, files_dir: Path) -> None:
        text = self._read(script)
        if text is None:
            return
        refs = []
        for match in FILES_REF_RE.finditer(text):
            rel_path = match.group(1)
            if rel_path.strip(". ") in ("", "."):
                continue
            refs.append((rel_path, text[: match.start()].count("\n") + 1))
        if refs and not files_dir.is_dir():
            self.add(files_dir, 1, "missing files/ directory")
            return
        for rel_path, line in refs:
            if ".." in Path(rel_path).parts:
                self.add(
                    script,
                    line,
                    "references %s, which escapes files/ — fix the reference, not the check" % rel_path,
                )
                continue
            target = files_dir / rel_path
            if not target.is_file():
                self.add(script, line, "references %s, which is not under files/" % rel_path)


def _normalize_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        raw = raw[1 : raw.index(">")]
    else:
        parts = raw.split()
        raw = parts[0] if parts else raw
        raw = raw.strip("'\"")
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    return raw


def _is_relative(url: str) -> bool:
    if not url or url.startswith("#") or url.startswith("//"):
        return False
    if SCHEME_RE.match(url):
        return False
    return True


def _json_key_line(path: Path, key: str) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 1
    match = re.search(r'^\s*"%s"\s*:' % re.escape(key), text, re.M)
    if not match:
        return 1
    return text[: match.start()].count("\n") + 1


def _png_size(path: Path) -> Optional[Tuple[int, int]]:
    """Width and height from a PNG's IHDR chunk, or None for other formats."""
    try:
        with path.open("rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def check_repo(root: Path) -> List[Problem]:
    return Checker(Path(root)).check()


def problems_to_json(problems: Sequence[Problem]) -> Dict[str, Any]:
    errors = sum(1 for p in problems if p.level == "error")
    warnings = sum(1 for p in problems if p.level == "warning")
    return {
        "ok": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "summary": summary_line(problems),
        "problems": [asdict(p) for p in problems],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check skill frontmatter, links, eval cases, and plugin manifests."
        )
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
    root = Path(args.root)
    if not root.exists():
        message = "%s:1: path does not exist" % args.root
        if args.as_json:
            json.dump(
                {
                    "ok": False,
                    "error_count": 1,
                    "warning_count": 0,
                    "summary": "1 error, 0 warnings",
                    "problems": [
                        {
                            "path": args.root,
                            "line": 1,
                            "level": "error",
                            "message": "path does not exist",
                        }
                    ],
                },
                sys.stdout,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(message + "\n1 error, 0 warnings\n")
        return 1
    problems = check_repo(root)
    if args.as_json:
        json.dump(problems_to_json(problems), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for problem in problems:
            sys.stdout.write(format_problem(problem) + "\n")
        sys.stdout.write(summary_line(problems) + "\n")
    return 1 if any(p.level == "error" for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
