"""Test Agent installation checks with temporary HOME/PATH, fake commands, and injected releases, without network or real user configuration."""

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
    """Relative paths and bytes of all files/directories, proving checks leave them byte-identical."""
    state = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        state[key] = path.read_bytes() if path.is_file() else None
    return state


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()  # macOS /var is a symlink; installers reject symlink paths
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.impl = self.root / "impl"
        for path in (self.home, self.bin, self.impl):
            path.mkdir()
        catalog = json.loads((SKILL / "scripts/agents.json").read_text(encoding="utf-8"))
        # Retain only ~ application locations and apply them to this platform, avoiding real /Applications.
        for agent in catalog["agents"]:
            darwin = agent["detect_agent"].get("paths", {}).get("darwin", [])
            agent["detect_agent"]["paths"] = {sys.platform: [p for p in darwin if p.startswith("~")]}
        self.catalog = self.root / "agents.json"
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.env = {key: value for key, value in os.environ.items()
                    if key not in ("OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME", "DSH_HOME")}
        self.env.update(PATH=str(self.bin), HOME=str(self.home), USERPROFILE=str(self.home))
        # Bare fake Python commands and their descendants must not add bytecode to the HOME being checked.
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.no_api = (self.root / "no-release.json").as_uri()

    def fake(self, name, stdout="", code=0, sleep=0):
        """Put a fake command in temporary PATH: ignore arguments and return preset output, status, and delay."""
        if not isinstance(stdout, str):
            stdout = json.dumps(stdout)
        body = "import sys, time\ntime.sleep(%r)\nsys.stdout.write(%r)\nsys.exit(%d)\n" % (sleep, stdout, code)
        self.command(name, body)

    def command(self, name, body):
        """Install a fake command; Windows uses the same Python, other platforms execute it directly."""
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


