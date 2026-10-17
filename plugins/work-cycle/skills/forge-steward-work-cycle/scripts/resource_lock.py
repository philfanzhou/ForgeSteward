#!/usr/bin/env python3
"""Named, capacity-limited locks shared by every worktree of a target repository.

Concurrent work-cycle stages use these locks to queue local verification on
resources they cannot isolate (fixed ports, a local database, a simulator, a
shared remote test environment), to cap heavy builds, and to serialize merges.
The reserved `run` resource lets one work-cycle own a checkout at a time.
State lives in the repository's Git common directory, never in project files.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
HOLDER_FILE = "holder.json"
CAPACITY_FILE = "capacity"
POLL_SECONDS = 1.0
# The `run` resource serializes whole work-cycles in one checkout, so it is always exclusive.
RESERVED_CAPACITY = {"run": 1}


def locks_root(repo):
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError("Target repository directory does not exist: " + str(repo))
    result = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo,
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError("Target is not a readable Git repository: " + str(repo))
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = repo / common
    common = common.resolve()
    if not common.is_dir():
        raise ValueError("Git common directory does not exist: " + str(common))
    return common / "forge-steward" / "locks"


def check_name(name):
    if not NAME.fullmatch(name):
        raise ValueError("Invalid resource name: " + repr(name))


def check_component(label, value):
    if not COMPONENT.fullmatch(value):
        raise ValueError("%s must be 1-64 letters, digits, '.', '_', or '-' and start with a letter or digit"
                         % label)


def attempt_number(text):
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1 or value > 9999:
        raise argparse.ArgumentTypeError("attempt must be a whole number from 1 to 9999")
    return value


def owner_key(run, task, attempt):
    return "%s/%s/%d" % (run, task, attempt)


def error_text(error):
    return getattr(error, "strerror", None) or str(error)


def process_start(pid):
    """Best-effort comparable identity of a running process; the reason is returned when unreadable."""
    if sys.platform.startswith("linux"):
        try:
            stat = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
            fields = stat.rsplit(")", 1)[1].split()
            if len(fields) < 20:
                return None, "process start time is missing from /proc"
            return "linux:" + fields[19], None
        except (OSError, UnicodeError) as error:
            return None, "cannot read process start time: " + error_text(error)
    if os.name == "posix":
        try:
            result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True,
                                    text=True, timeout=2, env=dict(os.environ, LC_ALL="C"),
                                    check=False)
        except (OSError, subprocess.SubprocessError) as error:
            return None, "cannot read process start time: " + error_text(error)
        value = result.stdout.strip()
        if result.returncode or not value:
            return None, "process start time is unavailable: ps did not report it"
        return "ps:" + value, None
    if os.name == "nt":
        return windows_process_start(pid)
    return None, "process start time is unavailable on this platform"


def windows_open_process(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    return ctypes, wintypes, kernel, handle, ctypes.get_last_error()


def windows_process_start(pid):
    ctypes, wintypes, kernel, handle, error = windows_open_process(pid)
    if not handle:
        return None, "cannot open process %d to read its start time (error %d)" % (pid, error)
    try:
        creation = wintypes.FILETIME()
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME)]
        kernel.GetProcessTimes.restype = wintypes.BOOL
        empty = [wintypes.FILETIME() for _ in range(3)]
        if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(empty[0]),
                                      ctypes.byref(empty[1]), ctypes.byref(empty[2])):
            return None, "cannot read process start time (error %d)" % ctypes.get_last_error()
        return "windows:%d" % ((creation.dwHighDateTime << 32) | creation.dwLowDateTime), None
    finally:
        kernel.CloseHandle(handle)


def process_running(pid):
    """True, False, or None when the platform cannot decide without risking the process."""
    if os.name == "nt":
        _, _, kernel, handle, error = windows_open_process(pid)
        if not handle:
            if error == 87:  # ERROR_INVALID_PARAMETER: no such process
                return False
            if error == 5:  # ERROR_ACCESS_DENIED: a process exists
                return True
            return None
        kernel.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def process_liveness(entry):
    """Return (alive|stopped|unknown, detail); the recorded start time guards against PID reuse."""
    pid = entry.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return "unknown", "no owner process ID recorded"
    running = process_running(pid)
    if running is False:
        return "stopped", "owner process %d is not running" % pid
    if running is None:
        return "unknown", "owner process %d cannot be checked" % pid
    recorded = entry.get("process_start")
    current, error = process_start(pid)
    if recorded and current:
        if str(recorded) != str(current):
            return "stopped", "process %d is running with a different start time; the recorded owner stopped" % pid
        return "alive", "owner process %d is running" % pid
    if recorded and not current:
        return "alive", "owner process %d is running; its start time cannot be compared (%s)" % (pid, error)
    return "alive", "owner process %d is running" % pid


def format_age(seconds):
    if seconds is None:
        return None
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        return "%dh %dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dd %dh" % (seconds // 86400, (seconds % 86400) // 3600)


def slot_age(value, now):
    if not isinstance(value, str) or not value:
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return max(0, int((now - at.astimezone(timezone.utc)).total_seconds()))


def resource_dir(root, name, capacity):
    """Create the resource directory and fix its capacity on first use."""
    reserved = RESERVED_CAPACITY.get(name)
    if reserved is not None and capacity != reserved:
        raise ValueError("Resource %s is reserved for run-level ownership and always uses capacity %d"
                         % (name, reserved))
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    marker = path / CAPACITY_FILE
    fd, staged = tempfile.mkstemp(prefix=".capacity-", dir=str(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(str(capacity) + "\n")
        # A hard link never replaces an existing file, so readers only see a complete value.
        os.link(staged, str(marker))
    except FileExistsError:
        saved = int(marker.read_text(encoding="utf-8").strip())
        if saved != capacity:
            raise ValueError("Resource %s already uses capacity %d, not %d" % (name, saved, capacity))
    finally:
        os.unlink(staged)
    return path


def holders(path):
    found = []
    if not path.is_dir():
        return found
    for slot in sorted(path.glob("slot-*")):
        try:
            data = json.loads((slot / HOLDER_FILE).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("holder.json is not an object")
        except (OSError, ValueError, UnicodeError):
            data = {}
        if "owner" not in data and isinstance(data.get("holder"), str):
            data["owner"] = data["holder"]
            data["legacy"] = True
        else:
            data["legacy"] = bool(data.get("legacy"))
        data["slot"] = slot.name
        found.append(data)
    return found


def describe(entry):
    now = datetime.now(timezone.utc)
    age = slot_age(entry.get("acquired_at"), now)
    state, detail = process_liveness(entry)
    return {"resource": entry.get("resource"), "owner": entry.get("owner"), "run": entry.get("run"),
            "task": entry.get("task"), "attempt": entry.get("attempt"), "pid": entry.get("pid"),
            "process_start": entry.get("process_start"),
            "process_start_error": entry.get("process_start_error"), "note": entry.get("note") or "",
            "acquired_at": entry.get("acquired_at"), "age_seconds": age, "age": format_age(age),
            "liveness": state, "liveness_detail": detail, "legacy": bool(entry.get("legacy")),
            "slot": entry.get("slot")}


def try_acquire(root, name, capacity, run, task, attempt, note):
    path = resource_dir(root, name, capacity)
    owner = owner_key(run, task, attempt)
    if any(entry.get("owner") == owner and not entry.get("legacy") for entry in holders(path)):
        return "HELD"
    start, start_error = process_start(os.getpid())
    record = {"resource": name, "owner": owner, "run": run, "task": task, "attempt": attempt,
              "pid": os.getpid(), "process_start": start, "note": note or "",
              "acquired_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    if start_error:
        record["process_start_error"] = start_error
    for index in range(capacity):
        staged = Path(tempfile.mkdtemp(prefix=".tmp-", dir=str(root)))
        try:
            (staged / HOLDER_FILE).write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            # Renaming a directory onto an occupied slot fails, so a slot has exactly one holder.
            os.rename(str(staged), str(path / ("slot-%d" % index)))
            return "ACQUIRED slot-%d" % index
        except OSError:
            continue
        finally:
            if staged.exists():
                shutil.rmtree(str(staged), ignore_errors=True)
    return None


def acquire(root, name, capacity, run, task, attempt, note, wait):
    deadline = time.monotonic() + wait
    while True:
        outcome = try_acquire(root, name, capacity, run, task, attempt, note)
        if outcome:
            return outcome
        if time.monotonic() >= deadline:
            return None
        time.sleep(POLL_SECONDS)


def release(root, name, run, task, attempt):
    owner = owner_key(run, task, attempt)
    path = root / name
    for entry in holders(path):
        if entry.get("legacy") or entry.get("owner") != owner:
            continue
        state, detail = process_liveness(entry)
        # The owner itself may release a slot that is still recorded as live.
        if entry.get("pid") != os.getpid() and state != "stopped":
            raise ValueError("Refusing to release %s from %s: %s. Confirm the owner stopped before recovering a slot"
                             % (owner, name, detail))
        slot = path / entry["slot"]
        retired = Path(tempfile.mkdtemp(prefix=".released-", dir=str(root)))
        os.rmdir(str(retired))
        os.rename(str(slot), str(retired))
        shutil.rmtree(str(retired), ignore_errors=True)
        return entry["slot"]
    raise ValueError("%s does not hold resource %s" % (owner, name))


def status(root, name=None):
    names = [name] if name else sorted(p.name for p in root.glob("*") if p.is_dir() and NAME.fullmatch(p.name))
    report = []
    for item in names:
        path = root / item
        capacity = None
        if (path / CAPACITY_FILE).is_file():
            capacity = int((path / CAPACITY_FILE).read_text(encoding="utf-8").strip() or "0")
        report.append({"resource": item, "capacity": capacity,
                       "holders": [describe(entry) for entry in holders(path)]})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("acquire")
    take.add_argument("resource")
    take.add_argument("--run", required=True)
    take.add_argument("--task", required=True)
    take.add_argument("--attempt", type=attempt_number, default=1)
    take.add_argument("--note")
    take.add_argument("--capacity", type=int, default=1)
    take.add_argument("--wait", type=float, default=0, help="Seconds to keep retrying")
    give = commands.add_parser("release")
    give.add_argument("resource")
    give.add_argument("--run", required=True)
    give.add_argument("--task", required=True)
    give.add_argument("--attempt", type=attempt_number, default=1)
    show = commands.add_parser("status")
    show.add_argument("resource", nargs="?")
    args = parser.parse_args(argv)
    try:
        root = locks_root(args.repo)
        root.mkdir(parents=True, exist_ok=True)
        if args.command == "status":
            if args.resource:
                check_name(args.resource)
            print(json.dumps(status(root, args.resource), ensure_ascii=False, indent=2))
            return 0
        check_name(args.resource)
        check_component("--run", args.run)
        check_component("--task", args.task)
        if args.command == "release":
            print("RELEASED " + release(root, args.resource, args.run, args.task, args.attempt))
            return 0
        if args.capacity < 1 or args.wait < 0:
            parser.error("--capacity must be positive and --wait must not be negative")
        outcome = acquire(root, args.resource, args.capacity, args.run, args.task, args.attempt,
                          args.note, args.wait)
        if outcome:
            print(outcome)
            return 0
        print("BUSY " + json.dumps([describe(entry) for entry in holders(root / args.resource)],
                                   ensure_ascii=False))
        return 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
