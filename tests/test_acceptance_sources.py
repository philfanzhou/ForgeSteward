"""Static guards for acceptance authority and recorded manual walkthrough outputs.

The rules are prose, not a runtime blocker evaluator. These checks detect loss
of source, suggestion, correction and recovery requirements; the scenario table
records the separately performed manual application to Issue #212's model.
"""

import importlib.util
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
RULES = REPO / "plugins/prepare-work/skills/forge-steward-prepare-work/references"
SCENARIOS = REPO / "docs/prepare-execute-scenarios.md"
SPEC = importlib.util.spec_from_file_location("acceptance_skill_limits", REPO / "scripts/check_skill_limits.py")
LIMITS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIMITS)


def text(name):
    return (RULES / name).read_text(encoding="utf-8")


def normalized(value):
    return re.sub(r"\s+", " ", value)


def walkthroughs():
    """Read recorded outputs, without simulating or inventing decision rules."""
    rows = {}
    for line in SCENARIOS.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| P(?:5[4-9]|6[01]) \|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] in rows:
                raise AssertionError("duplicate acceptance-source scenario " + cells[0])
            rows[cells[0]] = cells[1:]
    return rows


class AcceptanceSourceRuleTests(unittest.TestCase):
    def test_blocking_criteria_require_all_four_kinds_of_exact_source(self):
        readiness = text("readiness.md").split("### Acceptance sources\n", 1)[1]
        for phrase in ("For each blocking acceptance criterion", "exact source",
                       "explicit user decision", "original Issue criterion (quote or link)",
                       "applicable repository policy (path and section)",
                       "demonstrated technical prerequisite (reproducible evidence)",
                       "violated invariant", "smallest necessary condition",
                       "speculation is not evidence", "Preserve settled user decisions"):
            with self.subTest(requirement=phrase):
                self.assertIn(phrase, readiness)

    def test_suggestions_cannot_add_acceptance_work_questions_or_blockers(self):
        readiness = normalized(text("readiness.md"))
        for phrase in ("separately labeled as suggestions", "cannot become acceptance criteria",
                       "block required work", "force extra work", "clarification questions",
                       "blocker-release conditions", "does not imply old-version rollback support",
                       "mandatory applicable compatibility/rollback policy"):
            with self.subTest(requirement=phrase):
                self.assertIn(phrase, readiness)
        self.assertIn("require compatibility/rollback outcomes", readiness)
        self.assertIn("does not itself require old-version rollback", readiness)

    def test_blocker_records_source_gap_owner_and_genuine_conflict(self):
        blockers = normalized(text("blockers.md"))
        for phrase in ("Before declaring a blocker", "its exact source",
                       "missing evidence or prerequisite", "attempted paths",
                       "violated invariant and smallest necessary condition",
                       "responsible decision owner", "release evidence",
                       "name both sources and the decision needed",
                       "do not silently add scope or weaken repository policy"):
            with self.subTest(requirement=phrase):
                self.assertIn(phrase, blockers)
        self.assertIn("](readiness.md#acceptance-sources)", blockers)

    def test_correction_retains_valid_evidence_and_review_counts(self):
        correction = normalized(text("blockers.md").split("### Correct a scope mistake\n", 1)[1])
        handoff = normalized(text("handoff.md"))
        for phrase in ("original Issue's single current handoff", "audits, commits, check results, and review counts",
                       "Refresh only facts affected", "do not duplicate Issues/Change Requests",
                       "reset review counts", "unresolved conflicts between actual authorities",
                       "does not waive an applicable mandatory policy"):
            with self.subTest(requirement=phrase):
                self.assertIn(phrase, correction)
        for phrase in ("each blocking criterion's exact source and evidence",
                       "optional suggestions kept separate", "retaining history and still-valid audits",
                       "refresh only changed facts", "Respect recorded Issue ownership",
                       "switching tasks or compacting context", "Preserve the same record on an explicit stop",
                       "acceptance sources, evidence locations, and next actions"):
            with self.subTest(handoff=phrase):
                self.assertIn(phrase, handoff)
        self.assertIn("](handoff.md)", correction)
        self.assertIn("](readiness.md#acceptance-sources)", handoff)

    def test_edited_references_keep_existing_crlf_budget(self):
        for name in ("readiness.md", "blockers.md", "handoff.md"):
            raw = (RULES / name).read_bytes().replace(b"\r\n", b"\n")
            with self.subTest(reference=name):
                self.assertLessEqual(len(raw) + raw.count(b"\n"), LIMITS.REFERENCE_BYTES)


class AcceptanceSourceWalkthroughTests(unittest.TestCase):
    def test_every_model_outcome_has_a_complete_recorded_walkthrough(self):
        rows = walkthroughs()
        self.assertEqual(set(rows), {"P" + str(n) for n in range(54, 62)})
        for scenario, cells in rows.items():
            with self.subTest(scenario=scenario):
                self.assertEqual(len(cells), 3)
                self.assertTrue(all(cells))
                self.assertTrue(cells[-1].endswith("Passed"))
        document = SCENARIOS.read_text(encoding="utf-8")
        self.assertIn("not a second executable state model", document)
        self.assertIn("they do not evaluate arbitrary Agent behavior", document)

    def test_recorded_source_classification_and_release_evidence_are_explicit(self):
        rows = walkthroughs()
        assertions = {
            "P54": ("User decision U1", "No authoritative source", "optional suggestion", "Continue A"),
            "P55": ("Repository policy", "missing rollback verification", "A remains blocked"),
            "P56": ("Original Issue criterion", "Violated invariant", "Demonstrated technical prerequisite",
                    "E1's command/result", "smallest necessary conversion condition"),
            "P57": ("no user decision", "unproven", "A remains ready"),
            "P59": ("Current user decision U3", "Genuine conflict", "Decision owner",
                    "release evidence", "Continue independent B"),
        }
        for scenario, phrases in assertions.items():
            for phrase in phrases:
                with self.subTest(scenario=scenario, evidence=phrase):
                    self.assertIn(phrase, " ".join(rows[scenario]))

    def test_recorded_correction_stop_and_ownership_preserve_valid_work(self):
        rows = walkthroughs()
        for phrase in ("Owner O replaces", "retains H/C/K/Q and review count 2",
                       "No duplicate Issue/PR, new audit/check", "Refresh only evidence actually affected"):
            self.assertIn(phrase, " ".join(rows["P58"]))
        for phrase in ("cancellation supplies no release evidence", "save frozen A/B",
                       "valid H/C/K/Q, review count 2", "do not label A ready or reset counts"):
            self.assertIn(phrase, " ".join(rows["P60"]))
        for phrase in ("O alone updates", "continues its independent work", "No competing handoff"):
            self.assertIn(phrase, " ".join(rows["P61"]))


if __name__ == "__main__":
    unittest.main()
