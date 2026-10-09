"""Verify the shared resource locks that queue concurrent work-cycle verification and merges."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/resource_lock.py"
spec = importlib.util.spec_from_file_location("resource_lock", SCRIPT)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


class ResourceLockTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        git("init", "-q", cwd=self.repo)
        git("config", "user.name", "Test", cwd=self.repo)
        git("config", "user.email", "test@example.test", cwd=self.repo)
        git("commit", "--allow-empty", "-qm", "initial", cwd=self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments, repo=None):
        # -B 避免在技能目录生成 __pycache__，否则会进入安装快照。
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo or self.repo), *arguments],
                              capture_output=True, text=True)

    def test_acquire_release_and_exclusive_by_default(self):
        first = self.run_cli("acquire", "db", "--holder", "issue-1")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.strip(), "ACQUIRED slot-0")
        busy = self.run_cli("acquire", "db", "--holder", "issue-2")
        self.assertEqual(busy.returncode, 1)
        self.assertIn("issue-1", busy.stdout)
        self.assertEqual(self.run_cli("release", "db", "--holder", "issue-1").returncode, 0)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "issue-2").returncode, 0)

    def test_capacity_allows_that_many_holders_and_is_fixed_on_first_use(self):
        for holder in ("a", "b"):
            self.assertEqual(self.run_cli("acquire", "heavy", "--holder", holder, "--capacity", "2").returncode, 0)
        self.assertEqual(self.run_cli("acquire", "heavy", "--holder", "c", "--capacity", "2").returncode, 1)
        mismatch = self.run_cli("acquire", "heavy", "--holder", "c", "--capacity", "3")
        self.assertEqual(mismatch.returncode, 2)
        self.assertIn("capacity", mismatch.stderr)

    def test_same_holder_retry_reports_held_without_taking_a_second_slot(self):
        self.assertEqual(self.run_cli("acquire", "heavy", "--holder", "a", "--capacity", "2").returncode, 0)
        retry = self.run_cli("acquire", "heavy", "--holder", "a", "--capacity", "2")
        self.assertEqual((retry.returncode, retry.stdout.strip()), (0, "HELD"))
        self.assertEqual(self.run_cli("acquire", "heavy", "--holder", "b", "--capacity", "2").returncode, 0)

    def test_only_the_holder_can_release(self):
        self.run_cli("acquire", "simulator", "--holder", "issue-1")
        refused = self.run_cli("release", "simulator", "--holder", "issue-2")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("does not hold", refused.stderr)
        self.assertEqual(self.run_cli("acquire", "simulator", "--holder", "issue-2").returncode, 1)

    def test_wait_times_out_and_succeeds_once_released(self):
        self.run_cli("acquire", "merge", "--holder", "pr-1")
        started = time.monotonic()
        self.assertEqual(self.run_cli("acquire", "merge", "--holder", "pr-2", "--wait", "1").returncode, 1)
        self.assertGreaterEqual(time.monotonic() - started, 1)
        root = lock.locks_root(self.repo)
        lock.release(root, "merge", "pr-1")
        self.assertEqual(lock.acquire(root, "merge", 1, "pr-2", None, 1), "ACQUIRED slot-0")

    def test_simultaneous_acquirers_get_exactly_capacity_slots(self):
        command = [sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo), "acquire", "docker", "--capacity", "2"]
        processes = [subprocess.Popen(command + ["--holder", "h%d" % index], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for index in range(8)]
        codes = [process.wait() for process in processes]
        for process in processes:
            process.stdout.close()
            process.stderr.close()
        self.assertEqual(sorted(codes), [0, 0, 1, 1, 1, 1, 1, 1])
        report = json.loads(self.run_cli("status", "docker").stdout)
        self.assertEqual(sorted(h["slot"] for h in report[0]["holders"]), ["slot-0", "slot-1"])

    def test_invalid_names_and_holders_are_rejected(self):
        for name in ("", "DB", "../x", "a b", "x" * 65):
            with self.subTest(name=name):
                self.assertEqual(self.run_cli("acquire", name, "--holder", "a").returncode, 2)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "a\nb").returncode, 2)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "a", "--capacity", "0").returncode, 2)

    def test_status_reports_holders_and_note(self):
        self.run_cli("acquire", "port-5432", "--holder", "issue-7", "--note", "integration tests")
        report = json.loads(self.run_cli("status").stdout)
        self.assertEqual(report[0]["resource"], "port-5432")
        self.assertEqual(report[0]["capacity"], 1)
        self.assertEqual(report[0]["holders"][0]["holder"], "issue-7")
        self.assertEqual(report[0]["holders"][0]["note"], "integration tests")

    def test_worktrees_share_locks_and_project_files_stay_untouched(self):
        worktree = Path(self.temporary.name) / "worktree"
        git("worktree", "add", "-q", "--detach", str(worktree), cwd=self.repo)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "main-checkout").returncode, 0)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "worktree", repo=worktree).returncode, 1)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(status.stdout, "")

    def test_non_repository_is_an_error(self):
        outside = Path(self.temporary.name) / "plain"
        outside.mkdir()
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "a", repo=outside).returncode, 2)


if __name__ == "__main__":
    unittest.main()
