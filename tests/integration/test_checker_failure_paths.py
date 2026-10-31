#!/usr/bin/env python3
"""Failure-path tests for the checkers: mutate a COPY of the repo, never the
real one, and prove each hardened guard fires. Each test copies the repo with
shutil.copytree; a sha256 snapshot of the real gate files self-reports in
tearDown if any test mutated the real repo.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._support import REPO_ROOT

GUARDED = (
    "lints/clippy.toml",
    "lints/lints.toml",
    ".github/workflows/check.yml",
    ".claude-plugin/plugin.json",
    "scripts/examples.json",
    "plugin.json",
)
COPY_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".ruff_cache", "dist", "target"
)
SUBPROCESS_TIMEOUT = 300
HAS_CARGO = shutil.which("cargo") is not None
_CLIPPY_OK = None


def has_clippy():
    """Probe once for a working clippy component (not just a cargo shim)."""
    global _CLIPPY_OK
    if _CLIPPY_OK is None:
        if shutil.which("cargo") is None:
            _CLIPPY_OK = False
        else:
            probe = subprocess.run(
                ["cargo", "clippy", "--version"], capture_output=True, text=True,
            )
            _CLIPPY_OK = probe.returncode == 0
    return _CLIPPY_OK


def run_checker(argv, root_arg=None):
    """Run a python checker with python3 -I; return (returncode, combined output)."""
    args = ["python3", "-I"] + list(argv)
    if root_arg is not None:
        args.append(str(root_arg))
    proc = subprocess.run(
        args, cwd=str(REPO_ROOT), capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    return proc.returncode, proc.stdout + proc.stderr


def run_bash(argv):
    """Run a repo shell script (its ROOT comes from its own path)."""
    proc = subprocess.run(
        list(argv), cwd=str(REPO_ROOT), capture_output=True, text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    return proc.returncode, proc.stdout + proc.stderr


class GuardedRepoCase(unittest.TestCase):
    """Snapshot the real gate files; copy the repo for mutation."""

    def setUp(self):
        self._snapshot = {rel: _sha256(REPO_ROOT / rel) for rel in GUARDED}
        self.addCleanup(self._verify_real_repo_untouched)
        self.tmp = Path(tempfile.mkdtemp(prefix="brfailpath."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = self.tmp / "repo"
        shutil.copytree(REPO_ROOT, self.copy, ignore=COPY_IGNORE)
        self.assertFalse((self.copy / ".git").exists(), "copy must not carry .git")

    def _verify_real_repo_untouched(self):
        mutated = [
            rel for rel, digest in self._snapshot.items()
            if not (REPO_ROOT / rel).is_file() or _sha256(REPO_ROOT / rel) != digest
        ]
        self.assertEqual(
            mutated, [],
            "TEST BUG: the real repo's gate files were mutated: %s" % mutated,
        )


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BrokenRustBlock(GuardedRepoCase):
    """A broken ```rust block in a bare doc tree fails check-examples."""

    @unittest.skipUnless(HAS_CARGO, "cargo is not installed")
    def test_broken_rust_block_fails_check_examples(self):
        md = self.tmp / "README.md"
        md.write_text(
            "# Demo\n\n```rust\nfn f() -> i32 {\n    let = ;\n}\n```\n",
            encoding="utf-8",
        )
        rc, out = run_checker(["scripts/check-examples.py"], root_arg=self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("README.md", out)


class CopiedRepoFailures(GuardedRepoCase):
    """Failure paths that mutate a full copy of the repo."""

    def test_malformed_harness_list_is_reported_not_crashed(self):
        harness = self.copy / "scripts" / "examples.json"
        harness.write_text('{"files": ["oops"]}', encoding="utf-8")
        rc, out = run_checker(["scripts/check-examples.py"], root_arg=self.copy)
        self.assertEqual(rc, 1)
        self.assertIn("files must be a JSON object", out)

    def test_place_files_escape_is_rejected(self):
        script = sorted(self.copy.glob("skills/*/evals/*/place-files.sh"))[0]
        with script.open("a", encoding="utf-8") as fh:
            fh.write("\ncp files/../../outside.py .\n")
        rc, out = run_checker(["scripts/check-skill.py"], root_arg=self.copy)
        self.assertEqual(rc, 1)
        self.assertIn("escapes files/", out)

    def test_interface_bogus_key_rejected(self):
        manifest = self.copy / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["extensions"]["com.openai"]["interface"]["bogusInterfaceKey"] = "x"
        manifest.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        rc, out = run_checker(["scripts/check-skill.py"], root_arg=self.copy)
        self.assertEqual(rc, 1)
        self.assertIn("is not in the schema", out)

    @unittest.skipUnless(HAS_CARGO, "cargo is not installed")
    def test_nested_reference_compiled(self):
        sub = self.copy / "skills" / "rust-port" / "references" / "sub"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "broken.md").write_text(
            "# Nested reference\n\n```rust\nfn f() -> i32 {\n    let = ;\n}\n```\n",
            encoding="utf-8",
        )
        rc, out = run_checker(["scripts/check-examples.py"], root_arg=self.copy)
        self.assertEqual(rc, 1)
        self.assertIn("skills/rust-port/references/sub/broken.md", out)


class DeletedLints(GuardedRepoCase):
    """Text surgery on a copy's lints: removing a piece of the drop-in lints
    unit must fail the lints gate (byte-identity replica plus the real bash
    checker for one case)."""

    def _remove_warn_line(self, lint_name):
        path = self.copy / "lints" / "lints.toml"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [
            line for line in lines
            if not line.strip().startswith('%s = "warn"' % lint_name)
        ]
        assert len(kept) < len(lines), "could not remove %s from lints/lints.toml" % lint_name
        path.write_text("".join(kept), encoding="utf-8")

    def test_table_drift_in_check_crate_fails_replica(self):
        manifest = self.copy / "lints" / "check" / "Cargo.toml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace('unsafe_op_in_unsafe_fn = "warn"', 'unsafe_op_in_unsafe_fn = "allow"'),
            encoding="utf-8",
        )
        table = (self.copy / "lints" / "lints.toml").read_text(encoding="utf-8")
        self.assertNotIn(table, manifest.read_text(encoding="utf-8"),
                         "the mutation must break byte-identity for the replica to trip")

    @unittest.skipUnless(HAS_CARGO, "cargo is not installed")
    @unittest.skipUnless(has_clippy(), "clippy is not available")
    def test_deleted_warn_lint_fails_check_lints(self):
        self._remove_warn_line("missing_docs")
        rc, out = run_bash(["bash", str(self.copy / "scripts" / "check-lints.sh")])
        self.assertEqual(rc, 1)
        self.assertIn("missing_docs", out)

    @unittest.skipUnless(HAS_CARGO, "cargo is not installed")
    @unittest.skipUnless(has_clippy(), "clippy is not available")
    def test_deleted_clippy_config_fails_check_lints(self):
        (self.copy / "lints" / "clippy.toml").unlink()
        rc, out = run_bash(["bash", str(self.copy / "scripts" / "check-lints.sh")])
        self.assertEqual(rc, 1)
        self.assertIn("fn_params_excessive_bools", out)


if __name__ == "__main__":
    unittest.main()
