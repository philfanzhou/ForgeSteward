#!/usr/bin/env python3
"""Retain and validate one complete resolved rule-package set in run Git metadata."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
from rule_inventory import digest, inventory, is_link, package_file, resources
from run_record import MARKER, run_dir, runs_root


SCHEMA = 1
PACKAGES = ("work-cycle", "check-workflow", "prepare-work", "execute-work",
            "review-and-merge", "fix-feedback")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")
HELPERS = ("agent_install.py", "check_workflow_gate.py", "preflight_versions.py",
           "resource_lock.py", "rule_inventory.py", "rule_snapshot.py", "run_record.py")


def signature(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=True).encode("ascii"))


def describe(name, package, expected):
    """Capture the original resolved identity, markers and all package-local dependencies."""
    rules = inventory(package)
    root = Path(rules["package"])
    text = package_file(root, "SKILL.md")[1].decode("utf-8")
    if re.findall(r"^name: ([^\r\n]+)\r?$", text, re.MULTILINE) != ["forge-steward-" + name]:
        raise ValueError(f"{root / 'SKILL.md'}: package name does not match {name}")
    required = ["scripts/VERSION"] if name == "work-cycle" else ["VERSION"]
    if name == "work-cycle":
        required += ["scripts/agents.json", "references/report.md"]
        required += ["scripts/" + helper for helper in HELPERS]
    elif name == "review-and-merge":
        required += ["scripts/worktree_inventory.py"]
    elif name == "check-workflow":
        required += ["scripts/remove_workflow_blocks.py"]
    for relative in required:
        _, raw = package_file(root, relative)
        if relative.endswith("VERSION") and raw.decode("utf-8").strip() != expected:
            raise ValueError(f"{root / relative}: version mismatch (expected {expected})")
    return {"source": str(root), "version": expected, "resources": resources(root),
            "rule_hash": rules["package_hash"]}


def validate(manifest, identity, expected=None):
    """Verify the entire retained set without consulting a possibly removed source cache."""
    manifest = Path(manifest).absolute()
    if manifest.name != "manifest.json" or manifest.parent.name != "rules":
        raise ValueError(f"{manifest}: expected run rules/manifest.json")
    root = manifest.parent
    if is_link(root):
        raise ValueError(f"{root}: symlink retention directory")
    _, raw = package_file(root, "manifest.json")
    saved = json.loads(raw)
    payload = {key: saved[key] for key in ("schema", "version", "packages")}
    if (saved["schema"] != SCHEMA or saved["identity"] != identity or
            signature(payload) != identity or not VERSION.fullmatch(saved["version"])):
        raise ValueError(f"{manifest}: rule-set identity mismatch; retain state and recover explicitly")
    if expected is not None and saved["version"] != expected:
        raise ValueError(f"{manifest}: version {saved['version']} (expected {expected})")
    if set(saved["packages"]) != set(PACKAGES):
        raise ValueError(f"{manifest}: incomplete package set")
    result = {}
    for name in PACKAGES:
        row = saved["packages"][name]
        relative = "packages/" + name
        if row["retained"] != relative:
            raise ValueError(f"{manifest}: invalid retained path for {name}")
        # package_file checks each original path component before normalization.
        package_file(root, relative + "/SKILL.md")
        current = describe(name, root / relative, saved["version"])
        original = {key: row[key] for key in ("source", "version", "resources", "rule_hash")}
        if row["identity"] != signature(original):
            raise ValueError(f"{manifest}: original package identity mismatch for {name}")
        for key in ("version", "resources", "rule_hash"):
            if current[key] != row[key]:
                if key == "resources":
                    before = {r["path"]: r for r in row[key]}
                    after = {r["path"]: r for r in current[key]}
                    for path in sorted(set(before) | set(after)):
                        if before.get(path) != after.get(path):
                            raise ValueError(f"{root / relative / path}: retained resource mismatch "
                                             f"expected {before.get(path)}, actual {after.get(path)}")
                raise ValueError(f"{root / relative}: changed or missing retained {key}")
        result[name] = str(root / relative)
    return {"identity": identity, "version": saved["version"], "packages": result}


def resolve(packages, expected):
    if not VERSION.fullmatch(expected) or set(packages) != set(PACKAGES):
        raise ValueError("one coherent version and all six named packages are required")
    rows = {}
    for name in PACKAGES:
        original = describe(name, packages[name], expected)
        rows[name] = {**original, "identity": signature(original), "retained": "packages/" + name}
    if len({row["source"] for row in rows.values()}) != len(PACKAGES):
        raise ValueError("distinct original package roots are required")
    payload = {"schema": SCHEMA, "version": expected, "packages": rows}
    return {**payload, "identity": signature(payload)}


def create(repo, run, packages, expected):
    directory = run_dir(runs_root(Path(repo)), run)
    record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    if record.get("created_by") != MARKER or record.get("run_id") != run:
        raise ValueError(f"{directory}: not a script-created run")
    if is_link(directory):
        raise ValueError(f"{directory}: symlink run directory")
    destination, guard = directory / "rules", directory / ".rules.lock"
    guard.mkdir()  # Exclusive publication; never remove another writer's guard.
    staging = None
    try:
        if destination.exists() or is_link(destination):
            raise ValueError(f"{destination}: retention already exists; validate it, never overwrite it")
        resolved = resolve(packages, expected)
        staging = Path(tempfile.mkdtemp(prefix=".rules-", dir=directory))
        rows = {}
        for name, row in resolved["packages"].items():
            original = {key: row[key] for key in ("source", "version", "resources", "rule_hash")}
            target = staging / "packages" / name
            target.mkdir(parents=True)
            for resource in original["resources"]:
                path = target / resource["path"]
                if resource.get("directory"):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    _, raw = package_file(Path(original["source"]), resource["path"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
            copied = describe(name, target, expected)
            if any(copied[key] != original[key] for key in ("resources", "rule_hash")):
                raise ValueError(f"{target}: copy changed; no partial retention published")
            if describe(name, packages[name], expected) != original:
                raise ValueError(f"{packages[name]}: source changed during retention")
            rows[name] = row
        payload = {"schema": SCHEMA, "version": expected, "packages": rows}
        identity = signature(payload)
        (staging / "manifest.json").write_text(
            json.dumps({**payload, "identity": identity}, indent=2) + "\n", encoding="utf-8")
        # No existing retention may be replaced, even by a repeated dispatch.
        staging.rename(destination)
        staging = None
        return validate(destination / "manifest.json", identity, expected)
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        guard.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    creating = sub.add_parser("create")
    creating.add_argument("--repo", type=Path, required=True)
    creating.add_argument("--run", required=True)
    creating.add_argument("--expected", required=True)
    creating.add_argument("--package", action="append", required=True, help="name=actual-skill-directory")
    resolving = sub.add_parser("resolve")
    resolving.add_argument("--expected", required=True)
    resolving.add_argument("--package", action="append", required=True)
    checking = sub.add_parser("validate")
    checking.add_argument("--manifest", type=Path, required=True)
    checking.add_argument("--identity", required=True)
    checking.add_argument("--expected")
    args = parser.parse_args(argv)
    try:
        if args.command in ("create", "resolve"):
            packages = {}
            for value in args.package:
                name, path = value.split("=", 1)
                if name in packages:
                    raise ValueError("duplicate package: " + name)
                packages[name] = Path(path)
            result = (create(args.repo, args.run, packages, args.expected) if args.command == "create"
                      else resolve(packages, args.expected))
        else:
            result = validate(args.manifest, args.identity, args.expected)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(f"rule retention stopped: {exc}. Preserve run state and original deadlines; "
              "validate a complete retained set or record an explicit coherent transition.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
