#!/usr/bin/env python3
"""Check which ForgeSteward version each supported agent has at user level, and upgrade on consent.

How to find an agent, its installed plugins and its install commands comes
only from agents.json next to this script; nothing here repeats those
commands or paths. `check` never writes to agent configuration, install
directories or the maintained repository: external commands run without a
shell, with a timeout, and the only file written is the optional --output
result. The latest release is read with gh, or without credentials from the
GitHub API when gh fails. run_record.py renders the work-cycle report lines
from the --json result.

`apply` runs only after the user agreed to a target version and a list of
agents. It checks again, stops when the latest release changed, skips agents
that are already current or newer (never downgrades), handles one agent at a
time at user level only, and judges each agent by checking it again
afterwards. OpenCode and DeepSeek Harness use the installers of a source tree
whose commit matches the release tag; a temporary clone is deleted at the end.
One apply runs at a time, guarded by a lock directory in the system temporary
directory that is never removed on someone else's behalf. Once changes start,
an unexpected file error only marks the agent being handled, and a temporary
or lock directory that cannot be deleted is reported under "cleanup"; the
result is always the per-agent outcome, never a usage error.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import urllib.request


HERE = Path(__file__).resolve().parent
CATALOG = HERE / "agents.json"
# Plugins of this unified version; tests/test_agent_install.py keeps it equal to the repository's plugins/.
PLUGINS = ("check-workflow", "execute-work", "fix-feedback", "prepare-work", "review-and-merge", "work-cycle")
RELEASE_API = "https://api.github.com/repos/{repository}/releases/latest"
COMMAND_TIMEOUT = 20
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
TAG = re.compile(r"v(\d+\.\d+\.\d+)")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

ABSENT = "未安装 Agent"
MISSING = "缺少"
INCOMPLETE = "不完整"
BEHIND = "落后"
CURRENT = "最新"
AHEAD = "高于最新正式版"
UNKNOWN = "无法判断"
STATUSES = (ABSENT, MISSING, INCOMPLETE, BEHIND, CURRENT, AHEAD, UNKNOWN)


class Unknown(Exception):
    """The state cannot be determined; the message is a short everyday-Chinese reason."""


def expand(text):
    return Path(os.path.expanduser(text))


def stop(process):
    """Kill the command and anything it started, without waiting for its output pipes."""
    try:
        if os.name == "nt":
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
            subprocess.run([str(taskkill), "/F", "/T", "/PID", str(process.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        process.kill()
    except OSError:
        pass


def run_json(argv, timeout):
    """Run a read-only list command and parse its JSON output."""
    program = shutil.which(argv[0])
    if not program:
        raise Unknown("找不到命令 " + argv[0])
    extra = {} if os.name == "nt" else {"start_new_session": True}
    # Output goes to an anonymous temporary file so a timed-out child cannot block on a pipe.
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen([program] + list(argv[1:]), stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.DEVNULL, **extra)
        except OSError as error:
            raise Unknown("无法运行 %s：%s" % (argv[0], error.strerror or error))
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(process)
            raise Unknown("命令超时（%g 秒）" % timeout)
        output.seek(0)
        data = output.read()
    if code:
        raise Unknown("命令返回 %d" % code)
    try:
        return json.loads(data.decode("utf-8-sig"))
    except ValueError:
        raise Unknown("输出格式无法识别")


def fill(argv, values):
    result = []
    for arg in argv:
        for key, value in values.items():
            arg = arg.replace("{" + key + "}", value)
        if PLACEHOLDER.search(arg):
            raise Unknown("数据文件中的命令缺少参数：" + arg)
        result.append(arg)
    return result


def receipt_root(method):
    """First user root whose environment variable is set, else the default path."""
    for entry in method["user_roots"]:
        if "env" in entry:
            value = os.environ.get(entry["env"])
            if value:
                return expand(value) / entry["suffix"]
        else:
            return expand(entry["path"])
    raise Unknown("数据文件没有用户级目录")


def from_list(method, values, timeout):
    data = run_json(fill(method["argv"], values), timeout)
    items = data if method["items"] is None else data.get(method["items"]) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise Unknown("输出格式无法识别")
    found, other = {}, set()
    suffix = method["id_suffix"]
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(method["id_field"]), str):
            raise Unknown("输出格式无法识别")
        ident = item[method["id_field"]]
        if not ident.endswith(suffix):
            continue
        version = item.get(method["version_field"])
        if not isinstance(version, str):
            raise Unknown("输出格式无法识别")
        name = ident[:-len(suffix)]
        # Only user-level installs count; other scopes are noted separately.
        if item.get("scope", "user") != "user":
            other.add(name)
        else:
            found[name] = version
    return found, sorted(other)


def from_receipts(method):
    root = receipt_root(method)
    if not root.is_dir():
        return {}, []
    prefix = method["pattern"].rstrip("*")
    found, manual = {}, []
    for path in sorted(root.glob(method["pattern"])):
        if not path.is_dir():
            continue
        receipt = path / method["receipt"]
        if not receipt.is_file():
            manual.append(path.name)
            continue
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except ValueError:
            data = None
        version = data.get(method["version_field"]) if isinstance(data, dict) else None
        if not isinstance(version, str):
            raise Unknown("安装记录无法识别：" + path.name)
        found[path.name[len(prefix):]] = version
    if manual:
        raise Unknown("有手工副本（%s），无法判断" % "、".join(manual))
    return found, []


def command_values(agent, platform):
    """Placeholder values an agent's commands need, such as the ZCode CLI path; raise Unknown if missing."""
    where = agent["detect_agent"]
    for name in where.get("requires_commands", []):
        if not shutil.which(name):
            raise Unknown("缺少命令 " + name)
    values = {}
    if where.get("provides"):
        candidates = where.get("paths", {}).get(platform, [])
        paths = [path for path in candidates if expand(path).exists()]
        if not paths:
            raise Unknown("找不到 %s，已查：%s" % (where["provides"], "、".join(candidates) or "本平台没有已核对的位置"))
        values[where["provides"]] = str(expand(paths[0]))
    return values


