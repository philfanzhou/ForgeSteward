"""按标准模板同步目标仓库的 ForgeSteward 工作流区块；不读取或改写区块外的项目规则。"""

import argparse
import os
from pathlib import Path
import re
import sys


ASSETS = Path(__file__).resolve().parents[1] / "assets"
LANGUAGES = ("zh-CN", "en")
WORKFLOW = "workflow"
POINTER = "claude-rules"
IMPORTS = {"@AGENTS.md", "@./AGENTS.md"}
MARKER = re.compile(r"^<!-- forge-steward:([a-z-]+) (begin|end)(?: lang=([A-Za-z-]+))? -->$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class SyncError(Exception):
    pass


def say(message, stream=None):
    # CLI 输出采用 ASCII 转义，兼容 Windows Python 3.9 重定向时的默认单字节编码。
    print(message.encode("ascii", "backslashreplace").decode("ascii"), file=stream or sys.stdout)


def template(name, language):
    body = (ASSETS / (name + "." + language + ".md")).read_text(encoding="utf-8")
    lines = body.replace("\r\n", "\n").strip("\n").split("\n")
    return ["<!-- forge-steward:%s begin lang=%s -->" % (name, language)] + lines + [
        "<!-- forge-steward:%s end -->" % name]


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
    # 未闭合的围栏会吞掉追加在末尾的区块或导入，导致无法收敛，须先由项目修正。
    if fence:
        raise SyncError("Unclosed code fence opened at line %d" % (opened + 1))
    return result


def find_blocks(lines, name):
    blocks, start, language = [], None, None
    for index in outside_fences(lines):
        match = MARKER.match(lines[index].strip())
        if not match or match.group(1) != name:
            continue
        if match.group(2) == "begin":
            if start is not None:
                raise SyncError("Nested forge-steward:%s begin marker at line %d" % (name, index + 1))
            start, language = index, match.group(3)
        elif start is None:
            raise SyncError("forge-steward:%s end marker without begin at line %d" % (name, index + 1))
        else:
            blocks.append((start, index, language))
            start = None
    if start is not None:
        raise SyncError("forge-steward:%s begin marker without end at line %d" % (name, start + 1))
    return blocks


def trim(lines):
    result = list(lines)
    while result and not result[-1].strip():
        result.pop()
    return result


def place(lines, name, block, after=None):
    """block 为 None 时移除区块；重复区块只保留第一个位置。"""
    blocks = find_blocks(lines, name)
    if not blocks:
        if block is None:
            return list(lines)
        if after is None:
            body = trim(lines)
            return body + [""] + block if body else list(block)
        rest = lines[after + 1:]
        return lines[:after + 1] + [""] + block + ([""] if rest and rest[0].strip() else []) + rest
    result, position = [], 0
    for number, (start, end, _) in enumerate(blocks):
        result += lines[position:start]
        position = end + 1
        if number == 0 and block is not None:
            result += block
        elif position >= len(lines):
            result = trim(result)
        elif result and not result[-1].strip() and not lines[position].strip():
            position += 1
    return result + lines[position:]


class Document:
    def __init__(self, path):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise SyncError(path.name + " is not a regular file; it is not managed")
        self.path = path
        self.exists = path.exists()
        raw = path.read_bytes() if self.exists else b""
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw[3 if self.bom else 0:].decode("utf-8")
        except UnicodeDecodeError:
            raise SyncError(path.name + " is not valid UTF-8")
        self.crlf = "\r\n" in text
        self.lines = text.replace("\r\n", "\n").split("\n")
        if self.lines[-1] == "":
            self.lines.pop()
        try:
            outside_fences(self.lines)
        except SyncError as error:
            raise SyncError(path.name + ": " + str(error))

    def write(self, lines):
        text = "\n".join(lines) + "\n"
        if self.crlf:
            text = text.replace("\n", "\r\n")
        self.path.write_bytes((b"\xef\xbb\xbf" if self.bom else b"") + text.encode("utf-8"))


def plan(repo, requested):
    if not repo.is_dir():
        raise SyncError("Repository directory not found: " + str(repo))
    agents_path, claude_path = repo / "AGENTS.md", repo / "CLAUDE.md"
    agents = Document(agents_path)
    changes, warnings, pointer = [], [], False
    # CLAUDE.md 链接到 AGENTS.md 时 Claude 已直接读取区块，不写穿链接。
    alias = claude_path.is_symlink() and agents.exists and os.path.samefile(claude_path, agents_path)
    if not alias:
        claude = Document(claude_path)
        # CLAUDE.md 另有规则时，OpenCode 会因新建的 AGENTS.md 停止回退读取它，须保留读取指示。
        pointer = any(line.strip() and line.strip() not in IMPORTS for line in claude.lines)
        if not any(claude.lines[index].strip() in IMPORTS for index in outside_fences(claude.lines)):
            body = trim(claude.lines)
            reason = "add @AGENTS.md import" if claude.exists else "create with @AGENTS.md import"
            changes.append((claude, body + ["", "@AGENTS.md"] if body else ["@AGENTS.md"], reason))
    language = requested
    if language is None:
        blocks = find_blocks(agents.lines, WORKFLOW)
        language = blocks[0][2] if blocks else None
    if language not in LANGUAGES:
        raise SyncError("Choose --lang (zh-CN or en); no existing workflow block declares a supported language")
    expected = place(agents.lines, WORKFLOW, template(WORKFLOW, language))
    end = find_blocks(expected, WORKFLOW)[0][1]
    expected = place(expected, POINTER, template(POINTER, language) if pointer else None, after=end)
    if expected != agents.lines:
        changes.insert(0, (agents, expected, "sync workflow block" if agents.exists else "create with workflow block"))
    if (repo / "AGENTS.override.md").exists():
        warnings.append("AGENTS.override.md exists at the repository root; Codex reads it instead of AGENTS.md there")
    return changes, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synchronize the ForgeSteward standard workflow block.")
    parser.add_argument("--repo", default=".", help="Target repository root (default: current directory)")
    parser.add_argument("--lang", choices=LANGUAGES, help="Template language; defaults to the existing block language")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report differences without writing (exit 1 if any)")
    mode.add_argument("--write", action="store_true", help="Write the standard block and entry import")
    args = parser.parse_args(argv)
    try:
        changes, warnings = plan(Path(args.repo).resolve(), args.lang)
        for warning in warnings:
            say("Warning: " + warning)
        if not changes:
            say("Workflow block is in sync")
            return 0
        for document, _, reason in changes:
            say(("Needs change " if args.check else "Updating ") + document.path.name + ": " + reason)
        if args.check:
            return 1
        for document, lines, _ in changes:
            document.write(lines)
        say("Workflow block synchronized")
        return 0
    except (OSError, SyncError) as error:
        say("Error: " + str(error), sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
