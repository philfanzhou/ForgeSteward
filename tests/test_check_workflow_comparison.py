"""A standalone check-workflow compares against its catalog and reports skill gaps.

The policy catalog is the authoritative comparison source when the owning skill's
text is not installed. These static checks prove the rules say so; they do not
prove that an Agent model follows them.
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
    "When comparing another skill's equivalent rules, also inspect the rule files linked from its entry."
)


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


class StandaloneComparisonRuleTests(unittest.TestCase):
    def test_entry_no_longer_requires_rule_files_from_an_unbundled_entry(self):
        text = normalized(ENTRY)
        self.assertNotIn(OLD_ENTRY_SENTENCE, text)
        self.assertIn("[Check, migrate, and submit](references/procedure.md)", text)

    def test_procedure_uses_the_catalog_and_records_unverifiable_equivalence(self):
        text = normalized(PROCEDURE)
        for phrase in (
            "reference's policy catalog",
            "authoritative comparison source for a standalone install",
            "not installed or readable",
            "unverifiable equivalence",
            "retain its clause",
            "do not report it as equivalent or clean",
            "rule files linked from its entry",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_catalog_is_authoritative_for_a_standalone_install(self):
        self.assertIn(
            "This catalog is the authoritative comparison source for a standalone install",
            normalized(CATALOG),
        )

    def test_scenarios_record_the_standalone_gap_and_version_stops(self):
        text = SCENARIOS.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        expected = {
            "N01": ("skill gap", "retain", "not report it as equivalent or clean"),
            "N02": ("installed", "rule files linked from its entry"),
            "N03": ("0.2.24", "exit", "first write", "changes no project file"),
            "N04": ("exit", "0", "writes no project file"),
        }
        for scenario_id, phrases in expected.items():
            rows = [line for line in text.splitlines() if line.startswith("| " + scenario_id + " |")]
            with self.subTest(scenario=scenario_id):
                self.assertEqual(len(rows), 1, scenario_id + " must identify exactly one walkthrough")
                lower = rows[0].lower()
                for phrase in phrases:
                    self.assertIn(phrase.lower(), lower)


if __name__ == "__main__":
    unittest.main()