def detect(agent, platform, timeout):
    """Return (present, found plugins, other-scope plugins); raise Unknown when it cannot tell."""
    where = agent["detect_agent"]
    method = agent["detect_install"]
    paths = [path for path in where.get("paths", {}).get(platform, []) if expand(path).exists()]
    present = (any(shutil.which(name) for name in where.get("commands", []))
               or bool(paths) or any(expand(path).is_dir() for path in where.get("config_dirs", [])))
    if not present and method["method"] == "receipt":
        present = receipt_root(method).is_dir()
    if not present:
        return False, {}, []
    values = command_values(agent, platform)
    if method["method"] == "list-command":
        found, other = from_list(method, values, timeout)
    elif method["method"] == "receipt":
        found, other = from_receipts(method)
    else:
        raise Unknown("数据文件中的检测方式无法识别：" + str(method["method"]))
    return True, found, other


def version_key(text):
    match = VERSION.fullmatch(text)
    return tuple(int(part) for part in match.groups()) if match else None


def inspect(agent, retired, platform, timeout):
    """Find what one agent has installed; any failure only marks this agent as undeterminable."""
    record = {"id": agent["id"], "name": agent["name"]}
    try:
        present, found, other = detect(agent, platform, timeout)
        if not present:
            record["status"] = ABSENT
            return record
        current = {name: version for name, version in found.items() if name in PLUGINS}
        old = {name: version for name, version in found.items() if name in retired}
        versions = sorted(set(current.values()) | set(old.values()), key=lambda v: version_key(v) or ())
        bad = [version for version in versions if version_key(version) is None]
        if bad:
            raise Unknown("版本号格式无法识别：" + "、".join(bad))
    except Unknown as error:
        record.update(status=UNKNOWN, reason=str(error))
        return record
    except OSError as error:
        record.update(status=UNKNOWN, reason="无法读取：%s" % (error.strerror or error))
        return record
    record.update(plugins=dict(sorted(current.items())), versions=versions,
                  missing=[name for name in PLUGINS if name not in current])
    if old:
        record["retired"] = dict(sorted(old.items()))
    if other:
        record["other_scopes"] = other
    return record


