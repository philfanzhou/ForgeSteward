#!/usr/bin/env python3
"""从当前 checkout 管理 OpenCode 技能；仅使用 Python 标准库。"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
PREFIX = "forge-steward-"
RECEIPT = ".forge-steward-install.json"
LOCK = ".forge-steward.lock"
# 历史调用名不是归属凭据；仅用于报告可能遗留的手工副本。
LEGACY_NAMES = {"check-workflow", "find-work", "review-and-merge", "fix-feedback"}


class InstallError(Exception):
    pass


def skill_name(value):
    name = value if value.startswith(PREFIX) else PREFIX + value
    if len(name) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise InstallError("Invalid skill name: " + value)
    return name


def is_link(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def reject_links(path):
    # 检查尚未 resolve 的安装路径，防止配置目录链接把写入重定向到别处。
    for item in (path, *path.parents):
        if is_link(item):
            raise InstallError("Symlink paths are not managed: " + str(item))


def snapshot(directory):
    """包括空目录；添加、删除、修改文件或链接都会使已安装内容不再匹配。"""
    reject_links(directory)
    if not directory.is_dir():
        raise InstallError("Expected a skill directory: " + str(directory))
    result = {}
    for path in sorted(directory.rglob("*")):
        key = path.relative_to(directory).as_posix()
        if is_link(path):
            raise InstallError("Symlink content is not managed: " + str(path))
        if key == RECEIPT:
            continue
        if path.is_dir():
            result[key] = "directory"
        elif path.is_file():
            result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise InstallError("Unsupported file type: " + str(path))
    return result


def catalog(repo):
    result = {}
    for plugin in sorted((repo / "plugins").iterdir()):
        reject_links(plugin)
        if not plugin.is_dir():
            continue
        manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("name") != plugin.name or not isinstance(manifest.get("version"), str):
            raise InstallError("Invalid plugin manifest: " + str(plugin))
        for source in sorted((plugin / "skills").iterdir()):
            if not source.is_dir():
                continue
            files = snapshot(source)
            if (source / RECEIPT).exists():
                raise InstallError("Source contains an installation receipt: " + str(source))
            text = (source / "SKILL.md").read_text(encoding="utf-8")
            parts = text.split("---", 2)
            if len(parts) != 3 or parts[0].strip():
                raise InstallError("Missing frontmatter: " + str(source))
            # 本仓库使用单行 name/description；不实现通用 YAML 解析器。
            names = re.findall(r"^name: ([a-z0-9-]+)\s*$", parts[1], re.MULTILINE)
            descriptions = re.findall(r"^description: (.+)$", parts[1], re.MULTILINE)
            if names != [source.name] or source.name != skill_name(source.name):
                raise InstallError("Directory/frontmatter name mismatch: " + str(source))
            if len(descriptions) != 1 or not 1 <= len(descriptions[0].strip()) <= 1024:
                raise InstallError("Invalid single-line description: " + str(source))
            if source.name in result:
                raise InstallError("Duplicate skill: " + source.name)
            result[source.name] = {"path": source, "version": manifest["version"], "files": files}
    if not result:
        raise InstallError("No skills found in " + str(repo))
    return result


def source_revision(repo):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()
    try:
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "plugins"))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def read_install(path):
    if not path.exists() and not path.is_symlink():
        return None
    files = snapshot(path)
    receipt = path / RECEIPT
    if not receipt.is_file():
        raise InstallError("Unmanaged directory: " + str(path))
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("tool") != "ForgeSteward" or data.get("schema") != 1
            or data.get("name") != path.name or not isinstance(data.get("version"), str)
            or not isinstance(data.get("files"), dict)):
        raise InstallError("Invalid installation receipt: " + str(receipt))
    if files != data["files"]:
        raise InstallError("Locally modified skill: " + str(path))
    return data


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


@contextmanager
def locked(root):
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = root.parent / LOCK
    try:
        fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise InstallError("Installer lock exists: {}. Check for a running installer or interrupted transaction before removing it.".format(lock))
    try:
        with os.fdopen(fd, "w") as file:
            file.write("pid={}\n".format(os.getpid()))
        interrupted = sorted(root.parent.glob(".forge-steward-txn-*"))
        if interrupted:
            raise InstallError("Recover the interrupted transaction before retrying: " + str(interrupted[0]))
        yield
    finally:
        lock.unlink()


def plan_changes(command, names, root, available):
    changes = []
    for name in names:
        destination = root / name
        try:
            current = read_install(destination)
        except (InstallError, ValueError) as error:
            raise InstallError("{}. Back up/move the entire directory outside the skill search paths, then install again; no --force overwrite is provided.".format(error))
        if command == "uninstall":
            if current is not None:
                changes.append((name, current, None))
            else:
                print("Not installed: " + name)
            continue
        wanted = available[name]
        if wanted["path"] == destination or wanted["path"] in destination.parents:
            raise InstallError("Installation destination overlaps source: " + str(destination))
        if current and current["version"] == wanted["version"] and current["files"] == wanted["files"]:
            print("Already installed: {} {}".format(name, current["version"]))
            continue
        if command == "install" and current:
            raise InstallError("{} is installed at {} with different content/version; use update explicitly.".format(name, current["version"]))
        if command == "update" and current is None:
            raise InstallError(name + " is not installed; use install first.")
        changes.append((name, current, wanted))
    return changes


def transact(root, changes, revision):
    if not changes:
        return
    root.mkdir(exist_ok=True)
    # 放在 skills 外，避免 OpenCode 在安装期间发现 staging/backup 中的 SKILL.md。
    transaction = Path(tempfile.mkdtemp(prefix=".forge-steward-txn-", dir=str(root.parent)))
    journal = []
    try:
        for name, _, wanted in changes:
            if wanted is None:
                continue
            staged = transaction / ("new-" + name)
            shutil.copytree(wanted["path"], staged, symlinks=True)
            if snapshot(staged) != wanted["files"]:
                raise InstallError("Source changed during staging: " + name)
            data = {"tool": "ForgeSteward", "schema": 1, "name": name,
                    "version": wanted["version"], "source": revision, "files": wanted["files"]}
            (staged / RECEIPT).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # 所有选中项先验证、暂存，再改动安装目录。
        for name, current, wanted in changes:
            destination = root / name
            if read_install(destination) != current:
                raise InstallError("Installation changed during operation: " + name)
            backup = transaction / ("old-" + name)
            entry = {"destination": destination, "backup": backup, "installed": False}
            journal.append(entry)
            if current is not None:
                os.replace(destination, backup)
            if wanted is not None:
                os.replace(transaction / ("new-" + name), destination)
                entry["installed"] = True
    except BaseException:
        try:
            for entry in reversed(journal):
                if entry["installed"]:
                    shutil.rmtree(entry["destination"])
                if entry["backup"].exists():
                    os.replace(entry["backup"], entry["destination"])
        except BaseException as error:
            raise InstallError("Rollback incomplete. Preserve and recover backups from {}: {}".format(transaction, error)) from error
        shutil.rmtree(transaction)
        raise
    shutil.rmtree(transaction)
    for name, current, wanted in changes:
        if wanted is None:
            print("Uninstalled: " + name)
        else:
            print("{}: {} {} -> {}".format("Updated" if current else "Installed", name, current["version"] if current else "absent", wanted["version"]))


def report_uninstall_residues(root, names, all_skills):
    """只读核对本次选择的名称；不跨作用域、不跟随链接、不推定归属。"""
    print("Residual scan (selected names, target directory only): " + str(root))
    reject_links(root)
    candidates = sorted(root.iterdir()) if root.exists() else []
    selected = set(names)
    legacy = LEGACY_NAMES if all_skills else {
        name[len(PREFIX):] for name in names if name[len(PREFIX):] in LEGACY_NAMES
    }
    remaining = False
    scan_failed = False
    for path in candidates:
        if not (path.name in legacy or path.name in selected
                or (all_skills and path.name.startswith(PREFIX))):
            continue
        remaining = True
        if is_link(path):
            reason = "link/reparse point; not followed"
        elif path.name in legacy:
            reason = "possible legacy name; ownership unverified"
        else:
            try:
                current = read_install(path)
                reason = "managed installation remains" if current else "entry changed during scan"
            except OSError as error:
                scan_failed = True
                reason = "scan failed: " + str(error)
            except (InstallError, ValueError) as error:
                reason = str(error)
        print("Residual: {} ({})".format(path, reason))
    if remaining:
        print("Residual candidates were NOT deleted. Inspect ownership and back up/move confirmed copies outside skill search paths; do not delete unrelated files.")
    else:
        print("No residual candidates for the selected names in this target.")
    print("Other projects, user scopes, compatibility/custom paths and old sessions were NOT checked. Verify with opencode debug skill in a new session.")
    return 1 if scan_failed else (2 if remaining else 0)


def parser():
    cli = argparse.ArgumentParser(description="Manage OpenCode skills from this checkout using Python's standard library.")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List skills available in this checkout")
    for command in ("install", "update", "uninstall", "status"):
        sub = commands.add_parser(command)
        sub.add_argument("skills", nargs="*", help="Plugin short names or full forge-steward skill names")
        sub.add_argument("--all", action="store_true", help="Select all available skills (all managed installs for uninstall)")
        scope = sub.add_mutually_exclusive_group(required=True)
        scope.add_argument("--project", metavar="PATH", help="Use PATH/.opencode/skills")
        scope.add_argument("--user", action="store_true", help="Use OPENCODE_CONFIG_DIR/skills, XDG_CONFIG_HOME/opencode/skills, or ~/.config/opencode/skills")
        if command == "uninstall":
            sub.epilog = "After uninstall, report selected-name residues in the target only. Exit: 0 none found, 1 operation/scan failure, 2 residues (also argparse usage errors)."
    return cli


def main(argv=None, repo=REPO):
    args = parser().parse_args(argv)
    try:
        # 卸载只依赖已安装收据；原技能从新版本 checkout 删除后仍可卸载。
        available = {} if args.command == "uninstall" else catalog(repo)
        if args.command == "list":
            for name, item in available.items():
                print(name + " " + item["version"])
            return 0
        if bool(args.skills) == args.all:
            raise InstallError("Choose skill names OR --all.")
        root = target_root(args)
        print("Target: " + str(root))
        if args.all and args.command == "uninstall":
            # iterdir 不像 glob 那样隐藏目录访问错误；扫描失败不得报卸载成功。
            names = sorted(p.name for p in root.iterdir()
                           if p.name.startswith(PREFIX) and (p / RECEIPT).exists()) if root.exists() else []
        else:
            names = sorted(available) if args.all else sorted({skill_name(n) for n in args.skills})
        for name in names:
            if name != skill_name(name):
                raise InstallError("Invalid installed name: " + name)
            if args.command != "uninstall" and name not in available:
                raise InstallError("Unknown skill: " + name)
        if args.command == "status":
            failed = False
            for name in names:
                try:
                    data = read_install(root / name)
                    state = "not installed"
                    if data:
                        wanted = available[name]
                        differs = data["version"] != wanted["version"] or data["files"] != wanted["files"]
                        state = "installed " + data["version"]
                        state += " (checkout differs; use update)" if differs else " (matches checkout)"
                    print("{}: {}".format(name, state))
                except (InstallError, ValueError) as error:
                    failed = True
                    print(str(error))
            return int(failed)
        if args.command == "uninstall":
            failed = False
            try:
                if root.exists():
                    with locked(root):
                        changes = plan_changes(args.command, names, root, available)
                        transact(root, changes, {})
                else:
                    print("No managed installations.")
            except (InstallError, OSError, ValueError) as error:
                failed = True
                print("Error: " + str(error), file=sys.stderr)
            # 即使预检或事务失败也展示仍在目标内的内容；错误退出码优先。
            residue_code = report_uninstall_residues(root, names, args.all)
            return 1 if failed else residue_code
        with locked(root):
            changes = plan_changes(args.command, names, root, available)
            transact(root, changes, source_revision(repo) if args.command != "uninstall" else {})
        return 0
    except (InstallError, OSError, ValueError, KeyError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
