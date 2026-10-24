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
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys


OWNERSHIP_FIELDS = ("task", "workspace", "stage", "status", "updated_at")
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
        if "branch" not in entry or (entry["branch"] is not None
                                     and not isinstance(entry["branch"], str)):
            raise InventoryError(where + " needs a branch string or null")
        if "detached" in entry and not isinstance(entry["detached"], bool):
            raise InventoryError(where + " detached must be a boolean")
        if "disposable" in entry and not isinstance(entry["disposable"], bool):
            raise InventoryError(where + " disposable must be a boolean")
        if "head" in entry and (not isinstance(entry["head"], str)
                                or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",
                                                entry["head"]) is None):
            raise InventoryError(where + " head must be a full 40- or 64-digit Git object ID")
        entry = dict(entry)
        if isinstance(entry["branch"], str):
            entry["branch"] = entry["branch"].strip() or None
        if "head" in entry:
            entry["head"] = entry["head"].lower()
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


def identity_reasons(owner, record):
    """Ownership identity alone never authorizes detached disposal."""
    reasons = []
    branch = owner["branch"]
    detached = owner.get("detached")
    head = owner.get("head")
    if branch is None:
        if detached is not True or head is None:
            reasons.append("unverified ownership: empty/null branch needs detached true and a full head")
        if detached is False:
            reasons.append("ownership branch and detached flag disagree")
    elif detached is True:
        reasons.append("ownership branch and detached flag disagree")
    if detached is True and not record["detached"]:
        reasons.append("recorded detached identity does not match the attached worktree")
    if branch is not None and branch != record["branch"]:
        reasons.append("recorded branch does not match the worktree branch")
    if head is not None and head != record["head"]:
        reasons.append("recorded head does not match the worktree head")
    return reasons


def read_disposal(path):
    """Read cleanup's explicit facts; this file never grants ownership by itself."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InventoryError("Cannot read disposal checks %s: %s" % (path, exc)) from None
    if not isinstance(data, list):
        raise InventoryError("Disposal checks must be a JSON list")
    entries = {}
    for entry in data:
        if (not isinstance(entry, dict) or not isinstance(entry.get("workspace"), str)
                or not Path(entry["workspace"]).is_absolute()):
            raise InventoryError("Each disposal check needs an absolute workspace path")
        key = canonical(entry["workspace"])
        if key in entries:
            raise InventoryError("Disposal checks repeat workspace " + entry["workspace"])
        entries[key] = entry
    return entries


def saved_file(value, run_dir, workspace):
    """Evidence must survive disposal in this run's metadata, not via a symlink into it."""
    if not isinstance(value, str) or not Path(value).is_absolute():
        return False
    path = canonical(value)
    if (not path.startswith(canonical(run_dir) + os.sep)
            or path == workspace or path.startswith(workspace + os.sep)):
        return False
    try:
        with open(value, "rb") as stream:
            return bool(stream.read(1))
    except OSError:
        return False


def detached_checks(record, owner, checks, run_dir, ignored, mainline):
    """Combine recorded ownership, live Git facts, and explicit caller host checks."""
    reasons, method, recovery = [], None, None
    if owner is None or owner.get("disposable") is not True:
        reasons.append("detached HEAD: not explicitly recorded as disposable by this run")
    if owner is None or owner["status"] != "finished":
        reasons.append("detached HEAD: the owning stage is not confirmed finished")
    if checks is None:
        return reasons + ["detached HEAD: disposal checks were not supplied"], method, recovery
    if (owner is None or checks.get("task") != owner["task"]
            or checks.get("owner_updated_at") != owner["updated_at"]
            or checks.get("head") != record["head"]):
        reasons.append("disposal checks do not match the current owner and head")
    try:
        checked_at = datetime.fromisoformat(str(checks.get("checked_at", "")).replace("Z", "+00:00"))
        valid_time = checked_at.utcoffset() is not None and checked_at.utcoffset().total_seconds() == 0
    except ValueError:
        valid_time = False
    if not valid_time:
        reasons.append("disposal checks need a UTC checked_at time")
    if checks.get("inactive") is not True:
        reasons.append("no confirmation that all stages and conversations have stopped using it")
    if checks.get("requests_clear") is not True:
        reasons.append("no confirmation that no open Change Request uses the workspace or head")
    evidence = checks.get("evidence")
    workspace = canonical(record["path"])
    if (checks.get("evidence_complete") is not True
            or not saved_file(checks.get("handoff"), run_dir, workspace)
            or not isinstance(evidence, list) or not evidence
            or not all(saved_file(path, run_dir, workspace) for path in evidence)):
        reasons.append("complete handoff and evidence are not saved outside the workspace in this run")
    if (not isinstance(checks.get("ignored_paths"), list)
            or checks["ignored_paths"] != ignored):
        reasons.append("ignored files have not all been reviewed and confirmed dispensable")
    lifecycle = checks.get("lifecycle", {})
    if isinstance(lifecycle, dict) and lifecycle.get("kind") == "git":
        method = "git worktree remove"
    elif (isinstance(lifecycle, dict) and lifecycle.get("kind") == "host"
          and isinstance(lifecycle.get("artifact"), str) and lifecycle["artifact"].strip()
          and lifecycle.get("archive_supported") is True):
        method = "host archive"
    else:
        reasons.append("ordinary Git or supported host archive lifecycle is not confirmed")
    proof = checks.get("recovery", {})
    if isinstance(proof, dict) and proof.get("kind") == "mainline":
        reference = proof.get("ref")
        if (isinstance(reference, str) and reference == mainline
                and reference.startswith("refs/remotes/")):
            try:
                tip = git(record["path"], "show-ref", "--verify", "--hash", reference).strip()
                unique = git(record["path"], "rev-list", record["head"], "--not", reference)
                if tip == proof.get("tip") and not unique.strip():
                    recovery = {"kind": "mainline", "ref": reference, "tip": tip}
            except InventoryError:
                pass
    elif (isinstance(proof, dict) and proof.get("kind") == "request"
          and proof.get("state") in ("merged", "closed") and proof.get("restorable") is True
          and proof.get("head") == record["head"] and isinstance(proof.get("url"), str)
          and re.match(r"https?://[^/]+/.+", proof["url"])):
        recovery = dict(proof)
    if recovery is None:
        reasons.append("head has no verified durable mainline or restorable closed-request recovery")
    return reasons, method, recovery


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
        return False, False, [], None
    try:
        output = git(path, "--no-optional-locks", "status", "--porcelain")
        ignored = sorted(filter(None, git(path, "ls-files", "--others", "--ignored",
                                          "--exclude-standard", "-z").split("\0")))
    except InventoryError as exc:
        return False, False, [], str(exc)
    dirty = False
    untracked = False
    for line in output.splitlines():
        if line.startswith("??"):
            untracked = True
        elif line.strip():
            dirty = True
    return dirty, untracked, ignored, None


