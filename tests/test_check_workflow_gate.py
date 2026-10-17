"""Verify the low-frequency trigger and local Git state used by work-cycle."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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

    def owner(self, **overrides):
        owner = {"schema": 1, "purpose": gate.LOCK_PURPOSE, "pid": 4242,
                 "process_start": "ps:test owner", "acquired_at": "2026-10-17T11:00:00Z"}
        owner.update(overrides)
        return owner

    def write_lock(self, path, **overrides):
        lock = gate.lock_path(path)
        lock.parent.mkdir(parents=True, exist_ok=True)
        owner = self.owner(**overrides)
        lock.write_text(json.dumps(owner) + "\n", encoding="utf-8")
        return lock, owner

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
            self.assertFalse(gate.lock_path(path).exists())
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

    def test_state_lock_records_owner_and_removes_only_its_own_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            with mock.patch.object(gate, "process_start", return_value=("ps:current", None)):
                with gate.state_lock(path):
                    lock = gate.lock_path(path)
                    owner = json.loads(lock.read_text(encoding="utf-8"))
                    self.assertEqual(owner["pid"], os.getpid())
                    self.assertEqual(owner["purpose"], gate.LOCK_PURPOSE)
                    self.assertEqual(owner["process_start"], "ps:current")
                    self.assertIn("acquired_at", owner)
            self.assertFalse(gate.lock_path(path).exists())

    def test_leftover_lock_reports_owner_and_time_without_removing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            lock, owner = self.write_lock(path)
            before = lock.read_bytes()
            with self.assertRaises(ValueError) as raised:
                gate.claim(path, "main", "0.2.13", self.now)
            message = str(raised.exception)
            for text in ("owner process 4242", owner["process_start"], owner["acquired_at"], str(lock), "remove"):
                self.assertIn(text, message)
            self.assertEqual(lock.read_bytes(), before)

    def test_active_holder_lock_is_never_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            lock, owner = self.write_lock(path, pid=os.getpid())
            with self.assertRaisesRegex(ValueError, "owner process %d" % os.getpid()):
                gate.claim(path, "main", "0.2.13", self.now)
            self.assertEqual(lock.read_bytes(), (json.dumps(owner) + "\n").encode("utf-8"))

    def test_bare_legacy_lock_is_reported_and_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            lock = gate.lock_path(path)
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("", encoding="utf-8")
            before = lock.read_bytes()
            with self.assertRaises(ValueError) as raised:
                gate.claim(path, "main", "0.2.13", self.now)
            self.assertIn("readable owner metadata", str(raised.exception))
            self.assertIn(str(lock), str(raised.exception))
            self.assertEqual(lock.read_bytes(), before)

    def test_cli_refuses_leftover_owner_and_recovers_after_manual_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            command = [sys.executable, str(SCRIPT), "--repo", str(repo), "--branch", "main"]
            state = gate.state_path(repo)
            lock, owner = self.write_lock(state)
            claim = subprocess.run([*command, "--claim"], capture_output=True, text=True)
            recorded = subprocess.run([*command, "--record", "--result", "clean"],
                                      capture_output=True, text=True)
            for result in (claim, recorded):
                self.assertEqual(result.returncode, 2)
                self.assertIn("4242", result.stderr)
                self.assertIn(owner["acquired_at"], result.stderr)
                self.assertIn(str(lock), result.stderr)
                self.assertIn("remove", result.stderr)
                self.assertTrue(lock.is_file())
            self.assertFalse(state.exists())
            lock.unlink()
            recovered = subprocess.run([*command, "--record", "--result", "clean"],
                                       capture_output=True, text=True)
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(gate.read_state(state)[0]["result"], "clean")
            self.assertFalse(lock.exists())

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
