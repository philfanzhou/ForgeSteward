"""校验其他 Agent 安装检查：用临时 HOME、临时 PATH 里的假命令和注入的发布数据模拟各种状态，不联网、不碰本机真实配置。"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle"
SCRIPT = SKILL / "scripts/agent_install.py"
LATEST = "1.2.3"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = load("agent_install_under_test", SCRIPT)
record = load("run_record_for_agents", SKILL / "scripts/run_record.py")
PLUGINS = list(install.PLUGINS)


def snapshot(root):
    """所有文件和目录的相对路径及字节内容，用于证明检查前后逐字节不变。"""
    state = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        state[key] = path.read_bytes() if path.is_file() else None
    return state


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()  # macOS 的 /var 是链接，安装器不接受链接路径
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.impl = self.root / "impl"
        for path in (self.home, self.bin, self.impl):
            path.mkdir()
        catalog = json.loads((SKILL / "scripts/agents.json").read_text(encoding="utf-8"))
        # 只保留数据文件里以 ~ 开头的应用位置，并让它们适用于当前平台，避免读到本机真实的 /Applications。
        for agent in catalog["agents"]:
            darwin = agent["detect_agent"].get("paths", {}).get("darwin", [])
            agent["detect_agent"]["paths"] = {sys.platform: [p for p in darwin if p.startswith("~")]}
        self.catalog = self.root / "agents.json"
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.env = {key: value for key, value in os.environ.items()
                    if key not in ("OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME", "DSH_HOME")}
        self.env.update(PATH=str(self.bin), HOME=str(self.home), USERPROFILE=str(self.home))
        self.no_api = (self.root / "no-release.json").as_uri()

    def fake(self, name, stdout="", code=0, sleep=0):
        """在临时 PATH 里放一个假命令：忽略参数，按预设输出、退出码和延迟返回。"""
        if not isinstance(stdout, str):
            stdout = json.dumps(stdout)
        body = "import sys, time\ntime.sleep(%r)\nsys.stdout.write(%r)\nsys.exit(%d)\n" % (sleep, stdout, code)
        self.command(name, body)

    def command(self, name, body):
        """安装假命令脚本；Windows 通过同一 Python 启动，其他平台直接执行。"""
        script = self.impl / (name + ".py")
        script.write_text(body, encoding="utf-8")
        if os.name == "nt":
            (self.bin / (name + ".cmd")).write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8")
        else:
            launcher = self.bin / name
            launcher.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
            launcher.chmod(0o755)

    def gh(self, tag="v" + LATEST, prerelease=False, draft=False):
        self.fake("gh", {"tagName": tag, "isDraft": draft, "isPrerelease": prerelease})

    def receipts(self, root, versions, manual=()):
        for name, version in versions.items():
            skill = root / ("forge-steward-" + name)
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            (skill / ".forge-steward-install.json").write_text(json.dumps(
                {"tool": "ForgeSteward", "schema": 1, "name": skill.name, "version": version, "files": {}}),
                encoding="utf-8")
        for name in manual:
            (root / ("forge-steward-" + name)).mkdir(parents=True)
            (root / ("forge-steward-" + name) / "SKILL.md").write_text("manual\n", encoding="utf-8")

    def zcode(self, items):
        cli = self.home / "Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"
        cli.parent.mkdir(parents=True)
        cli.write_text("// fake\n", encoding="utf-8")
        self.fake("node", items)

    def run_check(self, *extra, api=None, timeout="5", as_json=True):
        arguments = [sys.executable, "-B", str(SCRIPT), "check", "--catalog", str(self.catalog),
                     "--release-api", api or self.no_api, "--command-timeout", timeout, *extra]
        if as_json:
            arguments.append("--json")
        result = subprocess.run(arguments, env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return json.loads(result.stdout.decode("utf-8")) if as_json else result.stdout.decode("utf-8")

    def by_id(self, result):
        return {agent["id"]: agent for agent in result["agents"]}


def claude_list(versions, scope="user"):
    items = [{"id": "other@elsewhere", "version": "9.9.9", "scope": "user"}]
    return items + [{"id": name + "@forge-steward", "version": v, "scope": scope, "enabled": True}
                    for name, v in versions.items()]


def every(version):
    return {name: version for name in PLUGINS}


class AgentStatusTests(Sandbox):
    def test_states_and_check_is_read_only(self):
        self.gh()
        self.fake("claude", claude_list(every(LATEST)) + claude_list({"prepare-work": LATEST}, scope="project"))
        self.fake("codex", {"installed": [{"pluginId": name + "@forge-steward", "version": LATEST, "installed": True}
                                          for name in ("prepare-work", "execute-work")]})
        self.zcode([{"id": name + "@forge-steward", "version": "1.2.2", "enabled": True} for name in PLUGINS])
        self.receipts(self.home / ".config/opencode/skills", every("1.3.0"))
        (self.home / ".dsh").mkdir()
        before = snapshot(self.home)
        result = self.run_check()
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual(result["latest"], {"version": LATEST, "tag": "v" + LATEST, "source": "gh"})
        agents = self.by_id(result)
        self.assertEqual({key: agent["status"] for key, agent in agents.items()},
                         {"claude-code": "最新", "codex": "不完整", "zcode": "落后",
                          "opencode": "高于最新正式版", "deepseek-harness": "缺少"})
        self.assertEqual(agents["claude-code"]["other_scopes"], ["prepare-work"])
        self.assertEqual(agents["codex"]["missing"], [p for p in PLUGINS if p not in ("prepare-work", "execute-work")])
        self.assertEqual(agents["zcode"]["versions"], ["1.2.2"])
        self.assertEqual(agents["deepseek-harness"]["missing"], PLUGINS)

    def test_missing_plugins_in_a_present_agent(self):
        self.gh()
        self.fake("claude", claude_list({}))
        self.assertEqual(self.by_id(self.run_check())["claude-code"]["status"], "缺少")

    def test_absent_agents_are_not_listed(self):
        self.gh()
        result = self.run_check()
        self.assertEqual({agent["status"] for agent in result["agents"]}, {"未安装 Agent"})
        self.assertEqual(self.run_check(as_json=False), "")

    def test_bad_output_and_failures_only_affect_that_agent(self):
        self.gh()
        self.fake("claude", "not json")
        self.fake("codex", {"installed": "not a list"})
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        (self.home / ".zcode").mkdir()
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["claude-code"], {"id": "claude-code", "name": "Claude Code",
                                                 "status": "无法判断", "reason": "输出格式无法识别"})
        self.assertEqual(agents["codex"]["reason"], "输出格式无法识别")
        self.assertEqual(agents["zcode"]["reason"], "缺少命令 node")
        self.assertEqual(agents["deepseek-harness"]["status"], "最新")

    def test_nonzero_exit_and_bad_version(self):
        self.gh()
        self.fake("claude", "", code=3)
        self.fake("codex", {"installed": [{"pluginId": "prepare-work@forge-steward", "version": "1.2"}]})
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["claude-code"]["reason"], "命令返回 3")
        self.assertEqual(agents["codex"]["reason"], "版本号格式无法识别：1.2")

    def test_command_timeout(self):
        self.gh()
        self.fake("claude", claude_list(every(LATEST)), sleep=30)
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        began = time.monotonic()
        agents = self.by_id(self.run_check(timeout="1"))
        self.assertLess(time.monotonic() - began, 20)
        self.assertEqual(agents["claude-code"]["status"], "无法判断")
        self.assertTrue(agents["claude-code"]["reason"].startswith("命令超时"), agents["claude-code"]["reason"])
        self.assertEqual(agents["deepseek-harness"]["status"], "最新")

    def test_manual_copies_cannot_be_judged(self):
        self.gh()
        self.receipts(self.home / ".config/opencode/skills", {"prepare-work": LATEST}, manual=["execute-work"])
        self.receipts(self.home / ".dsh/skills", {}, manual=["review-and-merge"])
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["opencode"]["reason"], "有手工副本（forge-steward-execute-work），无法判断")
        self.assertEqual(agents["deepseek-harness"]["reason"], "有手工副本（forge-steward-review-and-merge），无法判断")

    def test_user_roots_follow_environment_variables(self):
        self.gh()
        self.env["OPENCODE_CONFIG_DIR"] = str(self.root / "oc")
        self.env["DSH_HOME"] = str(self.root / "dsh")
        self.receipts(self.root / "oc/skills", every(LATEST))
        self.receipts(self.root / "dsh/skills", every("1.0.0"))
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["opencode"]["status"], "最新")
        self.assertEqual(agents["deepseek-harness"]["status"], "落后")

    def test_output_file_matches_json_and_text_uses_report_wording(self):
        self.gh()
        self.fake("claude", claude_list(every(LATEST)))
        target = self.root / "run" / "agent-check.json"
        target.parent.mkdir()
        printed = self.run_check("--output", str(target))
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), printed)
        self.assertEqual([p.name for p in target.parent.iterdir()], ["agent-check.json"])
        self.assertEqual(self.run_check(as_json=False), "")

    def test_non_json_check_only_offers_upgrade_and_saves_all_states(self):
        self.gh()
        self.fake("claude", claude_list(every("1.2.2")))
        self.fake("codex", {"installed": [{"pluginId": name + "@forge-steward", "version": LATEST,
                                           "installed": True} for name in PLUGINS]})
        target = self.root / "agent-check.json"
        text = self.run_check("--output", str(target), as_json=False)
        self.assertEqual(text, "- Claude Code：v1.2.2，落后于最新 v1.2.3\n"
                               "- Claude Code 可以安装或升级到 v1.2.3。要现在安装或升级吗？\n")
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(self.by_id(saved)["claude-code"]["status"], "落后")
        self.assertEqual(self.by_id(saved)["codex"]["status"], "最新")
        self.assertEqual(saved["schema"], 1)


class CodexQueryTests(Sandbox):
    ARGV = ["plugin", "list", "--marketplace", "forge-steward", "--json"]

    def setUp(self):
        super().setUp()
        self.gh()
        self.fake("claude", claude_list(every(LATEST)))
        self.log = self.root / "codex-calls.jsonl"
        self.remote_cache = self.root / "remote-cache"
        self.child_marker = self.root / "child-survived"
        config = self.home / ".codex"
        (config / "plugins").mkdir(parents=True)
        (config / "config.toml").write_text("# keep configuration\n", encoding="utf-8")
        # 查询失败时即使内部目录有看似可用的数据，也不能据此补结果。
        (config / "plugins/installed.json").write_text(json.dumps(every(LATEST)), encoding="utf-8")

    def codex(self, stdout, mode="normal"):
        if not isinstance(stdout, str):
            stdout = json.dumps(stdout)
        body = r'''
import json, pathlib, subprocess, sys, time
LOG, CACHE, CHILD, OUTPUT, MODE = %r, %r, %r, %r, %r
args = sys.argv[1:]
with open(LOG, "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
limited = args == ["plugin", "list", "--marketplace", "forge-steward", "--json"]
if not limited and args != ["plugin", "list", "--json"]:
    sys.exit(99)
if not limited:
    cache = pathlib.Path(CACHE)
    if not cache.exists():
        time.sleep(2)
        cache.write_text("remote fetched", encoding="utf-8")
if MODE == "unsupported" and limited:
    sys.exit(2)
if MODE == "exit":
    sys.exit(7)
if MODE == "timeout":
    code = ("import pathlib, time; pathlib.Path(%%r).write_text('started'); "
            "time.sleep(3); pathlib.Path(%%r).write_text('survived')") %% (CHILD + ".started", CHILD)
    subprocess.Popen([sys.executable, "-c", code])
    time.sleep(30)
if MODE == "normal" and limited:
    data = json.loads(OUTPUT)
    data["installed"] = [item for item in data["installed"] if item["pluginId"].endswith("@forge-steward")]
    OUTPUT = json.dumps(data)
sys.stdout.write(OUTPUT)
''' % (str(self.log), str(self.remote_cache), str(self.child_marker), stdout, mode)
        self.command("codex", body)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def output(self, versions):
        return {"installed": [{"pluginId": name + "@forge-steward", "version": version}
                              for name, version in versions.items()]
                + [{"pluginId": name + "@elsewhere", "version": "9.9.9"} for name in PLUGINS],
                "available": [{"pluginId": "uninstalled@forge-steward", "version": LATEST}]}

    def test_limited_cold_and_warm_queries_skip_remote_and_match_legacy(self):
        self.codex(self.output(every(LATEST)))
        before = snapshot(self.home)
        target = self.root / "run/agent-check.json"
        target.parent.mkdir()
        results = []
        for _ in range(2):
            began = time.monotonic()
            result = self.run_check("--output", str(target), timeout="20")
            self.assertLess(time.monotonic() - began, 60)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), result)
            results.append(self.by_id(result)["codex"])
            self.assertFalse(self.remote_cache.exists())
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["plugins"], every(LATEST))
        self.assertEqual(self.calls(), [self.ARGV, self.ARGV])
        # 对照假命令确实区分远端冷/热路径；旧查询只在测试中执行。
        for cold in (True, False):
            began = time.monotonic()
            legacy = subprocess.run([str(self.bin / ("codex.cmd" if os.name == "nt" else "codex")),
                                     "plugin", "list", "--json"], env=self.env, capture_output=True, check=True)
            if cold:
                self.assertGreaterEqual(time.monotonic() - began, 2)
            self.assertTrue(self.remote_cache.exists())
            found = {item["pluginId"].split("@")[0]: item["version"]
                     for item in json.loads(legacy.stdout)["installed"]
                     if item["pluginId"].endswith("@forge-steward")}
            self.assertEqual(found, results[0]["plugins"])
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual([p.name for p in target.parent.iterdir()], ["agent-check.json"])

    def test_strict_parameters_preserve_four_states_and_ignore_other_market(self):
        for versions, status in ((every(LATEST), "最新"), (every("1.2.2"), "落后"),
                                 ({}, "缺少"), ({"prepare-work": LATEST}, "不完整")):
            with self.subTest(status=status):
                self.log.unlink(missing_ok=True)
                self.codex(self.output(versions))
                before = snapshot(self.home)
                result = self.run_check()
                agents = self.by_id(result)
                self.assertEqual(agents["codex"]["status"], status)
                self.assertEqual(agents["codex"]["plugins"], versions)
                self.assertEqual(agents["codex"]["missing"], [p for p in PLUGINS if p not in versions])
                self.assertEqual(agents["claude-code"]["status"], "最新")
                self.assertEqual(result["schema"], 1)
                self.assertEqual(self.calls(), [self.ARGV])
                self.assertEqual(snapshot(self.home), before)

    def test_failures_only_mark_codex_unknown_without_retry_or_cache_fallback(self):
        for stdout, mode, reason in (("", "exit", "命令返回 7"),
                                     ("", "unsupported", "命令返回 2"),
                                     ("not json", "raw", "输出格式无法识别"),
                                     ({"installed": {}}, "raw", "输出格式无法识别"),
                                     ({"installed": [{"id": "prepare-work@forge-steward", "version": LATEST}]},
                                      "raw", "输出格式无法识别"),
                                     ({"installed": [{"pluginId": "prepare-work@forge-steward", "release": LATEST}]},
                                      "raw", "输出格式无法识别"),
                                     (self.output(every(LATEST)), "timeout", "命令超时（1 秒）")):
            with self.subTest(mode=mode, stdout=stdout):
                self.log.unlink(missing_ok=True)
                self.codex(stdout, mode)
                before = snapshot(self.home)
                agents = self.by_id(self.run_check(timeout="1" if mode == "timeout" else "5"))
                self.assertEqual(agents["codex"], {"id": "codex", "name": "Codex",
                                                 "status": "无法判断", "reason": reason})
                self.assertEqual(agents["claude-code"]["status"], "最新")
                self.assertEqual(self.calls(), [self.ARGV])
                self.assertFalse(self.remote_cache.exists())
                self.assertEqual(snapshot(self.home), before)
                if mode == "timeout":
                    self.assertTrue(Path(str(self.child_marker) + ".started").exists(), "子进程必须实际开始运行")
                    time.sleep(3)
                    self.assertFalse(self.child_marker.exists(), "超时后子进程不能继续写文件")

    def test_missing_cli_does_not_claim_plugins_are_missing(self):
        shutil.rmtree(self.home / ".codex")
        self.assertEqual(self.by_id(self.run_check())["codex"]["status"], "未安装 Agent")
        (self.home / ".codex").mkdir()
        codex = self.by_id(self.run_check())["codex"]
        self.assertEqual((codex["status"], codex["reason"]), ("无法判断", "找不到命令 codex"))
        self.assertFalse(self.log.exists())


class LatestReleaseTests(Sandbox):
    def setUp(self):
        super().setUp()
        self.fake("claude", claude_list(every(LATEST)))

    def api(self, data):
        path = self.root / "release.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path.as_uri()

    def test_prerelease_or_odd_tag_means_latest_unknown(self):
        for tag, prerelease in (("v" + LATEST, True), ("v1.2.3-rc.1", False), ("1.2.3", False)):
            with self.subTest(tag=tag, prerelease=prerelease):
                self.gh(tag, prerelease=prerelease)
                result = self.run_check()
                self.assertIsNone(result["latest"]["version"])
                self.assertEqual(self.by_id(result)["claude-code"],
                                 dict(self.by_id(result)["claude-code"], status="无法判断", reason="无法确认最新版本"))

    def test_api_is_used_when_gh_is_missing_or_fails(self):
        api = self.api({"tag_name": "v" + LATEST, "draft": False, "prerelease": False})
        self.assertEqual(self.run_check(api=api)["latest"], {"version": LATEST, "tag": "v" + LATEST, "source": "api"})
        self.fake("gh", "", code=1)
        self.assertEqual(self.run_check(api=api)["latest"]["source"], "api")
        self.assertIsNone(self.run_check(api=self.api({"tag_name": "v2.0.0", "prerelease": True}))["latest"]["version"])

    def test_query_failure_keeps_json_but_omits_text(self):
        self.fake("gh", "", code=1)
        result = self.run_check()
        self.assertIsNone(result["latest"]["version"])
        self.assertTrue(result["latest"]["error"].startswith("gh：命令返回 1；GitHub 接口："), result["latest"])
        lines = self.run_check(as_json=False).splitlines()
        self.assertEqual(lines, [])


class UsageAndSingleSourceTests(Sandbox):
    def test_usage_errors_return_two(self):
        for extra in (["--catalog", str(self.root / "missing.json")], ["--command-timeout", "0"]):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "check", *extra], env=self.env,
                                    capture_output=True)
            self.assertEqual(result.returncode, 2, extra)

    def test_plugins_match_repository(self):
        self.assertEqual(PLUGINS, sorted(p.name for p in (REPO / "plugins").iterdir() if p.is_dir()))

    def test_statuses_match_report_spec(self):
        words = record.load_report_spec()["agents"]
        self.assertEqual(set(install.STATUSES), set(words["statuses"]) | {words["absent"]})
        self.assertEqual(install.CURRENT, words["current"])

    def test_commands_and_paths_come_only_from_catalog(self):
        source = SCRIPT.read_text(encoding="utf-8")
        catalog = json.loads((SKILL / "scripts/agents.json").read_text(encoding="utf-8"))
        for agent in catalog["agents"]:
            where, method = agent["detect_agent"], agent["detect_install"]
            texts = list(where.get("commands", [])) + list(where.get("config_dirs", []))
            texts += [p for paths in where.get("paths", {}).values() for p in paths]
            texts += [" ".join(method.get("argv", []))] + [r.get("path", r.get("env")) for r in method.get("user_roots", [])]
            texts.append(" ".join(agent.get("detect_marketplace", {}).get("argv", [])))
            for text in filter(None, texts):
                self.assertFalse(text in source, "%s: %s" % (agent["id"], text))


# 有状态的假 Agent 命令：记录每次调用的参数，按调用更新插件和市场状态，list 时按各 Agent 的格式输出。
# 与实测一致：Claude Code、Codex 已有来源不同的市场时添加失败，ZCode 直接换来源；删除不存在的市场失败。
# 状态里的 market_list 为 "bad" 时列出市场输出无法识别，为 "slow" 时 30 秒才返回。
AGENT_FAKE = r"""
import json, os, re, sys, tempfile, time, uuid
STATE, LOG, NAME, KIND, FAIL = %r, %r, %r, %r, %r
args = [a for a in sys.argv[1:] if not a.endswith(".cjs")]
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=LOG,
                                 prefix=".pending-", suffix=".tmp", delete=False) as log:
    json.dump([NAME] + args, log)
    log.write("\n")
    pending = log.name
