#!/usr/bin/env python3
"""Keep work-cycle run records with per-stage timings in a repository's Git metadata.

Each run gets runs/<run id>/ under <git common dir>/forge-steward/: run.json,
an append-only events.jsonl and one evidence directory per task. Records
never touch version-controlled files; prune only removes run directories
this script created. The report command renders the final summary from
handoff.json, the events and, when recorded, the agent_install.py check
result; its sections and wording come only from references/report.md.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time


MARKER = "forge-steward-run-record"
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{4}")
TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
STATUSES = ("started", "finished", "failed", "wait-start", "wait-end")
WAITS = ("ci", "lock", "review", "external", "other")
RELEASE_AUDIT_STATES = ("clean", "findings", "incomplete", "not-run")
SECRET_TEXT = re.compile(
    r"(?i)(?:bearer\s+[a-z0-9._~+/=-]{16,}"
    r"|gh[pousr]_[a-z0-9]{20,}"
    r"|github_pat_[a-z0-9_]{20,}"
    r"|xox[baprs]-[a-z0-9-]{10,}"
    r"|sk-[a-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*[^\s;,]{8,}"
    r"|https?://[^/\s:@]+:[^/\s@]+@)")
MAX_DETAIL = 1000
REPORT_RULES = Path(__file__).resolve().parent.parent / "references" / "report.md"
SPEC_FENCE = "```json report-spec"


class ReportDataError(Exception):
    """handoff.json does not match the report fields; carries one message per field."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def runs_root(repo):
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError("Target repository directory does not exist: " + str(repo))
    result = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo,
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError("Target is not a readable Git repository: " + str(repo))
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = repo / common
    common = common.resolve()
    if not common.is_dir():
        raise ValueError("Git common directory does not exist: " + str(common))
    return common / "forge-steward" / "runs"


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def error_text(error):
    return getattr(error, "strerror", None) or str(error)


def process_start(pid):
    """Best-effort comparable identity of a running process; the reason is returned when unreadable."""
    if sys.platform.startswith("linux"):
        try:
            stat = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
            fields = stat.rsplit(")", 1)[1].split()
            if len(fields) < 20:
                return None, "process start time is missing from /proc"
            return "linux:" + fields[19], None
        except (OSError, UnicodeError) as error:
            return None, "cannot read process start time: " + error_text(error)
    if os.name == "posix":
        try:
            result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True,
                                    text=True, timeout=2, env=dict(os.environ, LC_ALL="C"),
                                    check=False)
        except (OSError, subprocess.SubprocessError) as error:
            return None, "cannot read process start time: " + error_text(error)
        value = result.stdout.strip()
        if result.returncode or not value:
            return None, "process start time is unavailable: ps did not report it"
        return "ps:" + value, None
    if os.name == "nt":
        return windows_process_start(pid)
    return None, "process start time is unavailable on this platform"


def windows_open_process(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    return ctypes, wintypes, kernel, handle, ctypes.get_last_error()


def windows_process_start(pid):
    ctypes, wintypes, kernel, handle, error = windows_open_process(pid)
    if not handle:
        return None, "cannot open process %d to read its start time (error %d)" % (pid, error)
    try:
        creation = wintypes.FILETIME()
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME),
                                           ctypes.POINTER(wintypes.FILETIME)]
        kernel.GetProcessTimes.restype = wintypes.BOOL
        empty = [wintypes.FILETIME() for _ in range(3)]
        if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(empty[0]),
                                      ctypes.byref(empty[1]), ctypes.byref(empty[2])):
            return None, "cannot read process start time (error %d)" % ctypes.get_last_error()
        return "windows:%d" % ((creation.dwHighDateTime << 32) | creation.dwLowDateTime), None
    finally:
        kernel.CloseHandle(handle)


GUARD_OWNER = "owner.json"


def owner_metadata(purpose):
    start, start_error = process_start(os.getpid())
    owner = {"schema": 1, "purpose": purpose, "pid": os.getpid(),
             "acquired_at": stamp(datetime.now(timezone.utc))}
    if start:
        owner["process_start"] = start
    else:
        owner["process_start_error"] = start_error
    return owner


