"""Verify the shared resource locks that queue concurrent work-cycle verification and merges."""

import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/resource_lock.py"
spec = importlib.util.spec_from_file_location("resource_lock", SCRIPT)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def stamp(hours_ago=0):
    moment = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def owner_arguments(run, task, attempt=1):
    arguments = ["--run", run, "--task", task]
    if attempt != 1:
        arguments += ["--attempt", str(attempt)]
    return arguments


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
        # -B avoids __pycache__ in the skill directory, which would enter installation snapshots.
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo or self.repo), *arguments],
                              capture_output=True, text=True)

    def acquire(self, resource, run, task, attempt=1, *arguments, repo=None):
        return self.run_cli("acquire", resource, *owner_arguments(run, task, attempt), *arguments, repo=repo)

    def release(self, resource, run, task, attempt=1):
        return self.run_cli("release", resource, *owner_arguments(run, task, attempt))

    def status(self, resource=None):
        arguments = ["status"] + ([resource] if resource else [])
        result = self.run_cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def seed_slot(self, record, resource="db", capacity=1):
        path = lock.locks_root(self.repo) / resource
        path.mkdir(parents=True, exist_ok=True)
        (path / "capacity").write_text(str(capacity) + "\n", encoding="utf-8")
        slot = path / "slot-0"
        slot.mkdir()
        (slot / "holder.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
        return slot

    def owner_record(self, run, task, attempt, pid, process_start=None, acquired_at=None):
        return {"resource": "db", "owner": lock.owner_key(run, task, attempt), "run": run, "task": task,
                "attempt": attempt, "pid": pid, "process_start": process_start,
                "note": "", "acquired_at": acquired_at or stamp()}

    def exited_pid(self):
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait()
        return process.pid

    def test_acquire_release_and_exclusive_by_default(self):
        first = self.acquire("db", "run-a", "implement-167")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.strip(), "ACQUIRED slot-0")
        busy = self.acquire("db", "run-b", "implement-167")
        self.assertEqual(busy.returncode, 1)
        self.assertIn("run-a/implement-167/1", busy.stdout)
        self.assertEqual(self.release("db", "run-a", "implement-167").returncode, 0)
        self.assertEqual(self.acquire("db", "run-b", "implement-167").returncode, 0)

    def test_two_runs_with_the_same_stage_identifiers_cannot_share_or_release(self):
        self.assertEqual(self.acquire("db", "run-a", "implement-167").returncode, 0)
        busy = self.acquire("db", "run-b", "implement-167")
        self.assertEqual(busy.returncode, 1)
        self.assertIn("run-a/implement-167/1", busy.stdout)
        waited = self.acquire("db", "run-b", "implement-167", 1, "--wait", "1")
        self.assertEqual(waited.returncode, 1)
        refused = self.release("db", "run-b", "implement-167")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("does not hold", refused.stderr)
        report = self.status("db")
        self.assertEqual([holder["owner"] for holder in report[0]["holders"]], ["run-a/implement-167/1"])
        self.assertEqual(self.release("db", "run-a", "implement-167").returncode, 0)
        self.assertEqual(self.acquire("db", "run-b", "implement-167").returncode, 0)

    def test_same_owner_retry_is_idempotent_and_attempts_are_distinct(self):
        self.assertEqual(self.acquire("heavy", "run-a", "a", 1, "--capacity", "2").returncode, 0)
        retry = self.acquire("heavy", "run-a", "a", 1, "--capacity", "2")
        self.assertEqual((retry.returncode, retry.stdout.strip()), (0, "HELD"))
        self.assertEqual(len(self.status("heavy")[0]["holders"]), 1)
        second_attempt = self.acquire("heavy", "run-a", "a", 2, "--capacity", "2")
        self.assertEqual(second_attempt.returncode, 0, second_attempt.stderr)
        self.assertEqual(sorted(h["owner"] for h in self.status("heavy")[0]["holders"]),
                         ["run-a/a/1", "run-a/a/2"])

    def test_capacity_allows_that_many_owners_and_is_fixed_on_first_use(self):
        for run in ("run-a", "run-b"):
            self.assertEqual(self.acquire("heavy", run, "worker", 1, "--capacity", "2").returncode, 0)
        self.assertEqual(self.acquire("heavy", "run-c", "worker", 1, "--capacity", "2").returncode, 1)
        mismatch = self.acquire("heavy", "run-c", "worker", 1, "--capacity", "3")
        self.assertEqual(mismatch.returncode, 2)
        self.assertIn("capacity", mismatch.stderr)
        self.assertEqual(len(self.status("heavy")[0]["holders"]), 2)

    def call_main(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = lock.main(["--repo", str(self.repo), *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_acquire_held_busy_and_omitted_capacity_error(self):
        first = self.acquire("heavy", "run-a", "worker", 1, "--capacity", "2", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["result"], "acquired")
        self.assertEqual((report["resource"], report["requested_capacity"], report["existing_capacity"]),
                         ("heavy", 2, 2))
        self.assertEqual((report["owner"], report["run"], report["task"], report["attempt"]),
                         ("run-a/worker/1", "run-a", "worker", 1))
        self.assertEqual(report["slot"], "slot-0")
        root = lock.locks_root(self.repo)
        before = (root / "heavy" / "slot-0" / "holder.json").read_bytes()
        # Keep the clock mock local: subprocess timeout polling also uses the time module.
        with mock.patch.object(lock, "time", wraps=time, sleep=mock.Mock()) as clock, \
                mock.patch.object(lock, "try_acquire", wraps=lock.try_acquire) as tried:
            code, output, errors = self.call_main("acquire", "heavy", "--run", "run-b", "--task", "worker",
                                                  "--wait", "60", "--json")
        self.assertEqual((code, errors), (2, ""))
        mismatch = json.loads(output)
        self.assertEqual(mismatch["result"], "error")
        self.assertEqual((mismatch["requested_capacity"], mismatch["existing_capacity"]), (1, 2))
        self.assertIn("retry with --capacity 2", mismatch["reason"])
        self.assertEqual(tried.call_count, 1)
        clock.sleep.assert_not_called()
        self.assertEqual((root / "heavy" / "capacity").read_text().strip(), "2")
        self.assertEqual((root / "heavy" / "slot-0" / "holder.json").read_bytes(), before)
        held = self.acquire("heavy", "run-a", "worker", 1, "--capacity", "2", "--json")
        self.assertEqual((held.returncode, json.loads(held.stdout)["result"]), (0, "held"))
        self.assertEqual(len(self.status("heavy")[0]["holders"]), 1)
        corrected = self.acquire("heavy", "run-b", "worker", 1, "--capacity", "2", "--json")
        self.assertEqual((corrected.returncode, json.loads(corrected.stdout)["result"]), (0, "acquired"))
        busy = self.acquire("heavy", "run-c", "worker", 1, "--capacity", "2", "--json")
        report = json.loads(busy.stdout)
        self.assertEqual((busy.returncode, report["result"]), (1, "busy"))
        self.assertEqual(sorted(h["owner"] for h in report["holders"]), ["run-a/worker/1", "run-b/worker/1"])
        self.assertEqual(len(self.status("heavy")[0]["holders"]), 2)

    def test_invalid_json_arguments_never_enter_retry_or_create_lock_state(self):
        cases = [("--wait", value) for value in ("nan", "inf", "-inf", "-1", "no-number")]
        cases += [("--capacity", value) for value in ("0", "-1", "no-number")]
        cases += [("--attempt", "0"), ("--run", "bad/run"), ("--task", "bad task")]
        for option, value in cases:
            with self.subTest(option=option, value=value), mock.patch.object(lock, "acquire") as acquire:
                code, output, errors = self.call_main("acquire", "db", "--run", "run-a", "--task", "worker",
                                                      option + "=" + value, "--json")
                self.assertEqual((code, errors), (2, ""))
                report = json.loads(output)
                self.assertEqual((report["schema_version"], report["result"]), (1, "error"))
                self.assertIn(option, report["reason"])
                acquire.assert_not_called()
                self.assertFalse(lock.locks_root(self.repo).exists())
        for arguments in (("acquire", "db", "--json"),
                          ("acquire", "../db", "--run", "run-a", "--task", "worker", "--json")):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["result"], "error")
                self.assertEqual(result.stderr, "")
        legacy = self.acquire("db", "run-a", "worker", 1, "--wait", "nan")
        self.assertEqual(legacy.returncode, 2)
        self.assertIn("finite nonnegative", legacy.stderr)

    def test_only_occupied_destination_errors_count_as_busy(self):
        root = lock.locks_root(self.repo)
        for code in (errno.EEXIST, errno.ENOTEMPTY):
            with self.subTest(errno=code), mock.patch.object(lock.os, "rename", side_effect=OSError(code, "occupied")):
                self.assertIsNone(lock.try_acquire(root, "db", 1, "run-a", "worker", 1, None))
        self.assertEqual(list(root.glob(".tmp-*")), [])
        for code in (errno.EACCES, errno.EIO, errno.ENOENT, errno.ENOSPC):
            with self.subTest(errno=code), mock.patch.object(lock.os, "rename", side_effect=OSError(code, "failure")), \
                    mock.patch.object(lock, "time", wraps=time, sleep=mock.Mock()) as clock:
                result, output, errors = self.call_main("acquire", "db", "--run", "run-a", "--task", "worker",
                                                        "--wait", "60", "--json")
                self.assertEqual((result, errors), (2, ""))
                self.assertEqual(json.loads(output)["result"], "error")
                self.assertIn("failure", json.loads(output)["reason"])
                clock.sleep.assert_not_called()
                self.assertEqual(list(root.glob(".tmp-*")), [])
                self.assertEqual(lock.holders(root / "db"), [])

    def test_creation_write_and_rename_failures_preserve_existing_holders(self):
        self.assertEqual(self.acquire("heavy", "run-a", "worker", 1, "--capacity", "2").returncode, 0)
        root = lock.locks_root(self.repo)
        before = (root / "heavy" / "slot-0" / "holder.json").read_bytes()
        for target in ("mkdtemp", "write_text", "rename"):
            module, attribute = {"mkdtemp": (lock.tempfile, "mkdtemp"),
                                 "write_text": (lock.Path, "write_text"),
                                 "rename": (lock.os, "rename")}[target]
            with self.subTest(target=target), mock.patch.object(module, attribute,
                                                               side_effect=PermissionError(errno.EACCES, "denied")), \
                    mock.patch.object(lock, "time", wraps=time, sleep=mock.Mock()) as clock:
                code, output, errors = self.call_main("acquire", "heavy", "--run", "run-b", "--task", "worker",
                                                      "--capacity", "2", "--wait", "60", "--json")
                self.assertEqual((code, errors), (2, ""))
                self.assertEqual(json.loads(output)["result"], "error")
                self.assertEqual(json.loads(output)["existing_capacity"], 2)
                self.assertIn("denied", json.loads(output)["reason"])
                clock.sleep.assert_not_called()
                self.assertEqual((root / "heavy" / "slot-0" / "holder.json").read_bytes(), before)
                self.assertEqual(len(lock.holders(root / "heavy")), 1)
                self.assertEqual(list(root.glob(".tmp-*")), [])

    def test_real_busy_wait_is_bounded_and_stop_preserves_holder(self):
        self.assertEqual(self.acquire("db", "run-a", "worker").returncode, 0)
        root = lock.locks_root(self.repo)
        before = (root / "db" / "slot-0" / "holder.json").read_bytes()
        with mock.patch.object(lock, "time", wraps=time, sleep=mock.Mock(),
                               monotonic=mock.Mock(side_effect=[0, 0, 1])) as clock:
            code, output, errors = self.call_main("acquire", "db", "--run", "run-b", "--task", "worker",
                                                  "--wait", "1", "--json")
        self.assertEqual((code, json.loads(output)["result"], errors), (1, "busy", ""))
        clock.sleep.assert_called_once_with(lock.POLL_SECONDS)
        with mock.patch.object(lock, "time", wraps=time, sleep=mock.Mock(side_effect=KeyboardInterrupt)):
            with self.assertRaises(KeyboardInterrupt):
                lock.acquire(root, "db", 1, "run-b", "worker", 1, None, 60)
        self.assertEqual((root / "db" / "slot-0" / "holder.json").read_bytes(), before)
        self.assertEqual(len(lock.holders(root / "db")), 1)

    def test_only_the_owner_key_can_release(self):
        self.assertEqual(self.acquire("simulator", "run-a", "issue-1").returncode, 0)
        refused = self.release("simulator", "run-b", "issue-1")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("does not hold", refused.stderr)
        self.assertEqual(self.acquire("simulator", "run-b", "issue-1").returncode, 1)

    def test_wait_times_out_and_succeeds_once_released(self):
        self.assertEqual(self.acquire("merge", "run-a", "pr-1").returncode, 0)
        started = time.monotonic()
        self.assertEqual(self.acquire("merge", "run-b", "pr-2", 1, "--wait", "1").returncode, 1)
        self.assertGreaterEqual(time.monotonic() - started, 1)
        self.assertEqual(self.release("merge", "run-a", "pr-1").returncode, 0)
        self.assertEqual(self.acquire("merge", "run-b", "pr-2").returncode, 0)

    def test_simultaneous_acquirers_get_exactly_capacity_slots(self):
        command = [sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo), "acquire", "docker",
                   "--capacity", "2"]
        processes = [subprocess.Popen(command + ["--run", "run-%d" % index, "--task", "docker"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for index in range(8)]
        codes = [process.wait() for process in processes]
        for process in processes:
            process.stdout.close()
            process.stderr.close()
        self.assertEqual(sorted(codes), [0, 0, 1, 1, 1, 1, 1, 1])
        report = self.status("docker")
        self.assertEqual(sorted(h["slot"] for h in report[0]["holders"]), ["slot-0", "slot-1"])

    def test_invalid_names_components_and_attempts_are_rejected(self):
        for name in ("", "DB", "../x", "a b", "x" * 65):
            with self.subTest(name=name):
                self.assertEqual(self.acquire(name, "run-a", "a").returncode, 2)
        for run in ("", "a/b", "a b", "-a", "a" * 65):
            with self.subTest(run=run):
                self.assertEqual(self.acquire("db", run, "a").returncode, 2)
        for attempt in ("0", "10000", "x"):
            with self.subTest(attempt=attempt):
                self.assertEqual(self.run_cli("acquire", "db", "--run", "run-a", "--task", "a",
                                              "--attempt", attempt).returncode, 2)
        self.assertEqual(self.run_cli("acquire", "db", "--task", "a").returncode, 2)
        self.assertEqual(self.run_cli("acquire", "db", "--run", "run-a").returncode, 2)
        self.assertEqual(self.run_cli("acquire", "db", "--holder", "a").returncode, 2)
        self.assertEqual(self.acquire("db", "run-a", "a", 1, "--capacity", "0").returncode, 2)
        self.assertEqual(self.run_cli("status", "DB").returncode, 2)

    def test_status_reports_owner_metadata_age_and_note(self):
        result = self.run_cli("acquire", "port-5432", "--run", "run-a", "--task", "issue-7",
                              "--note", "integration tests")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.status()
        self.assertEqual(report[0]["resource"], "port-5432")
        self.assertEqual(report[0]["capacity"], 1)
        holder = report[0]["holders"][0]
        self.assertEqual(holder["owner"], "run-a/issue-7/1")
        self.assertEqual((holder["run"], holder["task"], holder["attempt"]), ("run-a", "issue-7", 1))
        self.assertGreater(holder["pid"], 0)
        self.assertTrue(holder["process_start"] or holder["process_start_error"])
        self.assertEqual(holder["note"], "integration tests")
        self.assertTrue(holder["acquired_at"].endswith("Z"))
        self.assertGreaterEqual(holder["age_seconds"], 0)
        self.assertIn(holder["liveness"], ("alive", "stopped", "unknown"))
        self.assertFalse(holder["legacy"])

    def test_stale_slot_is_reported_and_can_be_recovered_after_the_owner_stopped(self):
        dead = self.exited_pid()
        slot = self.seed_slot(self.owner_record("run-a", "review-pr-45", 2, dead, acquired_at=stamp(2)))
        report = self.status("db")
        holder = report[0]["holders"][0]
        self.assertEqual(holder["owner"], "run-a/review-pr-45/2")
        self.assertEqual(holder["liveness"], "stopped")
        self.assertGreaterEqual(holder["age_seconds"], 7200)
        self.assertTrue(slot.is_dir(), "status must not remove a stale slot")
        released = self.release("db", "run-a", "review-pr-45", 2)
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual(released.stdout.strip(), "RELEASED slot-0")
        self.assertEqual(self.status("db")[0]["holders"], [])

    def test_active_slot_is_never_released_by_another_process(self):
        start, _ = lock.process_start(os.getpid())
        slot = self.seed_slot(self.owner_record("run-a", "implement-167", 1, os.getpid(), process_start=start))
        holder = self.status("db")[0]["holders"][0]
        self.assertEqual(holder["liveness"], "alive")
        refused = self.release("db", "run-a", "implement-167")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("Refusing", refused.stderr)
        self.assertTrue(slot.is_dir(), "an active slot must not be removed")

    def test_reused_process_id_is_not_treated_as_the_same_owner(self):
        start, _ = lock.process_start(os.getpid())
        if start is None:
            self.skipTest("process start times are unavailable on this platform")
        self.seed_slot(self.owner_record("run-a", "implement-167", 1, os.getpid(),
                                         process_start=start + "-different"))
        holder = self.status("db")[0]["holders"][0]
        self.assertEqual(holder["liveness"], "stopped")
        self.assertIn("different start time", holder["liveness_detail"])
        self.assertEqual(self.release("db", "run-a", "implement-167").returncode, 0)

    def test_legacy_holder_is_reported_read_only(self):
        slot = self.seed_slot({"resource": "db", "holder": "implement-167", "note": "old format",
                               "acquired_at": stamp(1)})
        holder = self.status("db")[0]["holders"][0]
        self.assertEqual(holder["owner"], "implement-167")
        self.assertTrue(holder["legacy"])
        self.assertEqual(holder["liveness"], "unknown")
        self.assertIn("no owner process ID", holder["liveness_detail"])
        refused = self.release("db", "run-a", "implement-167")
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(slot.is_dir())

    def test_run_level_ownership_is_exclusive(self):
        reserved = self.acquire("run", "run-a", "run", 1, "--capacity", "2")
        self.assertEqual(reserved.returncode, 2)
        self.assertIn("capacity 1", reserved.stderr)
        self.assertEqual(self.acquire("run", "run-a", "run").returncode, 0)
        busy = self.acquire("run", "run-b", "run")
        self.assertEqual(busy.returncode, 1)
        self.assertIn("run-a/run/1", busy.stdout)
        self.assertEqual(self.acquire("run", "run-b", "run", 1, "--wait", "1").returncode, 1)
        self.assertEqual(self.release("run", "run-a", "run").returncode, 0)
        self.assertEqual(self.acquire("run", "run-b", "run").returncode, 0)

    def test_worktrees_share_locks_and_project_files_stay_untouched(self):
        worktree = Path(self.temporary.name) / "worktree"
        git("worktree", "add", "-q", "--detach", str(worktree), cwd=self.repo)
        self.assertEqual(self.acquire("db", "run-a", "main-checkout").returncode, 0)
        self.assertEqual(self.acquire("db", "run-b", "worktree", 1, repo=worktree).returncode, 1)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(status.stdout, "")

    def test_non_repository_is_an_error(self):
        outside = Path(self.temporary.name) / "plain"
        outside.mkdir()
        self.assertEqual(self.acquire("db", "run-a", "a", 1, repo=outside).returncode, 2)


if __name__ == "__main__":
    unittest.main()
