"""Static checks for the fix-feedback merge, round-3 push, and force-push boundaries.

Reported contradictions were: references/repair.md told fix-feedback to merge "when
all conditions pass" while SKILL.md said it must never merge; step 5 forbade pushes at
three rounds while also allowing a mainline sync, which needs a push; and "use merge
when force-push is forbidden" implied that a force push was otherwise allowed. These
checks fail if that wording, or an instruction with the same effect, returns.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "plugins/fix-feedback/skills/forge-steward-fix-feedback"
SCENARIOS = REPO / "docs/skill-owned-policy-scenarios.md"
MERGE_LANE = (REPO / "plugins/review-and-merge/skills/forge-steward-review-and-merge"
              / "references/merge-lane.md")
FORBIDDEN_MERGE_WORDING = (
    "merge when all conditions pass",
    "merge if all conditions pass",
    "then merge",
    "use merge when force-push",
)


def normalized(text):
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip().lower()


def read(path):
    return normalized(path.read_text(encoding="utf-8"))


class FixFeedbackMergeAndRoundBoundaryTests(unittest.TestCase):
    def test_fix_feedback_never_tells_itself_to_merge_a_change_request(self):
        files = sorted(PACKAGE.rglob("*.md"))
        self.assertTrue(files, "the fix-feedback package must contain Markdown rules")
        for path in files:
            text = read(path)
            for phrase in FORBIDDEN_MERGE_WORDING:
                with self.subTest(file=path.relative_to(REPO).as_posix(), phrase=phrase):
                    self.assertNotIn(
                        phrase,
                        text,
                        path.relative_to(REPO).as_posix() + " again permits merging a Change Request",
                    )

    def test_fix_feedback_states_it_must_never_merge(self):
        self.assertIn("must never merge", read(PACKAGE / "SKILL.md"))

    def test_round_is_one_changes_requesting_state_then_one_author_push(self):
        skill = read(PACKAGE / "SKILL.md")
        self.assertIn("several comments or reviews before one push count once", skill)
        self.assertIn("a mainline-only sync does not count", skill)

    def test_third_round_allows_only_a_conflict_free_mainline_sync_push(self):
        skill = read(PACKAGE / "SKILL.md")
        repair = read(PACKAGE / "references/repair.md")
        for name, text in (("SKILL.md", skill), ("references/repair.md", repair)):
            with self.subTest(file=name):
                self.assertIn("conflict-free mainline sync", text)

    def test_third_round_hands_the_unreviewed_head_to_review_and_merge(self):
        repair = read(PACKAGE / "references/repair.md")
        sentences = re.split(r"(?<=[.!?])\s+", repair)
        third_round = [sentence for sentence in sentences if "third-round push" in sentence]
        self.assertTrue(third_round, "repair.md must describe the third-round push")
        for sentence in third_round:
            with self.subTest(sentence=sentence[:80]):
                self.assertIn("review-and-merge", sentence)
                self.assertIn("never merge", sentence)

    def test_force_push_needs_explicit_authorization_and_a_fresh_review(self):
        repair = read(PACKAGE / "references/repair.md")
        self.assertIn("do not force-push by default", repair)
        self.assertIn("explicit user or repository authorization", repair)
        self.assertIn("record the old and new heads", repair)
        self.assertIn("fresh review from the new head", repair)
        self.assertIn("never force-push", read(MERGE_LANE))

    def test_x02_separates_an_unreviewed_head_from_a_reviewed_head_with_remaining_feedback(self):
        rows = [line for line in SCENARIOS.read_text(encoding="utf-8").splitlines()
                if line.startswith("| X02 |")]
        self.assertEqual(len(rows), 1, "the scenarios matrix must contain exactly one X02 row")
        row = normalized(rows[0])
        self.assertIn("not yet finally reviewed", row)
        self.assertIn("finally reviewed with required in-scope feedback remaining", row)
        self.assertIn("conflict-free mainline sync", row)
        self.assertIn("review-and-merge", row)
        self.assertIn("human action", row)


if __name__ == "__main__":
    unittest.main()