class SandboxIsolationTests(Sandbox):
    def test_fake_command_and_descendant_do_not_write_bytecode(self):
        module = self.impl / "cache_probe.py"
        module.write_text("value = 123\n", encoding="utf-8")
        probe = ("import json, sys; sys.path.insert(0, %r); import cache_probe; "
                 "print(json.dumps([sys.dont_write_bytecode, cache_probe.__cached__]))") % str(self.impl)
        self.command("cache-probe", "import json, subprocess, sys\n"
                     "exec(%r)\n"
                     "child = subprocess.run([sys.executable, '-c', %r], check=True, capture_output=True)\n"
                     "print(child.stdout.decode('utf-8').strip())\n" % (probe, probe))
        command = [str(self.bin / ("cache-probe.cmd" if os.name == "nt" else "cache-probe"))]

        # A separate control HOME proves fresh imports would write at the forced cache destination.
        control_home = self.root / "control-home"
        control_home.mkdir()
        control = dict(self.env, HOME=str(control_home), USERPROFILE=str(control_home),
                       PYTHONPYCACHEPREFIX=str(control_home / "Library/Caches/python"))
        control.pop("PYTHONDONTWRITEBYTECODE")
        result = subprocess.run(command, env=control, capture_output=True, check=True)
        reports = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
        self.assertEqual(len(reports), 2)
        for disabled, cached in reports:
            self.assertFalse(disabled)
            self.assertTrue(Path(cached).is_file(), cached)
            self.assertIn(control_home, Path(cached).parents)

        self.env["PYTHONPYCACHEPREFIX"] = str(self.home / "Library/Caches/python")
        before = snapshot(self.home)
        result = subprocess.run(command, env=self.env, capture_output=True, check=True)
        reports = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
        self.assertEqual(len(reports), 2)
        for disabled, cached in reports:
            self.assertTrue(disabled)
            self.assertFalse(Path(cached).exists(), cached)
            self.assertIn(self.home, Path(cached).parents)
        self.assertEqual(snapshot(self.home), before)

    def test_read_only_snapshot_rejects_real_check_process_writes(self):
        self.gh()
        for relative, action in ((".codex/config.toml", "add"), (".codex/config.toml", "edit"),
                                 ("Library/Caches/installer-write", "add"),
                                 ("Library/Caches/installer-write", "edit"), ("empty-directory", "remove")):
            with self.subTest(path=relative, action=action):
                target = self.home / relative
                if action == "remove":
                    target.mkdir()
                before = snapshot(self.home)
                fault = """
real_check = m.check
def check(*args, **kwargs):
    result = real_check(*args, **kwargs)
    target = Path.home() / %r
    if %r == "remove":
        target.rmdir()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(%r, encoding="utf-8")
    return result
m.check = check
""" % (relative, action, action)
                runner = self.root / "fault-runner.py"
                runner.write_text(FAULT_RUNNER % (str(SCRIPT), fault), encoding="utf-8")
                result = subprocess.run([sys.executable, "-B", str(runner), "check", "--catalog", str(self.catalog),
                                         "--release-api", self.no_api, "--json"], env=self.env, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertEqual(json.loads(result.stdout)["latest"]["version"], LATEST)
                after = snapshot(self.home)
                if action == "remove":
                    self.assertNotIn(relative, after)
                else:
                    self.assertEqual(after[relative], action.encode("utf-8"))
                    if action == "edit":
                        self.assertEqual(before[relative], b"add")
                    else:
                        self.assertNotIn(relative, before)
                        self.assertNotIn(target.parent.relative_to(self.home).as_posix(), before)
                with self.assertRaises(AssertionError):
                    self.assertEqual(after, before)


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
                         {"claude-code": "Current", "codex": "Incomplete", "zcode": "Behind",
                          "opencode": "Ahead of latest release", "deepseek-harness": "Missing"})
        self.assertEqual(agents["claude-code"]["other_scopes"], ["prepare-work"])
        self.assertEqual(agents["codex"]["missing"], [p for p in PLUGINS if p not in ("prepare-work", "execute-work")])
        self.assertEqual(agents["zcode"]["versions"], ["1.2.2"])
        self.assertEqual(agents["deepseek-harness"]["missing"], PLUGINS)

    def test_missing_plugins_in_a_present_agent(self):
        self.gh()
        self.fake("claude", claude_list({}))
        self.assertEqual(self.by_id(self.run_check())["claude-code"]["status"], "Missing")

    def test_absent_agents_are_not_listed(self):
        self.gh()
        result = self.run_check()
        self.assertEqual({agent["status"] for agent in result["agents"]}, {"Agent not installed"})
        self.assertEqual(self.run_check(as_json=False), "")

    def test_bad_output_and_failures_only_affect_that_agent(self):
        self.gh()
        self.fake("claude", "not json")
        self.fake("codex", {"installed": "not a list"})
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        (self.home / ".zcode").mkdir()
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["claude-code"], {"id": "claude-code", "name": "Claude Code",
                                                 "status": "Unknown", "reason": "Unrecognized output format"})
        self.assertEqual(agents["codex"]["reason"], "Unrecognized output format")
        self.assertEqual(agents["zcode"]["reason"], "Missing command: node")
        self.assertEqual(agents["deepseek-harness"]["status"], "Current")

    def test_nonzero_exit_and_bad_version(self):
        self.gh()
        self.fake("claude", "", code=3)
        self.fake("codex", {"installed": [{"pluginId": "prepare-work@forge-steward", "version": "1.2"}]})
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["claude-code"]["reason"], "Command returned 3")
        self.assertEqual(agents["codex"]["reason"], "Unrecognized version format: 1.2")

    def test_command_timeout(self):
        self.gh()
        self.fake("claude", claude_list(every(LATEST)), sleep=30)
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        began = time.monotonic()
        agents = self.by_id(self.run_check(timeout="1"))
        self.assertLess(time.monotonic() - began, 20)
        self.assertEqual(agents["claude-code"]["status"], "Unknown")
        self.assertTrue(agents["claude-code"]["reason"].startswith("Command timed out"), agents["claude-code"]["reason"])
        self.assertEqual(agents["deepseek-harness"]["status"], "Current")

    def test_manual_copies_cannot_be_judged(self):
        self.gh()
        self.receipts(self.home / ".config/opencode/skills", {"prepare-work": LATEST}, manual=["execute-work"])
        self.receipts(self.home / ".dsh/skills", {}, manual=["review-and-merge"])
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["opencode"]["reason"], "Manual copies (forge-steward-execute-work) prevent determining the state")
        self.assertEqual(agents["deepseek-harness"]["reason"], "Manual copies (forge-steward-review-and-merge) prevent determining the state")

    def test_user_roots_follow_environment_variables(self):
        self.gh()
        self.env["OPENCODE_CONFIG_DIR"] = str(self.root / "oc")
        self.env["DSH_HOME"] = str(self.root / "dsh")
        self.receipts(self.root / "oc/skills", every(LATEST))
        self.receipts(self.root / "dsh/skills", every("1.0.0"))
        self.receipts(self.home / ".dsh/skills", every(LATEST))
        agents = self.by_id(self.run_check())
        self.assertEqual(agents["opencode"]["status"], "Current")
        self.assertEqual(agents["deepseek-harness"]["status"], "Behind")

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
        self.assertEqual(text, "- Claude Code: v1.2.2, behind latest v1.2.3\n"
                               "- Claude Code can be installed or upgraded to v1.2.3. Install or upgrade now?\n")
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(self.by_id(saved)["claude-code"]["status"], "Behind")
        self.assertEqual(self.by_id(saved)["codex"]["status"], "Current")
        self.assertEqual(saved["schema"], 1)


