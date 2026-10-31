#!/usr/bin/env python3
"""Contract tests: .github/workflows/check.yml — every CI job and pin must stay
on disk, plus the unittest gate job. Read-only on the real repo.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests._support import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "check.yml"


def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


class CheckerSteps(unittest.TestCase):
    """Every existing CI job keeps its exact entrypoint and pin."""

    def test_check_skill_step_present(self):
        self.assertIn("python3 scripts/check-skill.py", workflow_text())

    def test_clippy_toolchain_pin_present(self):
        self.assertIn("uses: dtolnay/rust-toolchain@stable", workflow_text())
        self.assertIn("components: clippy", workflow_text())

    def test_check_lints_step_present(self):
        self.assertIn("bash scripts/check-lints.sh", workflow_text())

    def test_check_examples_step_present(self):
        self.assertIn("python3 scripts/check-examples.py", workflow_text())

    def test_jobs_present(self):
        text = workflow_text()
        for job in ("  check:", "  lints:", "  examples:"):
            self.assertIn(job, text)


class TestsJob(unittest.TestCase):
    """The unittest gate: the full discovery is the CI job itself."""

    def test_tests_job_present(self):
        self.assertIn("  tests:", workflow_text())

    def test_tests_job_discovers_the_whole_suite(self):
        self.assertIn("unittest discover", workflow_text())
        self.assertIn("-s tests -t .", workflow_text())


if __name__ == "__main__":
    unittest.main()