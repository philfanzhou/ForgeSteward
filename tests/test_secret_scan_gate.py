"""The pre-publication secret scan is a stop gate, never a pass claim.

The execute-work and prepare-work packages install independently, so each rule
file carries its own gate: inspect the complete diff or evidence, run a
repository-defined secret-scan command when one exists, and stop publication on
a hit, a failed or unavailable command, or incomplete coverage. These checks
read rule text and scenario rows only; they run no scanner and contain no
secret values. Presence proves the rule exists, not that a model follows it.
"""

import ast
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
EXECUTE = REPO / "plugins/execute-work/skills/forge-steward-execute-work"
PREPARE = REPO / "plugins/prepare-work/skills/forge-steward-prepare-work"
SCENARIOS = REPO / "docs/skill-owned-policy-scenarios.md"
CHECK_WORKFLOW_SCENARIOS = REPO / "docs/check-workflow-scenarios.md"

GATES = {
    "execute-work": (
        EXECUTE / "references/implementation.md",
        "references/implementation.md",
        [
            "Before commit and push, inspect the complete diff or commit range for secrets",
            "When the repository defines a secret-scan command, run it and record the exact "
            "command, exit result, and coverage, including files or ranges not scanned",
            "On a hit, a failed or unavailable defined command, or coverage that does not "
            "include the complete diff or range",
            "stop the push, preserve the branch and local commits",
            "redact the value, report what was and was not scanned, and do not claim a pass",
            "If no command is defined, record that absence and the completed inspection",
            "do not claim an automated scan passed",
            "not authoritative over semantic acceptance and adds no dependency or credential",
        ],
    ),
    "prepare-work": (
        PREPARE / "references/handoff.md",
        "references/handoff.md",
        [
            "Before publishing experiment evidence or command output to an Issue or comment, "
            "inspect it for secrets",
            "When the repository defines a secret-scan command, run it and record the exact "
            "command, result, and coverage, including evidence not scanned",
            "On a hit, a failed or unavailable defined command, or coverage that does not "
            "include the complete evidence",
            "redact the value, report what was and was not scanned instead of publishing",
            "do not claim a pass",
            "If no command is defined, record that absence and the completed inspection",
            "do not claim an automated scan passed",
            "not authoritative over semantic acceptance and adds no dependency or credential",
        ],
    ),
}


def normalized(text):
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def read(path):
    return normalized(path.read_text(encoding="utf-8"))


def scenario_rows(path, wanted):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*([A-Z][0-9]{2})\s*\|", line)
        if not match or match.group(1) not in wanted:
            continue
        if match.group(1) in rows:
            raise AssertionError(f"duplicate scenario ID {match.group(1)} in {path}")
        rows[match.group(1)] = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return rows


class SecretScanGateTests(unittest.TestCase):
    def test_each_package_requires_the_reference_carrying_its_gate(self):
        for package, (_, relative, _) in GATES.items():
            entry = (REPO / "plugins" / package / "skills" / f"forge-steward-{package}" / "SKILL.md")
            with self.subTest(package=package):
                self.assertIn(f"]({relative})", entry.read_text(encoding="utf-8"))

    def test_both_rules_define_the_complete_inspection_and_failure_outcomes(self):
        for package, (path, _, phrases) in GATES.items():
            text = read(path)
            with self.subTest(package=package):
                self.assertTrue(path.is_file(), f"{path} is missing")
                for phrase in phrases:
                    self.assertIn(phrase, text, f"{path} is missing the secret-scan rule: {phrase}")

    def test_gate_precedes_the_publication_step(self):
        execute = read(GATES["execute-work"][0])
        prepare = read(GATES["prepare-work"][0])
        self.assertLess(
            execute.index("Pre-publication secret scan."),
            execute.index("commit/push this item's work branch"),
            "execute-work must scan before commit and push",
        )
        self.assertLess(
            prepare.index("Pre-publication secret scan."),
            prepare.index("Before switching tasks or compacting context"),
            "prepare-work must scan before publishing and switching tasks",
        )

    def test_no_command_absence_is_recorded_and_is_not_a_pass(self):
        for package, (path, _, _) in GATES.items():
            text = read(path)
            with self.subTest(package=package):
                self.assertIn("If no command is defined, record that absence and the completed inspection", text)
                self.assertIn("do not claim an automated scan passed", text)

    def test_scanner_is_not_authoritative_and_adds_no_dependency(self):
        for package, (path, _, _) in GATES.items():
            text = read(path)
            with self.subTest(package=package):
                self.assertIn("not authoritative over semantic acceptance", text)
                self.assertIn("adds no dependency or credential", text)

    def test_e17_stops_a_simulated_hit_and_records_recovery(self):
        rows = scenario_rows(SCENARIOS, {"E17"})
        self.assertIn("E17", rows)
        cells = [cell.lower() for cell in rows["E17"]]
        self.assertEqual(cells[0], "e17")
        self.assertEqual(cells[1], "execute-work")
        self.assertIn("simulated secret-scan hit", cells[2])
        self.assertIn("stop the push", cells[3])
        self.assertIn("preserve the branch and local commits", cells[3])
        self.assertIn("redact the value", cells[3])
        self.assertIn("record recovery", cells[3])
        self.assertIn("do not claim a pass", cells[3])

    def test_e18_treats_an_unavailable_scan_as_not_a_pass(self):
        rows = scenario_rows(SCENARIOS, {"E18"})
        self.assertIn("E18", rows)
        cells = [cell.lower() for cell in rows["E18"]]
        self.assertEqual(cells[0], "e18")
        self.assertEqual(cells[1], "execute-work")
        self.assertIn("cannot run or returns an error", cells[2])
        self.assertIn("stop the push", cells[3])
        self.assertIn("report coverage and recovery", cells[3])
        self.assertIn("unavailable scan is not a pass", cells[3])

    def test_collision_note_names_every_cross_document_label(self):
        text = read(SCENARIOS)
        self.assertIn("`E16`, `E17`, and `E18`", text)
        self.assertIn("docs/check-workflow-scenarios.md", text)
        self.assertIn("cross-document references must name the document", text)
        shared = scenario_rows(CHECK_WORKFLOW_SCENARIOS, {"E16", "E17", "E18"})
        self.assertEqual(sorted(shared), ["E16", "E17", "E18"])

    def test_checks_import_no_command_or_network_runner(self):
        """Static text checks cannot run a scanner or read a real secret."""
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