class ClassificationTests(Sandbox):
    """A mixed installation stays actionable: AHEAD only when nothing installed is below the target."""

    def status(self, versions, missing=()):
        return install.classify({"versions": list(versions), "missing": list(missing)}, "1.2.0")["status"]

    def test_mixed_newer_and_older_installation_is_behind(self):
        self.assertEqual(self.status(["1.3.0", "1.1.0"]), "Behind")

    def test_any_older_version_is_behind(self):
        self.assertEqual(self.status(["1.1.0", "1.0.0"]), "Behind")

    def test_all_newer_versions_are_ahead(self):
        self.assertEqual(self.status(["1.3.0", "1.4.0"]), "Ahead of latest release")

    def test_newer_versions_with_one_equal_are_ahead(self):
        self.assertEqual(self.status(["1.3.0", "1.2.0"]), "Ahead of latest release")

    def test_missing_plugin_alongside_a_newer_version_is_incomplete(self):
        self.assertEqual(self.status(["1.3.0"], ["work-cycle"]), "Incomplete")

    def test_single_version_states_are_unchanged(self):
        self.assertEqual(self.status(["1.2.0"]), "Current")
        self.assertEqual(self.status([]), "Missing")

    def test_mixed_receipts_are_reported_as_upgradeable(self):
        self.gh("v1.2.0")
        self.receipts(self.home / ".dsh/skills", dict(every("1.1.0"), **{"prepare-work": "1.3.0"}))
        agent = self.by_id(self.run_check())["deepseek-harness"]
        self.assertEqual(agent["status"], "Behind")
        self.assertEqual(agent["versions"], ["1.1.0", "1.3.0"])
        self.assertEqual(self.run_check(as_json=False),
                         "- DeepSeek Harness: v1.1.0, v1.3.0, behind latest v1.2.0\n"
                         "- DeepSeek Harness can be installed or upgraded to v1.2.0. Install or upgrade now?\n")


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
        # A failed query must not fill results from apparently usable internal data.
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
        # Ensure fake commands distinguish cold/warm remote paths; run the old query only in this test.
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
        for versions, status in ((every(LATEST), "Current"), (every("1.2.2"), "Behind"),
                                 ({}, "Missing"), ({"prepare-work": LATEST}, "Incomplete")):
            with self.subTest(status=status):
                self.log.unlink(missing_ok=True)
                self.codex(self.output(versions))
                before = snapshot(self.home)
                result = self.run_check()
                agents = self.by_id(result)
                self.assertEqual(agents["codex"]["status"], status)
                self.assertEqual(agents["codex"]["plugins"], versions)
                self.assertEqual(agents["codex"]["missing"], [p for p in PLUGINS if p not in versions])
                self.assertEqual(agents["claude-code"]["status"], "Current")
                self.assertEqual(result["schema"], 1)
                self.assertEqual(self.calls(), [self.ARGV])
                self.assertEqual(snapshot(self.home), before)

    def test_failures_only_mark_codex_unknown_without_retry_or_cache_fallback(self):
        for stdout, mode, reason in (("", "exit", "Command returned 7"),
                                     ("", "unsupported", "Command returned 2"),
                                     ("not json", "raw", "Unrecognized output format"),
                                     ({"installed": {}}, "raw", "Unrecognized output format"),
                                     ({"installed": [{"id": "prepare-work@forge-steward", "version": LATEST}]},
                                      "raw", "Unrecognized output format"),
                                     ({"installed": [{"pluginId": "prepare-work@forge-steward", "release": LATEST}]},
                                      "raw", "Unrecognized output format"),
                                     (self.output(every(LATEST)), "timeout", "Command timed out (1 seconds)")):
            with self.subTest(mode=mode, stdout=stdout):
                self.log.unlink(missing_ok=True)
                self.codex(stdout, mode)
                before = snapshot(self.home)
                agents = self.by_id(self.run_check(timeout="1" if mode == "timeout" else "5"))
                self.assertEqual(agents["codex"], {"id": "codex", "name": "Codex",
                                                 "status": "Unknown", "reason": reason})
                self.assertEqual(agents["claude-code"]["status"], "Current")
                self.assertEqual(self.calls(), [self.ARGV])
                self.assertFalse(self.remote_cache.exists())
                self.assertEqual(snapshot(self.home), before)
                if mode == "timeout":
                    self.assertTrue(Path(str(self.child_marker) + ".started").exists(), "The child process must actually start")
                    time.sleep(3)
                    self.assertFalse(self.child_marker.exists(), "The child process must not keep writing after timeout")

    def test_missing_cli_does_not_claim_plugins_are_missing(self):
        shutil.rmtree(self.home / ".codex")
        self.assertEqual(self.by_id(self.run_check())["codex"]["status"], "Agent not installed")
        (self.home / ".codex").mkdir()
        codex = self.by_id(self.run_check())["codex"]
        self.assertEqual((codex["status"], codex["reason"]), ("Unknown", "Command not found: codex"))
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
                                 dict(self.by_id(result)["claude-code"], status="Unknown", reason="Cannot confirm the latest version"))

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
        self.assertTrue(result["latest"]["error"].startswith("gh: Command returned 1; GitHub API: "), result["latest"])
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


