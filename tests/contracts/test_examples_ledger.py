#!/usr/bin/env python3
"""Contract tests: scripts/examples.json is the ledger of deliberately skipped
example blocks. Skips must carry a reason and point at real files, and the
ledger must agree with what scripts/check-examples.py actually skips.
Read-only on the real repo; mutation lives in tests/integration/.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from tests._support import REPO_ROOT, load_script

LEDGER = REPO_ROOT / "scripts" / "examples.json"
HAS_CARGO = shutil.which("cargo") is not None


def ledger_data() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def ledger_paths(data: dict) -> dict:
    """path -> the file entry, only for entries that are objects."""
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def ledger_skip_count(data: dict) -> int:
    """Count of block specs that ledger a skip (the checker must match it)."""
    count = 0
    for entry in ledger_paths(data).values():
        if not isinstance(entry, dict):
            continue
        blocks = entry.get("blocks")
        if not isinstance(blocks, dict):
            continue
        for spec in blocks.values():
            if isinstance(spec, dict) and "skip" in spec:
                count += 1
    return count


class LedgerShape(unittest.TestCase):
    def test_is_json_object_with_files_mapping(self):
        data = ledger_data()
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data.get("files"), dict)

    def test_every_ledgered_path_exists_on_disk(self):
        for path, entry in ledger_paths(ledger_data()).items():
            self.assertIsInstance(entry, dict, "%s: entry must be an object" % path)
            target = REPO_ROOT / path
            self.assertTrue(target.is_file(), "ledgered path %s does not exist" % path)

    def test_every_skip_has_a_nonempty_reason(self):
        for path, entry in ledger_paths(ledger_data()).items():
            blocks = entry.get("blocks")
            if not isinstance(blocks, dict):
                continue
            for key, spec in blocks.items():
                if not isinstance(spec, dict) or "skip" not in spec:
                    continue
                reason = str(spec.get("skip") or "").strip()
                self.assertTrue(
                    reason,
                    "%s block %s: skip is ledgered without a reason" % (path, key),
                )


class LedgerAgrees(unittest.TestCase):
    """The checker's skipped count must equal the ledger's skip count."""

    @unittest.skipUnless(HAS_CARGO, "cargo is not installed")
    def test_checker_skipped_count_equals_ledger(self):
        mod = load_script("check-examples.py")
        self.assertTrue(callable(getattr(mod, "check_repo", None)))
        _, checked, skipped = mod.check_repo(REPO_ROOT)
        self.assertEqual(
            skipped,
            ledger_skip_count(ledger_data()),
            "check-examples skipped %d blocks but the ledger accounts for %d"
            % (skipped, ledger_skip_count(ledger_data())),
        )
        self.assertIsInstance(checked, int)
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()