#!/usr/bin/env python3
"""Read-only rule inventory, bounded UTF-8 reads, and caller-attested coverage; Python 3.9+."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from urllib.parse import unquote


SCHEMA = 1


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def is_link(path):
    """Include Windows junction/reparse paths, which may not report is_symlink()."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def resources(package):
    """Inventory the complete package, excluding regenerable Python bytecode only."""
    package = Path(package).absolute()
    if is_link(package):
        raise ValueError(f"{package}: package must not be a symlink")
    root = package.resolve()
    pending, rows = [root], []
    while pending:
        for child in sorted(pending.pop().iterdir()):
            if is_link(child):
                raise ValueError(f"{child}: symlink package resource")
            if child.name == "__pycache__" or child.suffix == ".pyc":
                continue
            relative = child.relative_to(root).as_posix()
            if child.is_dir():
                rows.append({"path": relative, "directory": True})
                pending.append(child)
            else:
                name, raw = package_file(root, relative)
                rows.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    return sorted(rows, key=lambda row: row["path"])


def package_file(root, relative):
    """Reject escaping paths and every symlink component before reading a regular file."""
    if not relative or "\\" in relative or Path(relative).is_absolute():
        raise ValueError(f"{root / relative}: expected an in-package relative path")
    path = root
    try:
        for component in Path(relative).parts:
            path = path.parent if component == ".." else path / component
            if is_link(path):
                raise ValueError(f"{path}: symlink rule resource")
            if path != root and root not in path.parents:
                raise ValueError(f"{path}: path escapes package")
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"{path}: required resource is not a regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{path}: cannot read required resource: {exc}") from exc
    return path.relative_to(root).as_posix(), raw


def inventory(package):
    """Inventory rules and their checked local edges; do not infer conditional requirements."""
    package = Path(package).absolute()
    if is_link(package):
        raise ValueError(f"{package}: package must not be a symlink")
    root = package.resolve()
    paths = ["SKILL.md"]
    references = root / "references"
    if is_link(references):
        raise ValueError(f"{references}: symlink rule directory")
    if references.exists():
        pending = [references]
        while pending:
            directory = pending.pop()
            for child in sorted(directory.iterdir()):
                if is_link(child):
                    raise ValueError(f"{child}: symlink rule resource")
                if child.is_dir():
                    pending.append(child)
                elif child.suffix == ".md":
                    paths.append(child.relative_to(root).as_posix())
    files = {}
    for relative in paths:
        relative, raw = package_file(root, relative)
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"{root / relative}: cannot read UTF-8 rules: {exc}") from exc
        edges = []
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"^[a-zA-Z]:[/\\]", link) or link.startswith("/"):
                raise ValueError(f"{root / relative}: absolute reference {link}")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith("#"):
                continue
            target = unquote(link.split("#", 1)[0])
            # Normalize dot segments only after rejecting symlinks on the original path.
            joined = (Path(relative).parent / target).as_posix()
            name, _ = package_file(root, joined)
            name = (root / name).resolve().relative_to(root).as_posix()
            if name.endswith(".md") and name not in paths:
                raise ValueError(f"{root / name}: rule Markdown must be SKILL.md or under references/")
            if name not in edges:
                edges.append(name)
        files[relative] = {"path": relative, "sha256": digest(raw), "bytes": len(raw),
                           "lines": len(text.splitlines()), "edges": edges}
    order = []

    def visit(name):
        if name in order or name not in files:
            return
        order.append(name)
        for target in files[name]["edges"]:
            visit(target)

    visit("SKILL.md")
    for name in sorted(files):
        visit(name)
    rows = [files[name] for name in order]
    signature = json.dumps(rows, sort_keys=True, ensure_ascii=True).encode("ascii")
    return {"schema": SCHEMA, "package": str(root), "package_hash": digest(signature), "files": rows}


def frame(file, start, end, text):
    """The complete frame is emitted as UTF-8, with no platform newline translation."""
    tag = f"{file['path']} [{start},{end}) sha256={file['sha256']}"
    return f"BEGIN {tag}\n{text}\nEND {tag}\n".encode("utf-8")


