#!/usr/bin/env python3
"""Measure repository lock scope using only new disposable local fixtures."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/resource_lock.py"
CONDITIONS = ("serial", "isolated", "shared-identity", "same-repository")


class ExperimentError(Exception):
    pass


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unavailable(reason):
    return {"value": None, "unavailable_reason": reason}


def peak_memory():
    try:
        import resource
    except ImportError:
        return unavailable("POSIX resource is unavailable; no Windows RSS probe is used")
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        return unavailable("ru_maxrss units are not verified on this platform")
    native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"value": native if sys.platform == "darwin" else native * 1024,
            "unit": "bytes", "native_value": native,
            "native_unit": "bytes" if sys.platform == "darwin" else "KiB"}


def environment():
    try:
        load = {"value": list(os.getloadavg()), "unit": "runnable tasks, 1/5/15 minutes"}
    except (AttributeError, OSError) as error:
        load = unavailable("os.getloadavg is unavailable: " + str(error))
    memory = unavailable("No verified read-only host memory-pressure indicator on this platform")
    if sys.platform.startswith("linux"):
        try:
            memory = {"value": Path("/proc/pressure/memory").read_text(encoding="utf-8")[:4096],
                      "unit": "Linux PSI text; avg percentages and total microseconds"}
        except OSError as error:
            memory = unavailable(str(error))
    return {"os": platform.platform(), "python": platform.python_version(),
            "logical_cpus": os.cpu_count(), "host_load": load, "memory_pressure": memory,
            "background_load": "Uncontrolled; these bounded trials cannot establish host saturation or production throughput"}


def child_environment():
    # Inherited Git overrides must never redirect fixture commands to a real repository.
    result = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    result.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return result


def wait_for(path, deadline):
    while not path.exists():
        if time.monotonic() >= deadline:
            raise ExperimentError("worker deadline waiting for " + path.name)
        time.sleep(0.005)


def workload(config):
    """Internal child; all paths come from a parent-created configuration."""
    directory = Path(config["directory"])
    index = config["index"]
    marker = Path(config["marker"])
    if index not in (0, 1) or marker.parent != directory or marker.name not in ("exclusive", "exclusive-%d" % index):
        raise ExperimentError("invalid internal worker identity/path")
    for name, maximum in (("cpu_seconds", 0.5), ("memory_bytes", 16 * 1024 * 1024), ("deadline_seconds", 10)):
        if not math.isfinite(config[name]) or not 0 < config[name] <= maximum:
            raise ExperimentError("invalid internal worker bound: " + name)
    deadline = time.monotonic() + config["deadline_seconds"]
    (directory / ("ready-%d" % index)).touch(exist_ok=False)
    wait_for(directory / "go", deadline)
    active_start = time.time()
    created = False
    collision = False
    try:
        if config["role"] == "contender":
            wait_for(directory / "entered-0", deadline)
        try:
            with marker.open("x", encoding="utf-8") as stream:
                stream.write(str(index))
            created = True
        except FileExistsError:
            collision = True
        if config["role"] == "owner":
            (directory / "entered-0").touch(exist_ok=False)
            wait_for(directory / "attempted-1", deadline)
        elif config["role"] == "contender":
            (directory / "attempted-1").touch(exist_ok=False)
        start_wall = time.monotonic()
        work_start = time.time()
        start_cpu = time.process_time()
        allocation = bytearray(config["memory_bytes"])
        for offset in range(0, len(allocation), 4096):
            allocation[offset] = 1
        number = 1
        while time.process_time() - start_cpu < config["cpu_seconds"]:
            for _ in range(200):
                number = (number * 17 + 3) % 1000003
            if time.monotonic() >= deadline:
                raise ExperimentError("worker workload deadline")
        cpu = time.process_time() - start_cpu
        wall = time.monotonic() - start_wall
        done = time.time()
        (directory / ("done-%d" % index)).touch(exist_ok=False)
        if config["paired"]:
            wait_for(directory / ("done-%d" % (1 - index)), deadline)
        return {"worker": index, "pid": os.getpid(), "collision": collision,
                "marker_created": created, "active_start": active_start,
                "active_end": time.time(), "work_start": work_start, "work_end": done,
                "wall_seconds": wall, "cpu_seconds": cpu,
                "configured_allocation_bytes": len(allocation), "peak_rss": peak_memory()}
    finally:
        if created:
            marker.unlink()


class Experiment:
    def __init__(self, output, trials=3, cpu_seconds=0.25, memory_mib=4, deadline_seconds=60):
        self.output = Path(output).absolute()
        self.options = {"workers": 2, "trials": trials, "cpu_seconds": cpu_seconds,
                        "memory_mib": memory_mib, "deadline_seconds": deadline_seconds}
        self.processes = []
        self.held = []
        self.report = {"schema_version": 1, "status": "running", "options": self.options,
                       "trials": [], "commands": [], "cleanup_errors": []}

    def validate(self):
        options = self.options
        if isinstance(options["trials"], bool) or not isinstance(options["trials"], int) or not 1 <= options["trials"] <= 5:
            raise ExperimentError("trials must be a whole number from 1 to 5")
        for name, minimum, maximum in (("cpu_seconds", 0, 0.5), ("memory_mib", 0, 16), ("deadline_seconds", 0, 120)):
            value = options[name]
            if not math.isfinite(value) or not minimum < value <= maximum:
                raise ExperimentError("%s must be finite, greater than %s and at most %s" % (name, minimum, maximum))
        if self.output.is_symlink():
            raise ExperimentError("output must not be a symlink")
        if not self.output.parent.is_dir():
            raise ExperimentError("output parent must already exist")
        if self.output.exists():
            raise ExperimentError("output must be a new directory")
        # System temporary parents can themselves be aliases (for example /var on macOS).
        self.output = self.output.parent.resolve() / self.output.name

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise ExperimentError("overall experiment deadline")
        return left

    def start(self, arguments, label):
        self.remaining()
        record = {"label": label, "argv": [str(a) for a in arguments], "started": time.monotonic()}
        self.report["commands"].append(record)
        process = subprocess.Popen(record["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=child_environment())
        record["pid"] = process.pid
        self.processes.append((process, record))
        return process, record

    def finish(self, child, timeout=10):
        process, record = child
        try:
            stdout, stderr = process.communicate(timeout=min(timeout, self.remaining()))
        except subprocess.TimeoutExpired as error:
            raise ExperimentError(record["label"] + " subprocess deadline") from error
        record.update(exit=process.returncode, stdout=stdout, stderr=stderr,
                      finished=time.monotonic())
        record["elapsed_seconds"] = record["finished"] - record["started"]
        return record

    def command(self, arguments, label):
        result = self.finish(self.start(arguments, label))
        if result["exit"]:
            raise ExperimentError("%s exited %d: %s" % (label, result["exit"], result["stderr"] or result["stdout"]))
        return result

    def lock_arguments(self, repo, action, owner, wait=0):
        arguments = [sys.executable, "-B", str(HELPER), "--repo", str(repo), action, "heavy"]
        if action != "status":
            arguments += ["--run", "scope-experiment", "--task", owner, "--attempt", "1"]
        if action == "acquire":
            arguments += ["--capacity", "1", "--wait", str(wait), "--json"]
        return arguments

    def acquisition(self, repo, owner, wait=0, expected="acquired"):
        child = self.start(self.lock_arguments(repo, "acquire", owner, wait), "acquire-" + owner)
        child[1]["fixture_owner"] = [str(repo), owner]
        record = self.finish(child)
        self.check_acquisition(record, repo, owner, expected)
        return record

    def check_acquisition(self, record, repo, owner, expected):
        try:
            result = json.loads(record["stdout"])
        except (ValueError, KeyError) as error:
            raise ExperimentError("invalid helper JSON: " + str(record)) from error
        record["acquire_result"] = result
        if not isinstance(result, dict):
            raise ExperimentError("invalid helper JSON object")
        record["accounted"] = True
        if result.get("result") in ("acquired", "held") and record["exit"] == 0:
            self.held.append((repo, owner))
        if record["exit"] != (1 if expected == "busy" else 0) or result.get("result") != expected:
            raise ExperimentError("unexpected helper result: " + str(record))

    def release(self, repo, owner):
        result = self.command(self.lock_arguments(repo, "release", owner), "release-" + owner)
        self.held.remove((repo, owner))
        return result

    def workers(self, directory, paired, shared=False, only=None):
        directory.mkdir()
        children = []
        for index in ([only] if only is not None else [0, 1]):
            config = {"directory": str(directory), "index": index, "paired": paired,
                      "role": ("owner" if index == 0 else "contender") if shared else "isolated",
                      "marker": str(directory / ("exclusive" if shared else "exclusive-%d" % index)),
                      "cpu_seconds": self.options["cpu_seconds"],
                      "memory_bytes": int(self.options["memory_mib"] * 1024 * 1024),
                      "deadline_seconds": min(10, self.remaining())}
            config_path = directory / ("worker-%d.json" % index)
            save(config_path, config)
            children.append(self.start([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(config_path)], "worker-%d" % index))
        for index in ([only] if only is not None else [0, 1]):
            while not (directory / ("ready-%d" % index)).exists():
                self.remaining()
                if any(p.poll() is not None for p, _ in children):
                    raise ExperimentError("child exited before ready")
                time.sleep(0.005)
        (directory / "go").touch(exist_ok=False)
        results = []
        for child in children:
            record = self.finish(child)
            if record["exit"]:
                raise ExperimentError("worker failure: " + record["stderr"])
            try:
                results.append(json.loads(record["stdout"]))
            except ValueError as error:
                raise ExperimentError("invalid worker JSON") from error
        return results

    def trial(self, number, condition, repos):
        directory = self.output / ("trial-%d-%s" % (number, condition))
        directory.mkdir()
        row = {"trial": number, "condition": condition, "workers": [], "acquisitions": []}
        self.report["trials"].append(row)
        start = time.monotonic()
        owners = ["t%d-%s-%d" % (number, condition, i) for i in range(2)]
        if condition in ("serial", "same-repository"):
            repo0, repo1 = (repos[0], repos[0]) if condition == "same-repository" else repos
            row["acquisitions"].append(self.acquisition(repo0, owners[0]))
            row["workers"] += self.workers(directory / "first", False, only=0)
            if condition == "same-repository":
                busy = self.acquisition(repo1, owners[1], expected="busy")
                row["busy"] = busy
                if [h["owner"] for h in busy["acquire_result"]["holders"]] != ["scope-experiment/" + owners[0] + "/1"]:
                    raise ExperimentError("busy response did not preserve actual holder")
                pending = self.start(self.lock_arguments(repo1, "acquire", owners[1], wait=3), "wait-acquire")
                pending[1]["fixture_owner"] = [str(repo1), owners[1]]
                until = time.monotonic() + 0.2
                while time.monotonic() < until:
                    self.remaining()
                    if pending[0].poll() is not None:
                        raise ExperimentError("waiting acquisition ended before owned release")
                    time.sleep(0.005)
                row["release_started"] = time.monotonic()
                self.release(repo0, owners[0])
                row["release_finished"] = time.monotonic()
                acquired = self.finish(pending, timeout=6)
                self.check_acquisition(acquired, repo1, owners[1], "acquired")
                row["acquisitions"].append(acquired)
            else:
                self.release(repo0, owners[0])
                row["acquisitions"].append(self.acquisition(repo1, owners[1]))
            row["workers"] += self.workers(directory / "second", False, only=1)
            self.release(repo1, owners[1])
        else:
            for repo, owner in zip(repos, owners):
                row["acquisitions"].append(self.acquisition(repo, owner))
            row["workers"] = self.workers(directory / "pair", True, shared=condition == "shared-identity")
            for repo, owner in zip(repos, owners):
                self.release(repo, owner)
        row["elapsed_seconds"] = time.monotonic() - start
        workers = row["workers"]
        row["collisions"] = sum(w["collision"] for w in workers)
        row["overlap_seconds"] = max(0, min(w["active_end"] for w in workers) - max(w["active_start"] for w in workers))
        row["peak_active_workers"] = 2 if row["overlap_seconds"] > 0 else 1
        if row["collisions"] != (1 if condition == "shared-identity" else 0):
            raise ExperimentError("unexpected simulated identity collision count")
        if condition in ("isolated", "shared-identity") and row["peak_active_workers"] != 2:
            raise ExperimentError("paired worker entry did not overlap")

    def cleanup(self):
        # Every successfully started child is drained, including partial startup.
        for process, record in self.processes:
            if process.poll() is None:
                process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=2)
            if "exit" not in record:
                record.update(exit=process.returncode, stdout=stdout, stderr=stderr,
                              finished=time.monotonic(), interrupted=True)
            record["drained"] = True
            if record.get("fixture_owner") and not record.get("accounted"):
                try:
                    result = json.loads(record["stdout"])
                    if record["exit"] == 0 and isinstance(result, dict) and result.get("result") in ("acquired", "held"):
                        repo, owner = record["fixture_owner"]
                        self.held.append((Path(repo), owner))
                except ValueError:
                    pass
        # Only these new fixture repositories and exact acquired owners are used.
        for repo, owner in list(self.held):
            try:
                result = subprocess.run(self.lock_arguments(repo, "release", owner), capture_output=True,
                                        text=True, timeout=5, env=child_environment())
                self.report.setdefault("cleanup_releases", []).append({"owner": owner, "exit": result.returncode,
                                                                       "stdout": result.stdout, "stderr": result.stderr})
                if result.returncode:
                    raise ExperimentError("fixture release failed: " + result.stderr)
                self.held.remove((repo, owner))
            except (OSError, subprocess.SubprocessError, ExperimentError) as error:
                self.report["cleanup_errors"].append(str(error))

    def run(self):
        self.validate()
        self.output.mkdir(mode=0o700)  # Exclusive; never adopt, overwrite or delete an existing path.
        self.deadline = time.monotonic() + self.options["deadline_seconds"]
        self.report["started_utc"] = datetime.now(timezone.utc).isoformat()
        self.report["environment_before"] = environment()
        self.report["units"] = {"durations": "monotonic seconds; process-local on Python 3.9/macOS",
                                "worker_timestamps": "Unix epoch seconds; cross-process, subject to wall-clock adjustments",
                                "command_timestamps": "parent monotonic seconds", "cpu": "process CPU seconds",
                                "rss": "bytes, lifetime child peak", "allocation": "explicit bytes, not total RSS"}
        try:
            self.report["experiment_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            self.report["helper_sha256"] = hashlib.sha256(HELPER.read_bytes()).hexdigest()
            self.report["source_commit"] = self.command(["git", "-C", str(ROOT), "rev-parse", "HEAD"], "source-commit")["stdout"].strip()
            repos = [self.output / "repo-a", self.output / "repo-b"]
            template = self.output / "empty-git-template"
            template.mkdir()
            for repo in repos:
                repo.mkdir()
                self.command(["git", "-C", str(repo), "init", "--quiet", "--template=" + str(template)], "fixture-init")
            for number in range(1, self.options["trials"] + 1):
                for condition in CONDITIONS:
                    self.trial(number, condition, repos)
                    save(self.output / "results.json", self.report)
            for repo in repos:
                record = self.command(self.lock_arguments(repo, "status", "unused"), "final-status")
                if any(r["holders"] for r in json.loads(record["stdout"])):
                    raise ExperimentError("fixture holder survived successful experiment")
            self.report["status"] = "complete"
        except (Exception, KeyboardInterrupt) as error:
            self.report["status"] = "error"
            self.report["error"] = type(error).__name__ + ": " + str(error)
        finally:
            self.cleanup()
            self.report["environment_after"] = environment()
            if self.report["cleanup_errors"]:
                self.report["status"] = "error"
            self.report["finished_utc"] = datetime.now(timezone.utc).isoformat()
            save(self.output / "results.json", self.report)
        return self.report


def cancel(signum, frame):
    raise KeyboardInterrupt("cancelled by signal %d" % signum)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--cpu-seconds", type=float, default=0.25)
    parser.add_argument("--memory-mib", type=float, default=4)
    parser.add_argument("--deadline-seconds", type=float, default=60)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        try:
            print(json.dumps(workload(json.loads(args.worker.read_text(encoding="utf-8")))))
            return 0
        except (Exception, KeyboardInterrupt) as error:
            print(type(error).__name__ + ": " + str(error), file=sys.stderr)
            return 2
    if args.output is None:
        parser.error("--output is required")
    previous = signal.signal(signal.SIGTERM, cancel)
    try:
        report = Experiment(args.output, args.trials, args.cpu_seconds, args.memory_mib, args.deadline_seconds).run()
        print(json.dumps({"status": report["status"], "results": str(args.output.absolute() / "results.json"),
                          "error": report.get("error")}))
        return 0 if report["status"] == "complete" else 2
    except (OSError, ValueError, ExperimentError) as error:
        print("experiment error: " + str(error), file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
