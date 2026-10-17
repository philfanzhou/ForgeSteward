#!/usr/bin/env python3
"""Read-only inventory of worktrees and this run's recorded workspace ownership.

The work-cycle orchestrator records every workspace it dispatches in
<run directory>/workspaces.json. This script reports each worktree of the
target repository and whether the cleanup rules allow removing it, so a
cleanup stage can check ownership and every safety condition before running
``git worktree remove`` itself. It never removes, prunes, locks, or unlocks a
worktree and never writes project files.

Exit codes: 0 when the inventory completed, even if nothing is removable, and
2 for an invalid argument, unusable ownership record, or failed Git query.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


OWNERSHIP_FIELDS = ("task", "branch", "workspace", "stage", "status", "updated_at")
OWNERSHIP_STATUSES = ("active", "finished", "failed", "paused")
CONVENTIONAL_SUFFIX = "-forge-steward"


class InventoryError(Exception):
    """The inventory could not be produced; the caller must retain everything."""


def git(cwd, *arguments):
    try:
        result = subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                                text=True, check=False)
    except OSError as exc:
        raise InventoryError("Cannot run git: %s" % exc) from None
    if result.returncode:
        detail = result.stderr.strip() or "exit %d" % result.returncode
        raise InventoryError("git %s failed: %s" % (" ".join(arguments), detail))
    return result.stdout


def canonical(path):
    """Compare paths without symlink, relative-segment, or case differences."""
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def read_worktrees(repo):
    records = []
    record = None
    for token in git(repo, "worktree", "list", "--porcelain", "-z").split("\0"):
        if not token:
            if record is not None:
                records.append(record)
                record = None
            continue
        if token.startswith("worktree "):
            if record is not None:
                records.append(record)
            record = {"path": token[len("worktree "):], "head": None, "branch": None,
                      "detached": False, "locked": None, "prunable": None}
            continue
        if record is None:
            continue
        if token.startswith("HEAD "):
            record["head"] = token[len("HEAD "):]
        elif token.startswith("branch "):
            reference = token[len("branch "):]
            if reference.startswith("refs/heads/"):
                record["branch"] = reference[len("refs/heads/"):]
        elif token == "detached":
            record["detached"] = True
        elif token == "locked" or token.startswith("locked "):
            record["locked"] = token[len("locked "):] if token.startswith("locked ") else ""
        elif token == "prunable" or token.startswith("prunable "):
            record["prunable"] = token[len("prunable "):] if token.startswith("prunable ") else ""
    if record is not None:
        records.append(record)
    if not records:
        raise InventoryError("Git reported no worktrees for %s" % repo)
    return records


def read_ownership(path):
    """Read and validate a run-directory ownership record; return entries by workspace."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InventoryError("Cannot read the ownership record %s: %s" % (path, exc)) from None
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise InventoryError("Invalid JSON in the ownership record %s: %s" % (path, exc)) from None
    if not isinstance(data, list):
        raise InventoryError("The ownership record %s must be a JSON list" % path)
    entries = {}
    for number, entry in enumerate(data, 1):
        where = "ownership record entry %d" % number
        if not isinstance(entry, dict):
            raise InventoryError(where + " must be a JSON object")
        for field in OWNERSHIP_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise InventoryError(where + " needs a non-empty %s string" % field)
        if entry["status"] not in OWNERSHIP_STATUSES:
            raise InventoryError(where + " has an unknown status %r; use %s"
                                 % (entry["status"], ", ".join(OWNERSHIP_STATUSES)))
        workspace = Path(entry["workspace"])
        if not workspace.is_absolute():
            raise InventoryError(where + " workspace must be an absolute path: %r" % entry["workspace"])
        key = canonical(workspace)
        if key in entries:
            raise InventoryError(where + " repeats workspace " + entry["workspace"])
        entries[key] = entry
    return entries


def current_workspaces(records, requested):
    """Explicit --current paths plus the worktree containing the current directory."""
    where = {item["path"]: canonical(item["path"]) for item in records}
    found = set()
    for path in requested:
        found.add(canonical(path))
    try:
        top = git(Path.cwd(), "rev-parse", "--show-toplevel").strip()
    except InventoryError:
        top = None
    if top:
        found.add(canonical(top))
    return found & set(where.values())


def inspect(path):
    """Read working-tree state without writing; unreadable state is never removable."""
    if not Path(path).is_dir():
        return False, False, None
    try:
        output = git(path, "status", "--porcelain")
    except InventoryError as exc:
        return False, False, str(exc)
    dirty = False
    untracked = False
    for line in output.splitlines():
        if line.startswith("??"):
            untracked = True
        elif line.strip():
            dirty = True
    return dirty, untracked, None


