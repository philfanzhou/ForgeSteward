"""Guard identical CI instructions and recorded walkthroughs, not hosted CI behavior."""

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
SCENARIOS = REPO / "docs/ci-failure-scenarios.md"
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


    def test_original_numeric_policy_is_unchanged(self):
        shared = next(iter(CI_FILES)).read_text(encoding="utf-8")
        wait_section = shared.split("### Wait limit\n\n", 1)[1].split("\n### ", 1)[0]
        self.assertEqual(wait_section, """Use one limit for all required checks of the current Change Request:

- Recent runs are the last 10 successful completed runs of that required check on the default mainline that finished within 90 days.
- Use twice the median completed duration of the recent runs. If no run qualifies, use 30 minutes.
- Cap the limit for each required check at 60 minutes, then use the largest capped limit across all required checks.
- A rerun shares the original limit and does not start a new one. One long historical run cannot raise the limit past the cap.
""")

    def test_phase_diagnosis_never_waives_covering_verification(self):
        shared = next(iter(CI_FILES)).read_text(encoding="utf-8")
        for requirement in (
            "phase: queue, setup, network, build, test or final verification",
            "Unknown cause remains unknown",
            "Cancellation is incomplete verification",
            "a setup error caused by changed code/configuration still follows repair",
            "claim an external cause only with proof",
            "Later covering verification unverified",
            "Container startup unverified",
            "no overall pass or unrelated claim",
            "A proven setup failure never makes a required covering job unrelated",
            "neither cover the change nor depend on changed code",
            "Deterministic in-scope code failures follow repair",
            "without an authorized retry retain Waiting for CI",
            "never takes a second retry",
            "never copy secrets or full logs",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, shared)

    def test_check_handoff_survives_new_heads_and_stages(self):
        shared = next(iter(CI_FILES)).read_text(encoding="utf-8")
        for requirement in (
            "original wait start and absolute deadline",
            "current head, required-check set",
            "retry count and original/rerun links",
            "phase evidence, unfinished verification, recovery action and its owner",
            "implementation, review, repair and merge-lane inspection",
            "switching stages, pushing a new head, rerunning, or doing independent work cannot reset them",
            "older green results do not cover a new head",
            "reconstruct it from run timestamps/history",
            "do not invent a fresh budget or unused retry",
            "without starting another wait or retry",
            "Completed green current-head checks may satisfy verification",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, shared)
        for skill, files in LINKING_RULES.items():
            for name in files:
                with self.subTest(caller=f"{skill}/{name}"):
                    caller = (REPO / "plugins" / skill / name).read_text(encoding="utf-8")
                    self.assertIn("phase diagnosis", caller)
                    self.assertIn("check handoff", caller)
                    self.assertIn("Waiting for CI", caller)
        lane = (REPO / "plugins" / SKILLS[2] / "references/merge-lane.md").read_text(encoding="utf-8")
        self.assertIn("Before queue-result inspection, restore/save", lane)
        self.assertIn("including the new head, original deadline and retry history", lane)

    def test_recorded_walkthrough_covers_each_outcome(self):
        scenarios = SCENARIOS.read_text(encoding="utf-8")
        rows = {}
        for line in scenarios.splitlines():
            if line.startswith("| "):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) == 4:
                    rows[cells[0]] = cells[1:]
        expected_results = {
            "success": "Verified",
            "setup": "Later container verification unverified",
            "setup-code": "Failed; later verification unverified",
            "code": "Failed",
            "final-cancelled": "Container startup unverified",
            "ambiguous": "Unknown cause; named portions unverified",
            "retry-pass": "Passed",
            "retry-fail": "Unfinished",
            "expired-handoff": "Container verification unverified",
            "new-head": "Current-head verification unverified",
            "missing-record": "Verification/budget evidence missing",
            "expired-green": "Verified",
        }
        for case, result in expected_results.items():
            with self.subTest(case=case):
                self.assertIn(case, rows)
                self.assertEqual(rows[case][1], result)
                self.assertTrue(rows[case][0])
                self.assertTrue(rows[case][2])
        self.assertIn("No second retry", rows["retry-fail"][2])
        self.assertIn("Start no new wait/retry", rows["expired-handoff"][2])
        self.assertIn("`10:00Z` start, `10:20Z` deadline", rows["new-head"][2])
        self.assertIn("This covering job is not eligible", rows["setup"][2])
        self.assertIn("Credentials, private payloads and complete logs stay out", scenarios)
        self.assertIn("do not invent independent retry allowances", scenarios)


if __name__ == "__main__":
    unittest.main()
