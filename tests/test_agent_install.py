"""校验其他 Agent 安装检查：用临时 HOME、临时 PATH 里的假命令和注入的发布数据模拟各种状态，不联网、不碰本机真实配置。"""

import importlib.util
import json
import os
from pathlib import Path
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
        self.root = Path(self.temporary.name)
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
        self.assertEqual(self.run_check(as_json=False), "- 没有找到装了的受支持 Agent\n")

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
        self.assertEqual(self.run_check(as_json=False), "- 都已是最新（v%s）\n" % LATEST)


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

    def test_query_failure_lists_installed_versions_only(self):
        self.fake("gh", "", code=1)
        result = self.run_check()
        self.assertIsNone(result["latest"]["version"])
        self.assertTrue(result["latest"]["error"].startswith("gh：命令返回 1；GitHub 接口："), result["latest"])
        lines = self.run_check(as_json=False).splitlines()
        self.assertTrue(lines[0].startswith("- 无法确认最新版本：gh：命令返回 1"), lines)
        self.assertEqual(lines[1:], ["- Claude Code：已装 v" + LATEST])


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
            for text in filter(None, texts):
                self.assertFalse(text in source, "%s: %s" % (agent["id"], text))


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
            "D：v1.2.1、v1.2.2，落后于最新 v1.2.3", "E：已是最新 v1.2.3（另有非用户级安装）",
            "F：v1.3.0，比最新正式版新，不处理", "G：无法判断：命令超时（20 秒）"])

    def test_all_latest_none_and_latest_unknown(self):
        current = {"name": "A", "status": "最新", "versions": [LATEST], "missing": []}
        self.assertEqual(self.lines([current, dict(current, name="B")]), ["都已是最新（v1.2.3）"])
        self.assertEqual(self.lines([{"name": "A", "status": "未安装 Agent"}]), ["没有找到装了的受支持 Agent"])
        self.assertEqual(self.lines([
            {"name": "A", "status": "无法判断", "reason": "无法确认最新版本", "versions": [LATEST], "missing": []},
            {"name": "B", "status": "缺少", "versions": [], "missing": PLUGINS},
            {"name": "C", "status": "不完整", "versions": [LATEST], "missing": ["work-cycle"]},
            {"name": "D", "status": "无法判断", "reason": "缺少命令 node"}], version=None),
            ["无法确认最新版本：网络不可用", "A：已装 v1.2.3", "B：未安装", "C：缺 work-cycle", "D：无法判断：缺少命令 node"])

    def test_unusable_results_raise(self):
        for check in (None, {"schema": 2}, {"schema": 1, "latest": {"version": LATEST}, "agents": [{"name": "A"}]},
                      {"schema": 1, "latest": {"version": LATEST},
                       "agents": [{"name": "A", "status": "落后", "versions": "1.0.0"}]}):
            with self.subTest(check=check):
                with self.assertRaises(ValueError):
                    record.agent_lines(check, self.spec)


if __name__ == "__main__":
    unittest.main()
