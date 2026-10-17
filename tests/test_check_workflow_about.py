"""Check-workflow updates the repository About through read/write/read-back evidence.

These static checks prove the English reference, procedure, reporting, and
walkthroughs state the about read, write, read-back, failure, and single-setting
rules; they do not query or change a real repository About, and they do not prove
that an Agent model follows the rules.
"""

import ast
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
REFERENCE = SKILL / "references/english-conversion.md"
PROCEDURE = SKILL / "references/procedure.md"
REPORTING = SKILL / "references/reporting.md"
SCENARIOS = REPO / "docs/check-workflow-scenarios.md"


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


def about_section():
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index("## Repository About")
    end = text.index("## Limits and reporting", start)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def scenario_row(text, scenario_id):
    rows = [line for line in text.splitlines() if line.startswith("| " + scenario_id + " |")]
    if len(rows) != 1:
        raise AssertionError(scenario_id + " must identify exactly one walkthrough")
    return rows[0].lower()


class RepositoryAboutRuleTests(unittest.TestCase):
    def test_reference_defines_read_write_read_back_with_exact_evidence(self):
        text = normalized(REFERENCE)
        for phrase in (
            "## Repository About",
            "Apply this in default delivery mode after the working-environment rule and [Documentation translation](#documentation-translation)",
            "Read the current value and record its exact text, the read result, and the observation time",
            "write a faithful English translation of the current value, preserving product names, identifiers, and links",
            "then read the value back",
            "Record the exact before and after values, the query and write results, the read-back result, and the observation time",
            "Claim success only when the read-back equals the intended English description",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reference_reports_already_english_and_empty_values_without_a_write(self):
        text = normalized(REFERENCE)
        for phrase in (
            "If the value is already English, write nothing and report it as unchanged with that reason",
            "If the description is empty or absent, report that and write nothing",
            "there is no existing text to translate",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reference_handles_permission_unsupported_and_ambiguous_results(self):
        text = normalized(REFERENCE)
        for phrase in (
            "If the platform does not expose a writable About description, the value cannot be read, or permission is missing, retain the old value and report the exact blocker and the input needed to recover",
            "do not write blindly",
            "If the write result is ambiguous, read the value back before claiming anything",
            "A read-back matching the intended description is verified success",
            "one matching the old value means the write did not apply",
            "any other or unreadable result leaves the outcome unverified",
            "Restore the recorded old value when possible, and report the ambiguity, retained value, and recovery input without claiming success",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reference_keeps_no_write_modes_and_the_single_setting_boundary(self):
        text = normalized(REFERENCE)
        for phrase in (
            "Check-only, local-only, review-only, audit-only, and release-audit-only runs make no About write",
            "About is the only repository setting this flow may change",
            "About is external metadata, not a tracked file",
            "it never creates a branch, commit, or Change Request by itself",
            "it is applied even when no repository file needs a change",
            "Report an unchanged About with the reason",
            "Change no other repository setting, including visibility, topics, merge settings, or branch protection",
            "Never claim a successful About write without an exact read-back",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_about_rules_are_platform_neutral_and_add_no_configuration(self):
        text = about_section()
        for forbidden in ("GitHub", "GitLab", "Gitea", "gh api", "gh repo", "curl", "client configuration"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), text.lower())

    def test_procedure_plans_applies_and_finishes_about_work(self):
        text = normalized(PROCEDURE)
        for phrase in (
            "plan its rule, translation and About work against the post-language result",
            "no safe migration, language or English file work remains",
            "apply the planned About operation and report it; finish without a branch, commit, or Change Request",
            "rule, translation and About operation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reporting_requires_exact_about_evidence_and_honest_results(self):
        text = normalized(REPORTING)
        for phrase in (
            "**About:** report the exact before and after values, the read and write results, the observation time, and whether the read-back verified the change",
            "Report an unchanged About with the reason, and any missing permission, unsupported platform, ambiguous write, retained old value, or recovery input",
            "An About change is external metadata, not a project file",
            "never create a branch, commit, or Change Request only for About",
            "never claim a successful write without the read-back",
            "When no project file changed, explicitly say “No project files were changed” and report the About result",
            "and About writes verified by read-back",
            "plus the About result and verification, in the cleanup Change Request body",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_scenarios_cover_success_noop_and_each_failure(self):
        text = SCENARIOS.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        self.assertIn("## Repository About (#185)", text)
        self.assertIn("Every A01–A05 outcome changes no repository setting other than About", text)
        expected = {
            "A01": ("non-english", "faithful english translation", "read the value back",
                    "exact before/after values", "observation time", "claim success only when"),
            "A02": ("already english", "write nothing", "unchanged", "observation time"),
            "A03": ("permission", "retain the old value", "blocker", "recovery", "no success"),
            "A04": ("does not expose a writable about", "recorded absence", "unsupported capability", "recovery"),
            "A05": ("ambiguous", "read the value back before claiming", "did not apply",
                    "retained value", "without claiming success"),
        }
        for scenario_id, phrases in expected.items():
            row = scenario_row(text, scenario_id)
            with self.subTest(scenario=scenario_id):
                for phrase in phrases:
                    self.assertIn(phrase.lower(), row)

    def test_checks_do_not_query_or_change_real_repository_metadata(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertLessEqual(modules, {"ast", "pathlib", "re", "unittest"})


if __name__ == "__main__":
    unittest.main()
