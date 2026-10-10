"""Verify work-cycle run records: location, concurrent events, timing summary and pruning."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/run_record.py"
spec = importlib.util.spec_from_file_location("run_record", SCRIPT)
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


class RunRecordTests(unittest.TestCase):
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

    def start(self):
        result = self.run_cli("start", "--cycles", "10")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def event(self, run_id, task, stage, status, at, wait=None):
        arguments = ["event", "--run", run_id, "--task", task, "--stage", stage, "--status", status, "--at", at]
        if wait:
            arguments += ["--wait", wait]
        result = self.run_cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_uses_git_metadata_and_leaves_project_files_untouched(self):
        started = self.start()
        path = Path(started["path"])
        self.assertTrue((path / "run.json").is_file())
        self.assertIn(str(Path(".git") / "forge-steward" / "runs"), str(path))
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(status.stdout, "")
        worktree = Path(self.temporary.name) / "worktree"
        git("worktree", "add", "-q", "--detach", str(worktree), cwd=self.repo)
        shared = self.run_cli("task-dir", "--run", started["run_id"], "--task", "review-pr-1", repo=worktree)
        self.assertEqual(shared.returncode, 0, shared.stderr)
        self.assertTrue(Path(shared.stdout.strip()).is_dir())

    def test_summary_reports_task_stage_and_wait_durations(self):
        run_id = self.start()["run_id"]
        self.event(run_id, "prepare-1", "prepare", "started", "2026-10-10T01:00:00Z")
        self.event(run_id, "prepare-1", "prepare", "finished", "2026-10-10T01:20:00Z")
        self.event(run_id, "implement-7", "implement", "started", "2026-10-10T01:20:00Z")
        self.event(run_id, "implement-7", "implement", "wait-start", "2026-10-10T01:40:00Z", wait="ci")
        self.event(run_id, "implement-7", "implement", "wait-end", "2026-10-10T01:48:00Z", wait="ci")
        self.event(run_id, "implement-7", "implement", "wait-start", "2026-10-10T01:50:00Z", wait="lock")
        self.event(run_id, "implement-7", "implement", "wait-end", "2026-10-10T01:52:00Z", wait="lock")
        self.event(run_id, "implement-7", "implement", "finished", "2026-10-10T02:00:00Z")
        self.event(run_id, "review-pr-9", "review", "started", "2026-10-10T02:00:00Z")
        summary = json.loads(self.run_cli("summary", "--run", run_id).stdout)
        self.assertEqual(summary["wall_seconds"], 3600)
        self.assertEqual(summary["stage_seconds"], {"prepare": 1200, "implement": 2400})
        self.assertEqual(summary["wait_seconds"], {"ci": 480, "lock": 120})
        review = [task for task in summary["tasks"] if task["task"] == "review-pr-9"][0]
        self.assertEqual((review["result"], review["seconds"]), ("running", None))

    def test_concurrent_events_are_all_recorded_as_whole_lines(self):
        run_id = self.start()["run_id"]
        command = [sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo), "event", "--run", run_id,
                   "--stage", "implement", "--status", "started", "--detail", "x" * 900]
        processes = [subprocess.Popen(command + ["--task", "implement-%d" % index], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for index in range(8)]
        for process in processes:
            self.assertEqual(process.wait(), 0)
            process.stdout.close()
            process.stderr.close()
        path = record.run_dir(record.runs_root(self.repo), run_id)
        self.assertEqual(sorted(e["task"] for e in record.read_events(path)),
                         ["implement-%d" % index for index in range(8)])

    def test_prune_keeps_newest_runs_and_ignores_foreign_directories(self):
        root = record.runs_root(self.repo)
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        created = [record.start(root, 10, base + timedelta(hours=index))[0] for index in range(5)]
        foreign = root / "20260101T000000Z-abcd"
        foreign.mkdir()
        (foreign / "notes.txt").write_text("keep", encoding="utf-8")
        removed = record.prune(root, 3)
        self.assertEqual(removed, sorted(created[:2]))
        self.assertTrue(foreign.is_dir())
        self.assertEqual(sorted(p.name for p in root.iterdir() if p.name in created), sorted(created[2:]))

    def test_invalid_inputs_are_rejected(self):
        run_id = self.start()["run_id"]
        self.assertEqual(self.run_cli("summary", "--run", "../x").returncode, 2)
        self.assertEqual(self.run_cli("summary", "--run", "20261010T000000Z-ffff").returncode, 2)
        self.assertEqual(self.run_cli("event", "--run", run_id, "--task", "../x", "--stage", "s",
                                      "--status", "started").returncode, 2)
        self.assertEqual(self.run_cli("event", "--run", run_id, "--task", "t", "--stage", "s",
                                      "--status", "wait-start").returncode, 2)
        self.assertEqual(self.run_cli("event", "--run", run_id, "--task", "t", "--stage", "s",
                                      "--status", "started", "--at", "2026-10-10T01:00:00").returncode, 2)
        outside = Path(self.temporary.name) / "plain"
        outside.mkdir()
        self.assertEqual(self.run_cli("start", "--cycles", "1", repo=outside).returncode, 2)


if __name__ == "__main__":
    unittest.main()