# Python 3.9 的 macOS monotonic_ns() 从进程启动计时，不能跨假命令排序。
tick = (time.clock_gettime_ns(time.CLOCK_MONOTONIC) if hasattr(time, "clock_gettime_ns")
        else time.monotonic_ns())
published = os.path.join(LOG, "%%020d-%%s.json" %% (tick, uuid.uuid4().hex))
os.replace(pending, published)
with open(STATE, encoding="utf-8") as file:
    state = json.load(file)
joined = " ".join(args)
if any(pattern in joined for pattern in FAIL):
    sys.stderr.write("network is unreachable\n")
    sys.exit(1)
plugins = state["plugins"]
if "marketplace" in args and "list" in args:
    if state.get("market_list") == "bad":
        sys.stdout.write("not json")
        sys.exit(0)
    if state.get("market_list") == "slow":
        time.sleep(30)
    names = ["other-market"] + (["forge-steward"] if state["market"] else [])
    if KIND == "codex":
        out = {"marketplaces": [{"name": n, "root": "/x/" + n} for n in names]}
    elif KIND == "zcode":
        out = [{"id": n, "name": n, "official": n == "other-market"} for n in names]
    else:
        out = [{"name": n, "source": "github"} for n in names]
    sys.stdout.write(json.dumps(out))
    sys.exit(0)