def classify(record, latest):
    """Set the status of an inspected agent against the latest formal release (None when unknown)."""
    if "status" in record:
        return record
    keys = [version_key(version) for version in record["versions"]]
    target = version_key(latest) if latest else None
    if not keys:
        record["status"] = MISSING
    elif target and any(key > target for key in keys):
        record["status"] = AHEAD
    elif target and any(key < target for key in keys):
        record["status"] = BEHIND
    elif record["missing"]:
        record["status"] = INCOMPLETE
    elif target:
        record["status"] = CURRENT
    else:
        record.update(status=UNKNOWN, reason="无法确认最新版本")
    return record


def release(tag, draft, prerelease, source):
    if draft or prerelease:
        raise Unknown("最新发布 %s 是草稿或预发布" % tag)
    match = TAG.fullmatch(tag) if isinstance(tag, str) else None
    if not match:
        raise Unknown("最新发布的 Tag %s 不是 vX.Y.Z 形式" % tag)
    return {"version": match.group(1), "tag": tag, "source": source}


def latest_release(repository, api_url, timeout):
    """Latest formal release from gh, else from the GitHub API without credentials."""
    problems = []
    if shutil.which("gh"):
        try:
            data = run_json(["gh", "release", "view", "--repo", repository, "--json", "tagName,isDraft,isPrerelease"],
                            timeout)
            if not isinstance(data, dict):
                raise Unknown("输出格式无法识别")
        except Unknown as error:
            problems.append("gh：" + str(error))
        else:
            try:
                return release(data.get("tagName"), data.get("isDraft"), data.get("isPrerelease"), "gh")
            except Unknown as error:
                return {"version": None, "error": str(error)}
    else:
        problems.append("没有 gh")
    request = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "ForgeSteward-agent-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return release(data.get("tag_name"), data.get("draft"), data.get("prerelease"), "api")
    except Unknown as error:
        return {"version": None, "error": str(error)}
    except (OSError, ValueError) as error:
        problems.append("GitHub 接口：%s" % (getattr(error, "reason", None) or error))
    return {"version": None, "error": "；".join(problems)}


def load_catalog(path):
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Cannot read agent catalog %s: %s" % (path, error))
    try:
        for agent in catalog["agents"]:
            agent["id"], agent["name"], agent["detect_agent"], agent["detect_install"]["method"]
        catalog["repository"]
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed agent catalog %s: %s" % (path, error))
    return catalog


def check(catalog, api_url=None, timeout=COMMAND_TIMEOUT, platform=sys.platform, now=None):
    """Check every catalog agent and the latest release concurrently; never raises for one agent."""
    api_url = api_url or RELEASE_API.format(repository=catalog["repository"])
    retired = set(catalog.get("retired_plugins", []))
    with ThreadPoolExecutor(max_workers=len(catalog["agents"]) + 1) as pool:
        latest_job = pool.submit(latest_release, catalog["repository"], api_url, timeout)
        jobs = [pool.submit(inspect, agent, retired, platform, timeout) for agent in catalog["agents"]]
        latest = latest_job.result()
        agents = [classify(job.result(), latest["version"]) for job in jobs]
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {"schema": 1, "checked_at": moment.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "plugins": list(PLUGINS), "latest": latest, "agents": agents}


# ---- apply: install or upgrade the agents the user agreed to ----

ACTIONABLE = (MISSING, INCOMPLETE, BEHIND)
STEP_TIMEOUT = 900
COMMIT_API = "https://api.github.com/repos/{repository}/commits/{tag}"
LOCK_NAME = "forge-steward-agent-install.lock"
SHA = re.compile(r"[0-9a-f]{40}")
OUTPUT_TAIL = 600
# Claude Code keeps each marketplace as a Git clone under <config dir>/plugins/marketplaces/<name>; the same
# place under other agents' config dirs is used only when it, too, is a clean Git clone at the release commit.
MARKETPLACE_COPY = ("plugins", "marketplaces")


