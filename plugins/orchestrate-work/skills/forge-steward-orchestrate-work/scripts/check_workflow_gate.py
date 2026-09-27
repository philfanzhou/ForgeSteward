#!/usr/bin/env python3
"""Rate-limit automatic check-workflow runs in a target repository's local Git metadata."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


COOLDOWN = timedelta(days=7)
RESULTS = {"clean", "pr-open", "incomplete"}
VERSION_FILE = Path(__file__).with_name("VERSION")


def current_version():
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("Invalid bundled VERSION")
    return value


def state_path(repo):
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
    return common / "forge-steward" / "check-workflow.json"


def read_state(path):
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("branch"), str) or not data["branch"]
            or not isinstance(data.get("version"), str) or not data["version"]
            or data.get("result") not in RESULTS
            or not isinstance(data.get("run_at"), str)):
        raise ValueError("Invalid check-workflow state: " + str(path))
    at = datetime.fromisoformat(data["run_at"].replace("Z", "+00:00"))
    if at.tzinfo is None:
        raise ValueError("State timestamp has no timezone: " + str(path))
    if data["result"] == "pr-open" and not data.get("change_request"):
        raise ValueError("State has no change request URL: " + str(path))
    return data, at.astimezone(timezone.utc)


def decide(saved, branch, version, now):
    """Return (run, reason). PR and source-file changes deliberately play no role."""
    if saved is None:
        return True, "no prior run"
    data, at = saved
    if data["branch"] != branch:
        return True, "different default branch"
    age = now - at
    if age < -timedelta(minutes=5):
        raise ValueError("State timestamp is in the future")
    if age < COOLDOWN:
        return False, "seven-day cooldown"
    if data["result"] == "incomplete":
        return True, "previous run incomplete and cooldown elapsed"
    if data["version"] != version:
        return True, "version changed and cooldown elapsed"
    return False, "same version after completed run"


def write_state(path, branch, version, result, change_request, now):
    if result == "pr-open" and not change_request:
        raise ValueError("pr-open requires --change-request")
    if result != "pr-open" and change_request:
        raise ValueError("--change-request only applies to pr-open")
    data = {"schema": 1, "branch": branch, "version": version,
            "run_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "result": result}
    if change_request:
        data["change_request"] = change_request
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".check-workflow-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return data


@contextmanager
def state_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Check-workflow state is locked; inspect the running orchestration before retrying")
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def claim(path, branch, version, now):
    """Atomically decide and reserve one automatic check for this checkout."""
    with state_lock(path):
        run, reason = decide(read_state(path), branch, version, now)
        if run:
            write_state(path, branch, version, "incomplete", None, now)
        return run, reason


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--branch", required=True, help="Default branch name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--claim", action="store_true")
    mode.add_argument("--record", action="store_true")
    parser.add_argument("--result", choices=sorted(RESULTS))
    parser.add_argument("--change-request")
    args = parser.parse_args(argv)
    if not args.branch.strip():
        parser.error("--branch must not be empty")
    if (args.check or args.claim) and (args.result or args.change_request):
        parser.error("--result and --change-request require --record")
    if args.record and not args.result:
        parser.error("--record requires --result")
    try:
        version = current_version()
        path = state_path(args.repo)
        now = datetime.now(timezone.utc)
        if args.check:
            run, reason = decide(read_state(path), args.branch, version, now)
            print(("RUN" if run else "SKIP") + ": " + reason)
            return 1 if run else 0
        if args.claim:
            run, reason = claim(path, args.branch, version, now)
            print(("RUN" if run else "SKIP") + ": " + reason)
            return 1 if run else 0
        with state_lock(path):
            data = write_state(path, args.branch, version, args.result, args.change_request, now)
        print("RECORDED: " + json.dumps(data, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