def read_guard_owner(guard):
    """Return the recorded owner and why it cannot be used; never guess an owner."""
    try:
        data = json.loads((guard / GUARD_OWNER).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "the guard has no " + GUARD_OWNER
    except (OSError, UnicodeError, ValueError) as error:
        return None, "the guard's owner metadata is unreadable: " + error_text(error)
    if (not isinstance(data, dict)
            or not isinstance(data.get("pid"), int) or isinstance(data.get("pid"), bool)
            or data["pid"] <= 0
            or not isinstance(data.get("acquired_at"), str) or not data["acquired_at"]):
        return None, "the guard's owner metadata is incomplete"
    return data, None


def guard_recovery(guard):
    owner, problem = read_guard_owner(guard)
    if owner is None:
        return ("owner metadata is unreadable (%s); confirm that no event writer is running, "
                "then remove %s to recover" % (problem, guard))
    started = (owner.get("process_start")
               or "unavailable: " + str(owner.get("process_start_error") or "not recorded"))
    return ("owner process %d (start time %s) acquired it at %s; confirm that writer stopped, "
            "then remove %s to recover" % (owner["pid"], started, owner["acquired_at"], guard))


def parse(text):
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("Timestamp has no timezone: " + text)
    return moment.astimezone(timezone.utc)


def run_dir(root, run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run id: " + repr(run_id))
    path = root / run_id
    if not (path / "run.json").is_file():
        raise ValueError("Unknown run: " + run_id)
    return path


def start(root, cycles, now):
    root.mkdir(parents=True, exist_ok=True)
    while True:
        run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)
        path = root / run_id
        try:
            path.mkdir()
            break
        except FileExistsError:
            continue
    (path / "run.json").write_text(json.dumps({"created_by": MARKER, "run_id": run_id,
                                               "created_at": stamp(now), "cycles": cycles},
                                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (path / "events.jsonl").touch()
    return run_id, path


def task_dir(path, task):
    if not TASK.fullmatch(task):
        raise ValueError("Invalid task id: " + repr(task))
    target = path / task
    target.mkdir(exist_ok=True)
    return target


def add_event(path, task, stage, status, wait, detail, moment):
    if status not in STATUSES:
        raise ValueError("Invalid status: " + status)
    if status.startswith("wait-") and wait not in WAITS:
        raise ValueError("wait-start and wait-end need --wait " + "/".join(WAITS))
    task_dir(path, task)
    record = {"at": stamp(moment), "task": task, "stage": stage, "status": status}
    if wait:
        record["wait"] = wait
    if detail:
        record["detail"] = detail.replace("\r", " ").replace("\n", " ")[:MAX_DETAIL]
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    # A short directory lock serializes appends; O_APPEND alone is not atomic on every OS.
    guard = path / ".events.lock"
    deadline = time.monotonic() + 10
    while True:
        try:
            os.mkdir(str(guard))
            break
        except OSError as error:
            # A Windows delete-pending directory rejects recreation with access denied.
            # Retry only this guard acquisition; retain other filesystem errors.
            if not isinstance(error, FileExistsError) and getattr(error, "winerror", None) != 5:
                raise
            if time.monotonic() > deadline:
                raise ValueError("Timed out waiting for %s: %s; %s"
                                 % (guard, error, guard_recovery(guard))) from error
            time.sleep(0.01)
    try:
        owner = owner_metadata("run-record event append")
        (guard / GUARD_OWNER).write_text(json.dumps(owner, ensure_ascii=False) + "\n", encoding="utf-8")
        fd = os.open(str(path / "events.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    finally:
        try:
            (guard / GUARD_OWNER).unlink()
        except FileNotFoundError:
            pass
        try:
            os.rmdir(str(guard))
        except FileNotFoundError:
            pass
    return record


def read_events(path):
    events = []
    for number, line in enumerate((path / "events.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                raise ValueError("Corrupt event on line %d" % number)
    return events


def summarize(path):
    events = sorted(read_events(path), key=lambda e: e["at"])
    tasks = {}
    for event in events:
        moment = parse(event["at"])
        item = tasks.setdefault(event["task"], {"task": event["task"], "stage": event["stage"],
                                                "started": None, "ended": None, "result": "running",
                                                "waits": {}, "_open": {}})
        if event["status"] == "started" and item["started"] is None:
            item["started"] = moment
        elif event["status"] in ("finished", "failed"):
            item["ended"] = moment
            item["result"] = event["status"]
        elif event["status"] == "wait-start":
            item["_open"][event["wait"]] = moment
        elif event["status"] == "wait-end" and event["wait"] in item["_open"]:
            begun = item["_open"].pop(event["wait"])
            item["waits"][event["wait"]] = item["waits"].get(event["wait"], 0) + (moment - begun).total_seconds()
    stages, waits = {}, {}
    report = []
    for item in tasks.values():
        seconds = None
        if item["started"] and item["ended"]:
            seconds = (item["ended"] - item["started"]).total_seconds()
            stages[item["stage"]] = stages.get(item["stage"], 0) + seconds
        for kind, value in item["waits"].items():
            waits[kind] = waits.get(kind, 0) + value
        report.append({"task": item["task"], "stage": item["stage"], "result": item["result"],
                       "seconds": seconds, "waits": item["waits"]})
    wall = None
    if events:
        wall = (parse(events[-1]["at"]) - parse(events[0]["at"])).total_seconds()
    return {"run_id": path.name, "wall_seconds": wall, "stage_seconds": stages,
            "wait_seconds": waits, "tasks": report}


def load_report_spec(path=REPORT_RULES):
    """Read the single shared report spec block from references/report.md."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError("Cannot read report rules: %s" % error)
    try:
        begin = lines.index(SPEC_FENCE)
        end = lines.index("```", begin + 1)
    except ValueError:
        raise ValueError("No report-spec block in " + str(path))
    try:
        spec = json.loads("\n".join(lines[begin + 1:end]))
    except ValueError as error:
        raise ValueError("Invalid report-spec JSON: %s" % error)
    try:
        results = spec["results"]
        valid = (len(spec["sections"]) == 7 and all(isinstance(x, str) and x for x in spec["sections"])
                 and len(results) == 7 and len(set(results)) == 7 and all(isinstance(x, str) and x for x in results)
                 and spec["merged"] in results and set(spec["needs_you"]) <= set(results)
                 and set(spec["issue_only"]) <= set(results)
                 and all(isinstance(k, str) and isinstance(v, str) for k, v in spec["stages"].items())
                 and set(spec["waits"]) == {"ci", "lock"} and isinstance(spec["title"], str)
                 and valid_agent_spec(spec["agents"])
                 and valid_release_audit(spec["release_audit_results"])
                 and valid_aliases(spec["result_aliases"], results))
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("Malformed report-spec block in " + str(path))
    return spec


AGENT_TEXTS = ("absent", "current", "other_scopes", "ask", "session_old", "ask_session")


def valid_aliases(aliases, current):
    """Legacy names map only to current names; no chains or replacement vocabulary."""
    return (isinstance(aliases, dict)
            and all(isinstance(k, str) and k and k not in current and v in current
                    for k, v in aliases.items()))


def valid_agent_spec(agents):
    """The agents block names every check status and the wording of each report line."""
    texts = [agents[key] for key in AGENT_TEXTS] + list(agents["statuses"].values())
    return (all(isinstance(text, str) and text for text in texts)
            and len(agents["statuses"]) == 6 and agents["absent"] not in agents["statuses"]
            and agents["current"] in agents["statuses"]
            and valid_aliases(agents["aliases"], [agents["absent"]] + list(agents["statuses"]))
            and bool(agents["ask_for"]) and set(agents["ask_for"]) <= set(agents["statuses"]) - {agents["current"]})


def valid_release_audit(results):
    """The optional audit field has exactly the four contract states and distinct display names."""
    return (isinstance(results, dict) and set(results) == set(RELEASE_AUDIT_STATES)
            and all(isinstance(value, str) and value for value in results.values())
            and len(set(results.values())) == len(results))


def contains_secret(text):
    """Report text must not copy tokens, passwords, credentialed URLs, or private keys."""
    return bool(SECRET_TEXT.search(text))


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


KINDS = {
    "text": (lambda v: isinstance(v, str) and v.strip() != "", "must be nonempty text"),
    "free": (lambda v: isinstance(v, str), "must be text"),
    "count": (lambda v: is_int(v) and v >= 0, "must be an integer greater than or equal to 0"),
    "positive": (lambda v: is_int(v) and v >= 1, "must be a positive integer"),
    "bool": (lambda v: isinstance(v, bool), "must be true or false"),
    "list": (lambda v: isinstance(v, list), "must be a list"),
    "object": (lambda v: isinstance(v, dict), "must be an object"),
    "issue": (lambda v: (is_int(v) and v >= 1) or (isinstance(v, str) and v.strip() != ""),
              "must be an Issue number or nonempty text"),
}


def normalize_handoff(data, spec):
    """Copy known legacy outcome fields without altering saved input or free text."""
    data = deepcopy(data)
    if isinstance(data, dict):
        for key in ("change_requests", "issues_without_change_request"):
            if isinstance(data.get(key), list):
                for item in data[key]:
                    if isinstance(item, dict) and isinstance(item.get("result"), str):
                        item["result"] = spec["result_aliases"].get(item["result"], item["result"])
    return data


def check_handoff(data, spec):
    """Return one message per invalid field; empty when the data can be rendered."""
    data = normalize_handoff(data, spec)
    if not isinstance(data, dict):
        return ["handoff.json top level must be an object"]
    problems = []

    def need(obj, key, path, kind, optional=False):
        where = ".".join(part for part in (path, key) if part)
        if key not in obj:
            if not optional:
                problems.append(where + " is required")
            return None
        accept, message = KINDS[kind]
        if not accept(obj[key]):
            problems.append(where + " " + message)
            return None
        return obj[key]

    def entries(key, optional=False):
        for index, item in enumerate(need(data, key, "", "list", optional) or []):
            yield "%s[%d]" % (key, index), item

    def outcome(item, where, allowed, message):
        result = need(item, "result", where, "free")
        if result is not None and result not in allowed:
            problems.append("%s.result %s: %s" % (where, message, json.dumps(result, ensure_ascii=False)))
        reason = need(item, "reason", where, "free")
        need(item, "next", where, "free")
        if result in spec["needs_you"] and reason is not None and not reason.strip():
            problems.append("%s.reason must not be empty when result is %s" % (where, result))

    need(data, "requested_cycles", "", "positive")
    need(data, "completed_cycles", "", "count")
    for key in ("stop_reason", "startup_check", "branch_cleanup"):
        need(data, key, "", "text")
    queue = need(data, "startup_queue", "", "object")
    if queue is not None:
        need(queue, "count", "startup_queue", "count")
        need(queue, "note", "startup_queue", "free")
    mode = need(data, "concurrency", "", "object")
    if mode is not None:
        enabled = need(mode, "enabled", "concurrency", "bool")
        if enabled is True:
            need(mode, "agent_limit", "concurrency", "positive")
        elif enabled is False:
            need(mode, "serial_reason", "concurrency", "text")
        need(mode, "note", "concurrency", "free", optional=True)
    for key in ("change_requests", "issues_without_change_request", "exceptions"):
        for where, item in entries(key):
            if not isinstance(item, dict):
                problems.append(where + " must be an object")
            elif key == "change_requests":
                need(item, "url", where, "text")
                need(item, "number", where, "positive")
                for spot, issue in enumerate(need(item, "issues", where, "list") or []):
                    need({"": issue}, "", "%s.issues[%d]" % (where, spot), "issue")
                outcome(item, where, spec["results"], "is not a known result")
            elif key == "issues_without_change_request":
                need(item, "issue", where, "issue")
                outcome(item, where, spec["issue_only"], "must be one of: " + ", ".join(spec["issue_only"]))
            else:
                need(item, "what", where, "text")
                need(item, "recovery", where, "text")
    for where, text in entries("needs_you", optional=True):
        need({"": text}, "", where, "text")
    check = need(data, "agent_check", "", "object", optional=True)
    if check is not None:
        if len(check) != 1 or not set(check) <= {"file", "unavailable"}:
            problems.append("agent_check must contain exactly one of file or unavailable")
        elif "unavailable" in check:
            need(check, "unavailable", "agent_check", "text")
        else:
            name = need(check, "file", "agent_check", "text")
            if name is not None and (name in (".", "..") or "/" in name or "\\" in name):
                problems.append("agent_check.file must be a filename in the run directory")
    audit = need(data, "release_audit", "", "object", optional=True)
    if audit is not None:
        states = spec["release_audit_results"]
        state = need(audit, "result", "release_audit", "free")
        if state is not None and state not in states:
            problems.append("release_audit.result must be one of: %s: %s"
                            % (", ".join(states), json.dumps(state, ensure_ascii=False)))
        for key in ("summary", "evidence"):
            value = need(audit, key, "release_audit", "text")
            if value is not None and contains_secret(value):
                problems.append("release_audit.%s must contain redacted text only" % key)
        findings = need(audit, "findings", "release_audit", "list", optional=True)
        unknowns = need(audit, "unknowns", "release_audit", "list", optional=True)
        for key, items in (("findings", findings), ("unknowns", unknowns)):
            for index, item in enumerate(items or []):
                value = need({"": item}, "", "release_audit.%s[%d]" % (key, index), "text")
                if value is not None and contains_secret(value):
                    problems.append("release_audit.%s[%d] must contain redacted text only" % (key, index))
        if state == "findings" and not findings:
            problems.append("release_audit.findings must list at least one finding when result is findings")
        extra = sorted(set(audit) - {"result", "summary", "evidence", "findings", "unknowns"})
        if extra:
            problems.append("release_audit has unknown fields: " + ", ".join(extra))
    return problems


def flat(text):
    return " ".join(text.split())


def trim(text):
    # Preserve trimming for old free text (CJK full stop, semicolon, comma, list comma).
    return flat(text).rstrip(".;, " + "".join(chr(code) for code in (0x3002, 0xFF1B, 0xFF0C, 0x3001)))


def detail(item):
    parts = [trim(item["reason"])] if trim(item["reason"]) else []
    if trim(item["next"]):
        parts.append("Next: " + trim(item["next"]))
    return "; ".join(parts)


def issue_label(issue):
    return "#%d" % issue if is_int(issue) else flat(issue)


def minutes(seconds):
    return int(seconds / 60 + 0.5)


def duration(seconds):
    total = minutes(seconds)
    if total < 60:
        return "%d min" % total
    return "%d h %d min" % (total // 60, total % 60)


def release_version(text):
    """Only accept a three-part numeric release version; compare components as integers."""
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", text):
        return None
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return None


def agent_lines(check, spec, session_version=None):
    """Project usable check results to upgrade offers; do not change the saved check."""
    words = spec["agents"]
    latest = check.get("latest") if isinstance(check, dict) else None
    if (not isinstance(check, dict) or check.get("schema") != 1 or not isinstance(check.get("agents"), list)
            or not isinstance(latest, dict)):
        raise ValueError("Invalid Agent check format")
    version = latest.get("version")
    if version is not None and release_version(version) is None:
        raise ValueError("Invalid Agent check format")
    agents = []
    for index, source in enumerate(check["agents"]):
        agent = dict(source) if isinstance(source, dict) else source
        if isinstance(agent, dict) and isinstance(agent.get("status"), str):
            agent["status"] = words["aliases"].get(agent["status"], agent["status"])
        if not isinstance(agent, dict) or not isinstance(agent.get("name"), str):
            raise ValueError("Invalid Agent check format")
        if agent.get("status") == words["absent"]:
            continue
        if not isinstance(agent.get("status"), str) or agent["status"] not in words["statuses"]:
            raise ValueError("agents[%d].status is not a known Agent status: %r" % (index, agent.get("status")))
        for key in ("versions", "missing", "other_scopes"):
            items = agent.get(key, [])
            if not (isinstance(items, list) and all(isinstance(item, str) for item in items)):
                raise ValueError("Invalid Agent check format")
        if agent["status"] in words["ask_for"]:
            agents.append(agent)
    if version is None:
        return []
    lines = []
    session_key = release_version(session_version)
    session_old = session_key is not None and session_key < release_version(version)
    if session_old:
        lines.append(words["session_old"].format(session=session_version, latest=version))
    for agent in agents:
        values = {"name": flat(agent["name"]), "latest": version,
                  "versions": ", ".join("v" + flat(item) for item in dict.fromkeys(agent.get("versions", []))),
                  "missing": ", ".join(flat(item) for item in agent.get("missing", [])),
                  "reason": trim(str(agent.get("reason") or ""))}
        line = words["statuses"][agent["status"]].format(**values)
        line += words["other_scopes"] if agent.get("other_scopes") else ""
        if line not in lines:
            lines.append(line)
    offered = list(dict.fromkeys(flat(agent["name"]) for agent in agents))
    if offered:
        lines.append(words["ask"].format(names=", ".join(offered), latest=version))
    elif session_old:
        lines.append(words["ask_session"].format(latest=version))
    return lines


def load_agent_lines(path, data, spec):
    """Check/package read failures omit the optional section, preserving the rest of the report."""
    check = data.get("agent_check")
    if check is None or "unavailable" in check:
        return []
    try:
        session_version = (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        session_version = None
    try:
        result = json.loads((path / check["file"]).read_text(encoding="utf-8"))
        return agent_lines(result, spec, session_version=session_version)
    except (OSError, ValueError):
        return []


def render_report(data, summary, spec, agents=None):
    """Render six required sections and the optional upgrade section."""
    data = normalize_handoff(data, spec)
    titles, empty = spec["sections"], "- None"
    requests = data["change_requests"]
    paused = data["issues_without_change_request"]
    needs = []
    for item in requests:
        if item["result"] in spec["needs_you"]:
            needs.append("PR [#%d](%s) %s: %s." % (item["number"], flat(item["url"]), item["result"], detail(item)))
    for item in paused:
        if item["result"] in spec["needs_you"]:
            needs.append("Issue %s %s: %s." % (issue_label(item["issue"]), item["result"], detail(item)))
    needs.extend(trim(text) + "." for text in data.get("needs_you", []))
    merged = sum(1 for item in requests if item["result"] == spec["merged"])
    lines = ["## " + spec["title"], "",
             "%s: %d PRs merged; %d items need your action. Completed %d cycles (limit %d); %s." % (
                 titles[0], merged, len(needs), data["completed_cycles"], data["requested_cycles"],
                 trim(data["stop_reason"])), "", "### " + titles[1]]
    lines.extend(["%d. %s" % (index, text) for index, text in enumerate(needs, 1)] or [empty])

    def cell(text):
        return flat(text).replace("|", "\\|")

    lines += ["", "### " + titles[2]]
    rows = []
    for item in requests:
        issues = ", ".join(issue_label(issue) for issue in item["issues"]) or "None"
        rows.append("| [#%d](%s) | %s | %s | %s |" % (item["number"], cell(item["url"]), cell(issues),
                                                     item["result"], cell(detail(item))))
    for item in paused:
        rows.append("| None | %s | %s | %s |" % (cell(issue_label(item["issue"])), item["result"], cell(detail(item))))
    lines.extend(["| PR | Linked Issues | Result | Details |", "|---|---|---|---|"] + rows if rows else [empty])

    queue, mode = data["startup_queue"], data["concurrency"]
    queued = "%d" % queue["count"] + (", " + trim(queue["note"]) if trim(queue["note"]) else "")
    if mode["enabled"]:
        parallel = "Enabled, up to %d" % mode["agent_limit"]
    else:
        parallel = "Disabled; Reason: " + trim(mode["serial_reason"])
    if trim(mode.get("note", "")):
        parallel += "; " + trim(mode["note"])
    lines += ["", "### " + titles[3], "- Startup check: " + trim(data["startup_check"])]
    audit = data.get("release_audit")
    if audit:
        parts = [trim(audit["summary"]), "Result: " + spec["release_audit_results"][audit["result"]]]
        findings = [trim(item) for item in audit.get("findings", [])]
        if findings:
            parts.append("Findings: " + "; ".join(findings))
        unknowns = [trim(item) for item in audit.get("unknowns", [])]
        if unknowns:
            parts.append("Unknowns: " + "; ".join(unknowns))
        parts.append("Evidence: " + flat(audit["evidence"]))
        lines.append("- Release audit: " + "; ".join(parts))
    lines += ["- Existing PRs: " + queued,
              "- Cycles: %d / %d; Stop reason: %s" % (data["completed_cycles"], data["requested_cycles"],
                                          trim(data["stop_reason"])),
              "- Concurrency: " + parallel, "- Branch cleanup: " + trim(data["branch_cleanup"])]

    lines += ["", "### " + titles[4]]
    if summary["wall_seconds"] is None:
        lines.append("- No record")
    else:
        stage_seconds = summary["stage_seconds"]
        order = [name for name in spec["stages"] if name in stage_seconds]
        order += sorted(name for name in stage_seconds if name not in spec["stages"])
        stages = ", ".join("%s %d" % (spec["stages"].get(name, name), minutes(stage_seconds[name]))
                          for name in order)
        lines.append("- Total " + duration(summary["wall_seconds"]) + (": %s (minutes)" % stages if stages else ""))
        waits = summary["wait_seconds"]
        lines.append("- Including " + ", ".join("%s %s" % (spec["waits"][kind], duration(waits.get(kind, 0)))
                                        for kind in ("ci", "lock")))

    lines += ["", "### " + titles[5]]
    lines.extend(["- %s. Recovery: %s" % (trim(item["what"]), trim(item["recovery"]))
                  for item in data["exceptions"]] or [empty])
    if agents:
        lines += ["", "### " + titles[6]]
        lines.extend("- " + line for line in agents)
    return "\n".join(lines) + "\n"


def build_report(path, spec=None):
    """Validate handoff.json, render the report and atomically save it as report.md."""
    spec = spec or load_report_spec()
    source = path / "handoff.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError("Cannot read %s: %s" % (source, error))
    except ValueError as error:
        raise ValueError("%s is not valid JSON: %s" % (source, error))
    data = normalize_handoff(data, spec)
    problems = check_handoff(data, spec)
    if problems:
        raise ReportDataError(problems)
    text = render_report(data, summarize(path), spec, load_agent_lines(path, data, spec))
    target = path / "report.md"
    temporary = path / ".report.md.tmp"
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(str(temporary), str(target))
    return text


def write_utf8(stream, text):
    """Write UTF-8 bytes without newline translation, whatever the console encoding."""
    stream.flush()
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        stream.write(text)
    else:
        buffer.write(text.encode("utf-8"))
        buffer.flush()


def prune(root, keep, current=None):
    runs = []
    for path in root.glob("*"):
        if not (path.is_dir() and RUN_ID.fullmatch(path.name)):
            continue
        try:
            data = json.loads((path / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("created_by") == MARKER:
            runs.append((data.get("created_at", ""), path))
    runs.sort(reverse=True)
    removed = []
    for _, path in runs[keep:]:
        if path.name != current:
            shutil.rmtree(str(path))
            removed.append(path.name)
    return sorted(removed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    begin.add_argument("--cycles", type=int, required=True)
    begin.add_argument("--keep", type=int, default=20)
    note = commands.add_parser("event")
    note.add_argument("--run", required=True)
    note.add_argument("--task", required=True)
    note.add_argument("--stage", required=True)
    note.add_argument("--status", required=True, choices=STATUSES)
    note.add_argument("--wait", choices=WAITS)
    note.add_argument("--detail")
    note.add_argument("--at", help="ISO timestamp with timezone; defaults to now")
    where = commands.add_parser("task-dir")
    where.add_argument("--run", required=True)
    where.add_argument("--task", required=True)
    show = commands.add_parser("summary")
    show.add_argument("--run", required=True)
    render = commands.add_parser("report")
    render.add_argument("--run", required=True)
    trim = commands.add_parser("prune")
    trim.add_argument("--keep", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        root = runs_root(args.repo)
        now = datetime.now(timezone.utc)
        if args.command == "start":
            if args.cycles < 1 or args.keep < 1:
                parser.error("--cycles and --keep must be positive")
            run_id, path = start(root, args.cycles, now)
            prune(root, args.keep, current=run_id)
            print(json.dumps({"run_id": run_id, "path": str(path)}, ensure_ascii=False))
        elif args.command == "event":
            moment = parse(args.at) if args.at else now
            record = add_event(run_dir(root, args.run), args.task, args.stage, args.status,
                               args.wait, args.detail, moment)
            print(json.dumps(record, ensure_ascii=False))
        elif args.command == "task-dir":
            print(task_dir(run_dir(root, args.run), args.task))
        elif args.command == "summary":
            print(json.dumps(summarize(run_dir(root, args.run)), ensure_ascii=False, indent=2))
        elif args.command == "report":
            try:
                write_utf8(sys.stdout, build_report(run_dir(root, args.run)))
            except ReportDataError as error:
                write_utf8(sys.stderr, "ERROR: invalid handoff.json data; correct it and retry:\n"
                           + "".join("- " + problem + "\n" for problem in error.problems))
                return 1
        else:
            if args.keep < 1:
                parser.error("--keep must be positive")
            root.mkdir(parents=True, exist_ok=True)
            print(json.dumps({"removed": prune(root, args.keep)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
