"""Dangling-reference cleanup keeps content referenced outside candidate locations.

The entry, procedure, retention rule, and walkthroughs must agree that only
candidate-location referrers are cleaned up, while external referrers are kept
and reported. These static checks prove the rules say so; they do not prove that
an Agent model follows them.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
ENTRY = SKILL / "SKILL.md"
PROCEDURE = SKILL / "references/procedure.md"
CATALOG = SKILL / "references/skill-owned-rules.md"
SCENARIOS = REPO / "docs/check-workflow-scenarios.md"
OLD_ENTRY_SENTENCE = (
    "delete documents containing only workflow policy, together with links, contents entries, "
    "and reading instructions pointing to deleted documents or sections"
)
OLD_PROCEDURE_SENTENCE = (
    "Leave no links, contents entries, or reading instructions to removed documents/sections, "
    "heading-only empty sections, or broken numbered lists."
)
EXTERNAL_RULE = (
    "Content has references outside candidate locations, such as README, a code comment, or a script. "
    "If the referrer itself is a candidate, remove its reference too."
)


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


def scenario_row(text, scenario_id):
    rows = [line for line in text.splitlines() if line.startswith("| " + scenario_id + " |")]
    if len(rows) != 1:
        raise AssertionError(scenario_id + " must identify exactly one walkthrough")
    return rows[0].lower()


class DanglingReferenceRuleTests(unittest.TestCase):
    def test_entry_limits_reference_deletion_to_candidate_locations(self):
        text = normalized(ENTRY)
        self.assertNotIn(OLD_ENTRY_SENTENCE, text)
        for phrase in (
            "Delete dangling references:",
            "delete policy-only content",
            "links, contents entries, and reading instructions to it from candidate locations",
            "retain and report externally referenced content",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_procedure_limits_reference_cleanup_to_candidate_locations(self):
        text = normalized(PROCEDURE)
        self.assertNotIn(OLD_PROCEDURE_SENTENCE, text)
        for phrase in (
            "candidate-location links, contents entries, or reading instructions",
            "removed documents/sections, heading-only empty sections, or broken numbered lists",
            "retain and report externally referenced content",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_catalog_keeps_the_single_external_reference_rule(self):
        text = normalized(CATALOG)
        self.assertIn(EXTERNAL_RULE, text)
        self.assertIn("Retain these for maintainer decision", text)
        self.assertEqual(text.count("references outside candidate locations"), 1)
        self.assertEqual(text.count("remove its reference too"), 1)

    def test_entry_procedure_and_catalog_agree_on_the_referrer_limit(self):
        entry = normalized(ENTRY)
        procedure = normalized(PROCEDURE)
        catalog = normalized(CATALOG)
        self.assertIn("from candidate locations", entry)
        self.assertIn("retain and report externally referenced content", entry)
        self.assertIn("candidate-location", procedure)
        self.assertIn("retain and report externally referenced content", procedure)
        self.assertIn("outside candidate locations", catalog)
        self.assertIn("If the referrer itself is a candidate, remove its reference too.", catalog)
        self.assertNotIn("Leave no links, contents entries, or reading instructions", procedure)

    def test_scenarios_cover_external_and_candidate_referrers(self):
        text = SCENARIOS.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        self.assertIn("J09\u2013J20 are manual walkthroughs", text)
        self.assertNotIn("J09\u2013J19 are manual walkthroughs", text)

        j15 = scenario_row(text, "J15")
        for phrase in (
            "readme",
            "code comment",
            "script",
            "preserve",
            "report",
            "maintainer decision",
            "do not delete",
        ):
            with self.subTest(scenario="J15", phrase=phrase):
                self.assertIn(phrase, j15)

        j20 = scenario_row(text, "J20")
        for phrase in (
            "candidate section",
            "delete the link",
            "contents entry",
            "reading instruction",
            "not an external reference",
        ):
            with self.subTest(scenario="J20", phrase=phrase):
                self.assertIn(phrase, j20)


if __name__ == "__main__":
    unittest.main()
