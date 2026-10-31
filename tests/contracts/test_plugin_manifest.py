#!/usr/bin/env python3
"""Contract tests: the plugin manifests must agree with the folders on disk.

The checker (scripts/check-skill.py) gates name/version/marketplace naming but
does NOT cross-check .claude-plugin/plugin.json's skills[] list against the
skills/ tree; these tests pin that pairing in both directions.
Read-only on the real repo.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests._support import REPO_ROOT

ROOT_MANIFEST = REPO_ROOT / "plugin.json"
CLAUDE_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MARKET = REPO_ROOT / ".claude-plugin" / "marketplace.json"
AGENTS_MARKET = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
GROUNDED_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def skill_dirs() -> list:
    base = REPO_ROOT / "skills"
    return sorted(
        child.name
        for child in base.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    ) if base.is_dir() else []


class ManifestPairing(unittest.TestCase):
    def test_skills_list_matches_folders_both_directions(self):
        claude = _load(CLAUDE_MANIFEST)
        listed = sorted(
            entry.removeprefix("./skills/")
            for entry in claude.get("skills", [])
        )
        on_disk = skill_dirs()
        self.assertTrue(on_disk, "no skill folders with SKILL.md under skills/")
        self.assertEqual(listed, on_disk, "skills[] and skills/ folders have drifted")

    def test_root_and_claude_manifests_agree_on_name_version(self):
        root = _load(ROOT_MANIFEST)
        claude = _load(CLAUDE_MANIFEST)
        self.assertEqual(root.get("name"), claude.get("name"))
        self.assertEqual(root.get("version"), claude.get("version"))

    def test_marketplaces_name_the_plugin(self):
        name = _load(CLAUDE_MANIFEST).get("name")
        for market_path in (CLAUDE_MARKET, AGENTS_MARKET):
            market = _load(market_path)
            self.assertEqual(
                market.get("name"), name,
                "%s: name does not match plugin.json" % market_path,
            )
            for entry in market.get("plugins", []):
                self.assertEqual(
                    entry.get("name"), name,
                    "%s: plugins[] entry does not match plugin.json" % market_path,
                )

    def test_schema_pin(self):
        self.assertEqual(_load(ROOT_MANIFEST).get("$schema"), GROUNDED_SCHEMA)


if __name__ == "__main__":
    unittest.main()