class Stop(Exception):
    """apply stops before changing anything; the message is an everyday-Chinese reason."""


def file_error(error):
    """Short reason for an OSError, with the path it concerns when known."""
    reason = error.strerror or str(error)
    return "%s（%s）" % (reason, error.filename) if error.filename else reason


def remove_tree(path):
    """Delete a directory this script created, including read-only Git objects on Windows."""
    def writable(function, name, _):
        os.chmod(name, stat.S_IWRITE)
        function(name)
    if os.path.lexists(str(path)):
        shutil.rmtree(str(path), onerror=writable)


def run_step(argv, cwd, timeout):
    """Run one changing command without a shell; return (exit code or None, tail of its errors or output)."""
    program = argv[0] if os.path.isabs(argv[0]) else shutil.which(argv[0])
    if not program:
        return None, "找不到命令 " + argv[0]
    extra = {} if os.name == "nt" else {"start_new_session": True}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen([program] + list(argv[1:]), cwd=str(cwd), stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=errors, **extra)
        except OSError as error:
            return None, "无法运行 %s：%s" % (argv[0], error.strerror or error)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(process)
            return None, "命令超时（%g 秒）" % timeout
        except BaseException:
            stop(process)
            raise
        texts = []
        for stream in (errors, output):
            stream.seek(0)
            texts.append(stream.read().decode("utf-8", "replace").strip())
    return code, (texts[0] or texts[1])[-OUTPUT_TAIL:]


def git_output(directory, args, timeout):
    """Output of a read-only git command in directory, or None when it fails."""
    program = shutil.which("git")
    if not program:
        return None
    try:
        done = subprocess.run([program, "--no-optional-locks", "-C", str(directory)] + list(args),
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None


def tag_commit(repository, tag, api_url, timeout):
    """Commit of the release tag from gh, else from the GitHub API without credentials."""
    problems = []
    if shutil.which("gh"):
        try:
            data = run_json(["gh", "api", "repos/%s/commits/%s" % (repository, tag)], timeout)
            sha = data.get("sha") if isinstance(data, dict) else None
            if isinstance(sha, str) and SHA.fullmatch(sha):
                return sha
            problems.append("gh：输出格式无法识别")
        except Unknown as error:
            problems.append("gh：" + str(error))
    else:
        problems.append("没有 gh")
    request = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "ForgeSteward-agent-install"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        sha = data.get("sha") if isinstance(data, dict) else None
        if isinstance(sha, str) and SHA.fullmatch(sha):
            return sha
        problems.append("GitHub 接口：输出格式无法识别")
    except (OSError, ValueError) as error:
        problems.append("GitHub 接口：%s" % (getattr(error, "reason", None) or error))
    raise Unknown("查不到 %s 对应的提交（%s）" % (tag, "；".join(problems)))


def installer_steps(agent):
    """(clone step, installer script template, uninstall exit codes) from the catalog's install commands."""
    clone = next(step for step in agent["commands"]["install"] if step.get("skip_if_exists"))
    script = next(step["argv"][1] for step in agent["commands"]["install"]
                  if not step.get("skip_if_exists") and "{source}" in " ".join(step["argv"]))
    removal = next(step for step in agent["commands"]["uninstall"] if not step.get("skip_if_exists"))
    return clone, script, removal.get("ok_exit_codes", [0])


class Sources:
    """The release source tree for OpenCode and DeepSeek Harness, prepared once per apply."""

    def __init__(self, catalog, version, work, options):
        self.catalog, self.version, self.work, self.options = catalog, version, work, options
        self.result = None

    def get(self, agent):
        if self.result is None:
            try:
                self.result = self.prepare(agent)
            except Unknown as error:
                self.result = error
            except OSError as error:
                self.result = Unknown("准备源码时出现意外的文件错误：" + file_error(error))
        if isinstance(self.result, Unknown):
            raise self.result
        return self.result

    def local_copies(self):
        for agent in self.catalog["agents"]:
            for directory in agent["detect_agent"].get("config_dirs", []):
                yield expand(directory).joinpath(*MARKETPLACE_COPY) / self.catalog["marketplace"]

    def prepare(self, agent):
        repository, tag, timeout = self.catalog["repository"], "v" + self.version, self.options.command_timeout
        api = self.options.commit_api or COMMIT_API.format(repository=repository, tag=tag)
        commit = tag_commit(repository, tag, api, timeout)
        for copy in self.local_copies():
            if ((copy / ".git").exists() and git_output(copy, ["rev-parse", "HEAD"], timeout) == commit
                    and git_output(copy, ["status", "--porcelain"], timeout) == ""):
                return copy, "用了本地已有的副本 %s（与 %s 的提交一致）" % (copy, tag)
        target = self.work / "source"
        clone = fill(installer_steps(agent)[0]["argv"], {"version": self.version, "source": str(target)})
        if self.options.source_url:
            official = "https://github.com/%s.git" % repository
            clone = [self.options.source_url if arg == official else arg for arg in clone]
        code, text = run_step(clone, self.work, self.options.step_timeout)
        if code != 0:
            remove_tree(target)
            raise Unknown("下载 %s 的源码失败：%s" % (tag, last_line(text) or "返回 %s" % code))
        head = git_output(target, ["rev-parse", "HEAD"], timeout)
        if head != commit:
            remove_tree(target)
            raise Unknown("下载的源码提交 %s 与 Release %s 的提交 %s 不一致，没有安装" % (head or "未知", tag, commit))
        return target, "下载了 %s 的源码到临时目录，提交已核对，用完已删除" % tag


def last_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][-300:] if lines else ""


