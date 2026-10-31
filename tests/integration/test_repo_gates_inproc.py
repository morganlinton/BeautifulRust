#!/usr/bin/env python3
"""Tests for scripts/package-openai-plugin.py, run against the real repo
in-process (the zip build is read-only; heavy CLI mirrors live in tests/e2e)."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tests._support import REPO_ROOT, load_script


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packager = load_script("package-openai-plugin.py")

    def build(self, tmp):
        out = Path(tmp) / "plugin.zip"
        self.packager.build(REPO_ROOT, out)
        with zipfile.ZipFile(out) as archive:
            return out, archive.namelist()

    def test_package_holds_manifest_skills_and_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, names = self.build(tmp)
        self.assertIn("plugin.json", names)
        self.assertIn("assets/icon.png", names)
        for skill in sorted((REPO_ROOT / "skills").iterdir()):
            if (skill / "SKILL.md").is_file():
                self.assertIn("skills/%s/SKILL.md" % skill.name, names)

    def test_package_leaves_out_evals(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, names = self.build(tmp)
        self.assertFalse([n for n in names if "/evals/" in n], names)

    def test_package_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = self.build(tmp)
            first_bytes = first.read_bytes()
            second, _ = self.build(tmp)
            self.assertEqual(first_bytes, second.read_bytes())


if __name__ == "__main__":
    unittest.main()