if "list" in args:
    if KIND == "codex":
        if args != ["plugin", "list", "--marketplace", "forge-steward", "--json"]:
            sys.exit(99)
        out = {"installed": [{"pluginId": n + "@forge-steward", "version": v} for n, v in plugins.items()]}
    else:
        out = [{"id": n + "@forge-steward", "version": v, "scope": "user"} for n, v in plugins.items()]
    sys.stdout.write(json.dumps(out))
    sys.exit(0)
if "marketplace" in args:
    if "add" in args:
        target = re.search(r"v(\d+\.\d+\.\d+)", joined).group(1)
        if state["market"] not in (None, target) and KIND != "zcode":
            sys.stderr.write("marketplace forge-steward already exists with a different source\n")
            sys.exit(1)
        state["market"] = target
    elif "remove" in args:
        if state["market"] is None:
            sys.exit(1)
        state["market"] = None
else:
    name = next(a for a in args if a.endswith("@forge-steward"))[:-len("@forge-steward")]
    if {"install", "add"} & set(args):
        if state["market"] is None:
            sys.exit(1)
        plugins[name] = state["market"]
    elif {"uninstall", "remove"} & set(args):
        if plugins.pop(name, None) is None:
            sys.exit(1)
with open(STATE, "w", encoding="utf-8") as file:
    json.dump(state, file)