def has_marketplace(agent, name, values, timeout):
    """Whether the agent lists the marketplace; raise Unknown when the list cannot be read."""
    method = agent["detect_marketplace"]
    argv, field = fill(method["argv"], values), method["name_field"]
    try:
        data = run_json(argv, timeout)
        items = data if method["items"] is None else data.get(method["items"]) if isinstance(data, dict) else None
        if not isinstance(items, list) or not all(isinstance(item, dict) and isinstance(item.get(field), str)
                                                  for item in items):
            raise Unknown("输出格式无法识别")
    except Unknown as error:
        raise Unknown("查不到市场是否存在：%s" % error)
    return any(item[field] == name for item in items)


def plugin_steps(agent, record, version, values, marketplace, timeout):
    """Commands for an agent that installs plugins one by one (Claude Code, Codex, ZCode).

    The upgrade steps serve a first install too: with nothing installed the uninstall step is empty, and a
    marketplace left behind (perhaps from an older release) is removed before the target one is added. Whether
    it exists is asked before any change, so an unreadable list leaves this agent untouched.
    """
    installed = sorted(set(record.get("plugins", {})) | set(record.get("retired", {})))
    values = dict(values, version=version)
    steps = agent["commands"]["upgrade"]
    if any(step.get("only_if_marketplace") for step in steps):
        if not has_marketplace(agent, marketplace, values, timeout):
            steps = [step for step in steps if not step.get("only_if_marketplace")]
    planned = []
    for step in steps:
        ok = step.get("ok_exit_codes", [0])
        if step.get("per_plugin"):
            names = installed if step.get("only_installed") else list(PLUGINS)
            planned += [(fill(step["argv"], dict(values, plugin=name)), ok) for name in names]
        else:
            planned.append((fill(step["argv"], values), ok))
    return planned


