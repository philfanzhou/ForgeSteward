"""Bounded scenario and lifecycle checks for the disposable scope experiment."""

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/measure_resource_scope.py"
SPEC = importlib.util.spec_from_file_location("measure_resource_scope", SCRIPT)
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


class ResourceScopeExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.output = self.parent / "experiment"
        self.foreign = self.parent / "foreign"
        self.foreign.mkdir()
        (self.foreign / "keep").write_text("external data", encoding="utf-8")

    def experiment(self, cls=scope.Experiment, **kwargs):
        return cls(self.output, trials=1, cpu_seconds=0.01, memory_mib=0.125, **kwargs)

    def assert_drained(self, report):
        commands = [r for r in report["commands"] if "pid" in r]
        self.assertTrue(commands)
        self.assertTrue(all(r.get("drained") for r in commands))
        self.assertEqual((self.foreign / "keep").read_text(encoding="utf-8"), "external data")

    def test_all_conditions_metrics_owner_ordering_and_compatibility(self):
        helper_before = scope.HELPER.read_bytes()
        report = self.experiment().run()
        self.assertEqual(report["status"], "complete", report.get("error"))
        self.assertEqual(report["cleanup_errors"], [])
        self.assert_drained(report)
        self.assertEqual(scope.HELPER.read_bytes(), helper_before)
        rows = {r["condition"]: r for r in report["trials"]}
        self.assertEqual(set(rows), set(scope.CONDITIONS))
        for name, row in rows.items():
            self.assertEqual(len(row["workers"]), 2)
            self.assertEqual(row["collisions"], int(name == "shared-identity"))
            self.assertEqual(row["peak_active_workers"], 2 if name in ("isolated", "shared-identity") else 1)
            for worker in row["workers"]:
                for key in ("wall_seconds", "cpu_seconds"):
                    self.assertGreaterEqual(worker[key], 0)
                self.assertEqual(worker["configured_allocation_bytes"], 131072)
                metric = worker["peak_rss"]
                if metric["value"] is None:
                    self.assertTrue(metric["unavailable_reason"])
                else:
                    self.assertGreater(metric["value"], 0)
                    self.assertEqual(metric["unit"], "bytes")
            for acquisition in row["acquisitions"]:
                self.assertEqual(acquisition["exit"], 0)
                self.assertEqual(acquisition["acquire_result"]["result"], "acquired")
                self.assertEqual(acquisition["acquire_result"]["resource"], "heavy")
                self.assertGreaterEqual(acquisition["elapsed_seconds"], 0)
        same = rows["same-repository"]
        self.assertEqual(same["busy"]["exit"], 1)
        held = same["busy"]["acquire_result"]["holders"]
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["owner"], same["acquisitions"][0]["acquire_result"]["owner"])
        self.assertLess(same["acquisitions"][1]["started"], same["release_started"])
        self.assertLess(same["release_started"], same["release_finished"])
        self.assertLess(same["release_finished"], same["acquisitions"][1]["finished"])
        statuses = [r for r in report["commands"] if r["label"] == "final-status"]
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(not entry["holders"] for r in statuses for entry in json.loads(r["stdout"])))
        self.assertEqual(json.loads((self.output / "results.json").read_text())["status"], "complete")

    def test_bounds_rejected_before_creating_output(self):
        for field, values in {"trials": [0, 6, True], "cpu_seconds": [0, 0.51, float("nan"), float("inf")],
                              "memory_mib": [0, 17, float("nan")], "deadline_seconds": [0, 121]}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    experiment = self.experiment()
                    experiment.options[field] = value
                    with self.assertRaises(scope.ExperimentError):
                        experiment.run()
                    self.assertFalse(self.output.exists())

    def test_existing_directory_file_and_symlink_never_adopted(self):
        for kind in ("directory", "file", "symlink"):
            target = self.parent / kind
            if kind == "directory":
                target.mkdir()
                (target / "sentinel").write_text("keep", encoding="utf-8")
            elif kind == "file":
                target.write_text("keep", encoding="utf-8")
            else:
                try:
                    target.symlink_to(self.foreign, target_is_directory=True)
                except OSError:
                    continue  # Windows may deny unprivileged symlink creation.
            with self.assertRaises(scope.ExperimentError):
                scope.Experiment(target).run()
            self.assertTrue(target.exists())
        self.assertEqual((self.foreign / "keep").read_text(), "external data")

    def test_helper_error_is_not_busy_or_retried(self):
        helper = self.parent / "error_helper.py"
        helper.write_text('import json\nprint(json.dumps({"result":"error","reason":"fixture failure"}))\nraise SystemExit(2)\n', encoding="utf-8")
        with mock.patch.object(scope, "HELPER", helper):
            report = self.experiment().run()
        self.assertEqual(report["status"], "error")
        self.assertIn("unexpected helper result", report["error"])
        acquisitions = [r for r in report["commands"] if r["label"].startswith("acquire-")]
        self.assertEqual(len(acquisitions), 1)
        self.assertEqual(acquisitions[0]["exit"], 2)
        self.assert_drained(report)

    def test_inherited_git_overrides_cannot_redirect_fixture_locks(self):
        subprocess.run(["git", "init", "--quiet", str(self.foreign)], check=True,
                       capture_output=True, env=scope.child_environment())
        holder = self.foreign / ".git/forge-steward/locks/heavy/slot-0/holder.json"
        holder.parent.mkdir(parents=True)
        holder.write_text('{"owner":"foreign/run/1","pid":1}', encoding="utf-8")
        before = holder.read_bytes()
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.foreign / ".git"),
                                         "GIT_WORK_TREE": str(self.foreign),
                                         "GIT_COMMON_DIR": str(self.foreign / ".git")}):
            report = self.experiment().run()
        self.assertEqual(report["status"], "complete", report.get("error"))
        self.assertEqual(holder.read_bytes(), before)
        self.assert_drained(report)

    def test_malformed_helper_output_retains_failure_and_diagnostics(self):
        helper = self.parent / "malformed_helper.py"
        for number, text in enumerate(("not-json", "[]")):
            helper.write_text("print(%r)\n" % text, encoding="utf-8")
            self.output = self.parent / ("malformed-%d" % number)
            with mock.patch.object(scope, "HELPER", helper):
                report = self.experiment().run()
            self.assertEqual(report["status"], "error")
            self.assertIn("invalid helper JSON", report["error"])
            self.assert_drained(report)

    def test_internal_worker_cannot_bypass_bounds_or_marker_directory(self):
        valid = {"directory": str(self.parent), "index": 0,
                 "marker": str(self.parent / "exclusive"), "cpu_seconds": 0.01,
                 "memory_bytes": 1024, "deadline_seconds": 1}
        for field, value in (("cpu_seconds", 0.51), ("memory_bytes", 17 * 1024 * 1024),
                             ("deadline_seconds", float("inf")),
                             ("marker", str(self.foreign / "exclusive"))):
            with self.subTest(field=field):
                config = dict(valid)
                config[field] = value
                with self.assertRaises(scope.ExperimentError):
                    scope.workload(config)
                self.assertFalse((self.parent / "ready-0").exists())

    def test_interrupted_acquire_before_json_releases_its_exact_fixture_owner(self):
        helper = self.parent / "delayed_helper.py"
        helper.write_text("import contextlib,io,runpy,sys,time\n"
                          "module=runpy.run_path(%r)\n" % str(scope.HELPER) +
                          "if 'acquire' in sys.argv:\n"
                          " with contextlib.redirect_stdout(io.StringIO()):\n"
                          "  module['main'](sys.argv[1:])\n"
                          " time.sleep(30)\n"
                          "else:\n"
                          " raise SystemExit(module['main'](sys.argv[1:]))\n", encoding="utf-8")
        class Interrupted(scope.Experiment):
            def finish(self, child, timeout=10):
                if child[1]["label"].startswith("acquire-"):
                    deadline = time.monotonic() + 10
                    while not list(self.output.glob("repo-a/.git/forge-steward/locks/heavy/slot-*/holder.json")):
                        if child[0].poll() is not None or time.monotonic() >= deadline:
                            raise AssertionError("delayed helper did not create its fixture slot")
                        time.sleep(0.005)
                    raise scope.ExperimentError("injected acquire interruption before JSON")
                return super().finish(child, timeout)
        with mock.patch.object(scope, "HELPER", helper):
            report = self.experiment(Interrupted).run()
        self.assertEqual(report["status"], "error")
        self.assertIn("before JSON", report["error"])
        self.assert_drained(report)
        self.assertEqual(report["cleanup_errors"], [])
        self.assertEqual(len(report["cleanup_releases"]), 1)
        self.assertFalse(list(self.output.glob("repo-*/.git/forge-steward/locks/heavy/slot-*")))

    def test_partial_start_failure_drains_child_and_releases_fixtures(self):
        class Partial(scope.Experiment):
            def start(self, arguments, label):
                if label == "worker-1":
                    raise OSError("injected partial startup")
                return super().start(arguments, label)
        report = self.experiment(Partial).run()
        self.assertEqual(report["status"], "error")
        self.assertIn("partial startup", report["error"])
        self.assert_drained(report)
        self.assertEqual(report["cleanup_errors"], [])
        self.assertFalse(list(self.output.glob("repo-*/.git/forge-steward/locks/heavy/slot-*")))

    def test_child_failure_drains_all_started_children(self):
        class Failed(scope.Experiment):
            def start(self, arguments, label):
                if label.startswith("worker-"):
                    arguments = [sys.executable, "-c", "raise SystemExit(7)"]
                return super().start(arguments, label)
        report = self.experiment(Failed).run()
        self.assertEqual(report["status"], "error")
        self.assertIn("child exited before ready", report["error"])
        self.assert_drained(report)
        self.assertEqual(report["cleanup_errors"], [])

    def test_overall_deadline_with_started_worker_retains_diagnostics(self):
        class Expired(scope.Experiment):
            def start(self, arguments, label):
                child = super().start(arguments, label)
                if label.startswith("worker-"):
                    self.deadline = time.monotonic() - 1
                return child
        report = self.experiment(Expired).run()
        self.assertEqual(report["status"], "error")
        self.assertIn("deadline", report["error"])
        self.assert_drained(report)
        self.assertTrue((self.output / "results.json").is_file())

    def test_cancellation_after_start_drains_child(self):
        class Cancelled(scope.Experiment):
            def start(self, arguments, label):
                child = super().start(arguments, label)
                if label.startswith("worker-"):
                    raise KeyboardInterrupt("injected cancellation")
                return child
        report = self.experiment(Cancelled).run()
        self.assertEqual(report["status"], "error")
        self.assertIn("KeyboardInterrupt", report["error"])
        self.assert_drained(report)
        self.assertEqual(report["cleanup_errors"], [])

    def test_subprocess_deadline_drains_pending_child(self):
        class Hung(scope.Experiment):
            def command(self, arguments, label):
                if label == "source-commit":
                    self.finish(self.start([sys.executable, "-c", "import time; time.sleep(30)"], "hung"), timeout=0.05)
                return super().command(arguments, label)
        report = self.experiment(Hung).run()
        self.assertIn("subprocess deadline", report["error"])
        self.assert_drained(report)

    @unittest.skipUnless(os.name == "posix", "real SIGTERM cancellation requires POSIX signals")
    def test_cli_sigterm_retains_partial_evidence_and_leaves_no_child(self):
        process = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "--output", str(self.output)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not list(self.output.glob("trial-*/first/ready-0")):
                self.assertIsNone(process.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 2, (stdout, stderr))
            report = json.loads((self.output / "results.json").read_text())
            self.assertEqual(report["status"], "error")
            self.assert_drained(report)
            for command in report["commands"]:
                if command["label"].startswith("worker-"):
                    with self.assertRaises(ProcessLookupError):
                        os.kill(command["pid"], 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_unavailable_telemetry_and_rss_units(self):
        with mock.patch.dict(sys.modules, {"resource": None}):
            metric = scope.peak_memory()
        self.assertIsNone(metric["value"])
        self.assertTrue(metric["unavailable_reason"])
        fake = mock.Mock()
        fake.getrusage.return_value.ru_maxrss = 7
        with mock.patch.dict(sys.modules, {"resource": fake}):
            for system, expected in (("darwin", 7), ("linux", 7168)):
                with mock.patch.object(sys, "platform", system):
                    self.assertEqual(scope.peak_memory()["value"], expected)

    def test_windows_native_handle_closes_only_after_confirmed_exit(self):
        process = mock.Mock(returncode=None)
        with mock.patch.object(scope.os, "name", "nt"):
            with self.assertRaises(scope.ExperimentError):
                scope.close_finished_handle(process)
            process._handle.Close.assert_not_called()
            process.returncode = 0
            self.assertTrue(scope.close_finished_handle(process))
            process._handle.Close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