def ranges(raw, start, stop, file, budget, reserve):
    """Prefer line boundaries, splitting long lines only at UTF-8 character boundaries."""
    while start < stop:
        end = min(stop, start + budget - reserve)
        while end > start:
            try:
                part = raw[start:end].decode("utf-8")
            except UnicodeDecodeError:
                end -= 1
                continue
            excess = len(frame(file, start, end, part)) + reserve - budget
            if excess <= 0:
                break
            end -= excess
        if end <= start:
            raise ValueError(f"{file['path']}: byte budget cannot fit wrappers and one UTF-8 character")
        newline = raw.rfind(b"\n", start, end)
        if end < stop and newline >= start:
            end = newline + 1
        yield {"path": file["path"], "start": start, "end": end}
        start = end


def plan(package, stage, required, budget, reserve=0, receipt=None, context=None):
    if not stage or not isinstance(budget, int) or budget <= 0 or reserve < 0 or reserve >= budget:
        raise ValueError("stage and positive byte budget with 0 <= reserve < budget are required")
    found = inventory(package)
    files = {f["path"]: f for f in found["files"]}
    selected = list(dict.fromkeys(required))
    if not selected:
        raise ValueError("select required files in actual entry/stage order")
    for name in selected:
        if name not in files:
            raise ValueError(f"{Path(found['package']) / name}: selected rule not in inventory")
    manifest = {**found, "stage": stage, "required": selected,
                "budget_bytes": budget, "reserve_bytes": reserve, "groups": []}
    coverage = receipt_coverage(manifest, receipt, context) if receipt else {}
    for name in selected:
        file = files[name]
        _, raw = package_file(Path(found["package"]), name)
        cursor = 0
        for start, end in coverage.get(name, []):
            manifest["groups"].extend(ranges(raw, cursor, start, file, budget, reserve))
            cursor = end
        manifest["groups"].extend(ranges(raw, cursor, len(raw), file, budget, reserve))
    return manifest


def checked_manifest(manifest):
    """Fail closed on any package/rule change between planning, reading, and attestation."""
    current = inventory(manifest["package"])
    if (manifest.get("schema") != SCHEMA or current["package_hash"] != manifest["package_hash"]
            or current["files"] != manifest["files"]):
        raise ValueError(f"{manifest['package']}: package changed; invalidate coverage and reinspect rules")
    return {f["path"]: f for f in current["files"]}


def read_range(manifest, group):
    files = checked_manifest(manifest)
    name, start, end = group["path"], group["start"], group["end"]
    if name not in manifest["required"]:
        raise ValueError(f"{name}: range is not selected for this stage")
    _, raw = package_file(Path(manifest["package"]), name)
    if not 0 <= start < end <= len(raw):
        raise ValueError(f"{name}: invalid byte range [{start},{end})")
    try:
        output = frame(files[name], start, end, raw[start:end].decode("utf-8"))
    except UnicodeError as exc:
        raise ValueError(f"{name}: range splits a UTF-8 character") from exc
    if len(output) + manifest["reserve_bytes"] > manifest["budget_bytes"]:
        raise ValueError(f"{name}: emitted range exceeds the planned byte allowance")
    return output


def receipt_coverage(manifest, previous, context):
    if not context:
        raise ValueError("a current context identifier is required for receipt reuse")
    if (previous.get("schema") != SCHEMA or previous["package"] != manifest["package"]
            or previous["package_hash"] != manifest["package_hash"] or previous["stage"] != manifest["stage"]
            or previous["required"] != manifest["required"] or previous["files"] != manifest["files"]):
        raise ValueError("receipt identity/stage/selection changed; invalidate coverage and reinspect rules")
    # A disk receipt retains identity, never missing model context after compaction.
    if previous["context"] != context:
        return {}
    coverage = previous["observed"]
    files = {f["path"]: f for f in manifest["files"]}
    if not isinstance(coverage, dict):
        raise ValueError("invalid receipt observed ranges")
    for name, pairs in coverage.items():
        if name not in manifest["required"] or not isinstance(pairs, list):
            raise ValueError(f"{name}: invalid receipt coverage")
        _, raw = package_file(Path(manifest["package"]), name)
        last = -1
        for pair in pairs:
            if (not isinstance(pair, list) or len(pair) != 2 or
                    any(type(offset) is not int for offset in pair)):
                raise ValueError(f"{name}: invalid receipt range")
            start, end = pair
            if not last < start < end <= files[name]["bytes"]:
                raise ValueError(f"{name}: invalid receipt range [{start},{end})")
            try:
                raw[:start].decode("utf-8")
                raw[start:end].decode("utf-8")
            except UnicodeError as exc:
                raise ValueError(f"{name}: receipt range splits a UTF-8 character") from exc
            last = end
    return coverage


