#!/usr/bin/env python3
"""Tests for scripts/check-skill.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check-skill.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_skill", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s" % SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


VALID_SKILL = """\
---
name: demo-skill
description: >-
  A short skill used as a fixture. Checks Rust-like notes when the user
  asks for help writing robust library code.
---

# Demo skill

See `references/guide.md` for the long form.
"""

VALID_GUIDE = "# Guide\n\nDetails live here.\n"

VALID_README = """\
# Demo

See [the changelog](CHANGELOG.md) and [the license](LICENSE).
"""

VALID_CHANGELOG = """\
# Changelog

## [Unreleased]

- Fixture notes.

## [1.0.0] - 2026-01-01

- First cut.

[Unreleased]: https://github.com/example/demo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/example/demo/releases/tag/v1.0.0
"""

VALID_PLUGIN = """\
{
  "name": "demo",
  "version": "1.0.0"
}
"""

VALID_MARKETPLACE = """\
{
  "name": "demo",
  "plugins": [
    {
      "name": "demo",
      "source": "./"
    }
  ]
}
"""

VALID_CASE = """\
schema_version: "1.1"
name: sample-case
expected_outcome: |
  The program compiles and returns a result instead of panicking.
"""

VALID_PROMPT = """\
---
tags: [demo-skill]
max_turns: 10
timeout_seconds: 60
---

Write a small library.
"""

VALID_GRADER = """\
---
type: llm
focus: trace
weight: 1
---

The crate builds and the tests pass.
"""


VALID_PORTABLE = {
    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "name": "demo",
    "version": "1.0.0",
    "extensions": {
        "com.openai": {
            "interface": {
                "displayName": "Demo",
                "shortDescription": "A demo plugin",
                "longDescription": "Skills used as a fixture.",
                "developerName": "Example",
                "category": "Developer Tools",
                "capabilities": ["Check notes"],
                "supportURL": "https://example.com/support",
                "defaultPrompt": ["Check my notes"],
                "composerIcon": "./assets/icon.png",
                "logo": "./assets/icon.png",
            }
        }
    },
}


def png_header(width, height):
    """The first 24 bytes of a PNG, which is all the checker reads."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def add_portable_plugin(root, manifest=None, icon=(64, 64)):
    root = Path(root)
    write(root / "plugin.json", json.dumps(manifest or VALID_PORTABLE, indent=2))
    icon_path = root / "assets" / "icon.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.write_bytes(png_header(*icon))
    return root


def portable_with(**interface):
    manifest = json.loads(json.dumps(VALID_PORTABLE))
    manifest["extensions"]["com.openai"]["interface"].update(interface)
    return manifest


def build_valid_repo(root):
    root = Path(root)
    write(root / "README.md", VALID_README)
    write(root / "LICENSE", "MIT\n")
    write(root / "CHANGELOG.md", VALID_CHANGELOG)
    write(root / ".claude-plugin" / "plugin.json", VALID_PLUGIN)
    write(root / ".claude-plugin" / "marketplace.json", VALID_MARKETPLACE)
    skill = root / "skills" / "demo-skill"
    write(skill / "SKILL.md", VALID_SKILL)
    write(skill / "references" / "guide.md", VALID_GUIDE)
    case = skill / "evals" / "sample-case"
    write(case / "case.yaml", VALID_CASE)
    write(case / "prompt.md", VALID_PROMPT)
    write(case / "graders" / "01-builds.md", VALID_GRADER)
    return root


def messages(problems):
    return [p.message for p in problems]


def error_messages(problems):
    return [p.message for p in problems if p.level == "error"]


def formatted(checker, problems):
    return [checker.format_problem(p) for p in problems]


class CheckSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = load_checker()

    def run_root(self, root):
        return self.checker.check_repo(Path(root))

    def assert_has_error(self, problems, snippet):
        blob = "\n".join(error_messages(problems))
        self.assertTrue(
            any(snippet in m for m in error_messages(problems)),
            "expected error containing %r, got:\n%s" % (snippet, blob),
        )

    def test_valid_fixture_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            problems = self.run_root(root)
            errors = [p for p in problems if p.level == "error"]
            self.assertEqual(errors, [], formatted(self.checker, problems))

    def test_bad_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            skill_md = root / "skills" / "demo-skill" / "SKILL.md"
            write(skill_md, VALID_SKILL.replace("name: demo-skill", "name: Demo_Skill"))
            problems = self.run_root(root)
            self.assert_has_error(problems, "name")
            joined = "\n".join(formatted(self.checker, problems))
            self.assertIn("SKILL.md:", joined)

    def test_name_must_match_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            skill_md = root / "skills" / "demo-skill" / "SKILL.md"
            write(skill_md, VALID_SKILL.replace("name: demo-skill", "name: other-skill"))
            problems = self.run_root(root)
            self.assert_has_error(problems, "other-skill")
            self.assert_has_error(problems, "demo-skill")

    def test_long_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            long_desc = "x" * 1025
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                "---\nname: demo-skill\ndescription: %s\n---\n\nSee `references/guide.md`.\n"
                % long_desc,
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "1024")

    def test_unknown_frontmatter_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                "---\nname: demo-skill\ndescription: A fixture skill for checks.\n"
                "authors: someone\n---\n\nSee `references/guide.md`.\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "authors")

    def test_broken_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "README.md",
                VALID_README + "\nRead [missing](docs/NOPE.md).\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "docs/NOPE.md")

    def test_broken_references_mention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                VALID_SKILL.replace(
                    "`references/guide.md`",
                    "`references/guide.md` and `references/missing.md`",
                ),
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "references/missing.md")

    def test_markdown_link_covers_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                "---\nname: demo-skill\ndescription: A fixture skill for checks.\n"
                "---\n\nSee [the guide](references/guide.md).\n",
            )
            problems = self.run_root(root)
            errors = [p for p in problems if p.level == "error"]
            self.assertEqual(errors, [], formatted(self.checker, problems))

    def test_orphan_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "references" / "orphan.md",
                "# leftover\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "orphan.md")

    def test_gap_in_grader_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            graders = root / "skills" / "demo-skill" / "evals" / "sample-case" / "graders"
            write(graders / "03-extra.md", VALID_GRADER)
            problems = self.run_root(root)
            self.assert_has_error(problems, "contiguous")

    def test_missing_frontmatter_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "evals" / "sample-case" / "prompt.md",
                "---\ntags: [demo-skill]\nmax_turns: 10\n---\n\nWrite a small library.\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "timeout_seconds")

    def test_missing_skill_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                "---\nname: demo-skill\n---\n\nSee `references/guide.md`.\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "description")

    def test_missing_grader_frontmatter_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "evals" / "sample-case" / "graders" / "01-builds.md",
                "---\ntype: llm\nweight: 1\n---\n\nThe crate builds.\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "focus")

    def test_empty_grader_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "evals" / "sample-case" / "graders" / "01-builds.md",
                "---\ntype: llm\nfocus: trace\nweight: 1\n---\n\n\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "empty")

    def test_case_name_must_match_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "evals" / "sample-case" / "case.yaml",
                VALID_CASE.replace("name: sample-case", "name: other-case"),
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "other-case")

    def test_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / ".claude-plugin" / "plugin.json",
                '{\n  "name": "demo",\n  "version": "9.9.9"\n}\n',
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "9.9.9")

    def test_plugin_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / ".claude-plugin" / "marketplace.json",
                '{\n  "name": "other",\n  "plugins": [{"name": "other", "source": "./"}]\n}\n',
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "name")

    def test_invalid_semver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / ".claude-plugin" / "plugin.json",
                '{\n  "name": "demo",\n  "version": "1.0"\n}\n',
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "semver")

    def test_valid_portable_plugin_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = add_portable_plugin(build_valid_repo(tmp))
            problems = self.run_root(root)
            errors = [p for p in problems if p.level == "error"]
            self.assertEqual(errors, [], formatted(self.checker, problems))

    def test_portable_version_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = json.loads(json.dumps(VALID_PORTABLE))
            manifest["version"] = "1.1.0"
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "1.1.0")

    def test_portable_unknown_top_level_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = json.loads(json.dumps(VALID_PORTABLE))
            manifest["hooks"] = "./hooks.json"
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "'hooks' is not in the schema")

    def test_portable_display_name_too_long(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = portable_with(displayName="A display name over thirty chars")
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "interface.displayName")

    def test_portable_http_url_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = portable_with(supportURL="http://example.com/support")
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "HTTPS")

    def test_portable_too_many_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = portable_with(defaultPrompt=["a", "b", "c", "d"])
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "defaultPrompt")

    def test_portable_missing_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = portable_with(logo="./assets/logo.png")
            root = add_portable_plugin(build_valid_repo(tmp), manifest)
            problems = self.run_root(root)
            self.assert_has_error(problems, "./assets/logo.png not found")

    def test_portable_icon_must_be_square(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = add_portable_plugin(build_valid_repo(tmp), icon=(64, 32))
            problems = self.run_root(root)
            self.assert_has_error(problems, "64x32")

    def test_place_files_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            case = root / "skills" / "demo-skill" / "evals" / "sample-case"
            write(case / "files" / "input.rs", "fn main() {}\n")
            write(
                case / "place-files.sh",
                "#!/usr/bin/env bash\ncp files/missing.rs .\n",
            )
            write(
                case / "case.yaml",
                "schema_version: \"1.1\"\nname: sample-case\n"
                "context:\n  scaffold_script: place-files.sh\n"
                "expected_outcome: |\n  ok\n",
            )
            problems = self.run_root(root)
            self.assert_has_error(problems, "missing.rs")

    def test_place_files_existing_target_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            case = root / "skills" / "demo-skill" / "evals" / "sample-case"
            write(case / "files" / "input.rs", "fn main() {}\n")
            write(
                case / "place-files.sh",
                "#!/usr/bin/env bash\nset -eu\n"
                'cp "$(dirname "$0")/files/input.rs" .\n',
            )
            write(
                case / "case.yaml",
                "schema_version: \"1.1\"\nname: sample-case\n"
                "context:\n  scaffold_script: place-files.sh\n"
                "expected_outcome: |\n  ok\n",
            )
            problems = self.run_root(root)
            errors = [p for p in problems if p.level == "error"]
            self.assertEqual(errors, [], formatted(self.checker, problems))

    def test_long_skill_body_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            body = "\n".join("line %d" % i for i in range(501))
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                "---\nname: demo-skill\ndescription: A fixture skill for checks.\n"
                "---\n\nSee `references/guide.md`.\n\n%s\n" % body,
            )
            problems = self.run_root(root)
            warnings = [p for p in problems if p.level == "warning"]
            errors = [p for p in problems if p.level == "error"]
            self.assertEqual(errors, [])
            self.assertTrue(any("500" in p.message for p in warnings))

    def test_output_format_and_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_valid_repo(tmp)
            write(
                root / "skills" / "demo-skill" / "SKILL.md",
                VALID_SKILL.replace("name: demo-skill", "name: BadName"),
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2)
            self.assertRegex(lines[0], r"^.+:\d+: ")
            self.assertRegex(lines[-1], r"\d+ error")
            js = subprocess.run(
                [sys.executable, str(SCRIPT), "--json", str(root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(js.returncode, 1)
            payload = json.loads(js.stdout)
            self.assertFalse(payload["ok"])
            self.assertGreaterEqual(payload["error_count"], 1)
            self.assertIn("problems", payload)
            self.assertEqual(payload["problems"][0]["path"].count("\\"), 0)

    def test_real_repo_passes(self):
        problems = self.run_root(REPO_ROOT)
        errors = [p for p in problems if p.level == "error"]
        self.assertEqual(errors, [], formatted(self.checker, problems))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(REPO_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout.strip().splitlines()[-1], r"0 errors")

    def test_real_repo_json_ok(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["error_count"], 0)

    def test_cli_help(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--json", proc.stdout)


if __name__ == "__main__":
    unittest.main()
