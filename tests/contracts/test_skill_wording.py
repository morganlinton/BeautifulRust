#!/usr/bin/env python3
"""Contract tests: SKILL.md wording guarantees (the unbreakable-clause pins).

Read-only pins: if one of these red-fails, someone edited away the unbreakable
contract language or the cross-skill reference — a regression, not style.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "skills"
BP = ROOT / "rust-best-practices" / "SKILL.md"
RV = ROOT / "rust-review" / "SKILL.md"


def bp_body() -> str:
    return BP.read_text(encoding="utf-8")


def rv_body() -> str:
    return RV.read_text(encoding="utf-8")


class BestPractices(unittest.TestCase):
    def test_unbreakable_clause_present(self):
        body = bp_body()
        self.assertIn(
            "The contracts below are **unbreakable and non-waivable**", body
        )
        self.assertIn("never to weaken or delete the lints", body)
        self.assertIn("re-cut the layout", body)

    def test_silencing_prohibition(self):
        body = bp_body()
        self.assertIn("never to silence it with `#[allow]`", body)
        # Grounded on this repo's lints: suppression must be explained and
        # narrow — the file routes silencing through expect-with-reason.
        self.assertIn("`#[expect(", body)

    def test_points_at_review_as_the_critic(self):
        body = bp_body()
        self.assertIn(
            "Review treats a broken contract as an automatic Must fix", body
        )
        self.assertIn("`rust-review`", body)


class ReviewSkill(unittest.TestCase):
    def test_architecture_category_ranks_first_as_must_fix(self):
        body = rv_body()
        self.assertIn(
            "Architecture contracts (always Must fix, ranked first)", body
        )
        self.assertIn(
            "a broken architecture contract (ranked above everything)", body
        )

    def test_waiver_detection_clause(self):
        body = rv_body()
        self.assertIn("Waived gates:", body)
        self.assertIn("flag the deletion itself, loudly", body)


if __name__ == "__main__":
    unittest.main()