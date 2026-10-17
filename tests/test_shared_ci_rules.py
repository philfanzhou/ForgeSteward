"""The three stage skills carry one byte-identical, single-source CI wait rule and link to it."""

from pathlib import Path
import re
import subprocess
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
CI_FILES = {REPO / "plugins" / skill / "references" / "ci.md" for skill in SKILLS}
# Numeric facts that define the one bounded CI wait limit; every stage copy must carry them.
WAIT_LIMIT_FACTS = (
    "last 10 successful completed runs",
    "within 90 days",
    "twice the median completed duration",
    "If no run qualifies, use 30 minutes",
    "at 60 minutes",
    "largest capped limit across all required checks",
    "A rerun shares the original limit",
    "cannot raise the limit past the cap",
)
# Phrases that identify a duplicated numeric wait-limit rule. Historical release
# notes are excluded because published history is not rewritten.
LIMIT_PHRASES = re.compile(
    r"twice the (?:longest|slowest|median)|without history|last \d+ successful"
    r"|\b90 days\b|\b60 minutes\b"
)
# A numeric wait duration in a stage rule is also a copy of the limit, wherever it sits.
WAIT_MINUTES = re.compile(r"\bwait(?:s|ing)?\b[^.\n]{0,80}\b\d+\s*minutes\b", re.IGNORECASE)


def markdown_files():
    """Current repository Markdown, excluding published release history."""
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO,
    )
    names = [name for name in output.decode().split("\0")
             if name.endswith(".md") and not name.startswith("docs/releases/")]
    return sorted(REPO / name for name in names)


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

    def test_numeric_wait_limit_appears_only_in_ci_rules(self):
        shared = (REPO / "plugins" / SKILLS[0] / "references" / "ci.md").read_text(encoding="utf-8")
        for fact in WAIT_LIMIT_FACTS:
            with self.subTest(fact=fact):
                self.assertIn(fact, shared)
        for path in markdown_files():
            if path in CI_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            where = path.relative_to(REPO).as_posix()
            for phrase in LIMIT_PHRASES.finditer(text):
                with self.subTest(file=where, phrase=phrase.group(0)):
                    self.fail(f"{where}: numeric CI wait limit is duplicated outside ci.md")
            if path.is_relative_to(REPO / "plugins"):
                for statement in WAIT_MINUTES.finditer(text):
                    with self.subTest(file=where, phrase=statement.group(0)):
                        self.fail(f"{where}: CI wait duration belongs only in ci.md")


if __name__ == "__main__":
    unittest.main()
