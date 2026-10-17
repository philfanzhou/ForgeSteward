"""Check-workflow translates documentation and reports every result honestly.

These static checks prove the procedure, English reference, reporting, and
walkthroughs state the translation, preservation, retention, link, and
honest-reporting rules; they do not prove that an Agent model follows them or
that a translation is correct.
"""

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


def scenario_row(text, scenario_id):
    rows = [line for line in text.splitlines() if line.startswith("| " + scenario_id + " |")]
    if len(rows) != 1:
        raise AssertionError(scenario_id + " must identify exactly one walkthrough")
    return rows[0].lower()


class DocumentationTranslationRuleTests(unittest.TestCase):
    def test_reference_defines_the_default_translation_operation(self):
        text = normalized(REFERENCE)
        for phrase in (
            "## Documentation translation",
            "Translate the project's README and project-maintained documentation",
            "same cleanup branch and Change Request",
            "after policy deletion",
            "The default delivery flow authorizes this operation",
            "check-only, review-only, and audit-only runs write no translated file",
            "local-only stops at the verified local diff",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reference_preserves_technical_and_historical_content(self):
        text = normalized(REFERENCE)
        for phrase in (
            "Preserve code blocks, inline code, commands, paths, link destinations, identifiers, logs, technical data, code comments, and quoted external text",
            "Do not translate historical Issues, Change Requests, comments, releases, release notes, or other people's content",
            "Do not restructure, reorder, summarize, or rewrite already-English prose",
            "an unrelated rewrite is outside the diff gate",
            "A file with no non-English prose stays byte-unchanged",
            "If a retained rule requires specific documentation to stay non-English, leave those files unchanged and report them as unresolved",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reference_retains_large_or_failed_work_and_verifies_links(self):
        text = normalized(REFERENCE)
        for phrase in (
            "translate only complete sections whose result you can verify",
            "retain the remaining bytes unchanged",
            "report the exact boundary and recovery input",
            "Never truncate a document or present a partial translation as complete",
            "permission failure and recovery input",
            "verify every relative link and heading fragment",
            "On a link regression, stop translating the affected document, restore its original content, and report the regression",
            "Report each file, its translated sections, every replaced passage, and unchanged content",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_procedure_plans_applies_and_admits_translation(self):
        text = normalized(PROCEDURE)
        for phrase in (
            "plan its rule and translation against the post-language result",
            "no safe migration, language, rule, or translation work remains",
            "rule and translation.",
            "section, its translation, and separable documentation or collaboration rule replacements",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reporting_requires_per_file_and_honest_results(self):
        text = normalized(REPORTING)
        for phrase in (
            "language operations, and translations separately",
            "**Translation:** for each translated file",
            "quote the exact before/after text and source lines for every replaced passage",
            "translated sections, unchanged technical content, unresolved text, permission failures, skipped content, and recovery inputs",
            "A file is translated only when all its prose is English",
            "cleanup Change Request body",
            "never claim full-English coverage while unresolved prose remains",
            "Claim only verified policy removals, entry migrations, language operations, and translations",
            "deletion, migration, translation or language work would change",
            "cleanup deletions, migrations, translations, and language changes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_scenarios_cover_translation_preservation_retention_and_failure(self):
        text = SCENARIOS.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        expected = {
            "T01": ("readme", "same cleanup branch", "preserve", "verify relative links", "report"),
            "T02": ("byte-identical", "quoted", "link destinations", "unchanged technical"),
            "T03": ("retain the remaining bytes unchanged", "boundary", "recovery input", "never truncate"),
            "T04": ("retain the mixed rule unchanged", "maintainer decision", "unresolved", "full-english"),
            "T05": ("permission", "link regression", "stopping point", "recovery input", "never call the result complete"),
            "T06": ("historical", "byte-unchanged", "other person's content", "unresolved text"),
        }
        for scenario_id, phrases in expected.items():
            row = scenario_row(text, scenario_id)
            with self.subTest(scenario=scenario_id):
                for phrase in phrases:
                    self.assertIn(phrase.lower(), row)


if __name__ == "__main__":
    unittest.main()
