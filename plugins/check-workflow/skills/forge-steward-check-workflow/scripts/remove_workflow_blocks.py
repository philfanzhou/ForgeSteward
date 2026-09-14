"""删除旧版 check-workflow 写入目标仓库的 ForgeSteward 标记区块；不读取或改写区块外的项目规则。"""

import argparse
from pathlib import Path
import re
import sys


NAMES = ("workflow", "claude-rules")
IMPORTS = {"@AGENTS.md", "@./AGENTS.md"}
MARKER = re.compile(r"^<!-- forge-steward:([a-z-]+) (begin|end)(?: lang=([A-Za-z-]+))? -->$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class BlockError(Exception):
    pass


def say(message, stream=None):
    # CLI 输出采用 ASCII 转义，兼容 Windows Python 3.9 重定向时的默认单字节编码。
    print(message.encode("ascii", "backslashreplace").decode("ascii"), file=stream or sys.stdout)


def outside_fences(lines):
    """返回围栏代码块以外的行号；代码块中的标记和导入不生效。"""
    fence, opened, result = None, None, []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if fence:
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        match = FENCE.match(line)
        if match:
            fence, opened = match.group(1), index
        else:
            result.append(index)
    # 未闭合的围栏无法确定标记是否生效，须先由项目修正。
    if fence:
        raise BlockError("Unclosed code fence opened at line %d" % (opened + 1))
    return result


def find_blocks(lines, name):
    blocks, start = [], None
    for index in outside_fences(lines):
        match = MARKER.match(lines[index].strip())
        if not match or match.group(1) != name:
            continue
        if match.group(2) == "begin":
            if start is not None:
                raise BlockError("Nested forge-steward:%s begin marker at line %d" % (name, index + 1))
            start = index
        elif start is None:
            raise BlockError("forge-steward:%s end marker without begin at line %d" % (name, index + 1))
        else:
            blocks.append((start, index))
            start = None
    if start is not None:
        raise BlockError("forge-steward:%s begin marker without end at line %d" % (name, start + 1))
    return blocks


def trim(lines):
    result = list(lines)
    while result and not result[-1].strip():
        result.pop()
    return result


def remove(lines, name):
    """删除全部同名区块，连同因此多出的一个空行。"""
    result, position = [], 0
    for start, end in find_blocks(lines, name):
        result += lines[position:start]
        position = end + 1
        if position >= len(lines):
            result = trim(result)
        elif not lines[position].strip() and (not result or not result[-1].strip()):
            position += 1
    return result + lines[position:]


class Line(str):
    """原文件中的一行，记录其换行符。"""
    ending = ""


class Document:
    def __init__(self, path):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise BlockError(path.name + " is not a regular file; it is not managed")
        self.path = path
        self.exists = path.exists()
        raw = path.read_bytes() if self.exists else b""
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw[3 if self.bom else 0:].decode("utf-8")
        except UnicodeDecodeError:
            raise BlockError(path.name + " is not valid UTF-8")
        *complete, last = text.split("\n")
        self.lines = []
        for part in complete:
            line = Line(part[:-1]) if part.endswith("\r") else Line(part)
            line.ending = "\r\n" if part.endswith("\r") else "\n"
            self.lines.append(line)
        if last:
            self.lines.append(Line(last))
        try:
            outside_fences(self.lines)
        except BlockError as error:
            raise BlockError(path.name + ": " + str(error))

    def write(self, lines):
        if not any(line.strip() for line in lines):
            self.path.unlink()
            return
        # 保留行各自的换行符；删除区块不会产生新行。
        text = "".join(line + line.ending for line in lines)
        self.path.write_bytes((b"\xef\xbb\xbf" if self.bom else b"") + text.encode("utf-8"))


def plan(repo):
    if not repo.is_dir():
        raise BlockError("Repository directory not found: " + str(repo))
    agents_path, claude_path = repo / "AGENTS.md", repo / "CLAUDE.md"
    if agents_path.is_symlink() or not agents_path.exists():
        return []
    agents = Document(agents_path)
    expected = agents.lines
    for name in NAMES:
        expected = remove(expected, name)
    if expected == agents.lines:
        return []
    changes = [(agents, expected, "remove forge-steward workflow blocks")]
    # AGENTS.md 只剩区块时整份删除；CLAUDE.md 中指向它的导入随之悬空，一并删除。
    if not any(line.strip() for line in expected) and claude_path.exists() and not claude_path.is_symlink():
        claude = Document(claude_path)
        effective = set(outside_fences(claude.lines))
        kept = [line for index, line in enumerate(claude.lines)
                if not (index in effective and line.strip() in IMPORTS)]
        if kept != claude.lines:
            reason = "delete dangling @AGENTS.md import"
            changes.append((claude, remove_extra_blank(kept), reason))
    return changes


def remove_extra_blank(lines):
    result = []
    for line in lines:
        if not line.strip() and (not result or not result[-1].strip()):
            continue
        result.append(line)
    return trim(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove ForgeSteward workflow blocks written by earlier check-workflow versions.")
    parser.add_argument("--repo", default=".", help="Target repository root (default: current directory)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report blocks without writing (exit 1 if any)")
    mode.add_argument("--write", action="store_true", help="Remove the blocks")
    args = parser.parse_args(argv)
    try:
        changes = plan(Path(args.repo).resolve())
        if (Path(args.repo) / "AGENTS.override.md").exists():
            say("Warning: AGENTS.override.md exists at the repository root; it is not modified")
        if not changes:
            say("No forge-steward workflow blocks found")
            return 0
        for document, lines, reason in changes:
            action = "delete file" if not any(line.strip() for line in lines) else reason
            say(("Needs change " if args.check else "Updating ") + document.path.name + ": " + action)
        if args.check:
            return 1
        for document, lines, _ in changes:
            document.write(lines)
        say("Workflow blocks removed")
        return 0
    except (OSError, BlockError) as error:
        say("Error: " + str(error), sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