"""


class ApplySandbox(Sandbox):
    """apply 的测试环境：临时 HOME、临时目录、临时 PATH 中的假命令、本地 Git 仓库充当发布源码，不联网。"""

    @classmethod
    def setUpClass(cls):
        cls.real_git = shutil.which("git")
        if not cls.real_git:
            raise unittest.SkipTest("git is required to build the local release repository")
        cls.source_dir = tempfile.TemporaryDirectory()
        src = Path(cls.source_dir.name) / "src"
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(str(REPO / "plugins"), str(src / "plugins"), ignore=ignore)
        shutil.copytree(str(REPO / "scripts"), str(src / "scripts"), ignore=ignore)
        for manifest in (src / "plugins").glob("*/plugin.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["version"] = LATEST
            manifest.write_text(json.dumps(data), encoding="utf-8")
        git = [cls.real_git, "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
               "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
        for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "release"], ["tag", "v" + LATEST]):
            subprocess.run(git + command, check=True, capture_output=True)
        cls.src = src
        cls.commit = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                                    text=True).stdout.strip()

    @classmethod
    def tearDownClass(cls):
        cls.source_dir.cleanup()

    def setUp(self):
        super().setUp()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.env.update(TMPDIR=str(self.tmp), TEMP=str(self.tmp), TMP=str(self.tmp))
        self.log = self.root / "calls"
        self.log.mkdir()
        if os.name == "nt":
            (self.bin / "git.cmd").write_text('@"%s" %%*\r\n' % self.real_git, encoding="utf-8")
        else:
            os.symlink(self.real_git, str(self.bin / "git"))
        self.release = self.write("release.json", {"tag_name": "v" + LATEST, "draft": False, "prerelease": False})
        self.commit_api = self.write("commit.json", {"sha": self.commit})

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path.as_uri()

    def agent(self, command, kind, plugins, fail=(), market="installed", market_list=None):
        """放一个有状态的假 Agent 命令；plugins 是已装插件与版本，市场缺省按已装版本设置，None 表示没有市场。"""
        state = self.root / (command + "-state.json")
        if market == "installed":
            market = next(iter(plugins.values()), None)
        state.write_text(json.dumps({"plugins": plugins, "market": market, "market_list": market_list}),
                         encoding="utf-8")
        body = AGENT_FAKE % (str(state), str(self.log), command, kind, list(fail))
        script = self.impl / (command + ".py")
        script.write_text(body, encoding="utf-8")
        if os.name == "nt":
            (self.bin / (command + ".cmd")).write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script),
                                                        encoding="utf-8")
        else:
            launcher = self.bin / command
            launcher.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
            launcher.chmod(0o755)
        return state

    def plugins_of(self, state):
        return json.loads(state.read_text(encoding="utf-8"))["plugins"]

    def calls(self, name=None):
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.log.glob("*.json"))]
        return [row[1:] for row in rows if name is None or row[0] == name]

    def clear_calls(self):
        for path in self.log.iterdir():
            path.unlink()

    def changing_calls(self):
        return [row for row in self.calls() if "list" not in row]

    def market_lists(self, name):
        return [row for row in self.calls(name) if "marketplace" in row and "list" in row]

    def without_plugin_list(self, name):
        """该假命令被调用的参数，去掉检查和复查时的列出插件。"""
        return [row for row in self.calls(name) if not ("list" in row and "marketplace" not in row)]

    def harness(self):
        (self.home / ".dsh").mkdir(exist_ok=True)
        self.env["DSH_HOME"] = str(self.root / "dsh")
        return self.root / "dsh" / "skills"

    def apply(self, *extra, version=LATEST, agents="deepseek-harness", source=None, commit_api=None):
        arguments = [sys.executable, "-B", str(SCRIPT), "apply", "--catalog", str(self.catalog),
                     "--release-api", self.release, "--commit-api", commit_api or self.commit_api,
                     "--source-url", source or self.src.as_uri(), "--command-timeout", "20"]
        if version is not None:
            arguments += ["--version", version]
        if agents is not None:
            arguments += ["--agents", agents]
        result = subprocess.run(arguments + list(extra), env=self.env, capture_output=True)
        return result.returncode, result.stdout.decode("utf-8"), result.stderr.decode("utf-8", "replace")

    def apply_json(self, expect, extra=(), **options):
        code, out, err = self.apply("--json", *extra, **options)
        self.assertEqual(code, expect, out + err)
        return json.loads(out)

    def installed(self, skills):
        result = {}
        for path in sorted(skills.glob("forge-steward-*")):
            receipt = path / ".forge-steward-install.json"
            result[path.name] = json.loads(receipt.read_text(encoding="utf-8"))["version"] if receipt.exists() else None
        return result


class ApplyHarnessTests(ApplySandbox):
    def test_only_harness_missing_installs_all_six_skills(self):
        skills = self.harness()
        before = snapshot(self.root / "home")
        # 不同意：只做检查，或 apply 缺参数，HOME 与 DSH_HOME 都逐字节不变。
        self.run_check()
        self.assertEqual(self.apply(agents=None)[0], 2)
        self.assertEqual(snapshot(self.root / "home"), before)
        self.assertFalse(skills.exists())
        result = self.apply_json(0)
        entry = result["agents"][0]
        self.assertEqual((entry["before"], entry["after"]["status"], entry["done"]), ("缺少", "最新", True))
        self.assertIn("下载了 v%s 的源码" % LATEST, entry["source"])
        self.assertEqual(self.installed(skills), {"forge-steward-" + name: LATEST for name in PLUGINS})
        self.assertEqual(list(self.tmp.iterdir()), [], "temporary source and lock must be removed")
        code, out, _ = self.apply()
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "- DeepSeek Harness：没有处理，已是最新")

    def test_text_result_and_next_session_note(self):
        self.harness()
        code, out, _ = self.apply()
        self.assertEqual(code, 0)
        self.assertEqual(out, "- DeepSeek Harness：已安装 v%s\n- 新版本要在各 Agent 的下一个新会话里才生效。\n" % LATEST)

    def test_matching_local_copy_is_used_and_kept(self):
        skills = self.harness()
        copy = self.home / ".claude/plugins/marketplaces/forge-steward"
        subprocess.run([self.real_git, "clone", "-q", self.src.as_uri(), str(copy)], check=True, capture_output=True)
        entry = self.apply_json(0, source=(self.root / "nowhere").as_uri())["agents"][0]
        self.assertIn("本地已有的副本", entry["source"])
        self.assertEqual(len(self.installed(skills)), len(PLUGINS))
        self.assertTrue((copy / "scripts/deepseek.py").is_file())

    def test_local_copy_with_other_commit_or_changes_is_not_used(self):
        skills = self.harness()
        copy = self.home / ".claude/plugins/marketplaces/forge-steward"
        subprocess.run([self.real_git, "clone", "-q", self.src.as_uri(), str(copy)], check=True, capture_output=True)
        (copy / "untracked.txt").write_text("local change\n", encoding="utf-8")
        entry = self.apply_json(1, source=(self.root / "nowhere").as_uri())["agents"][0]
        self.assertFalse(entry["done"])
        self.assertTrue(entry["problems"][0].startswith("下载 v%s 的源码失败" % LATEST), entry["problems"])
        self.assertFalse(skills.exists() and any(skills.iterdir()))
        entry = self.apply_json(0)["agents"][0]
        self.assertIn("下载了", entry["source"])

    def test_clone_commit_differs_from_release_stops_without_installing(self):
        skills = self.harness()
        entry = self.apply_json(1, commit_api=self.write("other.json", {"sha": "0" * 40}))["agents"][0]
        self.assertIn("不一致，没有安装", entry["problems"][0])
        self.assertEqual(entry["steps"], [])
        self.assertFalse(skills.exists() and any(skills.iterdir()))
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_modified_or_unrecorded_copies_are_not_overwritten(self):
        skills = self.harness()
        self.receipts(skills, {"prepare-work": "1.2.2"})  # 安装记录里的文件清单与实际内容不符，即被修改过
        before = snapshot(skills / "forge-steward-prepare-work")
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertEqual(snapshot(skills / "forge-steward-prepare-work"), before)
        self.assertEqual(len(self.installed(skills)), len(PLUGINS))
        self.assertIn("没有装好，复查结果：落后（v1.2.2、v%s）" % LATEST, out)
        self.assertIn("Locally modified skill: " + str(skills / "forge-steward-prepare-work"), out)
        opencode = self.home / ".config/opencode/skills"
        self.receipts(opencode, {}, manual=["review-and-merge"])
        before = snapshot(opencode)
        code, out, _ = self.apply(agents="opencode")
        self.assertEqual((code, snapshot(opencode)), (0, before))
        self.assertEqual(out, "- OpenCode：没有处理，无法判断：有手工副本（forge-steward-review-and-merge），无法判断\n")


class ApplyPluginAgentTests(ApplySandbox):
    def test_calls_ignore_unpublished_file_but_reject_broken_published_record(self):
        (self.log / "00000000000000000001-first.json").write_text(
            json.dumps(["claude", "plugin", "list"]), encoding="utf-8")
        (self.log / ".pending-interrupted.tmp").write_text('["claude",', encoding="utf-8")
        (self.log / "00000000000000000002-second.json").write_text(
            json.dumps(["claude", "plugin", "marketplace", "list"]), encoding="utf-8")
        self.assertEqual(self.calls("claude"), [["plugin", "list"], ["plugin", "marketplace", "list"]])
        self.assertEqual(self.market_lists("claude"), [["plugin", "marketplace", "list"]])
        self.assertEqual(self.changing_calls(), [])
        (self.log / "00000000000000000003-broken.json").write_text('["claude",', encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.calls()

    def test_only_the_lagging_agent_is_handled(self):
        claude = self.agent("claude", "claude", every(LATEST))
        old = dict(every("1.2.2"), **{"find-work": "1.2.2"})
        codex = self.agent("codex", "codex", old)
        skills = self.harness()
        self.receipts(skills, every(LATEST))
        before = snapshot(skills)
        result = self.apply_json(0, agents="codex,claude-code,deepseek-harness")
        entries = {entry["id"]: entry for entry in result["agents"]}
        self.assertEqual(entries["claude-code"]["skipped"], "已是最新")
        self.assertEqual(entries["deepseek-harness"]["skipped"], "已是最新")
        self.assertTrue(entries["codex"]["done"])
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertEqual(self.plugins_of(claude), every(LATEST))
        self.assertEqual(snapshot(skills), before)
        self.assertTrue(all(row[:2] == ["plugin", "list"] for row in self.calls("claude")))
        removed = sorted(old)
        expected = ([["plugin", "remove", name + "@forge-steward"] for name in removed]
                    + [["plugin", "marketplace", "remove", "forge-steward"],
                       ["plugin", "marketplace", "add", "philfanzhou/ForgeSteward", "--ref", "v" + LATEST]]
                    + [["plugin", "add", name + "@forge-steward"] for name in PLUGINS])
        self.assertEqual([row for row in self.calls("codex") if "list" not in row], expected)
        self.assertEqual(self.market_lists("codex"), [["plugin", "marketplace", "list", "--json"]])
        code, out, _ = self.apply(agents="codex")
        self.assertEqual(out, "- Codex：没有处理，已是最新\n")

    def test_missing_agent_uses_upgrade_steps_without_uninstall_or_market_removal(self):
        claude = self.agent("claude", "claude", {})
        code, out, _ = self.apply(agents="claude-code")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.plugins_of(claude), every(LATEST))
        self.assertEqual(self.changing_calls()[0],
                         ["plugin", "marketplace", "add", "philfanzhou/ForgeSteward@v" + LATEST, "--scope", "user"])
        self.assertTrue(out.startswith("- Claude Code：已安装 v%s\n" % LATEST), out)

    def test_leftover_old_marketplace_is_replaced_before_installing(self):
        for command, kind, agent_id, remove, add, put in (
                ("claude", "claude", "claude-code",
                 ["plugin", "marketplace", "remove", "forge-steward", "--scope", "user"],
                 ["plugin", "marketplace", "add", "philfanzhou/ForgeSteward@v" + LATEST, "--scope", "user"],
                 ["plugin", "install", "{}@forge-steward", "--scope", "user"]),
                ("codex", "codex", "codex",
                 ["plugin", "marketplace", "remove", "forge-steward"],
                 ["plugin", "marketplace", "add", "philfanzhou/ForgeSteward", "--ref", "v" + LATEST],
                 ["plugin", "add", "{}@forge-steward"])):
            with self.subTest(agent=agent_id):
                self.clear_calls()
                state = self.agent(command, kind, {}, market="1.2.2")
                code, out, _ = self.apply(agents=agent_id)
                self.assertEqual(code, 0, out)
                self.assertEqual(self.plugins_of(state), every(LATEST))
                self.assertEqual(self.without_plugin_list(command),
                                 [["plugin", "marketplace", "list", "--json"], remove, add]
                                 + [[arg.format(name) for arg in put] for name in PLUGINS])
                self.assertTrue(out.startswith("- %s：已安装 v%s\n" % (
                    "Claude Code" if command == "claude" else "Codex", LATEST)), out)

    def test_missing_marketplace_is_not_removed(self):
        codex = self.agent("codex", "codex", every("1.2.2"), market=None)
        result = self.apply_json(0, agents="codex")
        entry = result["agents"][0]
        self.assertTrue(entry["done"], entry)
        self.assertEqual(entry["after"]["status"], "最新")
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertFalse(any(row[:3] == ["plugin", "marketplace", "remove"] for row in self.calls("codex")))
        self.assertEqual(self.changing_calls(),
                         [["plugin", "remove", name + "@forge-steward"] for name in PLUGINS]
                         + [["plugin", "marketplace", "add", "philfanzhou/ForgeSteward", "--ref", "v" + LATEST]]
                         + [["plugin", "add", name + "@forge-steward"] for name in PLUGINS])

    def test_unreadable_marketplace_list_leaves_that_agent_untouched(self):
        # Windows CI 每次跑完整套测试时，都把发生过偶发失败的场景连续验证十次。
        for attempt in range(10 if os.name == "nt" else 1):
            with self.subTest(attempt=attempt):
                self.assert_unreadable_marketplace_list_leaves_that_agent_untouched()

    def assert_unreadable_marketplace_list_leaves_that_agent_untouched(self):
        for market_list, fail, reason in ((None, ["marketplace list"], "命令返回 1"),
                                          ("bad", [], "输出格式无法识别"),
                                          ("slow", [], "命令超时（2 秒）")):
            with self.subTest(market_list=market_list or "fail"):
                self.clear_calls()
                claude = self.agent("claude", "claude", every("1.2.2"), fail=fail, market_list=market_list)
                codex = self.agent("codex", "codex", every("1.2.2"))
                result = self.apply_json(1, agents="claude-code,codex", extra=("--command-timeout", "2"))
                entries = {entry["id"]: entry for entry in result["agents"]}
                claude_entry = entries["claude-code"]
                self.assertEqual(claude_entry["problems"], ["查不到市场是否存在：" + reason])
                self.assertEqual(claude_entry["steps"], [])
                self.assertEqual(claude_entry["after"]["status"], "落后")
                self.assertTrue(self.market_lists("claude"), "市场列表调用必须有完整记录")
                self.assertTrue(all("list" in row for row in self.calls("claude")))
                self.assertEqual(self.plugins_of(claude), every("1.2.2"))
                self.assertTrue(entries["codex"]["done"])
                self.assertEqual(self.plugins_of(codex), every(LATEST))
        code, out, _ = self.apply("--command-timeout", "2", agents="claude-code")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- Claude Code：没有装好，复查结果：落后（v1.2.2）；"
                                       "查不到市场是否存在：命令超时（2 秒）。"), out)

    def test_check_does_not_list_marketplaces(self):
        self.agent("claude", "claude", every("1.2.2"))
        self.agent("codex", "codex", {}, market="1.2.2")
        self.zcode([])
        self.agent("node", "zcode", every(LATEST))
        self.gh()
        result = self.run_check(api=self.release)
        self.assertEqual({key: agent["status"] for key, agent in self.by_id(result).items()
                          if key in ("claude-code", "codex", "zcode")},
                         {"claude-code": "落后", "codex": "缺少", "zcode": "最新"})
        self.assertTrue(self.calls())
        self.assertFalse(any("marketplace" in row for row in self.calls()))

    def test_newer_install_is_not_downgraded(self):
        codex = self.agent("codex", "codex", every("1.3.0"))
        code, out, _ = self.apply(agents="codex")
        self.assertEqual(code, 0)
        self.assertEqual(out, "- Codex：没有处理，已装 v1.3.0，比目标版本新，不降级\n")
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.3.0"))

    def test_failed_step_stops_that_agent_only_and_reports_rechecked_state(self):
        self.zcode([])  # 建出 zcode.cjs；node 稍后换成有状态的假命令
        zcode = self.agent("node", "zcode", every("1.2.2"), fail=["marketplace add"])
        codex = self.agent("codex", "codex", every("1.2.2"))
        result = self.apply_json(1, agents="zcode,codex")
        entries = {entry["id"]: entry for entry in result["agents"]}
        self.assertEqual(entries["zcode"]["after"]["status"], "缺少")
        self.assertFalse(entries["zcode"]["done"])
        self.assertTrue(entries["codex"]["done"])
        self.assertEqual(self.plugins_of(zcode), {})
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertFalse(any("install" in row for row in self.calls("node")))
        code, out, _ = self.apply(agents="zcode")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- ZCode：没有装好，复查结果：缺少；`node zcode.cjs plugins marketplace add "
                                       "philfanzhou/ForgeSteward@v%s` 没成功：network is unreachable。" % LATEST), out)


class ApplyRefusalTests(ApplySandbox):
    def test_nothing_changes_without_valid_arguments_same_latest_or_free_lock(self):
        codex = self.agent("codex", "codex", every("1.2.2"))
        skills = self.harness()
        before = snapshot(self.root / "home")
        for options, expect in (({"version": None}, 2), ({"agents": None}, 2), ({"version": "1.2"}, 2),
                                ({"agents": "codex,unknown"}, 2), ({"agents": ""}, 2)):
            with self.subTest(options=options):
                self.assertEqual(self.apply(**dict({"agents": "codex"}, **options))[0], expect)
        code, out, _ = self.apply(version="1.2.4", agents="codex,deepseek-harness")
        self.assertEqual(code, 3)
        self.assertEqual(out, "- 没有做任何改动：最新正式版已变成 v%s，不是同意的 v1.2.4；请按新版本重新询问\n" % LATEST)
        lock = self.tmp / "forge-steward-agent-install.lock"
        lock.mkdir()
        code, out, _ = self.apply(agents="codex,deepseek-harness")
        self.assertEqual(code, 3)
        self.assertTrue(out.startswith("- 没有做任何改动：另一个安装正在进行"), out)
        self.assertTrue(lock.is_dir(), "someone else's lock must not be removed")
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.2.2"))
        self.assertEqual(snapshot(self.root / "home"), before)
        self.assertFalse(skills.exists())


# 在子进程里加载脚本、替换其中一个函数制造文件错误，再照常运行 main；环境变量（HOME、PATH、TMPDIR）与其他测试相同。
FAULT_RUNNER = r"""
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("agent_install_with_fault", %r)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
%s
sys.exit(m.main(sys.argv[1:]))
"""

FAIL_REMOVE = """
real_remove = m.remove_tree
def remove_tree(path):
    if Path(str(path)).name.startswith(%r):
        raise PermissionError(13, "Permission denied", str(path))
    real_remove(path)