def skill_steps(agent, record, version, source):
    """Installer commands per skill (OpenCode, DeepSeek Harness): install missing, update older, drop retired."""
    _, script, removal_ok = installer_steps(agent)
    prefix = agent["detect_install"]["pattern"].rstrip("*")
    run = [sys.executable, fill([script], {"source": str(source), "version": version})[0]]
    target = version_key(version)
    planned = []
    for name in PLUGINS:
        have = record.get("plugins", {}).get(name)
        if have is None:
            planned.append((run + ["install", prefix + name, "--user"], [0]))
        elif version_key(have) < target:
            planned.append((run + ["update", prefix + name, "--user"], [0]))
    for name in sorted(record.get("retired", {})):
        planned.append((run + ["uninstall", prefix + name, "--user"], removal_ok))
    return planned


def skip_reason(record):
    status = record["status"]
    if status == ABSENT:
        return "本机没有这个 Agent"
    if status == CURRENT:
        return "已是最新"
    if status == AHEAD:
        return "已装 %s，比目标版本新，不降级" % "、".join("v" + v for v in record.get("versions", []))
    return "无法判断：" + record.get("reason", "")


def apply_agent(agent, record, version, retired, platform, options, sources, work, marketplace):
    """Handle one agent; any failure, including an unexpected file error, stays inside this agent's entry."""
    entry = {"id": agent["id"], "name": agent["name"], "before": record["status"], "steps": [], "problems": []}
    if record.get("versions"):
        entry["before_versions"] = record["versions"]
    if record.get("other_scopes"):
        entry["other_scopes"] = record["other_scopes"]
    if record["status"] not in ACTIONABLE:
        entry["skipped"] = skip_reason(record)
        return entry
    per_skill = agent["detect_install"]["method"] == "receipt"
    stage = "准备安装步骤"
    try:
        try:
            if per_skill:
                source, entry["source"] = sources.get(agent)
                steps = skill_steps(agent, record, version, source)
            else:
                steps = plugin_steps(agent, record, version, command_values(agent, platform), marketplace,
                                     options.command_timeout)
        except Unknown as error:
            entry["problems"].append(str(error))
            steps = []
        except (KeyError, IndexError, TypeError, StopIteration):
            entry["problems"].append("数据文件中的安装命令无法识别")
            steps = []
        for argv, ok in steps:
            stage = "运行 `%s` " % shown(argv)
            code, text = run_step(argv, work, options.step_timeout)
            step = {"argv": argv, "code": code, "ok": code in ok}
            if not step["ok"]:
                step["output"] = text
            entry["steps"].append(step)
            # One skill refused by an installer does not stop the others; a failed plugin command stops this agent.
            if not step["ok"] and not per_skill:
                break
    except OSError as error:
        # The rest of this agent's steps are skipped; the check below still decides whether it is done.
        entry["problems"].append("%s时出现意外的文件错误：%s" % (stage, file_error(error)))
    after = classify(inspect(agent, retired, platform, options.command_timeout), version)
    entry["after"] = {key: after[key] for key in ("status", "versions", "missing", "reason") if key in after}
    entry["done"] = after["status"] == CURRENT
    return entry


def tidy(path, kind, cleanup):
    """Delete a directory this apply created; a failure is added to cleanup instead of raised."""
    try:
        remove_tree(path)
    except OSError as error:
        cleanup.append({"kind": kind, "path": str(path), "reason": file_error(error)})


@contextmanager
def apply_lock(cleanup):
    """Only one apply at a time; an existing lock is reported, never removed. A failed removal goes to cleanup."""
    lock = Path(tempfile.gettempdir()) / LOCK_NAME
    try:
        os.mkdir(str(lock))
    except FileExistsError:
        raise Stop("另一个安装正在进行（锁目录 %s 已存在）。确认没有安装在运行后，再手动删除它" % lock)
    except OSError as error:
        raise Stop("无法建立锁目录 %s：%s" % (lock, error.strerror or error))
    try:
        try:
            (lock / "owner").write_text("pid=%d\n" % os.getpid(), encoding="utf-8")
        except OSError as error:
            raise Stop("无法写入锁目录：" + file_error(error))
        yield
    finally:
        tidy(lock, "lock", cleanup)


