"""Verify the low-frequency trigger and local Git state used by work-cycle."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/check_workflow_gate.py"
spec = importlib.util.spec_from_file_location("check_workflow_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CheckWorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)

    def saved(self, days, version="0.2.13", result="clean", branch="main"):
        at = self.now - timedelta(days=days)
        return ({"branch": branch, "version": version, "result": result}, at)

    def test_first_run_and_branch_change(self):
        self.assertEqual(gate.decide(None, "main", "0.2.13", self.now)[0], True)
        self.assertEqual(gate.decide(self.saved(1, branch="develop"), "main", "0.2.13", self.now)[0], True)

    def test_version_change_requires_seven_days(self):
        self.assertFalse(gate.decide(self.saved(6, version="0.2.12"), "main", "0.2.13", self.now)[0])
        self.assertTrue(gate.decide(self.saved(7, version="0.2.12"), "main", "0.2.13", self.now)[0])
        self.assertFalse(gate.decide(self.saved(30), "main", "0.2.13", self.now)[0])

    def test_incomplete_run_has_cooldown_even_without_version_change(self):
        self.assertFalse(gate.decide(self.saved(6, result="incomplete"), "main", "0.2.13", self.now)[0])
        self.assertTrue(gate.decide(self.saved(7, result="incomplete"), "main", "0.2.13", self.now)[0])

    def test_claim_reserves_run_before_another_coordinator_can_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "check-workflow.json"
            self.assertTrue(gate.claim(path, "main", "0.2.13", self.now)[0])
            self.assertEqual(gate.read_state(path)[0]["result"], "incomplete")
            self.assertFalse(gate.claim(path, "main", "0.2.13", self.now)[0])

    def test_record_stays_out_of_project_files_and_worktrees_share_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.test"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-qm", "initial"], check=True)
            path = gate.state_path(root)
            recorded = gate.write_state(path, "main", "0.2.13", "pr-open",
                                        "https://example.test/pr/1", self.now)
            self.assertEqual(gate.read_state(path)[0], recorded)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], "0.2.13")
            worktree = Path(temporary) / "worktree"
            subprocess.run(["git", "-C", str(root), "worktree", "add", "-qb", "other", str(worktree)], check=True)
            self.assertEqual(gate.state_path(worktree), path)
            status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(status.stdout, "")

    def test_pr_record_needs_link_and_invalid_state_is_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            with self.assertRaises(ValueError):
                gate.write_state(path, "main", "0.2.13", "pr-open", None, self.now)
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                gate.read_state(path)

    def test_cli_claim_and_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            command = [sys.executable, str(SCRIPT), "--repo", str(repo), "--branch", "main"]
            first = subprocess.run([*command, "--claim"], capture_output=True, text=True)
            second = subprocess.run([*command, "--claim"], capture_output=True, text=True)
            recorded = subprocess.run([*command, "--record", "--result", "clean"],
                                      capture_output=True, text=True)
            self.assertEqual((first.returncode, second.returncode, recorded.returncode), (1, 0, 0))
            self.assertIn("RUN:", first.stdout)
            self.assertIn("SKIP:", second.stdout)


if __name__ == "__main__":
    unittest.main()
