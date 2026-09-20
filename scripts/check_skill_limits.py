#!/usr/bin/env python3
"""只读校验技能的跨 Agent 长度预算和引用完整性；仅依赖 Python 标准库。"""

import argparse
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[1]
# 仓库维护预算的唯一数值来源；依据和平台差异见 docs/skill-compatibility.md。
ENTRYPOINT_BYTES = 6_000
ENTRYPOINT_LINES = 499
REFERENCE_BYTES = 8_000
REFERENCE_LINES = 499
DESCRIPTION_UTF16_UNITS = 1_024
NAME_CHARS = 64


def utf16_units(text):
    """与 JavaScript String.length 一致；非 BMP 字符占两个单元。"""
    return len(text.encode("utf-16-le")) // 2


def frontmatter(text):
    """读取本仓库的 name/description 单行裸标量约定，不冒充通用 YAML 解析器。"""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md 必须以 YAML frontmatter 开始")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("frontmatter 缺少结束分隔符") from None
    values = {}
    for key in ("name", "description"):
        matches = [line[len(key) + 1:].strip() for line in lines[1:end]
                   if line.startswith(key + ":")]
        if len(matches) != 1 or not matches[0]:
            raise ValueError(key + " 必须恰好出现一次且非空")
        value = matches[0]
        position = next(i for i, line in enumerate(lines[1:end], 1) if line.startswith(key + ":"))
        for following in lines[position + 1:end]:
            if not following.strip() or following.lstrip().startswith("#"):
                continue
            if following[0].isspace():
                raise ValueError(key + " 不允许缩进续行；请保留单行文本")
            break
        # 禁止把块标量、别名、引号或 YAML 注释误当成描述计数。
        if (value[0] in "\"'|>!&*[{#%@`" or ": " in value or " #" in value
                or value.lower() in ("null", "true", "false", "~")):
            raise ValueError(key + " 必须使用不带引号、注释或 YAML 特殊语法的单行文本")
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
            error(path, "技能规则必须是包内普通文件，不能通过符号链接绕过检查")
            continue
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            error(path, f"无法读取 UTF-8 规则文件：{exc}")
            continue
        texts[path.resolve()] = text
        is_entry = path == entrypoint
        byte_limit = ENTRYPOINT_BYTES if is_entry else REFERENCE_BYTES
        line_limit = ENTRYPOINT_LINES if is_entry else REFERENCE_LINES
        lines = len(text.splitlines())
        rows.append((path, len(raw), byte_limit, lines, line_limit))
        if len(raw) > byte_limit:
            error(path, f"{len(raw)} UTF-8 bytes > {byte_limit}；按阶段拆分规则，不删减语义绕过检查")
        if lines > line_limit:
            error(path, f"{lines} lines > {line_limit}；将细节拆为明确链接的引用文件")

    entry_text = texts.get(entrypoint.resolve())
    description_units = 0
    if entry_text is not None:
        try:
            metadata, _ = frontmatter(entry_text)
            name = metadata["name"]
            if (len(name) > NAME_CHARS or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
                    or name != root.name):
                error(entrypoint, f"name 须为 1–{NAME_CHARS} 位小写字母/数字及单连字符，且与目录名一致")
            description_units = utf16_units(metadata["description"])
            if description_units > DESCRIPTION_UTF16_UNITS:
                error(entrypoint, f"description {description_units} UTF-16 units > {DESCRIPTION_UTF16_UNITS}；细节移到正文")
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
                error(source, f"引用超出独立技能目录：{link}")
            elif not target.is_file():
                error(source, f"引用文件缺失：{link}")
            elif target.suffix == ".md":
                if target not in texts:
                    error(source, f"规则 Markdown 必须位于 references/ 并接受长度检查：{link}")
                else:
                    pending.append(target)
    for path in references:
        if path.resolve() not in visited:
            error(path, "引用规则无法从 SKILL.md 到达；补充读取时机和相对 Markdown 链接")
    return rows, errors, description_units


def check_repository(repo):
    skills = sorted((repo / "plugins").glob("*/skills/**/SKILL.md"))
    rows, errors, description_units = [], [], 0
    if not skills:
        errors.append(f"{repo}: 未发现技能入口，禁止空集合通过检查")
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
    parser.add_argument("--repo", type=Path, default=REPO, help="待检查的仓库根目录")
    parser.add_argument("--check", action="store_true", help="只读检查（默认行为）")
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
