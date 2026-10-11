#!/usr/bin/env python3
"""Check, read-only, which ForgeSteward version each supported agent has at user level.

How to find an agent and its installed plugins comes only from agents.json
next to this script; nothing here repeats those commands or paths. The check
never writes to agent configuration, install directories or the maintained
repository: external commands run without a shell, with a timeout, and the
only file written is the optional --output result. The latest release is
read with gh, or without credentials from the GitHub API when gh fails.
run_record.py renders the work-cycle report lines from the --json result.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
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
    for name in where.get("requires_commands", []):
        if not shutil.which(name):
            raise Unknown("缺少命令 " + name)
    values = {}
    if where.get("provides"):
        if not paths:
            raise Unknown("找不到 %s，已查：%s" % (where["provides"], "、".join(where.get("paths", {}).get(platform, []))
                                                  or "本平台没有已核对的位置"))
        values[where["provides"]] = str(expand(paths[0]))
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("check", help="read-only check; exit 0 whatever the result, 2 on usage errors")
    probe.add_argument("--json", action="store_true", help="print the machine-readable result")
    probe.add_argument("--output", type=Path, help="also save the JSON result to this file")
    probe.add_argument("--catalog", type=Path, default=CATALOG)
    probe.add_argument("--command-timeout", type=float, default=COMMAND_TIMEOUT)
    probe.add_argument("--release-api", help="GitHub API URL for the latest release (tests use file://)")
    args = parser.parse_args(argv)
    try:
        if args.command_timeout <= 0:
            parser.error("--command-timeout must be positive")
        result = check(load_catalog(args.catalog), args.release_api, args.command_timeout)
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            write_atomic(args.output, text)
        if not args.json:
            text = "".join("- " + line + "\n" for line in text_lines(result))
        # UTF-8 bytes whatever the console encoding.
        sys.stdout.flush()
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            sys.stdout.write(text)
        else:
            buffer.write(text.encode("utf-8"))
            buffer.flush()
        return 0
    except (OSError, ValueError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
