#!/usr/bin/env python3
"""Read-only checks of cross-Agent skill budgets and reference integrity; Python standard library only."""

import argparse
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[1]
# Single numeric source for repository budgets; evidence and platform differences are in docs/skill-compatibility.md.
ENTRYPOINT_BYTES = 6_000
ENTRYPOINT_LINES = 499
REFERENCE_BYTES = 8_000
REFERENCE_LINES = 499
# Covers full descriptions in the default DeepSeek Harness discovery list, not the body loading limit.
DESCRIPTION_UTF16_UNITS = 500
NAME_CHARS = 64


def utf16_units(text):
    """Match JavaScript String.length; non-BMP characters use two units."""
    return len(text.encode("utf-16-le")) // 2


def frontmatter(text):
    """Read this repository's single-line plain name/description scalars, not general YAML."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("frontmatter has no closing delimiter") from None
    values = {}
    for key in ("name", "description"):
        matches = [line[len(key) + 1:].strip() for line in lines[1:end]
                   if line.startswith(key + ":")]
        if len(matches) != 1 or not matches[0]:
            raise ValueError(key + " must appear exactly once and be nonempty")
        value = matches[0]
        position = next(i for i, line in enumerate(lines[1:end], 1) if line.startswith(key + ":"))
        for following in lines[position + 1:end]:
            if not following.strip() or following.lstrip().startswith("#"):
                continue
            if following[0].isspace():
                raise ValueError(key + " must not have indented continuation lines; use a single line")
            break
        # Do not count block scalars, aliases, quotes, or YAML comments as description text.
        if (value[0] in "\"'|>!&*[{#%@`" or ": " in value or " #" in value
                or value.lower() in ("null", "true", "false", "~")):
            raise ValueError(key + " must be a single plain line without quotes, comments, or special YAML syntax")
        values[key] = value
    return values, "\n".join(lines[end + 1:])


def check_skill(entrypoint):
    root = entrypoint.parent.resolve()
    errors = []
    rows = []
    texts = {}

    def error(path, message):
        errors.append(f"{path}: {message}")

    references = sorted((root / "references").rglob("*.md"))
    for path in [entrypoint, *references]:
        if path.is_symlink() or root not in path.resolve().parents:
            error(path, "Skill rules must be regular files in the package; symlinks cannot bypass checks")
            continue
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            error(path, f"Cannot read UTF-8 rule file: {exc}")
            continue
        texts[path.resolve()] = text
        is_entry = path == entrypoint
        byte_limit = ENTRYPOINT_BYTES if is_entry else REFERENCE_BYTES
        line_limit = ENTRYPOINT_LINES if is_entry else REFERENCE_LINES
        lines = len(text.splitlines())
        rows.append((path, len(raw), byte_limit, lines, line_limit))
        if len(raw) > byte_limit:
            error(path, f"{len(raw)} UTF-8 bytes > {byte_limit}; split rules by stage without deleting constraints to bypass checks")
        if lines > line_limit:
            error(path, f"{lines} lines > {line_limit}; move details into explicitly linked references")

    entry_text = texts.get(entrypoint.resolve())
    description_units = 0
    if entry_text is not None:
        try:
            metadata, _ = frontmatter(entry_text)
            name = metadata["name"]
            if (len(name) > NAME_CHARS or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
                    or name != root.name):
                error(entrypoint, f"name must be 1–{NAME_CHARS} lowercase letters/digits with single hyphens and match the directory name")
            description_units = utf16_units(metadata["description"])
            if description_units > DESCRIPTION_UTF16_UNITS:
                error(entrypoint, f"description {description_units} UTF-16 units > {DESCRIPTION_UTF16_UNITS}; move details into the body")
        except ValueError as exc:
            error(entrypoint, str(exc))

    visited = set()
    pending = [entrypoint.resolve()]
    while pending:
        source = pending.pop()
        if source in visited or source not in texts:
            continue
        visited.add(source)
        for link in re.findall(r"\]\(([^)]+)\)", texts[source]):
            if "://" in link or link.startswith("#"):
                continue
            target = (source.parent / link.split("#", 1)[0]).resolve()
            if root not in target.parents:
                error(source, f"Reference leaves the standalone skill directory: {link}")
            elif not target.is_file():
                error(source, f"Missing reference file: {link}")
            elif target.suffix == ".md":
                if target not in texts:
                    error(source, f"Rule Markdown must be under references/ and subject to length checks: {link}")
                else:
                    pending.append(target)
    for path in references:
        if path.resolve() not in visited:
            error(path, "Reference rules are unreachable from SKILL.md; add loading instructions and relative Markdown links")
    return rows, errors, description_units


def check_repository(repo):
    skills = sorted((repo / "plugins").glob("*/skills/**/SKILL.md"))
    rows, errors, description_units = [], [], 0
    if not skills:
        errors.append(f"{repo}: No skill entrypoints found; an empty set must not pass")
    for skill in skills:
        found, problems, units = check_skill(skill)
        rows.extend(found)
        errors.extend(problems)
        description_units += units
    return rows, errors, description_units


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO, help="repository root to check")
    parser.add_argument("--check", action="store_true", help="read-only check (default)")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    rows, errors, description_units = check_repository(repo)
    for path, size, byte_limit, lines, line_limit in rows:
        print(f"{path.relative_to(repo)}: {size}/{byte_limit} bytes, {lines}/{line_limit} lines")
    print(f"Description total: {description_units} UTF-16 units (not an agent catalog budget)")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