def evaluate(record, primary, conventional_root, ownership, currents, active, deletable,
             open_requests, disposal, run_dir, mainline):
    path = canonical(record["path"])
    owner = ownership.get(path) if ownership is not None else None
    dirty, untracked, ignored, status_error = inspect(record["path"])
    inside_conventional = path == conventional_root or path.startswith(conventional_root + os.sep)
    branch = record["branch"]
    owner_reasons = identity_reasons(owner, record) if owner is not None else []

    reasons = list(owner_reasons)
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
    method, recovery = None, None
    checks = disposal.get(path)
    if record["detached"]:
        detached_reasons, method, recovery = detached_checks(
            record, owner, checks, run_dir, ignored, mainline)
        reasons.extend(detached_reasons)
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
        "ignored_paths": ignored,
        "status_error": status_error,
        "current": path in currents,
        "active": path in active,
        "inside_conventional": inside_conventional,
        "ownership": owner,
        "ownership_identity_verified": not owner_reasons if owner is not None else False,
        "ownership_identity_reasons": owner_reasons,
        "disposal_checks": checks,
        "reclamation_method": method,
        "recovery": recovery,
        "removal_allowed": not reasons,
        "retain_reasons": reasons,
    }


def inventory(repo, ownership_path, current, active, deletable, open_requests,
              disposal_path=None, mainline=None):
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise InventoryError("Target repository directory does not exist: " + str(repo))
    records = read_worktrees(repo)
    ownership = read_ownership(ownership_path) if ownership_path is not None else None
    disposal = read_disposal(disposal_path) if disposal_path is not None else {}
    run_dir = ownership_path.resolve().parent if ownership_path is not None else repo
    if disposal_path is not None and (ownership_path is None
                                     or disposal_path.resolve().parent != run_dir):
        raise InventoryError("Disposal checks must be beside this run's ownership record")
    primary = canonical(records[0]["path"])
    primary_path = Path(records[0]["path"]).resolve()
    conventional_root = canonical(primary_path.parent / (primary_path.name + CONVENTIONAL_SUFFIX))
    currents = current_workspaces(records, current)
    deletable = set(deletable)
    open_requests = set(open_requests)
    active = {canonical(path) for path in active}

    worktrees = [evaluate(record, primary, conventional_root, ownership, currents, active,
                          deletable, open_requests, disposal, run_dir, mainline) for record in records]
    removable = [item["path"] for item in worktrees if item["removal_allowed"]]
    return {
        "repository": str(repo),
        "conventional_root": str(conventional_root),
        "ownership_record": str(ownership_path) if ownership_path is not None else None,
        "ownership_entries": len(ownership) if ownership is not None else 0,
        "disposal_record": str(disposal_path) if disposal_path is not None else None,
        "current_workspaces": sorted(currents),
        "deletable_branches": sorted(deletable),
        "open_request_branches": sorted(open_requests),
        "worktrees": worktrees,
        "removable": removable,
        "counts": {"inventoried": len(worktrees), "eligible": len(removable),
                   "retained": len(worktrees) - len(removable)},
        "retained": [{"path": item["path"], "reasons": item["retain_reasons"]}
                     for item in worktrees if not item["removal_allowed"]],
    }


def parse(arguments):
    parser = argparse.ArgumentParser(
        description="Read-only inventory of worktrees and recorded workspace ownership. "
                    "It never removes a worktree; removal stays a reviewed cleanup action.")
    parser.add_argument("--repo", required=True, help="local repository to inspect")
    parser.add_argument("--ownership", help="this run's workspaces.json in its run directory")
    parser.add_argument("--disposal", help="cleanup's detached disposal checks beside workspaces.json")
    parser.add_argument("--mainline", help="confirmed remote-tracking mainline ref, e.g. refs/remotes/origin/main")
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
    disposal = Path(arguments.disposal) if arguments.disposal else None
    try:
        report = inventory(arguments.repo, ownership, arguments.current, arguments.active,
                           arguments.deletable_branch, arguments.open_request, disposal,
                           arguments.mainline)
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
