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
        except FileExistsError:
            if time.monotonic() > deadline:
                raise ValueError("Timed out waiting for " + str(guard))
            time.sleep(0.01)
    try:
        fd = os.open(str(path / "events.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    finally:
        os.rmdir(str(guard))
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
                 and valid_agent_spec(spec["agents"]))
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("Malformed report-spec block in " + str(path))
    return spec


AGENT_TEXTS = ("unchecked", "unavailable", "absent", "current", "none", "all_latest", "latest_unknown",
               "other_scopes")
AGENT_WITHOUT_LATEST = 3


def valid_agent_spec(agents):
    """The agents block names every check status and the wording of each report line."""
    texts = [agents[key] for key in AGENT_TEXTS]
    texts += list(agents["statuses"].values()) + list(agents["without_latest"].values())
    return (all(isinstance(text, str) and text for text in texts)
            and len(agents["statuses"]) == 6 and agents["absent"] not in agents["statuses"]
            and agents["current"] in agents["statuses"]
            and len(agents["without_latest"]) == AGENT_WITHOUT_LATEST
            and len(set(agents["without_latest"]) - set(agents["statuses"])) == 1)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


KINDS = {
    "text": (lambda v: isinstance(v, str) and v.strip() != "", "应为非空文本"),
    "free": (lambda v: isinstance(v, str), "应为文本"),
    "count": (lambda v: is_int(v) and v >= 0, "应为不小于 0 的整数"),
    "positive": (lambda v: is_int(v) and v >= 1, "应为正整数"),
    "bool": (lambda v: isinstance(v, bool), "应为 true 或 false"),
    "list": (lambda v: isinstance(v, list), "应为列表"),
    "object": (lambda v: isinstance(v, dict), "应为对象"),
    "issue": (lambda v: (is_int(v) and v >= 1) or (isinstance(v, str) and v.strip() != ""),
              "应为 Issue 编号或非空文本"),
}


def check_handoff(data, spec):
    """Return one message per invalid field; empty when the data can be rendered."""
    if not isinstance(data, dict):
        return ["handoff.json 顶层应为对象"]
    problems = []

    def need(obj, key, path, kind, optional=False):
        where = ".".join(part for part in (path, key) if part)
        if key not in obj:
            if not optional:
                problems.append(where + " 缺少必填字段")
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
            problems.append("%s.result %s：%s" % (where, message, json.dumps(result, ensure_ascii=False)))
        reason = need(item, "reason", where, "free")
        need(item, "next", where, "free")
        if result in spec["needs_you"] and reason is not None and not reason.strip():
            problems.append("%s.reason 结果为%s时不能为空" % (where, result))

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
                problems.append(where + " 应为对象")
            elif key == "change_requests":
                need(item, "url", where, "text")
                need(item, "number", where, "positive")
                for spot, issue in enumerate(need(item, "issues", where, "list") or []):
                    need({"": issue}, "", "%s.issues[%d]" % (where, spot), "issue")
                outcome(item, where, spec["results"], "不在结果词表中")
            elif key == "issues_without_change_request":
                need(item, "issue", where, "issue")
                outcome(item, where, spec["issue_only"], "只能是" + "、".join(spec["issue_only"]))
            else:
                need(item, "what", where, "text")
                need(item, "recovery", where, "text")
    for where, text in entries("needs_you", optional=True):
        need({"": text}, "", where, "text")
    check = need(data, "agent_check", "", "object", optional=True)
    if check is not None:
        if len(check) != 1 or not set(check) <= {"file", "unavailable"}:
            problems.append("agent_check 只能有 file 或 unavailable 其中一个")
        elif "unavailable" in check:
            need(check, "unavailable", "agent_check", "text")
        else:
            name = need(check, "file", "agent_check", "text")
            if name is not None and (name in (".", "..") or "/" in name or "\\" in name):
                problems.append("agent_check.file 只能是运行目录下的文件名")
    return problems


def flat(text):
    return " ".join(text.split())


def trim(text):
    return flat(text).rstrip("。；;，,、 ")


def detail(item):
    parts = [trim(item["reason"])] if trim(item["reason"]) else []
    if trim(item["next"]):
        parts.append("下一步：" + trim(item["next"]))
    return "；".join(parts)


def issue_label(issue):
    return "#%d" % issue if is_int(issue) else flat(issue)


def minutes(seconds):
    return int(seconds / 60 + 0.5)


def duration(seconds):
    total = minutes(seconds)
    if total < 60:
        return "%d 分" % total
    return "%d 小时 %d 分" % (total // 60, total % 60)


def agent_lines(check, spec):
    """Turn an agent_install.py check result into report lines; raise ValueError if it is unusable."""
    words = spec["agents"]
    latest = check.get("latest") if isinstance(check, dict) else None
    if (not isinstance(check, dict) or check.get("schema") != 1 or not isinstance(check.get("agents"), list)
            or not isinstance(latest, dict)):
        raise ValueError("format")
    version = latest.get("version")
    if version is not None and not (isinstance(version, str) and version):
        raise ValueError("format")
    agents = []
    for agent in check["agents"]:
        if not isinstance(agent, dict) or not isinstance(agent.get("name"), str):
            raise ValueError("format")
        if agent.get("status") == words["absent"]:
            continue
        if agent.get("status") not in words["statuses"]:
            raise ValueError("format")
        for key in ("versions", "missing", "other_scopes"):
            items = agent.get(key, [])
            if not (isinstance(items, list) and all(isinstance(item, str) for item in items)):
                raise ValueError("format")
        agents.append(agent)
    lines = []
    if version is None:
        lines.append(words["latest_unknown"].format(reason=trim(str(latest.get("error") or ""))))
    elif not agents:
        return [words["none"]]
    elif all(agent["status"] == words["current"] and not agent.get("other_scopes") for agent in agents):
        return [words["all_latest"].format(latest=flat(version))]
    installed = next(key for key in words["without_latest"] if key not in words["statuses"])
    for agent in agents:
        versions = agent.get("versions", [])
        values = {"name": flat(agent["name"]), "latest": flat(version or ""),
                  "versions": "、".join("v" + flat(item) for item in versions),
                  "missing": "、".join(flat(item) for item in agent.get("missing", [])),
                  "reason": trim(str(agent.get("reason") or ""))}
        template = words["statuses"][agent["status"]]
        if version is None and agent["status"] in words["without_latest"]:
            template = words["without_latest"][agent["status"]]
        elif version is None and versions:
            template = words["without_latest"][installed]
        lines.append(template.format(**values) + (words["other_scopes"] if agent.get("other_scopes") else ""))
    return lines


def load_agent_lines(path, data, spec):
    """Report lines for the agent check recorded in handoff.json; problems only affect this section."""
    words = spec["agents"]
    check = data.get("agent_check")
    if check is None:
        return [words["unchecked"]]
    if "unavailable" in check:
        return [words["unavailable"].format(reason=trim(check["unavailable"]))]
    try:
        result = json.loads((path / check["file"]).read_text(encoding="utf-8"))
    except OSError:
        return [words["unavailable"].format(reason="找不到检查结果文件 " + flat(check["file"]))]
    except ValueError:
        result = None
    try:
        return agent_lines(result, spec)
    except ValueError:
        return [words["unavailable"].format(reason="检查结果格式无法识别")]


def render_report(data, summary, spec, agents=None):
    """Render the fixed seven-section report; output depends only on the inputs."""
    titles, empty = spec["sections"], "- 无"
    requests = data["change_requests"]
    paused = data["issues_without_change_request"]
    needs = []
    for item in requests:
        if item["result"] in spec["needs_you"]:
            needs.append("PR [#%d](%s) %s：%s。" % (item["number"], flat(item["url"]), item["result"], detail(item)))
    for item in paused:
        if item["result"] in spec["needs_you"]:
            needs.append("Issue %s %s：%s。" % (issue_label(item["issue"]), item["result"], detail(item)))
    needs.extend(trim(text) + "。" for text in data.get("needs_you", []))
    merged = sum(1 for item in requests if item["result"] == spec["merged"])
    lines = ["## " + spec["title"], "",
             "%s：合并 %d 个 PR，%d 项需要你处理。共跑 %d 轮（上限 %d），%s。" % (
                 titles[0], merged, len(needs), data["completed_cycles"], data["requested_cycles"],
                 trim(data["stop_reason"])), "", "### " + titles[1]]
    lines.extend(["%d. %s" % (index, text) for index, text in enumerate(needs, 1)] or [empty])

    def cell(text):
        return flat(text).replace("|", "\\|")

    lines += ["", "### " + titles[2]]
    rows = []
    for item in requests:
        issues = "、".join(issue_label(issue) for issue in item["issues"]) or "无"
        rows.append("| [#%d](%s) | %s | %s | %s |" % (item["number"], cell(item["url"]), cell(issues),
                                                     item["result"], cell(detail(item))))
    for item in paused:
        rows.append("| 无 | %s | %s | %s |" % (cell(issue_label(item["issue"])), item["result"], cell(detail(item))))
    lines.extend(["| PR | 对应 Issue | 结果 | 说明 |", "|---|---|---|---|"] + rows if rows else [empty])

    queue, mode = data["startup_queue"], data["concurrency"]
    queued = "%d 个" % queue["count"] + ("，" + trim(queue["note"]) if trim(queue["note"]) else "")
    if mode["enabled"]:
        parallel = "开启，最多 %d 个" % mode["agent_limit"]
    else:
        parallel = "未开启，原因：" + trim(mode["serial_reason"])
    if trim(mode.get("note", "")):
        parallel += "；" + trim(mode["note"])
    lines += ["", "### " + titles[3], "- 启动检查：" + trim(data["startup_check"]),
              "- 开始前已有的 PR：" + queued,
              "- 轮数：%d / %d，停止原因：%s" % (data["completed_cycles"], data["requested_cycles"],
                                          trim(data["stop_reason"])),
              "- 同时进行：" + parallel, "- 分支清理：" + trim(data["branch_cleanup"])]

    lines += ["", "### " + titles[4]]
    if summary["wall_seconds"] is None:
        lines.append("- 无记录")
    else:
        stage_seconds = summary["stage_seconds"]
        order = [name for name in spec["stages"] if name in stage_seconds]
        order += sorted(name for name in stage_seconds if name not in spec["stages"])
        stages = "、".join("%s %d" % (spec["stages"].get(name, name), minutes(stage_seconds[name]))
                          for name in order)
        lines.append("- 总计 " + duration(summary["wall_seconds"]) + ("：%s（分钟）" % stages if stages else ""))
        waits = summary["wait_seconds"]
        lines.append("- 其中" + "，".join("%s %s" % (spec["waits"][kind], duration(waits.get(kind, 0)))
                                        for kind in ("ci", "lock")))

    lines += ["", "### " + titles[5]]
    lines.extend(["- %s。处理：%s" % (trim(item["what"]), trim(item["recovery"]))
                  for item in data["exceptions"]] or [empty])
    lines += ["", "### " + titles[6]]
    lines.extend("- " + line for line in agents or [spec["agents"]["unchecked"]])
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
                write_utf8(sys.stderr, "ERROR: handoff.json 数据有问题，改正后重试：\n"
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
