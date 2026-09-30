#!/usr/bin/env python3
"""从当前 checkout 管理 OpenCode 技能；仅使用 Python 标准库。"""

import os
from pathlib import Path
import sys

import skill_installer as core
from skill_installer import InstallError, reject_links

REPO = Path(__file__).resolve().parents[1]
AGENT = "OpenCode"
PROJECT_HELP = "Use PATH/.opencode/skills"
USER_HELP = "Use OPENCODE_CONFIG_DIR/skills, XDG_CONFIG_HOME/opencode/skills, or ~/.config/opencode/skills"
VERIFY_HINT = "Verify with opencode debug skill in a new session."


def target_root(args):
    if args.project is not None:
        project = Path(args.project).expanduser().resolve()
        if not project.is_dir():
            raise InstallError("Project directory must already exist: " + str(project))
        root = project / ".opencode" / "skills"
    else:
        custom = os.environ.get("OPENCODE_CONFIG_DIR")
        config = Path(custom or os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))).expanduser()
        if not config.is_absolute():
            raise InstallError("OPENCODE_CONFIG_DIR / XDG_CONFIG_HOME must be absolute")
        root = config / "skills" if custom else config / "opencode" / "skills"
    reject_links(root)
    if root.exists() and not root.is_dir():
        raise InstallError("Not a directory: " + str(root))
    return root


def parser():
    return core.parser(sys.modules[__name__])


def main(argv=None, repo=REPO):
    return core.main(argv, repo, sys.modules[__name__])


if __name__ == "__main__":
    sys.exit(main())
