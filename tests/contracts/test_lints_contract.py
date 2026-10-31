#!/usr/bin/env python3
"""Contract tests: the drop-in lints ship as a three-file unit that must stay
paired — lints/lints.toml (the [lints] table agents paste), lints/clippy.toml
(the clippy config clippy reads next to it), and lints/check/src/lib.rs (the
violation harness whose // expect: markers prove the table fires).
Read-only on the real repo.
"""

from __future__ import annotations

import re
import shutil
import tomllib
import unittest
from pathlib import Path

from tests._support import REPO_ROOT

TABLE = REPO_ROOT / "lints" / "lints.toml"
CLIPPY_CONFIG = REPO_ROOT / "lints" / "clippy.toml"
CRATE = REPO_ROOT / "lints" / "check"
MANIFEST = CRATE / "Cargo.toml"
LIB = CRATE / "src" / "lib.rs"
MARKER_RE = re.compile(r"// expect:\s*(\S+)")
# Group lints (see the "Groups first" comment in the table) fire per member,
# not as a lint of their own — they take no // expect: marker in the harness.
GROUPS = frozenset({"all", "pedantic"})


def marker_names() -> set:
    text = LIB.read_text(encoding="utf-8")
    names = set()
    for line in text.splitlines():
        for token in MARKER_RE.findall(line):
            names.add(token.removeprefix("clippy::"))
    return names


def warn_lints() -> set:
    data = tomllib.loads(TABLE.read_text(encoding="utf-8"))
    names = set()
    for section in (data["lints"]["rust"], data["lints"]["clippy"]):
        for name, value in section.items():
            level = value.get("level", value) if isinstance(value, dict) else value
            if level == "warn":
                names.add(name)
    return names - GROUPS


class TablePairing(unittest.TestCase):
    def test_table_is_byte_identical_in_the_check_crate(self):
        table = TABLE.read_text(encoding="utf-8")
        manifest = MANIFEST.read_text(encoding="utf-8")
        self.assertIn(
            "must stay byte-identical to lints/lints.toml", manifest,
            "the check crate must declare the byte-identity contract",
        )
        self.assertIn(table, manifest,
                      "lints/lints.toml is not byte-identical in lints/check/Cargo.toml")

    def test_harness_covers_every_warn_lint(self):
        self.assertTrue(marker_names(), "no // expect: markers in lints/check/src/lib.rs")
        self.assertTrue(warn_lints(), "no warn lints in lints/lints.toml")
        missing = warn_lints() - marker_names()
        self.assertEqual(missing, set(),
                         "warn lints without a // expect: marker: %s" % sorted(missing))

    def test_markers_reference_selected_lints(self):
        unknown = marker_names() - warn_lints()
        self.assertEqual(unknown, set(),
                         "// expect: markers without a warn entry in lints/lints.toml: %s"
                         % sorted(unknown))


class ClippyConfigPairing(unittest.TestCase):
    def test_clippy_toml_parses_nonempty(self):
        data = tomllib.loads(CLIPPY_CONFIG.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertTrue(data, "lints/clippy.toml should carry at least one setting")

    def test_threshold_config_pairs_with_its_lint(self):
        config = tomllib.loads(CLIPPY_CONFIG.read_text(encoding="utf-8"))
        self.assertIn("max-fn-params-bools", config)
        self.assertIn("fn_params_excessive_bools", warn_lints())

    def test_test_allowances_pair_with_their_lints(self):
        config = tomllib.loads(CLIPPY_CONFIG.read_text(encoding="utf-8"))
        for key in (
            "allow-unwrap-in-tests",
            "allow-expect-in-tests",
            "allow-print-in-tests",
        ):
            self.assertIn(key, config)
        self.assertIn("unwrap_used", warn_lints())
        self.assertIn("print_stdout", warn_lints())
        self.assertIn("print_stderr", warn_lints())


if __name__ == "__main__":
    unittest.main()