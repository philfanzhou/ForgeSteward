"""显式选定 CLI/route 的真实模型验收；无输入不调用模型。"""
import argparse
import hashlib
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests/fixtures"))
from deepseek_platform import seed

STAGES = ("check-workflow", "prepare-work", "execute-work", "review-and-merge", "fix-feedback")
SCENARIOS = ("startup", "repair", "constraints", "waiting", "uncertain", "rounds", "missing", "stop")


def preflight(root):
    versions = set()
    for name in (*STAGES, "work-cycle"):
        directory = root / ".dsh/skills" / ("forge-steward-" + name)
        receipt = json.loads((directory / ".forge-steward-install.json").read_text(encoding="utf-8"))
        versions.add(receipt["version"])
        for file in receipt["files"]:
            if receipt["files"][file] != "directory":
                resource = directory / file
                if not resource.is_file():
                    raise ValueError("Missing skill resource: " + file)
                if hashlib.sha256(resource.read_bytes()).hexdigest() != receipt["files"][file]:
                    raise ValueError("Changed skill resource: " + file)
    if len(versions) != 1:
        raise ValueError("Mixed stage versions")
    return versions.pop()


def events_of(frames, session):
    return [f["params"]["event"] for f in frames if f.get("method") == "session.event"
            and f["params"]["sessionId"] == session]


def calls_of(events):
    calls = []
    for event in events:
        if event["type"] == "tool/call":
            data = event["data"]
            calls.append((data["name"], json.loads(data["arguments"]), data["callId"]))
    return calls