def apply(catalog, version, ids, options, platform=sys.platform):
    """Check again, then install or upgrade the agreed agents one by one at user level; never raises OSError."""
    cleanup = []
    try:
        with apply_lock(cleanup):
            api_url = options.release_api or RELEASE_API.format(repository=catalog["repository"])
            try:
                result = check(catalog, api_url, options.command_timeout, platform)
            except OSError as error:
                raise Stop("重新检查时出现意外的文件错误：" + file_error(error))
            latest = result["latest"]["version"]
            if latest is None:
                raise Stop("无法确认最新版本：" + result["latest"].get("error", ""))
            if latest != version:
                raise Stop("最新正式版已变成 v%s，不是同意的 v%s；请按新版本重新询问" % (latest, version))
            records = {record["id"]: record for record in result["agents"]}
            retired = set(catalog.get("retired_plugins", []))
            try:
                work = Path(tempfile.mkdtemp(prefix="forge-steward-apply-"))
            except OSError as error:
                raise Stop("无法建立临时目录（%s）：%s" % (tempfile.gettempdir(), file_error(error)))
            # Changes start here: from now on every agreed agent gets an entry, whatever goes wrong.
            try:
                sources = Sources(catalog, version, work, options)
                entries = [apply_agent(agent, records[agent["id"]], version, retired, platform, options, sources,
                                       work, catalog["marketplace"])
                           for agent in catalog["agents"] if agent["id"] in ids]
            finally:
                tidy(work, "work", cleanup)
    except Stop as error:
        return {"schema": 1, "command": "apply", "version": version, "outcome": "stopped", "reason": str(error),
                "agents": [], "cleanup": cleanup}
    return {"schema": 1, "command": "apply", "version": version, "outcome": "done", "agents": entries,
            "cleanup": cleanup}


def shown(argv):
    return " ".join(Path(arg).name if os.path.isabs(arg) else arg for arg in argv)


def state_text(after):
    status = after["status"]
    if status == BEHIND or status == AHEAD:
        return "%s（%s）" % (status, "、".join("v" + v for v in after.get("versions", [])))
    if status == INCOMPLETE:
        return "不完整，缺 " + "、".join(after.get("missing", []))
    if status == UNKNOWN:
        return "无法判断：" + after.get("reason", "")
    return status


def cleanup_line(item):
    if item["kind"] == "lock":
        return ("锁目录 %s 没能删除：%s。确认没有安装在运行后手动删除它，否则下次会提示“另一个安装正在进行”"
                % (item["path"], item["reason"]))
    return "临时目录 %s 没能删除：%s，可以手动删除" % (item["path"], item["reason"])


def apply_lines(result):
    """Everyday-Chinese lines telling the user what actually happened."""
    cleanup = [cleanup_line(item) for item in result.get("cleanup", [])]
    if result["outcome"] == "stopped":
        return ["没有做任何改动：" + result["reason"]] + cleanup
    lines = []
    version = result["version"]
    for entry in result["agents"]:
        name = entry["name"]
        if "skipped" in entry:
            line = "%s：没有处理，%s" % (name, entry["skipped"])
        elif entry["done"]:
            if entry["before"] == MISSING:
                line = "%s：已安装 v%s" % (name, version)
            elif entry["before"] == BEHIND:
                line = "%s：已从 %s 升到 v%s" % (name, "、".join("v" + v for v in entry.get("before_versions", [])),
                                             version)
            else:
                line = "%s：已补齐，现在是 v%s" % (name, version)
            refused = [step for step in entry["steps"] if not step["ok"]]
            if refused:
                line += "；但有步骤没成功：" + "；".join("%s（%s）" % (shown(step["argv"]), last_line(step.get("output"))
                                                                   or "返回 %s" % step["code"]) for step in refused)
            if entry["problems"]:
                line += "；但" + "；".join(entry["problems"])
        else:
            parts = ["复查结果：" + state_text(entry["after"])] + entry["problems"]
            parts += ["`%s` 没成功：%s" % (shown(step["argv"]), last_line(step.get("output")) or "返回 %s" % step["code"])
                      for step in entry["steps"] if not step["ok"]]
            line = "%s：没有装好，%s。解决后再同意一次，重新运行即可补齐" % (name, "；".join(parts))
        if entry.get("other_scopes"):
            line += "（另有非用户级安装，没有改动）"
        lines.append(line)
    lines += cleanup
    if any(entry.get("done") for entry in result["agents"]):
        lines.append("新版本要在各 Agent 的下一个新会话里才生效。")
    return lines