def attest(manifest, context, observed=(), previous=None):
    """Output caller-attested coverage, never infer receipt from disk reads or matching hashes."""
    files = checked_manifest(manifest)
    if not context:
        raise ValueError("provide the current context identifier; change it after compaction")
    coverage = receipt_coverage(manifest, previous, context) if previous else {}
    coverage = {name: [list(pair) for pair in pairs] for name, pairs in coverage.items()}
    for group in observed:
        name, start, end = group["path"], group["start"], group["end"]
        if name not in manifest["required"] or not 0 <= start < end <= files[name]["bytes"]:
            raise ValueError(f"{name}: invalid observed range [{start},{end})")
        _, raw = package_file(Path(manifest["package"]), name)
        try:
            raw[:start].decode("utf-8")
            raw[start:end].decode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"{name}: observed range splits a UTF-8 character") from exc
        pairs = sorted([*coverage.get(name, []), [start, end]])
        merged = []
        for left, right in pairs:
            if merged and left <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], right)
            else:
                merged.append([left, right])
        coverage[name] = merged
    missing = []
    for name in manifest["required"]:
        cursor = 0
        for start, end in coverage.get(name, []):
            if cursor < start:
                missing.append({"path": name, "start": cursor, "end": start})
            cursor = end
        if cursor < files[name]["bytes"]:
            missing.append({"path": name, "start": cursor, "end": files[name]["bytes"]})
    return {k: manifest[k] for k in ("schema", "package", "package_hash", "files", "stage", "required")} | {
        "context": context, "observed": coverage, "complete": not missing,
        "next_missing": missing[0] if missing else None}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--package", type=Path, required=True)
    planning = sub.add_parser("plan")
    planning.add_argument("--package", type=Path, required=True)
    planning.add_argument("--stage", required=True)
    planning.add_argument("--required", action="append", required=True)
    planning.add_argument("--budget-bytes", type=int, required=True)
    planning.add_argument("--reserve-bytes", type=int, default=0)
    planning.add_argument("--receipt", type=Path)
    planning.add_argument("--context")
    reading = sub.add_parser("read")
    reading.add_argument("--manifest", type=Path, required=True)
    reading.add_argument("--group", type=int, required=True, help="zero-based group index")
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--manifest", type=Path, required=True)
    receipt.add_argument("--context", required=True)
    receipt.add_argument("--previous", type=Path)
    receipt.add_argument("--observed", action="append", default=[], help="path:start:end, UTF-8 byte offsets")
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.package)
        elif args.command == "plan":
            result = plan(args.package, args.stage, args.required, args.budget_bytes, args.reserve_bytes,
                          load_json(args.receipt) if args.receipt else None, args.context)
        elif args.command == "read":
            manifest = load_json(args.manifest)
            if not 0 <= args.group < len(manifest["groups"]):
                raise ValueError("group index outside manifest")
            sys.stdout.buffer.write(read_range(manifest, manifest["groups"][args.group]))
            return 0
        else:
            observed = []
            for value in args.observed:
                name, start, end = value.rsplit(":", 2)
                observed.append({"path": name, "start": int(start), "end": int(end)})
            result = attest(load_json(args.manifest), args.context, observed,
                            load_json(args.previous) if args.previous else None)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"rule loading stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