m.remove_tree = remove_tree
"""


class ApplyFileErrorTests(ApplySandbox):
    """开始改动后的意外文件错误：不再返回 2，逐个 Agent 的结果照常输出。"""

    def apply_with(self, fault, *extra, agents="deepseek-harness"):
        runner = self.root / "fault-runner" / "run.py"
        runner.parent.mkdir(exist_ok=True)
        runner.write_text(FAULT_RUNNER % (str(SCRIPT), fault), encoding="utf-8")
        arguments = [sys.executable, "-B", "-I", str(runner), "apply", "--catalog", str(self.catalog),
                     "--release-api", self.release, "--commit-api", self.commit_api,
                     "--source-url", self.src.as_uri(), "--command-timeout", "20", "--version", LATEST,
                     "--agents", agents]
        result = subprocess.run(arguments + list(extra), env=self.env, capture_output=True)
        return result.returncode, result.stdout.decode("utf-8"), result.stderr.decode("utf-8", "replace")

    def test_work_directory_not_removed_keeps_results_and_returns_one(self):
        skills = self.harness()
        code, out, err = self.apply_with(FAIL_REMOVE % "forge-steward-apply-")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.installed(skills), {"forge-steward-" + name: LATEST for name in PLUGINS})
        lines = out.splitlines()
        self.assertEqual(lines[0], "- DeepSeek Harness：已安装 v%s" % LATEST)
        work = [path for path in self.tmp.iterdir() if path.name.startswith("forge-steward-apply-")]
        self.assertEqual(len(work), 1)
        self.assertEqual(lines[1], "- 临时目录 %s 没能删除：Permission denied（%s），可以手动删除" % (work[0], work[0]))
        self.assertEqual(lines[2], "- 新版本要在各 Agent 的下一个新会话里才生效。")
        self.assertFalse((self.tmp / install.LOCK_NAME).exists())
        code, out, err = self.apply_with(FAIL_REMOVE % "forge-steward-apply-", "--json")
        self.assertEqual(code, 1, out + err)
        result = json.loads(out)
        self.assertEqual(result["outcome"], "done")
        self.assertEqual(result["agents"][0]["skipped"], "已是最新")
        [item] = result["cleanup"]
        self.assertEqual(item["kind"], "work")
        self.assertTrue(Path(item["path"]).name.startswith("forge-steward-apply-"), item)
        self.assertTrue(item["reason"].startswith("Permission denied"), item)

    def test_lock_not_removed_asks_to_check_before_deleting_it(self):
        skills = self.harness()
        lock = self.tmp / install.LOCK_NAME
        code, out, err = self.apply_with(FAIL_REMOVE % install.LOCK_NAME)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(len(self.installed(skills)), len(PLUGINS))
        self.assertEqual(out.splitlines(), [
            "- DeepSeek Harness：已安装 v%s" % LATEST,
            "- 锁目录 %s 没能删除：Permission denied（%s）。确认没有安装在运行后手动删除它，"
            "否则下次会提示“另一个安装正在进行”" % (lock, lock),
            "- 新版本要在各 Agent 的下一个新会话里才生效。"])
        self.assertTrue(lock.is_dir())
        shutil.rmtree(str(lock))
        result = json.loads(self.apply_with(FAIL_REMOVE % install.LOCK_NAME, "--json")[1])
        self.assertEqual(result["cleanup"], [{"kind": "lock", "path": str(lock),
                                              "reason": "Permission denied（%s）" % lock}])
        self.assertEqual(result["agents"][0]["skipped"], "已是最新")

    def test_file_error_while_handling_one_agent_stays_in_its_entry(self):
        fault = """