def text_lines(result):
    """Everyday-Chinese lines, worded exactly as the work-cycle report renders them."""
    sys.dont_write_bytecode = True  # never leave __pycache__ inside the installed skill
    spec = importlib.util.spec_from_file_location("forge_steward_run_record", str(HERE / "run_record.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent_lines(result, module.load_report_spec())


def write_atomic(path, text):
    path = path.resolve()
    if not path.parent.is_dir():
        raise ValueError("Output directory does not exist: " + str(path.parent))
    temporary = path.parent / ("." + path.name + ".tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(str(temporary), str(path))


def write_utf8(text):
    """UTF-8 bytes whatever the console encoding."""
    sys.stdout.flush()
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(text)
    else:
        buffer.write(text.encode("utf-8"))
        buffer.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("check", help="read-only check; exit 0 whatever the result, 2 on usage errors")
    change = commands.add_parser(
        "apply", help="install or upgrade the agents the user agreed to; exit 0 all done and cleaned up, "
                      "1 some agent not done or some cleanup not done (one line each), 2 usage or environment error "
                      "before any change (nothing changed), 3 stopped before any change")
    change.add_argument("--version", required=True, help="the X.Y.Z the user saw and agreed to")
    change.add_argument("--agents", required=True, help="comma-separated agent ids the user agreed to")
    change.add_argument("--step-timeout", type=float, default=STEP_TIMEOUT)
    change.add_argument("--commit-api", help="GitHub API URL for the tag commit (tests use file://)")
    change.add_argument("--source-url", help="clone URL in place of the GitHub repository (tests use a local one)")
    for sub in (probe, change):
        sub.add_argument("--json", action="store_true", help="print the machine-readable result")
        sub.add_argument("--catalog", type=Path, default=CATALOG)
        sub.add_argument("--command-timeout", type=float, default=COMMAND_TIMEOUT)
        sub.add_argument("--release-api", help="GitHub API URL for the latest release (tests use file://)")
    probe.add_argument("--output", type=Path, help="also save the JSON result to this file")
    args = parser.parse_args(argv)
    try:
        if args.command_timeout <= 0:
            parser.error("--command-timeout must be positive")
        catalog = load_catalog(args.catalog)
        if args.command == "apply":
            ids = list(dict.fromkeys(item.strip() for item in args.agents.split(",") if item.strip()))
            known = [agent["id"] for agent in catalog["agents"]]
            if not VERSION.fullmatch(args.version):
                parser.error("--version must look like X.Y.Z")
            if not ids or any(item not in known for item in ids):
                parser.error("--agents must list ids from %s" % ", ".join(known))
            if args.step_timeout <= 0:
                parser.error("--step-timeout must be positive")
            result = apply(catalog, args.version, ids, args)
            lines = apply_lines(result)
            if result["cleanup"]:
                code = 1
            elif result["outcome"] == "stopped":
                code = 3
            else:
                code = 0 if all(entry.get("done", True) for entry in result["agents"]) else 1
        else:
            result = check(catalog, args.release_api, args.command_timeout)
            text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                write_atomic(args.output, text)
            lines = None if args.json else text_lines(result)
            code = 0
        if args.json:
            write_utf8(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        else:
            write_utf8("".join("- " + line + "\n" for line in lines))
        return code
    except (OSError, ValueError) as error:
        # Only errors before apply starts changing anything reach here; apply itself reports file errors per agent.
        print("ERROR: " + str(error), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
