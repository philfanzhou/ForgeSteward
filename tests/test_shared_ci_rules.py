"""The three stage skills carry byte-identical references/ci.md copies linked from their stage rules."""

from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILLS = (
    "execute-work/skills/forge-steward-execute-work",
    "fix-feedback/skills/forge-steward-fix-feedback",
    "review-and-merge/skills/forge-steward-review-and-merge",
)
LINKING_RULES = {
    SKILLS[0]: ("references/implementation.md",),
    SKILLS[1]: ("references/repair.md",),
    SKILLS[2]: ("references/review.md", "references/merge-lane.md"),
}
LINK = "](ci.md)"


class SharedCiRulesTests(unittest.TestCase):
    def test_ci_rules_are_byte_identical(self):
        copies = {skill: (REPO / "plugins" / skill / "references" / "ci.md").read_bytes() for skill in SKILLS}
        first = copies[SKILLS[0]]
        for skill, content in copies.items():
            with self.subTest(skill=skill):
                self.assertEqual(content, first, f"{skill}/references/ci.md differs from the {SKILLS[0]} copy")

    def test_stage_rules_link_to_ci_rules(self):
        for skill, files in LINKING_RULES.items():
            for name in files:
                with self.subTest(file=f"{skill}/{name}"):
                    text = (REPO / "plugins" / skill / name).read_text(encoding="utf-8")
                    self.assertIn(LINK, text)


if __name__ == "__main__":
    unittest.main()
