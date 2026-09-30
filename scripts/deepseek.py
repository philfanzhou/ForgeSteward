#!/usr/bin/env python3
"""从当前 checkout 管理 DeepSeek Harness 技能；仅使用 Python 标准库。"""

import os
from pathlib import Path
import sys

import skill_installer as core
from skill_installer import InstallError, reject_links

REPO = Path(__file__).resolve().parents[1]
AGENT = "DeepSeek Harness"
PROJECT_HELP = "Use the nearest Git root's .dsh/skills (PATH itself without a Git root)"
USER_HELP = "Use DSH_HOME/skills or ~/.dsh/skills"
VERIFY_HINT = "Verify skill discovery and resource paths in a new DeepSeek Harness session."


def expand_home(value):
    # 与 resolveDshHome 一致，非空配置保留前后空白；~\\ 在 POSIX 也展开。
    if value == "~":
        return Path.home()
    if value.startswith(("~/", "~\\")):
        return Path.home() / value[2:]
    return Path(value)


def checked_absolute(path):
    raw = path.absolute()
    reject_links(raw)
    resolved = raw.resolve()
    reject_links(resolved)
    return resolved


def target_root(args):
    if args.project is not None:
        project = checked_absolute(expand_home(args.project))
        if not project.is_dir():
            raise InstallError("Project directory must already exist: " + str(project))
        selected = project
        for candidate in (project, *project.parents):
            marker = candidate / ".git"
            reject_links(marker)
            if marker.exists():
                selected = candidate
                break
        root = selected / ".dsh" / "skills"
    else:
        custom = os.environ.get("DSH_HOME")
        home = expand_home(custom) if custom is not None and custom.strip() else Path.home() / ".dsh"
        root = home / "skills"
    root = checked_absolute(root)
    if root.exists() and not root.is_dir():
        raise InstallError("Not a directory: " + str(root))
    return root


def parser():
    return core.parser(sys.modules[__name__])


def main(argv=None, repo=REPO):
    return core.main(argv, repo, sys.modules[__name__])


if __name__ == "__main__":
    sys.exit(main())
