#!/usr/bin/env python3
"""Keep work-cycle run records with per-stage timings in a repository's Git metadata.

Each run gets runs/<run id>/ under <git common dir>/forge-steward/: run.json,
an append-only events.jsonl and one evidence directory per task. Records
never touch version-controlled files; prune only removes run directories
this script created.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time


MARKER = "forge-steward-run-record"
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{4}")
TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
STATUSES = ("started", "finished", "failed", "wait-start", "wait-end")
WAITS = ("ci", "lock", "review", "external", "other")
MAX_DETAIL = 1000


def runs_root(repo):
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
    return common / "forge-steward" / "runs"


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(text):
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("Timestamp has no timezone: " + text)
    return moment.astimezone(timezone.utc)


def run_dir(root, run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run id: " + repr(run_id))
    path = root / run_id
    if not (path / "run.json").is_file():
        raise ValueError("Unknown run: " + run_id)
    return path


def start(root, cycles, now):
    root.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)
        path = root / run_id
        try:
            path.mkdir()
            break
        except FileExistsError:
            continue
    (path / "run.json").write_text(json.dumps({"created_by": MARKER, "run_id": run_id,
                                               "created_at": stamp(now), "cycles": cycles},
                                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path / "events.jsonl").touch()
    return run_id, path


def task_dir(path, task):
    if not TASK.fullmatch(task):
        raise ValueError("Invalid task id: " + repr(task))
    target = path / task
    target.mkdir(exist_ok=True)
    return target


def add_event(path, task, stage, status, wait, detail, moment):
    if status not in STATUSES:
        raise ValueError("Invalid status: " + status)
    if status.startswith("wait-") and wait not in WAITS:
        raise ValueError("wait-start and wait-end need --wait " + "/".join(WAITS))
    task_dir(path, task)
    record = {"at": stamp(moment), "task": task, "stage": stage, "status": status}
    if wait:
        record["wait"] = wait
    if detail:
        record["detail"] = detail.replace("\r", " ").replace("\n", " ")[:MAX_DETAIL]
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    # A short directory lock serializes appends; O_APPEND alone is not atomic on every OS.
    guard = path / ".events.lock"
    deadline = time.monotonic() + 10
    while True:
        try:
            os.mkdir(str(guard))
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise ValueError("Timed out waiting for " + str(guard))
            time.sleep(0.01)
    try:
        fd = os.open(str(path / "events.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    finally:
        os.rmdir(str(guard))
    return record


def read_events(path):
    events = []
    for number, line in enumerate((path / "events.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                raise ValueError("Corrupt event on line %d" % number)
    return events


def summarize(path):
    events = sorted(read_events(path), key=lambda e: e["at"])
    tasks = {}
    for event in events:
        moment = parse(event["at"])
        item = tasks.setdefault(event["task"], {"task": event["task"], "stage": event["stage"],
                                                "started": None, "ended": None, "result": "running",
                                                "waits": {}, "_open": {}})
        if event["status"] == "started" and item["started"] is None:
            item["started"] = moment
        elif event["status"] in ("finished", "failed"):
            item["ended"] = moment
            item["result"] = event["status"]
        elif event["status"] == "wait-start":
            item["_open"][event["wait"]] = moment
        elif event["status"] == "wait-end" and event["wait"] in item["_open"]:
            begun = item["_open"].pop(event["wait"])
            item["waits"][event["wait"]] = item["waits"].get(event["wait"], 0) + (moment - begun).total_seconds()
    stages, waits = {}, {}
    report = []
    for item in tasks.values():
        seconds = None
        if item["started"] and item["ended"]:
            seconds = (item["ended"] - item["started"]).total_seconds()
            stages[item["stage"]] = stages.get(item["stage"], 0) + seconds
        for kind, value in item["waits"].items():
            waits[kind] = waits.get(kind, 0) + value
        report.append({"task": item["task"], "stage": item["stage"], "result": item["result"],
                       "seconds": seconds, "waits": item["waits"]})
    wall = None
    if events:
        wall = (parse(events[-1]["at"]) - parse(events[0]["at"])).total_seconds()
    return {"run_id": path.name, "wall_seconds": wall, "stage_seconds": stages,
            "wait_seconds": waits, "tasks": report}


def prune(root, keep, current=None):
    runs = []
    for path in root.glob("*"):
        if not (path.is_dir() and RUN_ID.fullmatch(path.name)):
            continue
        try:
            data = json.loads((path / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("created_by") == MARKER:
            runs.append((data.get("created_at", ""), path))
    runs.sort(reverse=True)
    removed = []
    for _, path in runs[keep:]:
        if path.name != current:
            shutil.rmtree(str(path))
            removed.append(path.name)
    return sorted(removed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    begin.add_argument("--cycles", type=int, required=True)
    begin.add_argument("--keep", type=int, default=20)
    note = commands.add_parser("event")
    note.add_argument("--run", required=True)
    note.add_argument("--task", required=True)
    note.add_argument("--stage", required=True)
    note.add_argument("--status", required=True, choices=STATUSES)
    note.add_argument("--wait", choices=WAITS)
    note.add_argument("--detail")
    note.add_argument("--at", help="ISO timestamp with timezone; defaults to now")
    where = commands.add_parser("task-dir")
    where.add_argument("--run", required=True)
    where.add_argument("--task", required=True)
    show = commands.add_parser("summary")
    show.add_argument("--run", required=True)
    trim = commands.add_parser("prune")
    trim.add_argument("--keep", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        root = runs_root(args.repo)
        now = datetime.now(timezone.utc)
        if args.command == "start":
            if args.cycles < 1 or args.keep < 1:
                parser.error("--cycles and --keep must be positive")
            run_id, path = start(root, args.cycles, now)
            prune(root, args.keep, current=run_id)
            print(json.dumps({"run_id": run_id, "path": str(path)}, ensure_ascii=False))
        elif args.command == "event":
            moment = parse(args.at) if args.at else now
            record = add_event(run_dir(root, args.run), args.task, args.stage, args.status,
                               args.wait, args.detail, moment)
            print(json.dumps(record, ensure_ascii=False))
        elif args.command == "task-dir":
            print(task_dir(run_dir(root, args.run), args.task))
        elif args.command == "summary":
            print(json.dumps(summarize(run_dir(root, args.run)), ensure_ascii=False, indent=2))
        else:
            if args.keep < 1:
                parser.error("--keep must be positive")
            root.mkdir(parents=True, exist_ok=True)
            print(json.dumps({"removed": prune(root, args.keep)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