def evaluate(record, primary, conventional_root, ownership, currents, active, deletable,
             open_requests):
    path = canonical(record["path"])
    owner = ownership.get(path) if ownership is not None else None
    dirty, untracked, status_error = inspect(record["path"])
    inside_conventional = path == conventional_root or path.startswith(conventional_root + os.sep)
    branch = record["branch"]

    reasons = []
    if path == primary:
        reasons.append("the primary repository worktree")
    if path in currents:
        reasons.append("the workspace running this skill")
    if path in active:
        reasons.append("listed as active by the caller")
    if owner is not None and owner["status"] == "active":
        reasons.append("the owning stage is still active")
    if not inside_conventional:
        if ownership is None:
            reasons.append("outside the conventional workspace directory and no ownership record "
                           "was supplied")
        elif owner is None:
            reasons.append("outside the conventional workspace directory and not recorded by this run")
    if record["detached"]:
        reasons.append("detached HEAD")
    elif not branch:
        reasons.append("no local branch is checked out")
    if record["locked"] is not None:
        reasons.append("locked worktree")
    if record["prunable"] is not None or not Path(record["path"]).is_dir():
        reasons.append("the worktree directory is missing, so prune the record instead")
    if status_error is not None:
        reasons.append("the working tree state could not be read: " + status_error)
    if dirty:
        reasons.append("uncommitted changes")
    if untracked:
        reasons.append("untracked files")
    if branch and branch in open_requests:
        reasons.append("an open Change Request uses branch " + branch)
    if branch and branch not in deletable:
        reasons.append("branch is not confirmed deletable under the merged, closed, or "
                       "missing-upstream rows")

    return {
        "path": record["path"],
        "head": record["head"],
        "branch": branch,
        "detached": record["detached"],
        "locked": record["locked"] is not None,
        "lock_reason": record["locked"] or None,
        "prunable": record["prunable"] is not None,
        "missing": not Path(record["path"]).is_dir(),
        "dirty": dirty,
        "untracked": untracked,
        "status_error": status_error,
        "current": path in currents,
        "active": path in active,
        "inside_conventional": inside_conventional,
        "ownership": owner,
        "removal_allowed": not reasons,
        "retain_reasons": reasons,
    }


def inventory(repo, ownership_path, current, active, deletable, open_requests):
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise InventoryError("Target repository directory does not exist: " + str(repo))
    records = read_worktrees(repo)
    ownership = read_ownership(ownership_path) if ownership_path is not None else None
    primary = canonical(records[0]["path"])
    primary_path = Path(records[0]["path"]).resolve()
    conventional_root = canonical(primary_path.parent / (primary_path.name + CONVENTIONAL_SUFFIX))
    currents = current_workspaces(records, current)
    deletable = set(deletable)
    open_requests = set(open_requests)
    active = {canonical(path) for path in active}

    worktrees = [evaluate(record, primary, conventional_root, ownership, currents, active,
                          deletable, open_requests) for record in records]
    removable = [item["path"] for item in worktrees if item["removal_allowed"]]
    return {
        "repository": str(repo),
        "conventional_root": str(conventional_root),
        "ownership_record": str(ownership_path) if ownership_path is not None else None,
        "ownership_entries": len(ownership) if ownership is not None else 0,
        "current_workspaces": sorted(currents),
        "deletable_branches": sorted(deletable),
        "open_request_branches": sorted(open_requests),
        "worktrees": worktrees,
        "removable": removable,
        "retained": [{"path": item["path"], "reasons": item["retain_reasons"]}
                     for item in worktrees if not item["removal_allowed"]],
    }


def parse(arguments):
    parser = argparse.ArgumentParser(
        description="Read-only inventory of worktrees and recorded workspace ownership. "
                    "It never removes a worktree; removal stays a reviewed cleanup action.")
    parser.add_argument("--repo", required=True, help="local repository to inspect")
    parser.add_argument("--ownership", help="this run's workspaces.json in its run directory")
    parser.add_argument("--current", action="append", default=[],
                        help="workspace path running the cleanup; repeatable")
    parser.add_argument("--active", action="append", default=[],
                        help="workspace path the caller lists as active; repeatable")
    parser.add_argument("--deletable-branch", action="append", default=[],
                        help="branch confirmed deletable under the cleanup table; repeatable")
    parser.add_argument("--open-request", action="append", default=[],
                        help="branch used by an open Change Request; repeatable")
    return parser.parse_args(arguments)


def main(arguments=None):
    arguments = parse(sys.argv[1:] if arguments is None else arguments)
    ownership = Path(arguments.ownership) if arguments.ownership else None
    try:
        report = inventory(arguments.repo, ownership, arguments.current, arguments.active,
                           arguments.deletable_branch, arguments.open_request)
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