real_run = m.run_step
count = [0]
def run_step(argv, cwd, timeout):
    if argv[0] == "codex":
        count[0] += 1
        if count[0] == 2:
            raise PermissionError(13, "Permission denied", "/denied/output")
    return real_run(argv, cwd, timeout)
m.run_step = run_step
"""
        codex = self.agent("codex", "codex", every("1.2.2"))
        claude = self.agent("claude", "claude", every("1.2.2"))
        code, out, err = self.apply_with(fault, "--json", agents="codex,claude-code")
        self.assertEqual(code, 1, out + err)
        result = json.loads(out)
        entries = {entry["id"]: entry for entry in result["agents"]}
        problem = ("运行 `codex plugin remove execute-work@forge-steward` 时出现意外的文件错误："
                   "Permission denied（/denied/output）")
        self.assertEqual(entries["codex"]["problems"], [problem])
        self.assertEqual(len(entries["codex"]["steps"]), 1)
        self.assertEqual(entries["codex"]["after"]["status"], "落后")
        self.assertFalse(entries["codex"]["done"])
        self.assertTrue(entries["claude-code"]["done"])
        self.assertEqual(self.plugins_of(claude), every(LATEST))
        self.assertEqual(self.plugins_of(codex), {name: "1.2.2" for name in PLUGINS if name != "check-workflow"})
        self.assertEqual(result["cleanup"], [])
        code, out, _ = self.apply_with(fault, agents="codex")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- Codex：没有装好，复查结果：落后（v1.2.2）；运行 `codex plugin remove "
                                       "fix-feedback@forge-steward` 时出现意外的文件错误："), out)

    def test_file_error_after_the_last_step_is_still_reported_when_installed(self):
        fault = """