# Stateful fake Agent command: log arguments, update plugin/marketplace state, and emit each Agent's list format.
# Match observations: Claude Code/Codex reject a different existing source; ZCode replaces it; removing an absent marketplace fails.
# market_list="bad" yields unrecognized output; "slow" waits 30 seconds.
AGENT_FAKE = r"""
import json, os, re, sys, tempfile, time, uuid
STATE, LOG, NAME, KIND, FAIL = %r, %r, %r, %r, %r
args = [a for a in sys.argv[1:] if not a.endswith(".cjs")]
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=LOG,
                                 prefix=".pending-", suffix=".tmp", delete=False) as log:
    json.dump([NAME] + args, log)
    log.write("\n")
    pending = log.name
# macOS Python 3.9 monotonic_ns() starts at process launch and cannot order separate fake commands.
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
    """Offline apply environment: temporary HOME/directories/PATH commands and local Git release source."""

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
        """Create a stateful fake Agent; plugins maps installed versions, marketplace defaults to that version, and None means absent."""
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
        """Arguments passed to the fake command, excluding plugin lists for checks and rechecks."""
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
        # Without consent: check only or apply with missing arguments leaves HOME and DSH_HOME byte-identical.
        self.run_check()
        self.assertEqual(self.apply(agents=None)[0], 2)
        self.assertEqual(snapshot(self.root / "home"), before)
        self.assertFalse(skills.exists())
        result = self.apply_json(0)
        entry = result["agents"][0]
        self.assertEqual((entry["before"], entry["after"]["status"], entry["done"]), ("Missing", "Current", True))
        self.assertIn("Downloaded source for v%s" % LATEST, entry["source"])
        self.assertEqual(self.installed(skills), {"forge-steward-" + name: LATEST for name in PLUGINS})
        self.assertEqual(list(self.tmp.iterdir()), [], "temporary source and lock must be removed")
        code, out, _ = self.apply()
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "- DeepSeek Harness: Skipped: Already current")

    def test_text_result_and_next_session_note(self):
        self.harness()
        code, out, _ = self.apply()
        self.assertEqual(code, 0)
        self.assertEqual(out, "- DeepSeek Harness: Installed v%s\n- The new version takes effect in the next new session of each Agent.\n" % LATEST)

    def test_matching_local_copy_is_used_and_kept(self):
        skills = self.harness()
        copy = self.home / ".claude/plugins/marketplaces/forge-steward"
        subprocess.run([self.real_git, "clone", "-q", self.src.as_uri(), str(copy)], check=True, capture_output=True)
        entry = self.apply_json(0, source=(self.root / "nowhere").as_uri())["agents"][0]
        self.assertIn("existing local copy", entry["source"])
        self.assertEqual(len(self.installed(skills)), len(PLUGINS))
        self.assertTrue((copy / "scripts/deepseek.py").is_file())

    def test_local_copy_with_other_commit_or_changes_is_not_used(self):
        skills = self.harness()
        copy = self.home / ".claude/plugins/marketplaces/forge-steward"
        subprocess.run([self.real_git, "clone", "-q", self.src.as_uri(), str(copy)], check=True, capture_output=True)
        (copy / "untracked.txt").write_text("local change\n", encoding="utf-8")
        entry = self.apply_json(1, source=(self.root / "nowhere").as_uri())["agents"][0]
        self.assertFalse(entry["done"])
        self.assertTrue(entry["problems"][0].startswith("Failed to download source for v%s" % LATEST), entry["problems"])
        self.assertFalse(skills.exists() and any(skills.iterdir()))
        entry = self.apply_json(0)["agents"][0]
        self.assertIn("Downloaded", entry["source"])

    def test_clone_commit_differs_from_release_stops_without_installing(self):
        skills = self.harness()
        entry = self.apply_json(1, commit_api=self.write("other.json", {"sha": "0" * 40}))["agents"][0]
        self.assertIn("; nothing installed", entry["problems"][0])
        self.assertEqual(entry["steps"], [])
        self.assertFalse(skills.exists() and any(skills.iterdir()))
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_modified_or_unrecorded_copies_are_not_overwritten(self):
        skills = self.harness()
        self.receipts(skills, {"prepare-work": "1.2.2"})  # Receipt files differ from actual contents, indicating a modified installation
        before = snapshot(skills / "forge-steward-prepare-work")
        code, out, _ = self.apply()
        self.assertEqual(code, 1)
        self.assertEqual(snapshot(skills / "forge-steward-prepare-work"), before)
        self.assertEqual(len(self.installed(skills)), len(PLUGINS))
        self.assertIn("Installation incomplete; Recheck: Behind (v1.2.2, v%s)" % LATEST, out)
        self.assertIn("Locally modified skill: " + str(skills / "forge-steward-prepare-work"), out)
        opencode = self.home / ".config/opencode/skills"
        self.receipts(opencode, {}, manual=["review-and-merge"])
        before = snapshot(opencode)
        code, out, _ = self.apply(agents="opencode")
        self.assertEqual((code, snapshot(opencode)), (0, before))
        self.assertEqual(out, "- OpenCode: Skipped: Unknown: Manual copies (forge-steward-review-and-merge) prevent determining the state\n")


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
        self.assertEqual(entries["claude-code"]["skipped"], "Already current")
        self.assertEqual(entries["deepseek-harness"]["skipped"], "Already current")
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
        self.assertEqual(out, "- Codex: Skipped: Already current\n")

    def test_missing_agent_uses_upgrade_steps_without_uninstall_or_market_removal(self):
        claude = self.agent("claude", "claude", {})
        code, out, _ = self.apply(agents="claude-code")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.plugins_of(claude), every(LATEST))
        self.assertEqual(self.changing_calls()[0],
                         ["plugin", "marketplace", "add", "philfanzhou/ForgeSteward@v" + LATEST, "--scope", "user"])
        self.assertTrue(out.startswith("- Claude Code: Installed v%s\n" % LATEST), out)

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
                self.assertTrue(out.startswith("- %s: Installed v%s\n" % (
                    "Claude Code" if command == "claude" else "Codex", LATEST)), out)

    def test_missing_marketplace_is_not_removed(self):
        codex = self.agent("codex", "codex", every("1.2.2"), market=None)
        result = self.apply_json(0, agents="codex")
        entry = result["agents"][0]
        self.assertTrue(entry["done"], entry)
        self.assertEqual(entry["after"]["status"], "Current")
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertFalse(any(row[:3] == ["plugin", "marketplace", "remove"] for row in self.calls("codex")))
        self.assertEqual(self.changing_calls(),
                         [["plugin", "remove", name + "@forge-steward"] for name in PLUGINS]
                         + [["plugin", "marketplace", "add", "philfanzhou/ForgeSteward", "--ref", "v" + LATEST]]
                         + [["plugin", "add", name + "@forge-steward"] for name in PLUGINS])

    def test_unreadable_marketplace_list_leaves_that_agent_untouched(self):
        # Every full Windows CI suite repeats the formerly intermittent scenario ten times.
        for attempt in range(10 if os.name == "nt" else 1):
            with self.subTest(attempt=attempt):
                self.assert_unreadable_marketplace_list_leaves_that_agent_untouched()

    def assert_unreadable_marketplace_list_leaves_that_agent_untouched(self):
        for market_list, fail, reason in ((None, ["marketplace list"], "Command returned 1"),
                                          ("bad", [], "Unrecognized output format"),
                                          ("slow", [], "Command timed out (2 seconds)")):
            with self.subTest(market_list=market_list or "fail"):
                self.clear_calls()
                claude = self.agent("claude", "claude", every("1.2.2"), fail=fail, market_list=market_list)
                codex = self.agent("codex", "codex", every("1.2.2"))
                result = self.apply_json(1, agents="claude-code,codex", extra=("--command-timeout", "2"))
                entries = {entry["id"]: entry for entry in result["agents"]}
                claude_entry = entries["claude-code"]
                self.assertEqual(claude_entry["problems"], ["Cannot determine whether the marketplace exists: " + reason])
                self.assertEqual(claude_entry["steps"], [])
                self.assertEqual(claude_entry["after"]["status"], "Behind")
                self.assertTrue(self.market_lists("claude"), "Marketplace list calls must be fully logged")
                self.assertTrue(all("list" in row for row in self.calls("claude")))
                self.assertEqual(self.plugins_of(claude), every("1.2.2"))
                self.assertTrue(entries["codex"]["done"])
                self.assertEqual(self.plugins_of(codex), every(LATEST))
        code, out, _ = self.apply("--command-timeout", "2", agents="claude-code")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- Claude Code: Installation incomplete; Recheck: Behind (v1.2.2); "
                                       "Cannot determine whether the marketplace exists: Command timed out (2 seconds)."), out)

    def test_check_does_not_list_marketplaces(self):
        self.agent("claude", "claude", every("1.2.2"))
        self.agent("codex", "codex", {}, market="1.2.2")
        self.zcode([])
        self.agent("node", "zcode", every(LATEST))
        self.gh()
        result = self.run_check(api=self.release)
        self.assertEqual({key: agent["status"] for key, agent in self.by_id(result).items()
                          if key in ("claude-code", "codex", "zcode")},
                         {"claude-code": "Behind", "codex": "Missing", "zcode": "Current"})
        self.assertTrue(self.calls())
        self.assertFalse(any("marketplace" in row for row in self.calls()))

    def test_newer_install_is_not_downgraded(self):
        codex = self.agent("codex", "codex", every("1.3.0"))
        code, out, _ = self.apply(agents="codex")
        self.assertEqual(code, 0)
        self.assertEqual(out, "- Codex: Skipped: Installed v1.3.0 is newer than the target; no downgrade\n")
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.3.0"))

    def test_failed_step_stops_that_agent_only_and_reports_rechecked_state(self):
        self.zcode([])  # Create zcode.cjs; replace node with a stateful fake later
        zcode = self.agent("node", "zcode", every("1.2.2"), fail=["marketplace add"])
        codex = self.agent("codex", "codex", every("1.2.2"))
        result = self.apply_json(1, agents="zcode,codex")
        entries = {entry["id"]: entry for entry in result["agents"]}
        self.assertEqual(entries["zcode"]["after"]["status"], "Missing")
        self.assertFalse(entries["zcode"]["done"])
        self.assertTrue(entries["codex"]["done"])
        self.assertEqual(self.plugins_of(zcode), {})
        self.assertEqual(self.plugins_of(codex), every(LATEST))
        self.assertFalse(any("install" in row for row in self.calls("node")))
        code, out, _ = self.apply(agents="zcode")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- ZCode: Installation incomplete; Recheck: Missing; `node zcode.cjs plugins marketplace add "
                                       "philfanzhou/ForgeSteward@v%s` failed: network is unreachable." % LATEST), out)


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
        self.assertEqual(out, "- No changes made: Latest release changed to v%s from the agreed v1.2.4; ask again for the new version\n" % LATEST)
        lock = self.tmp / "forge-steward-agent-install.lock"
        lock.mkdir()
        code, out, _ = self.apply(agents="codex,deepseek-harness")
        self.assertEqual(code, 3)
        self.assertTrue(out.startswith("- No changes made: Another installation is running"), out)
        self.assertTrue(lock.is_dir(), "someone else's lock must not be removed")
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.2.2"))
        self.assertEqual(snapshot(self.root / "home"), before)
        self.assertFalse(skills.exists())


# Load the script in a subprocess, inject a file error into one function, then run main normally with the same HOME/PATH/TMPDIR as other tests.
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
    """Unexpected file errors after changes start report per-Agent outcomes instead of exit 2."""

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
        self.assertEqual(lines[0], "- DeepSeek Harness: Installed v%s" % LATEST)
        work = [path for path in self.tmp.iterdir() if path.name.startswith("forge-steward-apply-")]
        self.assertEqual(len(work), 1)
        self.assertEqual(lines[1], "- Could not remove temporary directory %s: Permission denied (%s); you can remove it manually" % (work[0], work[0]))
        self.assertEqual(lines[2], "- The new version takes effect in the next new session of each Agent.")
        self.assertFalse((self.tmp / install.LOCK_NAME).exists())
        code, out, err = self.apply_with(FAIL_REMOVE % "forge-steward-apply-", "--json")
        self.assertEqual(code, 1, out + err)
        result = json.loads(out)
        self.assertEqual(result["outcome"], "done")
        self.assertEqual(result["agents"][0]["skipped"], "Already current")
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
            "- DeepSeek Harness: Installed v%s" % LATEST,
            "- Could not remove lock directory %s: Permission denied (%s). Once no installation is running, remove it manually; "
            "otherwise the next attempt will report another installation is running" % (lock, lock),
            "- The new version takes effect in the next new session of each Agent."])
        self.assertTrue(lock.is_dir())
        shutil.rmtree(str(lock))
        result = json.loads(self.apply_with(FAIL_REMOVE % install.LOCK_NAME, "--json")[1])
        self.assertEqual(result["cleanup"], [{"kind": "lock", "path": str(lock),
                                              "reason": "Permission denied (%s)" % lock}])
        self.assertEqual(result["agents"][0]["skipped"], "Already current")

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
        problem = ("running `codex plugin remove execute-work@forge-steward` encountered an unexpected file error: "
                   "Permission denied (/denied/output)")
        self.assertEqual(entries["codex"]["problems"], [problem])
        self.assertEqual(len(entries["codex"]["steps"]), 1)
        self.assertEqual(entries["codex"]["after"]["status"], "Behind")
        self.assertFalse(entries["codex"]["done"])
        self.assertTrue(entries["claude-code"]["done"])
        self.assertEqual(self.plugins_of(claude), every(LATEST))
        self.assertEqual(self.plugins_of(codex), {name: "1.2.2" for name in PLUGINS if name != "check-workflow"})
        self.assertEqual(result["cleanup"], [])
        code, out, _ = self.apply_with(fault, agents="codex")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("- Codex: Installation incomplete; Recheck: Behind (v1.2.2); running `codex plugin remove "
                                       "fix-feedback@forge-steward` encountered an unexpected file error: "), out)

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
        self.assertEqual(out.splitlines()[0], "- Codex: Upgraded from v1.2.2 to v%s; however, running `codex plugin add "
                         "work-cycle@forge-steward` encountered an unexpected file error: Permission denied (/denied/output)" % LATEST)

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
        self.assertTrue(entry["problems"][0].startswith("Unexpected file error while preparing source: Permission denied ("), entry)
        self.assertEqual(entry["after"]["status"], "Missing")
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
        self.assertEqual(out, "- No changes made: Cannot create temporary directory (%s): Permission denied (/denied/tmp)\n" % self.tmp)
        self.assertEqual(self.changing_calls(), [])
        self.assertEqual(self.plugins_of(codex), every("1.2.2"))
        self.assertEqual(list(self.tmp.iterdir()), [])
        result = json.loads(self.apply_with(fault, "--json", agents="codex")[1])
        self.assertEqual((result["outcome"], result["agents"], result["cleanup"]), ("stopped", [], []))


class ReportLineTests(unittest.TestCase):
    def setUp(self):
        self.spec = record.load_report_spec()

    def lines(self, agents, version=LATEST, error="Network unavailable"):
        latest = {"version": version} if version else {"version": None, "error": error}
        return record.agent_lines({"schema": 1, "latest": latest, "agents": agents}, self.spec)

    def test_each_status_wording(self):
        agents = [
            {"name": "A", "status": "Agent not installed"},
            {"name": "B", "status": "Missing", "versions": [], "missing": PLUGINS},
            {"name": "C", "status": "Incomplete", "versions": [LATEST], "missing": ["fix-feedback", "work-cycle"]},
            {"name": "D", "status": "Behind", "versions": ["1.2.1", "1.2.2"], "missing": []},
            {"name": "E", "status": "Current", "versions": [LATEST], "missing": [], "other_scopes": ["prepare-work"]},
            {"name": "F", "status": "Ahead of latest release", "versions": ["1.3.0"], "missing": []},
            {"name": "G", "status": "Unknown", "reason": "Command timed out (20 seconds)"},
        ]
        self.assertEqual(self.lines(agents), [
            "B: Not installed (latest v1.2.3)", "C: Missing fix-feedback, work-cycle (latest v1.2.3)",
            "D: v1.2.1, v1.2.2, behind latest v1.2.3",
            "B, C, D can be installed or upgraded to v1.2.3. Install or upgrade now?"])

    def test_question_only_when_something_can_be_installed_or_upgraded(self):
        newer = {"name": "A", "status": "Ahead of latest release", "versions": ["1.3.0"], "missing": []}
        unknown = {"name": "B", "status": "Unknown", "reason": "Missing command: node"}
        current = {"name": "C", "status": "Current", "versions": [LATEST], "missing": [], "other_scopes": ["x"]}
        self.assertEqual(self.lines([newer, unknown, current]), [])
        missing = {"name": "DeepSeek Harness", "status": "Missing", "versions": [], "missing": PLUGINS}
        self.assertEqual(self.lines([missing, current]), [
            "DeepSeek Harness: Not installed (latest v1.2.3)",
            "DeepSeek Harness can be installed or upgraded to v1.2.3. Install or upgrade now?"])
        self.assertEqual(self.lines([dict(missing, status="Missing")], version=None),
                         [])

    def test_all_latest_none_and_latest_unknown(self):
        current = {"name": "A", "status": "Current", "versions": [LATEST], "missing": []}
        self.assertEqual(self.lines([current, dict(current, name="B")]), [])
        self.assertEqual(self.lines([{"name": "A", "status": "Agent not installed"}]), [])
        self.assertEqual(self.lines([
            {"name": "A", "status": "Unknown", "reason": "Cannot confirm the latest version", "versions": [LATEST], "missing": []},
            {"name": "B", "status": "Missing", "versions": [], "missing": PLUGINS},
            {"name": "C", "status": "Incomplete", "versions": [LATEST], "missing": ["work-cycle"]},
            {"name": "D", "status": "Unknown", "reason": "Missing command: node"}], version=None),
            [])

    def test_unusable_results_raise(self):
        for check in (None, {"schema": 2}, {"schema": 1, "latest": {"version": LATEST}, "agents": [{"name": "A"}]},
                      {"schema": 1, "latest": {"version": LATEST},
                       "agents": [{"name": "A", "status": "Behind", "versions": "1.0.0"}]}):
            with self.subTest(check=check):
                with self.assertRaises(ValueError):
                    record.agent_lines(check, self.spec)


if __name__ == "__main__":
    unittest.main()
