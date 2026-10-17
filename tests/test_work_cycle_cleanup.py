"""Static checks for the final work-cycle cleanup stage and its durable audit.

These checks verify rule wording and that report data with a cleanup summary still
renders. They do not prove that a cleanup subagent ran or inspected real resources.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle"
ENTRY = SKILL / "SKILL.md"
CYCLES = SKILL / "references/cycles.md"
REPORT_DATA = SKILL / "references/report-data.md"
BRANCH_CLEANUP = (REPO / "plugins/review-and-merge/skills/forge-steward-review-and-merge"
                  / "references/branch-cleanup.md")
README = REPO / "README.md"
SCENARIOS = REPO / "docs/work-cycle-scenarios.md"
SCRIPT = SKILL / "scripts/run_record.py"
EMPTY_HANDOFF = REPO / "tests/fixtures/run_report/empty.json"


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip().lower()


def numbered_steps(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return {int(match.group(1)): match.group(2) for match in
            re.finditer(r"^(\d+)\. (.+)$", text, re.MULTILINE)}


class CleanupRuleWordingTests(unittest.TestCase):
    def test_entry_has_cleanup_as_the_final_stage_before_the_report(self):
        steps = numbered_steps(ENTRY)
        self.assertEqual(sorted(steps), [1, 2, 3, 4, 5])
        cleanup = re.sub(r"\s+", " ", steps[4]).lower()
        report = re.sub(r"\s+", " ", steps[5]).lower()
        for phrase in ("after all stages end", "cleanup-only", "`review-and-merge` subagent",
                       "[cycles](references/cycles.md)", "`cleanup` event", "`branch_cleanup`",
                       "audit", "explicit-stop skip"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, cleanup)
        self.assertIn("final report", report)
        text = ENTRY.read_text(encoding="utf-8")
        self.assertLess(text.index("\n4. "), text.index("\n5. "))

    def test_entry_stays_within_the_windows_crlf_byte_budget(self):
        raw = ENTRY.read_bytes()
        # Windows CI checks out with CRLF, adding one byte per line. Check the larger
        # of the actual checkout and that simulated worst case.
        simulated = len(raw) if b"\r\n" in raw else len(raw) + raw.count(b"\n")
        self.assertLessEqual(simulated, 6000,
                             "work-cycle SKILL.md exceeds 6000 bytes on a CRLF checkout")
        self.assertLessEqual(len(raw), 6000)

    def test_cycles_dispatches_one_cleanup_pass_and_records_its_audit(self):
        text = normalized(CYCLES)
        for phrase in ("dispatch one review-and-merge subagent solely for leftover cleanup",
                       "run-directory path",
                       "retained branches and workspaces",
                       "wait for its result",
                       "records the `cleanup` stage event",
                       "reads the run directory's `cleanup.md` audit",
                       "sets `branch_cleanup` from it",
                       "never claim a completed cleanup",
                       "explicit user stop",
                       "cleanup was skipped"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_branch_cleanup_requires_a_single_complete_audit_file(self):
        text = normalized(BRANCH_CLEANUP)
        for phrase in ("write `cleanup.md` there once",
                       "only this cleanup stage writes the file",
                       "no tracked files change",
                       "do not claim the file exists",
                       "every remote branch, local branch, and worktree checked",
                       "deleted, with the deletion-time commit",
                       "retained or listed only, with the reason",
                       "failed, with the error",
                       "unqueried, with the failed query or permission gap",
                       "deferred branches under the 50-branch limit",
                       "must agree with this file"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_report_data_defines_the_summary_as_agreeing_with_the_audit(self):
        row = next(line for line in REPORT_DATA.read_text(encoding="utf-8").splitlines()
                   if line.startswith("| `branch_cleanup`"))
        text = re.sub(r"\s+", " ", row).lower()
        for phrase in ("concise summary", "`cleanup.md`", "must agree", "checked", "deleted",
                       "retained", "failed", "unqueried", "deferred"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_readme_and_scenarios_describe_the_stage_artifact_stop_and_limit(self):
        for path, expected in ((README, "readme"), (SCENARIOS, "scenarios")):
            text = normalized(path)
            for phrase in ("cleanup-only", "`cleanup.md`", "explicit stop", "50"):
                with self.subTest(file=expected, phrase=phrase):
                    self.assertIn(phrase, text)
            self.assertIn("deferred", text)


class CleanupReportDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-qm", "initial"], cwd=self.repo,
                       check=True, capture_output=True)

    def record(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo),
                               *arguments], capture_output=True, text=True)

    def test_cleanup_event_and_audit_summary_render_without_changing_input(self):
        started = self.record("start", "--cycles", "1")
        self.assertEqual(started.returncode, 0, started.stderr)
        run = json.loads(started.stdout)
        for status in ("started", "finished"):
            event = self.record("event", "--run", run["run_id"], "--task", "cleanup-1",
                                "--stage", "cleanup", "--status", status)
            self.assertEqual(event.returncode, 0, event.stderr)
        handoff = json.loads(EMPTY_HANDOFF.read_text(encoding="utf-8"))
        handoff["branch_cleanup"] = ("cleanup.md: one branch deleted; one worktree retained; "
                                     "one query failed; no items deferred")
        path = Path(run["path"])
        (path / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
        source = (path / "handoff.json").read_bytes()
        report = self.record("report", "--run", run["run_id"])
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("- Branch cleanup: cleanup.md: one branch deleted", report.stdout)
        self.assertRegex(report.stdout, r"- Total \d+ min: Cleanup \d+ \(minutes\)")
        self.assertIn("Stop reason: Preparation found no ready Issues", report.stdout)
        self.assertEqual((path / "handoff.json").read_bytes(), source)
        self.assertEqual((path / "report.md").read_text(encoding="utf-8"), report.stdout)
        summary = json.loads(self.record("summary", "--run", run["run_id"]).stdout)
        self.assertIn("cleanup", summary["stage_seconds"])


if __name__ == "__main__":
    unittest.main()
