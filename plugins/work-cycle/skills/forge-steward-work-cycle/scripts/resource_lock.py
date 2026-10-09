#!/usr/bin/env python3
"""Named, capacity-limited locks shared by every worktree of a target repository.

Concurrent work-cycle stages use these locks to queue local verification on
resources they cannot isolate (fixed ports, a local database, a simulator, a
shared remote test environment), to cap heavy builds, and to serialize merges.
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
HOLDER_FILE = "holder.json"
CAPACITY_FILE = "capacity"
POLL_SECONDS = 1.0


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


def check_holder(holder):
    if not holder or len(holder) > 200 or any(c in holder for c in "\r\n"):
        raise ValueError("Holder must be a non-empty single line of at most 200 characters")


def resource_dir(root, name, capacity):
    """Create the resource directory and fix its capacity on first use."""
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
        except (OSError, ValueError):
            data = {"holder": None}
        data["slot"] = slot.name
        found.append(data)
    return found


def try_acquire(root, name, capacity, holder, note):
    path = resource_dir(root, name, capacity)
    if any(entry.get("holder") == holder for entry in holders(path)):
        return "HELD"
    record = {"resource": name, "holder": holder, "note": note or "",
              "acquired_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
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


def acquire(root, name, capacity, holder, note, wait):
    deadline = time.monotonic() + wait
    while True:
        outcome = try_acquire(root, name, capacity, holder, note)
        if outcome:
            return outcome
        if time.monotonic() >= deadline:
            return None
        time.sleep(POLL_SECONDS)


def release(root, name, holder):
    path = root / name
    for entry in holders(path):
        if entry.get("holder") == holder:
            slot = path / entry["slot"]
            retired = Path(tempfile.mkdtemp(prefix=".released-", dir=str(root)))
            os.rmdir(str(retired))
            os.rename(str(slot), str(retired))
            shutil.rmtree(str(retired), ignore_errors=True)
            return entry["slot"]
    raise ValueError("%s does not hold resource %s" % (holder, name))


def status(root, name=None):
    names = [name] if name else sorted(p.name for p in root.glob("*") if p.is_dir() and NAME.fullmatch(p.name))
    report = []
    for item in names:
        path = root / item
        capacity = None
        if (path / CAPACITY_FILE).is_file():
            capacity = int((path / CAPACITY_FILE).read_text(encoding="utf-8").strip() or "0")
        report.append({"resource": item, "capacity": capacity, "holders": holders(path)})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("acquire")
    take.add_argument("resource")
    take.add_argument("--holder", required=True)
    take.add_argument("--note")
    take.add_argument("--capacity", type=int, default=1)
    take.add_argument("--wait", type=float, default=0, help="Seconds to keep retrying")
    give = commands.add_parser("release")
    give.add_argument("resource")
    give.add_argument("--holder", required=True)
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
        check_holder(args.holder)
        if args.command == "release":
            print("RELEASED " + release(root, args.resource, args.holder))
            return 0
        if args.capacity < 1 or args.wait < 0:
            parser.error("--capacity must be positive and --wait must not be negative")
        outcome = acquire(root, args.resource, args.capacity, args.holder, args.note, args.wait)
        if outcome:
            print(outcome)
            return 0
        print("BUSY " + json.dumps(holders(root / args.resource), ensure_ascii=False))
        return 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
