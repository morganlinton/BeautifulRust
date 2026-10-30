#!/usr/bin/env python3
"""Tests for scripts/package-openai-plugin.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "package-openai-plugin.py"


def load_packager():
    spec = importlib.util.spec_from_file_location("package_openai_plugin", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s" % SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packager = load_packager()

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

    def test_package_icon_paths_resolve(self):
        manifest = json.loads((REPO_ROOT / "plugin.json").read_text(encoding="utf-8"))
        interface = manifest["extensions"]["com.openai"]["interface"]
        with tempfile.TemporaryDirectory() as tmp:
            _, names = self.build(tmp)
        for key in ("composerIcon", "logo"):
            self.assertIn(interface[key].removeprefix("./"), names)

    def test_package_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = self.build(tmp)
            first_bytes = first.read_bytes()
            second, _ = self.build(tmp)
            self.assertEqual(first_bytes, second.read_bytes())


if __name__ == "__main__":
    unittest.main()
