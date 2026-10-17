"""Check-workflow carries the English working-environment rule and keeps no-write limits.

These static checks prove the entry and its reference say so; they do not prove
that an Agent model follows the rules or translates content correctly.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
ENTRY = SKILL / "SKILL.md"
REFERENCE = SKILL / "references/english-conversion.md"
PROCEDURE = SKILL / "references/procedure.md"
CATALOG = SKILL / "references/skill-owned-rules.md"
SCENARIOS = REPO / "docs/check-workflow-scenarios.md"


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


def utf16_units(text):
    return len(text.encode("utf-16-le")) // 2


def description(text):
    lines = text.replace("\r\n", "\n").splitlines()
    return next(line[len("description:"):].strip() for line in lines if line.startswith("description:"))


class EnglishWorkingEnvironmentRuleTests(unittest.TestCase):
    def test_entry_requires_the_reference_before_acting(self):
        text = normalized(ENTRY)
        self.assertIn("Before checking, read", text)
        self.assertIn("[English working environment](references/english-conversion.md)", text)
        self.assertIn("in full, then follow the authorized mode", text)

    def test_entry_authorizes_the_conversion(self):
        text = normalized(ENTRY)
        for phrase in (
            "also authorizes converting project documentation and About to English",
            "adding the rule for future project content",
            "No mode rewrites history, releases, or other people's content",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_entry_keeps_every_no_write_mode_explicit(self):
        text = normalized(ENTRY)
        for phrase in (
            "check-only means report candidates without editing or creating a branch",
            "local-only means no commit or push",
            "review-only and audit-only mean no project changes",
            "release-audit-only means only the read-only audit and report, with no project changes or delivery",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_entry_limits_settings_to_the_about_exception(self):
        text = normalized(ENTRY)
        self.assertIn("do not change repository settings other than About", text)

    def test_description_stays_within_budget_and_names_the_purpose_and_modes(self):
        text = ENTRY.read_text(encoding="utf-8")
        desc = description(text)
        self.assertLessEqual(utf16_units(desc), 500)
        for phrase in (
            "convert project documentation and About to English by default",
            "Check-only, local-only, review-only, and audit-only runs remain read-only",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, desc)

    def test_reference_states_the_working_environment_rule(self):
        text = normalized(REFERENCE)
        for phrase in (
            "## English working environment",
            "project-maintained documentation (README and docs)",
            "Issue and Change Request titles and bodies",
            "future commit messages",
            "Preserve historical Issues, Change Requests, and comments",
            "Do not translate code, commands, paths, identifiers, logs, technical data, or quoted external text",
            "replace its heading and prose",
            "leaving no duplicate section",
            "retain it unchanged and report the conflict",
            "Preserve unrelated conventions",
            "About is the only repository setting this flow may change",
            "Do not rewrite historical Issues, Change Requests, comments, releases, release notes",
            "Check-only, review-only and audit-only write no project files",
            "local-only stops at the local diff",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_procedure_plans_applies_and_admits_the_rule(self):
        text = normalized(PROCEDURE)
        for phrase in (
            "read [English working environment](english-conversion.md) and plan its rule",
            "followed by the planned [language operation](collaboration-language.md) and [English working environment](english-conversion.md) rule",
            "the fixed [English working environment](english-conversion.md) section and separable documentation or collaboration rule replacements it defines",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_catalog_moves_documentation_and_commit_languages_to_the_rule(self):
        text = normalized(CATALOG)
        self.assertIn("Code-comment languages, title and branch formats", text)
        self.assertIn(
            "Documentation, Issue/Change Request text, and future commit messages follow the [English working environment](english-conversion.md)",
            text,
        )

    def test_scenarios_cover_replacement_retention_and_each_no_write_mode(self):
        text = SCENARIOS.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        expected = {
            "W01": ("replace that section", "duplicate", "source lines"),
            "W02": ("replace only", "preserve", "before/after"),
            "W03": ("retain the mixed rule unchanged", "maintainer decision", "competing"),
            "W04": ("write nothing", "duplicate"),
            "W05": ("check-only", "unchanged", "no branch"),
            "W06": ("local-only", "no commit", "stopping point"),
            "W07": ("review-only", "no project bytes", "Change Request"),
            "W08": ("audit-only", "read-only", "No project files were changed"),
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