def validate_missing(root, frames, parent, state):
    """有限缺技能轨迹准入，不执行命令，也不充当通用 shell/sandbox。"""
    root = root.resolve()
    events = events_of(frames, parent)
    calls = calls_of(events)
    results = {e["data"]["message"]["toolCallId"]: e["data"]
               for e in events if e["type"] == "tool/result"}
    assert not any(f.get("method") in ("subagent.started", "subagent.finished") for f in frames), "missing stage must stop before delegation"
    assert not state["prepared"] and not state["prs"] and not state["handoffs"], "missing must not perform stage work"
    assert all(op["operation"] == "seed" for op in state["operations"]), "missing must not perform stage writes"

    def local(path):
        candidate = Path(path)
        candidate = candidate if candidate.is_absolute() else root / candidate
        assert candidate.resolve().is_relative_to(root), "missing preflight accessed outside workspace"
        return candidate.resolve()

    directory = root / ".dsh/skills/forge-steward-work-cycle"
    absent = root / ".dsh/skills/forge-steward-fix-feedback/SKILL.md"
    assert not absent.exists(), "missing fixture must actually lack the stage skill"
    for name, args, call_id in calls:
        assert call_id in results, "missing preflight needs observed tool results"
        if name == "read":
            local(args["file_path"])
        elif name == "skill":
            assert args["name"] == "forge-steward-work-cycle", "missing must not activate a stage"
        elif name == "bash":
            command = args.get("command", "")
            # 仅识别简单本地读取/列目录与 view；复合 shell、脚本、重定向等不猜测安全性。
            assert not re.search(r"[;|&<>`$\n]", command), "unrecognized missing preflight shell command"
            words = shlex.split(command)
            if words == ["python3", "fixture.py", "view"]:
                continue
            assert words and words[0] in ("ls", "cat"), "unrecognized missing preflight shell command"
            for word in words[1:]:
                if word in ("-a", "-l", "-la", "-al") and words[0] == "ls":
                    continue
                assert not word.startswith("-") and not re.search(r"[*?~]", word), "unrecognized missing preflight path"
                local(word)
        else:
            raise AssertionError("unrecognized missing preflight tool: " + name)
    skill_calls = [cid for name, args, cid in calls if name == "skill"]
    assert skill_calls, "missing needs work-cycle preflight load"
    body = (directory / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[2].strip()
    assert any(results[cid]["message"].get("isError") is False and body in "".join(
        b.get("text", "") for b in results[cid]["message"]["content"] if b["type"] == "text")
        for cid in skill_calls), "missing needs complete work-cycle body"
    for filename in ("startup.md", "cycles.md"):
        resource = directory / "references" / filename
        observed = set()
        for name, args, cid in calls:
            if name == "read" and local(args["file_path"]) == resource:
                result = results[cid]
                assert result["message"].get("isError") is False, "missing reference read failed"
                observed.update(line["number"] for line in result.get("meta", {}).get("lines", []))
        assert observed.issuperset(range(1, len(resource.read_text(encoding="utf-8").splitlines()) + 1)), "missing needs complete reference: " + filename
    diagnostic_ids = [cid for name, args, cid in calls if name == "read" and local(args["file_path"]) == absent
                      and results[cid]["message"].get("isError") is True
                      and re.search(r"not found|no such file|does not exist|missing|不存在|缺失", " ".join(
                          b.get("text", "") for b in results[cid]["message"]["content"]), re.I)]
    assert diagnostic_ids, "missing needs observed absent-stage diagnostic"
    ends = [(i, e) for i, e in enumerate(events) if e["type"] == "turn/end"]
    assert len(ends) == 1 and ends[0][1]["data"]["reason"]["kind"] == "completed", "missing needs completed parent terminal"
    reports = [(i, e) for i, e in enumerate(events) if e["type"] == "assistant/message"]
    assert reports, "missing needs explicit final stop report"
    report_index, report = reports[-1]
    text = " ".join(b.get("text", "") for b in report["data"]["message"]["content"] if b["type"] == "text")
    assert "forge-steward-fix-feedback" in text and re.search(r"缺少|缺失|missing|not installed|not found", text, re.I) and re.search(r"停止|stop|cannot proceed", text, re.I), "missing needs explicit final stop report"
    diagnostic_end = max(i for i, e in enumerate(events) if e["type"] == "tool/result" and e["data"]["message"]["toolCallId"] in diagnostic_ids)
    assert diagnostic_end < report_index < ends[0][0], "missing report must follow diagnostic before terminal"
    assert not any(e["type"] in ("tool/call", "tool/result") for e in events[report_index + 1:]), "missing must stop after final report"
    return {"scenario": "missing", "status": "passed", "children": [],
            "missingSkill": "forge-steward-fix-feedback", "parentTerminal": "completed"}


def validate(root, frames, parent, scenario, shutdown=None):
    """验收观测器：只读实际模型/平台结果，不运行阶段或补写平台。"""
    state = json.loads((root / "platform.json").read_text(encoding="utf-8"))
    starts = [(i, f["params"]) for i, f in enumerate(frames) if f.get("method") == "subagent.started"]
    finishes = {f["params"]["childSessionId"]: (i, f["params"]) for i, f in enumerate(frames)
                if f.get("method") == "subagent.finished"}
    if scenario == "stop":
        assert len(starts) == 1, "stop must not dispatch dependent stage"
        child = starts[0][1]["childSessionId"]
        terminal = finishes.get(child)
        child_events = events_of(frames, child)
        aborted = any(e["type"] == "turn/end" and e["data"]["reason"]["kind"] != "completed" for e in child_events)
        assert (terminal and terminal[1]["stopReason"] != "completed") or aborted or (
            shutdown and shutdown["acknowledged"] and shutdown["exit_code"] == 0 and shutdown["owned_processes_gone"] and shutdown["platform_unchanged"]), "stop needs native termination evidence"
        assert not terminal or terminal[1]["stopReason"] != "completed", "stopped partial stage is not completed"
        assert not any(x["operation"] in ("create", "repair", "merge", "delete") for x in state["operations"])
        return {"scenario": scenario, "status": "passed", "children": [{"id": child, "stopped": True, "terminal": "unknown" if not terminal else terminal[1]["stopReason"]}], "shutdown": shutdown}
    if scenario == "missing":
        return validate_missing(root, frames, parent, state)
    children = []
    previous_end = -1
    for begin, info in starts:
        assert info["parentSessionId"] == parent, "stages must be direct independent children"
        child = info["childSessionId"]
        assert child in finishes, "id receipt is not completion"
        end, terminal = finishes[child]
        assert begin > previous_end, "same repository stages overlap"
        previous_end = end
        assert terminal["stopReason"] == "completed", "partial child cannot be successful"
        events = events_of(frames, child)
        calls = calls_of(events)
        skills = [args["name"] for name, args, _ in calls if name == "skill"]
        stage_skills = {skill for skill in skills if skill in {"forge-steward-" + stage for stage in STAGES}}
        assert len(stage_skills) == 1, "stage must load its own unambiguous skill"
        primary = stage_skills.pop()
        assert set(skills) <= {primary, "forge-steward-work-cycle"}, "unrelated stage activation"
        stage = primary[len("forge-steward-"): ]
        directory = root / ".dsh/skills" / primary
        resources = list(directory.glob("references/*.md"))
        # 每条读取逐行 meta 证明完整资源；不能只看到调用路径就算加载。
        results = {e["data"]["message"]["toolCallId"]: e["data"] for e in events if e["type"] == "tool/result"}
        skill_call = next(call_id for name, args, call_id in calls if name == "skill" and args["name"] == primary)
        loaded = results[skill_call]["message"]
        assert not loaded.get("isError"), "stage skill load failed"
        loaded_text = "".join(block.get("text", "") for block in loaded["content"] if block["type"] == "text")
        body = (directory / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[2].strip()
        assert body in loaded_text, "stage must receive complete skill body"
        for resource in resources:
            line_count = len(resource.read_text(encoding="utf-8").splitlines())
            observed = set()
            for name, args, call_id in calls:
                if name != "read" or Path(args.get("file_path", "")) != resource:
                    continue
                result = results[call_id]
                assert not result["message"].get("isError")
                observed.update(line["number"] for line in result.get("meta", {}).get("lines", []))
            assert observed.issuperset(range(1, line_count + 1)), "incomplete reference: " + str(resource)
        assert not any(name in ("subagent", "subagent_fork") for name, _, _ in calls), "stage must not replace orchestrator"
        shell = [args.get("command", "") for name, args, _ in calls if name in ("bash", "pwsh")]
        allowed = {"prepare-work": {"prepare"}, "execute-work": {"create"},
                   "review-and-merge": {"review", "merge", "delete"}, "fix-feedback": {"repair"},
                   "check-workflow": set()}[stage] | {"view", "handoff", "--help"}
        for command in shell:
            actions = re.findall(r"fixture\.py\s+([a-z-]+)\b", command)
            assert set(actions) <= allowed, "stage performed another stage's platform operation"
        assert any(re.search(r"fixture\.py\s+handoff\b", command) for command in shell), "child must persist handoff itself"
        children.append({"id": child, "stage": stage, "stopReason": terminal["stopReason"],
                         "references": [p.name for p in resources]})
    for position in range(1, len(starts)):
        previous_child = starts[position - 1][1]["childSessionId"]
        lower = finishes[previous_child][0]
        upper = starts[position][0]
        between = events_of(frames[lower:upper], parent)
        assert any((name in ("bash", "pwsh") and re.search(r"fixture\.py\s+view\b", args.get("command", "")))
                   or (name == "read" and args.get("file_path", "").endswith("platform.json"))
                   for name, args, _ in calls_of(between)), "handoff must be read before next dependency"
    assert children, "no actual stage children"
    stages = [c["stage"] for c in children]
    assert len(state["handoffs"]) >= len(children), "each stage must persist handoff"
    parent_calls = calls_of(events_of(frames, parent))
    for name, args, _ in parent_calls:
        if name in ("bash", "pwsh"):
            assert not re.search(r"fixture\.py\s+(prepare|create|review|repair|merge|delete)\b", args.get("command", "")), "parent cannot replace actual stage"
        if name == "subagent":
            assert args.get("run_in_background") is False, "dependent stages need foreground result"
            if scenario == "constraints":
                assert "只读" in args["prompt"] and "不推送" in args["prompt"], "lost user constraints"
    operations = [op["operation"] for op in state["operations"]]
    if scenario == "startup":
        assert stages[:2] == ["review-and-merge", "prepare-work"]
        assert state["prepared"] == [] and "execute-work" not in stages
        assert state["prs"]["P0"]["merged"] and state["prs"]["P0"]["deleted"]
    elif scenario == "repair":
        assert stages == ["prepare-work", "execute-work", "review-and-merge", "fix-feedback", "review-and-merge"]
        assert state["prs"]["I1"]["round"] == 1 and state["prs"]["I1"]["merged"]
    elif scenario == "constraints":
        assert not any(action in operations for action in ("create", "repair", "merge", "delete"))
    elif scenario == "waiting":
        assert not state["prs"]["I1"]["merged"] and "fix-feedback" not in stages
    elif scenario == "uncertain":
        assert sum(op["operation"] == "create" for op in state["operations"]) == 1
    elif scenario == "rounds":
        assert state["prepared"] == ["I1", "I2"], "execute cannot shrink original queue"
        assert state["prs"]["I1"]["round"] == 3 and not state["prs"]["I1"]["merged"]
        assert state["prs"]["I2"]["merged"]
        assert stages.count("fix-feedback") == 3 and stages.count("review-and-merge") == 4
    return {"scenario": scenario, "status": "passed", "children": children,
            "operations": state["operations"], "prs": state["prs"], "handoffs": state["handoffs"]}


def descendants(pid):
    if os.name == "nt":
        raise RuntimeError("SDK stop process proof currently requires POSIX ps")
    pairs = [tuple(map(int, line.split())) for line in subprocess.check_output(
        ["ps", "-axo", "pid=,ppid="], text=True).splitlines() if line.strip()]
    owned = {pid}
    changed = True
    while changed:
        before = len(owned)
        owned.update(child for child, parent in pairs if parent in owned)
        changed = len(owned) != before
    return owned


class Sdk:
    def __init__(self, cli, root):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GH_", "GITHUB_", "GIT_"))}
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env.pop("DSH_MAX_TOKENS_AS_SUCCESS", None)
        self.process = subprocess.Popen([str(cli), "sdk"], cwd=root, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.frames, self.messages, self.counter = [], queue.Queue(), 0
        def reader():
            for line in self.process.stdout:
                try:
                    frame = json.loads(line)
                    self.messages.put(frame)
                except json.JSONDecodeError:
                    self.messages.put({"invalid_frame": True})
            self.messages.put({"eof": True})
        self.thread = threading.Thread(target=reader, daemon=True)
        self.thread.start()

    def receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("SDK deadline expired; do not re-dispatch unknown writes")
        try:
            frame = self.messages.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("SDK deadline expired; do not re-dispatch unknown writes") from None
        if "eof" in frame or "invalid_frame" in frame:
            raise RuntimeError("SDK EOF or malformed frame")
        self.frames.append(frame)
        return frame

    def request(self, method, params=None, seconds=30):
        self.counter += 1
        identity = self.counter
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": identity, "method": method,
                                             "params": params or {}}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + seconds
        while True:
            frame = self.receive(deadline)
            if frame.get("id") == identity:
                if "error" in frame:
                    raise RuntimeError("SDK request failed: " + str(frame["error"]))
                return frame["result"]

    def close(self):
        if self.process.poll() is None:
            try:
                self.request("shutdown", seconds=10)
                self.process.wait(timeout=10)
            except (Exception, KeyboardInterrupt):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.thread.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


def run(cli, provider, model, output, scenario, timeout, max_tokens=8192):
    root = seed(output / scenario, scenario)
    shutil.copyfile(REPO / "tests/fixtures/deepseek_platform.py", root / "fixture.py")
    fixture_bytes = (root / "fixture.py").read_bytes()
    subprocess.run([sys.executable, str(REPO / "scripts/deepseek.py"), "install", "--all", "--project", str(root)],
                   check=True, stdout=subprocess.DEVNULL)
    version = preflight(root)
    gate = root / ".dsh/skills/forge-steward-work-cycle/scripts/check_workflow_gate.py"
    subprocess.run([sys.executable, str(gate), "--repo", str(root), "--branch", "main", "--record", "--result", "clean"],
                   check=True, stdout=subprocess.DEVNULL)
    if scenario == "missing":
        shutil.rmtree(root / ".dsh/skills/forge-steward-fix-feedback")
    instructions = """# 隔离验收仓库
本仓库仅用本地 bare origin 测试，禁止运行 gh/联网平台工具、读取工作区以外文件或用户配置/凭据。
共享六技能业务规则完全保留。托管平台适配为 `python3 fixture.py` 命令，可 view 查完整Issue/PR/checks/approval/head及review round。
prepare-work读取view审计原Issue；本夹具每个Issue是一个独立文件目标（create实现内容\"验收目标已实现\"，无依赖/敏感/部署变更），准备证据由prepare命令持久化，最终只输出完整编号列表或[]。
execute-work按该原清单逐项调用create <Issue>：此为平台适配事务，同时建独立分支/写目标/commit/push/建PR；不调用merge。写回包未知先view回查，不重试create。
review-and-merge调用review <PR>取得本范围阻塞反馈；checks/approval/protected均为实际fixture门禁。无反馈且门禁通过可merge <PR> --head <实际head>，随后delete <PR>，两命令为本地fixture受控合并与分支清理，不是生产平台。
fix-feedback仅对required项repair <PR>原分支，再由全新review child审查。第三次后仍required暂停，不第四修复；其他独立项继续。
每阶段child先用skill加载自身技能，再read完整全部references/*.md。每阶段结束前运行handoff <stage>保存现状/清单/round/head，编排parent每次在下阶段前必须独立运行view回读实际head/checks/交接，即使child最终已返回完整state也不得省略。
父Agent仅预检、委派、等待、view核对；不能执行prepare/create/review/repair/merge/delete替child代做。每次child独立subagent(run_in_background:false)，prompt含本次用户约束与原始完整清单。
已记录本版本启动check-workflow clean；不要重跑。只读/不推送模式仅可view和handoff，不改变PR状态。无技能或能力先停止。
"""
    (root / "AGENTS.md").write_text(instructions, encoding="utf-8")
    parent = "fs41-" + scenario + "-" + str(uuid.uuid4())
    prompt = "显式调用 forge-steward-work-cycle 1。完整读取技能及startup/cycles，按真实规则执行本隔离仓库，平台适配见AGENTS.md。请短而准确，child派发prompt仅需阶段技能/目录/原清单/用户约束，引用AGENTS不用重复全文；每个依赖阶段前必须独立fixture view回查。完成前保存阶段交接。不寻找child id；SDK观察器已记录生命周期。"
    if scenario == "constraints":
        prompt += " 用户约束：只读、不推送，必须传给每个child。"
    sdk = Sdk(cli, root)
    shutdown = None
    try:
        sdk.request("initialize", {"cwd": str(root), "provider": provider, "model": model, "maxTokens": max_tokens})
        sdk.request("session/prompt", {"sessionId": parent, "contentBlocks": [{"type": "text", "text": prompt}]})
        deadline = time.monotonic() + timeout
        while True:
            frame = sdk.receive(deadline)
            if scenario == "stop" and frame.get("method") == "subagent.started":
                # SDK root disposal是真实用户停止；不再发送任何prompt或重派。
                owned = descendants(sdk.process.pid)
                before = (root / "platform.json").read_bytes()
                ack = sdk.request("shutdown", seconds=15)
                code = sdk.process.wait(timeout=15)
                live_pids = {int(line) for line in subprocess.check_output(["ps", "-axo", "pid="], text=True).splitlines() if line.strip()}
                shutdown = {"acknowledged": ack == {}, "exit_code": code,
                            "owned_processes_gone": not (owned & live_pids),
                            "platform_unchanged": before == (root / "platform.json").read_bytes()}
                break
            if frame.get("method") == "session.event" and frame["params"]["sessionId"] == parent:
                event = frame["params"]["event"]
                if event["type"] == "turn/end":
                    assert event["data"]["reason"]["kind"] == "completed", "parent partial/failed turn"
                    break
        assert (root / "fixture.py").read_bytes() == fixture_bytes, "model changed platform adapter"
        if scenario != "missing":
            assert preflight(root) == version, "model changed shared skills"
        proof = validate(root, sdk.frames, parent, scenario, shutdown)
        proof["version"] = version
    except BaseException as error:
        (root / "failure.json").write_text(json.dumps({"scenario": scenario, "status": "failed",
            "reason": type(error).__name__ + ": " + str(error), "production_operations": False}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    finally:
        sdk.close()
        # 仅本SDK产生的隔离测试帧；不读取Harness其他会话。
        (root / "sdk-events.json").write_text(json.dumps(sdk.frames, ensure_ascii=False), encoding="utf-8")
    (root / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scenario": scenario, "status": "passed", "children": len(proof["children"])}), flush=True)
    return proof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", default=os.environ.get("FORGESTEWARD_DEEPSEEK_CLI"))
    parser.add_argument("--provider", default=os.environ.get("FORGESTEWARD_DEEPSEEK_PROVIDER"))
    parser.add_argument("--model", default=os.environ.get("FORGESTEWARD_DEEPSEEK_MODEL"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS, action="append")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-tokens", type=int, default=8192)
    args = parser.parse_args()
    if not any((args.cli, args.provider, args.model)):
        print("SKIP: explicitly select CLI/provider/model to authorize real model acceptance")
        return 0
    if not all((args.cli, args.provider, args.model)):
        parser.error("CLI, provider and model must all be explicitly selected")
    if not Path(args.cli).is_file() or args.timeout <= 0 or args.max_tokens <= 0:
        parser.error("invalid CLI or timeout")
    output = (args.output or Path(tempfile.mkdtemp(prefix="fs41-model-"))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for scenario in args.scenario or SCENARIOS:
        run(Path(args.cli).resolve(), args.provider, args.model, output, scenario, args.timeout, args.max_tokens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