real_run = m.run_step
def run_step(argv, cwd, timeout):
    result = real_run(argv, cwd, timeout)
    if argv[0] == "codex" and argv[-1] == "work-cycle@forge-steward" and "add" in argv:
        raise PermissionError(13, "Permission denied", "/denied/output")
    return result
m.run_step = run_step
"""
        codex = self.agent("codex", "codex", every("1.2.2"))
        code, out, err = self.apply_with(fault, agents="codex")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertEqual(out.splitlines()[0], "- Codex：已从 v1.2.2 升到 v%s；但运行 `codex plugin add "
                         "work-cycle@forge-steward` 时出现意外的文件错误：Permission denied（/denied/output）" % LATEST)

    def test_source_removal_error_is_reported_for_that_agent(self):
        skills = self.harness()
        fault = """
real_remove = m.remove_tree
def remove_tree(path):
    if Path(str(path)).name == "source":
        raise PermissionError(13, "Permission denied", str(path))
    real_remove(path)
m.remove_tree = remove_tree
"""
        code, out, err = self.apply_with(fault, "--json", "--commit-api", self.write("other.json", {"sha": "0" * 40}))
        self.assertEqual(code, 1, out + err)
        entry = json.loads(out)["agents"][0]
        self.assertEqual(len(entry["problems"]), 1)
        self.assertTrue(entry["problems"][0].startswith("准备源码时出现意外的文件错误：Permission denied（"), entry)
        self.assertEqual(entry["after"]["status"], "缺少")
        self.assertFalse(skills.exists() and any(skills.iterdir()))

    def test_work_directory_cannot_be_created_stops_before_any_change(self):
        codex = self.agent("codex", "codex", every("1.2.2"))
        fault = """
