"""Verify work-cycle run records: location, concurrent events, timing summary and pruning."""

from datetime import datetime, timedelta, timezone
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/run_record.py"
spec = importlib.util.spec_from_file_location("run_record", SCRIPT)
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def run_concurrent(commands, timeout=30):
    """Start all writers before waiting, and reap every child even on interruption."""
    processes = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True))
        results = []
        for process in processes:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                raise AssertionError("Writer timed out; earlier results: %r; current stderr: %r" %
                                     (results, error.stderr)) from error
            results.append(subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr))
        return results
    finally:
        # Stop all live writers first; never leave one writing into a removed fixture.
        for process in processes:
            if process.poll() is None:
                process.kill()
        for process in processes:
            try:
                process.communicate(timeout=5)
            finally:
                process.stdout.close()
                process.stderr.close()


class ConcurrentChildTests(unittest.TestCase):
    def setUp(self):
        self.children = []
        popen = subprocess.Popen
        self.popen = popen

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            self.children.append(child)
            return child

        self.patch = mock.patch.object(subprocess, "Popen", side_effect=launch)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def assert_reaped(self):
        self.assertTrue(self.children)
        for child in self.children:
            self.assertIsNotNone(child.poll())
            self.assertTrue(child.stdout.closed)
            self.assertTrue(child.stderr.closed)

    def test_nonzero_child_preserves_stderr_and_reaps_later_children(self):
        results = run_concurrent([[sys.executable, "-c", "import sys; sys.stderr.write('initial error'); sys.exit(2)"],
                                  [sys.executable, "-c", "print('later writer')"]])
        with self.assertRaisesRegex(AssertionError, "initial error"):
            self.assertEqual([r.returncode for r in results], [0, 0], repr(results))
        self.assert_reaped()

    def test_launch_failure_reaps_started_children(self):
        with self.assertRaises(OSError):
            run_concurrent([[sys.executable, "-c", "import time; time.sleep(60)"],
                            [str(Path(__file__).parent / "missing-event-writer")]])
        self.assert_reaped()

    def test_timeout_reaps_all_children(self):
        with self.assertRaisesRegex(AssertionError, "Writer timed out"):
            run_concurrent([[sys.executable, "-c", "import time; time.sleep(60)"]] * 2, timeout=0.1)
        self.assert_reaped()

    def test_timeout_preserves_an_earlier_child_error(self):
        with self.assertRaisesRegex(AssertionError, "initial error"):
            run_concurrent([[sys.executable, "-c", "import sys; sys.stderr.write('initial error'); sys.exit(2)"],
                            [sys.executable, "-c", "import time; time.sleep(60)"]], timeout=1)
        self.assert_reaped()

    def test_interruption_reaps_all_children(self):
        real_communicate = self.popen.communicate
        interrupted = False

        def communicate(child, *args, **kwargs):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            return real_communicate(child, *args, **kwargs)

        with mock.patch.object(self.popen, "communicate", new=communicate):
            with self.assertRaises(KeyboardInterrupt):
                run_concurrent([[sys.executable, "-c", "import time; time.sleep(60)"]] * 2)
        self.assert_reaped()


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
        # -B avoids __pycache__ in the skill directory, which would enter installation snapshots.
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo or self.repo), *arguments],
                              capture_output=True, text=True)

    def start(self):
        result = self.run_cli("start", "--cycles", "10")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def event(self, run_id, task, stage, status, at, wait=None, attempt=None):
        arguments = ["event", "--run", run_id, "--task", task, "--stage", stage, "--status", status, "--at", at]
        if wait:
            arguments += ["--wait", wait]
        if attempt is not None:
            arguments += ["--attempt", str(attempt)]
        result = self.run_cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)

    def write_guard(self, path, **overrides):
        guard = path / ".events.lock"
        guard.mkdir()
        owner = {"schema": 1, "purpose": "run-record event append", "pid": 4242,
                 "process_start": "ps:test writer", "acquired_at": "2026-10-17T11:00:00Z"}
        owner.update(overrides)
        (guard / record.GUARD_OWNER).write_text(json.dumps(owner) + "\n", encoding="utf-8")
        return guard, owner

    def timeout_event(self, path, task="blocked"):
        with mock.patch.object(record.time, "monotonic", side_effect=[100, 111]):
            with mock.patch.object(record.time, "sleep") as sleep:
                with self.assertRaisesRegex(ValueError, "Timed out waiting for") as raised:
                    record.add_event(path, task, "implement", "started", None, None,
                                     datetime.now(timezone.utc))
        sleep.assert_not_called()
        return raised.exception

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
        # Require every wave to succeed; repeated contention exposes short lock transitions.
        for wave in range(20):
            with self.subTest(wave=wave):
                run_id = self.start()["run_id"]
                command = [sys.executable, "-B", str(SCRIPT), "--repo", str(self.repo), "event", "--run", run_id,
                           "--stage", "implement", "--status", "started", "--detail", "x" * 900]
                results = run_concurrent([command + ["--task", "implement-%d" % index] for index in range(8)])
                diagnostics = "\n".join("writer %d: exit %s; stdout=%r; stderr=%r" %
                                        (index, result.returncode, result.stdout, result.stderr)
                                        for index, result in enumerate(results))
                self.assertEqual([result.returncode for result in results], [0] * 8, diagnostics)
                path = record.run_dir(record.runs_root(self.repo), run_id)
                self.assertEqual(sorted(e["task"] for e in record.read_events(path)),
                                 ["implement-%d" % index for index in range(8)])

    def test_event_guard_records_owner_metadata_and_is_removed(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        observed = {}
        real_write = record.os.write

        def write(fd, data):
            observed["owner"] = json.loads((path / ".events.lock" / record.GUARD_OWNER)
                                           .read_text(encoding="utf-8"))
            return real_write(fd, data)

        with mock.patch.object(record, "process_start", return_value=("ps:writer", None)):
            with mock.patch.object(record.os, "write", side_effect=write):
                record.add_event(path, "writer", "implement", "started", None, None,
                                 datetime.now(timezone.utc))
        self.assertEqual(observed["owner"]["pid"], os.getpid())
        self.assertEqual(observed["owner"]["purpose"], "run-record event append")
        self.assertEqual(observed["owner"]["process_start"], "ps:writer")
        self.assertIn("acquired_at", observed["owner"])
        self.assertFalse((path / ".events.lock").exists())
        self.assertEqual([event["task"] for event in record.read_events(path)], ["writer"])

    def test_leftover_guard_reports_owner_and_time_without_removing_it(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        record.add_event(path, "prior", "implement", "started", None, None, datetime.now(timezone.utc))
        before = (path / "events.jsonl").read_bytes()
        guard, owner = self.write_guard(path)
        owner_before = (guard / record.GUARD_OWNER).read_bytes()
        message = str(self.timeout_event(path))
        for text in ("owner process 4242", owner["process_start"], owner["acquired_at"],
                     str(guard), "remove"):
            self.assertIn(text, message)
        self.assertEqual((path / "events.jsonl").read_bytes(), before)
        self.assertEqual((guard / record.GUARD_OWNER).read_bytes(), owner_before)
        self.assertTrue(guard.is_dir())

    def test_active_guard_is_never_removed(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        guard, owner = self.write_guard(path, pid=os.getpid())
        self.timeout_event(path)
        self.assertTrue(guard.is_dir())
        self.assertEqual(json.loads((guard / record.GUARD_OWNER).read_text(encoding="utf-8")), owner)

    def test_manual_guard_recovery_allows_later_events(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        guard, _ = self.write_guard(path)
        self.timeout_event(path)
        (guard / record.GUARD_OWNER).unlink()
        guard.rmdir()
        record.add_event(path, "recovered", "implement", "started", None, None,
                         datetime.now(timezone.utc))
        self.assertEqual([event["task"] for event in record.read_events(path)], ["recovered"])
        self.assertFalse(guard.exists())

    @unittest.skipUnless(sys.platform == "win32", "Requires native Windows directory deletion semantics")
    def test_event_waits_for_windows_pending_directory_deletion(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                      wintypes.LPVOID, wintypes.DWORD]
        kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        guard = path / ".events.lock"
        guard.mkdir()
        # Explicit legacy delete disposition keeps the directory pending deletion.
        # Recent Windows versions can unlink immediately with ordinary rmdir.
        handle = kernel.CreateFileW(str(guard), 0x00010000, 7, None, 3, 0x02000000, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value, ctypes.WinError(ctypes.get_last_error()))
        mkdir = record.os.mkdir
        observed = []

        def create(*args, **kwargs):
            nonlocal handle
            try:
                return mkdir(*args, **kwargs)
            except PermissionError as error:
                if args[0] == str(guard):
                    observed.append(error.winerror)
                    if handle is not None:
                        kernel.CloseHandle(handle)
                        handle = None
                raise

        try:
            delete = ctypes.c_ubyte(1)
            self.assertTrue(kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(delete),
                                                             ctypes.sizeof(delete)),
                            ctypes.WinError(ctypes.get_last_error()))
            stderr = io.StringIO()
            with mock.patch.object(record.os, "mkdir", side_effect=create):
                with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                    result = record.main(["--repo", str(self.repo), "event", "--run", run_id,
                                          "--task", "windows-writer", "--stage", "implement", "--status", "started"])
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertEqual(set(observed), {5}, "Expected real ERROR_ACCESS_DENIED from pending deletion")
            self.assertEqual([event["task"] for event in record.read_events(path)], ["windows-writer"])
            self.assertFalse(guard.exists())
        finally:
            if handle is not None:
                kernel.CloseHandle(handle)

    def test_event_retries_transient_windows_guard_access_denied(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        guard = path / ".events.lock"
        mkdir = record.os.mkdir
        error = PermissionError(13, "Windows guard pending deletion", str(guard))
        error.winerror = 5
        denied = False

        def create(*args, **kwargs):
            nonlocal denied
            if args[0] == str(guard) and not denied:
                denied = True
                raise error
            return mkdir(*args, **kwargs)

        with mock.patch.object(record.os, "mkdir", side_effect=create):
            with mock.patch.object(record.time, "sleep") as sleep:
                record.add_event(path, "writer", "implement", "started", None, None, datetime.now(timezone.utc))
        sleep.assert_called_once_with(0.01)
        self.assertEqual([event["task"] for event in record.read_events(path)], ["writer"])
        self.assertFalse(guard.exists())

    def test_unavailable_guard_times_out_without_appending_or_removing_it(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        record.add_event(path, "prior", "implement", "started", None, None, datetime.now(timezone.utc))
        before = (path / "events.jsonl").read_bytes()
        guard = path / ".events.lock"
        guard.mkdir()
        mkdir = record.os.mkdir
        windows_error = PermissionError(13, "Windows guard access denied", str(guard))
        windows_error.winerror = 5
        for error in (FileExistsError(17, "guard already held", str(guard)), windows_error):
            with self.subTest(error=error):
                def create(*args, **kwargs):
                    if args[0] == str(guard):
                        raise error
                    return mkdir(*args, **kwargs)

                with mock.patch.object(record.os, "mkdir", side_effect=create):
                    with mock.patch.object(record.time, "monotonic", side_effect=[100, 111]):
                        with self.assertRaisesRegex(ValueError, "Timed out waiting for") as raised:
                            record.add_event(path, "blocked", "implement", "started", None, None,
                                             datetime.now(timezone.utc))
                self.assertIs(raised.exception.__cause__, error)
                self.assertIn(str(error), str(raised.exception))
                self.assertIn(record.GUARD_OWNER, str(raised.exception))
                self.assertIn("remove", str(raised.exception))
                self.assertEqual((path / "events.jsonl").read_bytes(), before)
                self.assertTrue(guard.is_dir())

    def test_unrelated_guard_errors_fail_immediately_and_preserve_events(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        record.add_event(path, "prior", "implement", "started", None, None, datetime.now(timezone.utc))
        before = (path / "events.jsonl").read_bytes()
        guard = path / ".events.lock"
        mkdir = record.os.mkdir
        for error in (PermissionError(13, "unrelated permission denied"), OSError(5, "I/O failure")):
            with self.subTest(error=error):
                def create(*args, **kwargs):
                    if args[0] == str(guard):
                        raise error
                    return mkdir(*args, **kwargs)

                with mock.patch.object(record.os, "mkdir", side_effect=create):
                    with mock.patch.object(record.time, "sleep") as sleep:
                        with self.assertRaises(OSError) as raised:
                            record.add_event(path, "denied", "implement", "started", None, None,
                                             datetime.now(timezone.utc))
                self.assertIs(raised.exception, error)
                sleep.assert_not_called()
                self.assertEqual((path / "events.jsonl").read_bytes(), before)
                self.assertFalse(guard.exists())

    def test_failed_append_releases_only_its_owned_guard_and_keeps_prior_lines(self):
        run_id = self.start()["run_id"]
        path = record.run_dir(record.runs_root(self.repo), run_id)
        record.add_event(path, "prior", "implement", "started", None, None, datetime.now(timezone.utc))
        before = (path / "events.jsonl").read_bytes()
        for operation in ("open", "write"):
            with self.subTest(operation=operation):
                with mock.patch.object(record.os, operation, side_effect=PermissionError("append denied")):
                    with self.assertRaisesRegex(PermissionError, "append denied"):
                        record.add_event(path, "denied", "implement", "started", None, None,
                                         datetime.now(timezone.utc))
                self.assertFalse((path / ".events.lock").exists())
                self.assertEqual((path / "events.jsonl").read_bytes(), before)

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

    def test_repeated_task_dirs_keep_earlier_evidence(self):
        run_id = self.start()["run_id"]
        first = self.run_cli("task-dir", "--run", run_id, "--task", "review-pr-45")
        self.assertEqual(first.returncode, 0, first.stderr)
        earlier = Path(first.stdout.strip())
        self.assertTrue(earlier.is_absolute())
        self.assertEqual(earlier.name, "review-pr-45")
        evidence = earlier / "result.md"
        evidence.write_bytes(b"first review\n")
        before = evidence.read_bytes()

        second = self.run_cli("task-dir", "--run", run_id, "--task", "review-pr-45", "--attempt", "2")
        self.assertEqual(second.returncode, 0, second.stderr)
        later = Path(second.stdout.strip())
        self.assertTrue(later.is_absolute())
        self.assertEqual(later.name, "review-pr-45-r2")
        self.assertTrue(later.is_dir())
        self.assertNotEqual(later, earlier)
        self.assertEqual(evidence.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in later.parent.iterdir() if path.name.startswith("review-pr-45")),
                         ["review-pr-45", "review-pr-45-r2"])

    def test_event_writes_evidence_into_its_attempt_directory(self):
        run_id = self.start()["run_id"]
        self.event(run_id, "review-pr-45", "review", "started", "2026-10-10T01:00:00Z")
        self.event(run_id, "review-pr-45", "review", "started", "2026-10-10T02:00:00Z", attempt=2)
        path = record.run_dir(record.runs_root(self.repo), run_id)
        self.assertTrue((path / "review-pr-45").is_dir())
        self.assertTrue((path / "review-pr-45-r2").is_dir())
        events = record.read_events(path)
        self.assertEqual([event["task"] for event in events], ["review-pr-45", "review-pr-45"])
        self.assertTrue(all("attempt" not in event for event in events))

    def test_attempt_outside_range_is_rejected(self):
        run_id = self.start()["run_id"]
        for attempt in ("0", "10000"):
            with self.subTest(attempt=attempt):
                result = self.run_cli("task-dir", "--run", run_id, "--task", "review-pr-45",
                                      "--attempt", attempt)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("attempt must be a whole number from 1 to 9999", result.stderr)

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