def mkdtemp(*args, **kwargs):
    raise PermissionError(13, "Permission denied", "/denied/tmp")
m.tempfile.mkdtemp = mkdtemp
"""
        code, out, err = self.apply_with(fault, agents="codex")
        self.assertEqual(code, 3, out + err)
        self.assertEqual(out, "- 没有做任何改动：无法建立临时目录（%s）：Permission denied（/denied/tmp）\n" % self.tmp)
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.2.2"))
        self.assertEqual(list(self.tmp.iterdir()), [])
        result = json.loads(self.apply_with(fault, "--json", agents="codex")[1])
        self.assertEqual((result["outcome"], result["agents"], result["cleanup"]), ("stopped", [], []))


class ReportLineTests(unittest.TestCase):
    def setUp(self):
        self.spec = record.load_report_spec()

    def lines(self, agents, version=LATEST, error="网络不可用"):
        latest = {"version": version} if version else {"version": None, "error": error}
        return record.agent_lines({"schema": 1, "latest": latest, "agents": agents}, self.spec)

    def test_each_status_wording(self):
        agents = [
            {"name": "A", "status": "未安装 Agent"},
            {"name": "B", "status": "缺少", "versions": [], "missing": PLUGINS},
            {"name": "C", "status": "不完整", "versions": [LATEST], "missing": ["fix-feedback", "work-cycle"]},
            {"name": "D", "status": "落后", "versions": ["1.2.1", "1.2.2"], "missing": []},
            {"name": "E", "status": "最新", "versions": [LATEST], "missing": [], "other_scopes": ["prepare-work"]},
            {"name": "F", "status": "高于最新正式版", "versions": ["1.3.0"], "missing": []},
            {"name": "G", "status": "无法判断", "reason": "命令超时（20 秒）"},
        ]
        self.assertEqual(self.lines(agents), [
            "B：未安装（最新 v1.2.3）", "C：缺 fix-feedback、work-cycle（最新 v1.2.3）",
            "D：v1.2.1、v1.2.2，落后于最新 v1.2.3",
            "B、C、D 可以安装或升级到 v1.2.3。要现在安装或升级吗？"])

    def test_question_only_when_something_can_be_installed_or_upgraded(self):
        newer = {"name": "A", "status": "高于最新正式版", "versions": ["1.3.0"], "missing": []}
        unknown = {"name": "B", "status": "无法判断", "reason": "缺少命令 node"}
        current = {"name": "C", "status": "最新", "versions": [LATEST], "missing": [], "other_scopes": ["x"]}
        self.assertEqual(self.lines([newer, unknown, current]), [])
        missing = {"name": "DeepSeek Harness", "status": "缺少", "versions": [], "missing": PLUGINS}
        self.assertEqual(self.lines([missing, current]), [
            "DeepSeek Harness：未安装（最新 v1.2.3）",
            "DeepSeek Harness 可以安装或升级到 v1.2.3。要现在安装或升级吗？"])
        self.assertEqual(self.lines([dict(missing, status="缺少")], version=None),
                         [])

    def test_all_latest_none_and_latest_unknown(self):
        current = {"name": "A", "status": "最新", "versions": [LATEST], "missing": []}
        self.assertEqual(self.lines([current, dict(current, name="B")]), [])
        self.assertEqual(self.lines([{"name": "A", "status": "未安装 Agent"}]), [])
        self.assertEqual(self.lines([
            {"name": "A", "status": "无法判断", "reason": "无法确认最新版本", "versions": [LATEST], "missing": []},
            {"name": "B", "status": "缺少", "versions": [], "missing": PLUGINS},
            {"name": "C", "status": "不完整", "versions": [LATEST], "missing": ["work-cycle"]},
            {"name": "D", "status": "无法判断", "reason": "缺少命令 node"}], version=None),
            [])

    def test_unusable_results_raise(self):
        for check in (None, {"schema": 2}, {"schema": 1, "latest": {"version": LATEST}, "agents": [{"name": "A"}]},
                      {"schema": 1, "latest": {"version": LATEST},
                       "agents": [{"name": "A", "status": "落后", "versions": "1.0.0"}]}):
            with self.subTest(check=check):
                with self.assertRaises(ValueError):
                    record.agent_lines(check, self.spec)


if __name__ == "__main__":
    unittest.main()
