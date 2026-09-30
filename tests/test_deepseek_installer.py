"""DeepSeek 路径与共享生命周期；真实 Provider 仅显式选择时加载。"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest import mock

import test_opencode_installer as lifecycle
import deepseek
import skill_installer as installer


class DeepSeekInstallerTests(lifecycle.InstallerTests):
    adapter = deepseek
    agent_dir = ".dsh"

    def setUp(self):
        super().setUp()
        self.isolated_home = self.base / "os-home"
        self.isolated_home.mkdir()
        self.home_patch = mock.patch.object(Path, "home", return_value=self.isolated_home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        os.environ.pop("DSH_HOME", None)

    def test_user_scope_respects_xdg(self):
        # XDG 是 OpenCode 约定，Harness 默认使用 OS home。
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.base / "unused")}):
            output = self.run_cli("install", "--all", user=True)
            root = self.isolated_home / ".dsh/skills"
            self.assertIn("Target: " + str(root), output)
            self.assertEqual(len(list(root.iterdir())), len(installer.catalog(self.source)))
            for name, item in installer.catalog(self.source).items():
                self.assertEqual(installer.snapshot(root / name), item["files"])
            self.run_cli("uninstall", "--all", user=True)
        self.assertFalse(self.root.exists())

    def test_user_scope_respects_opencode_config_dir(self):
        with mock.patch.dict(os.environ, {"DSH_HOME": str(self.base / "custom home")}):
            self.run_cli("install", "prepare-work", user=True)
            self.assertTrue((self.base / "custom home/skills/forge-steward-prepare-work/SKILL.md").is_file())
            self.run_cli("uninstall", "--all", user=True)

    def test_user_residue_scan_does_not_cross_scopes(self):
        config = self.base / "custom home"
        with mock.patch.dict(os.environ, {"DSH_HOME": str(config)}):
            self.run_cli("install", "prepare-work", user=True)
            manual = config / "skills/find-work"
            manual.mkdir()
            output = self.run_cli("uninstall", "--all", user=True, expected=2)
            self.assertIn(str(manual), output)
            self.assertTrue(manual.is_dir())
            output = self.run_cli("uninstall", "--all")
            self.assertNotIn(str(manual), output)
        self.assertFalse(self.root.parent.exists())

    def test_project_git_root_file_directory_and_fallback(self):
        original = self.project
        for marker_type in ("file", "directory", "absent"):
            with self.subTest(marker=marker_type):
                marker = original / ".git"
                if marker_type == "file":
                    marker.write_text("gitdir: fixture\n", encoding="utf-8")
                elif marker_type == "directory":
                    marker.mkdir()
                nested = original / ("nested " + marker_type)
                nested.mkdir()
                self.project = nested
                target = original if marker_type != "absent" else nested
                self.root = target / ".dsh/skills"
                self.assertIn("Target: " + str(self.root), self.run_cli("install", "prepare-work"))
                self.run_cli("uninstall", "--all")
                if marker_type == "file":
                    marker.unlink()
                elif marker_type == "directory":
                    marker.rmdir()
        self.project = original

    def test_dsh_home_resolution_matrix(self):
        args = argparse.Namespace(project=None)
        for value, expected in ((None, self.isolated_home / ".dsh"), ("", self.isolated_home / ".dsh"),
                                (" \t ", self.isolated_home / ".dsh"), ("relative root", Path.cwd() / "relative root"),
                                (" padded ", Path.cwd() / " padded "), ("~", self.isolated_home),
                                ("~/harness root", self.isolated_home / "harness root"),
                                ("~\\harness root", self.isolated_home / "harness root")):
            with self.subTest(value=value), mock.patch.dict(os.environ, {}, clear=False):
                if value is None:
                    os.environ.pop("DSH_HOME", None)
                else:
                    os.environ["DSH_HOME"] = value
                self.assertEqual(deepseek.target_root(args), expected / "skills")

    def test_project_alias_is_rejected_before_resolve(self):
        alias = self.base / "alias"
        self.make_link(alias, self.project, True)
        with lifecycle.redirect_stdout(lifecycle.io.StringIO()), lifecycle.redirect_stderr(lifecycle.io.StringIO()):
            code = deepseek.main(["install", "prepare-work", "--project", str(alias)], repo=self.source)
        self.assertEqual(code, 1)
        self.assertFalse(self.root.exists())

    def test_user_alias_is_rejected_before_resolve(self):
        alias = self.base / "alias"
        self.make_link(alias, self.isolated_home, True)
        with mock.patch.dict(os.environ, {"DSH_HOME": str(alias)}):
            self.run_cli("install", "prepare-work", expected=1, user=True)
        self.assertEqual(list(self.isolated_home.iterdir()), [])

    def test_fixed_commit_update_and_rollback_tracks_source(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.source), *args], text=True).strip()
        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("add", "plugins")
        git("commit", "-qm", "baseline")
        original = git("rev-parse", "HEAD")
        self.run_cli("install", "prepare-work")
        before = self.contents(self.installed())
        (self.source_skill() / "new.txt").write_text("next", encoding="utf-8")
        git("add", "plugins")
        git("commit", "-qm", "next")
        next_commit = git("rev-parse", "HEAD")
        self.run_cli("update", "prepare-work")
        self.assertEqual(installer.read_install(self.installed())["source"], {"commit": next_commit, "dirty": False})
        git("checkout", "-q", original)
        self.run_cli("update", "prepare-work")
        self.assertEqual(before, self.contents(self.installed()))

    def test_copy_failure_after_one_staged_item_preserves_batch(self):
        self.run_cli("install", "--all")
        before = self.contents(self.root)
        for skill in self.source.glob("plugins/*/skills/*/SKILL.md"):
            skill.write_text(skill.read_text(encoding="utf-8") + "\nnext source\n", encoding="utf-8")
        copytree = shutil.copytree
        calls = 0

        def fail_second(source, destination, *args, **kwargs):
            nonlocal calls
            # copytree 递归也调用自身，只统计事务顶层技能目录。
            if Path(destination).name.startswith("new-forge-steward-"):
                calls += 1
                if calls == 2:
                    raise OSError("second staged skill failed")
            return copytree(source, destination, *args, **kwargs)

        with mock.patch.object(installer.shutil, "copytree", side_effect=fail_second):
            self.run_cli("update", "--all", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_interrupt_rolls_back(self):
        self.run_cli("install", "--all")
        before = self.contents(self.root)
        for skill in self.source.glob("plugins/*/skills/*/SKILL.md"):
            skill.write_text(skill.read_text(encoding="utf-8") + "\nnext source\n", encoding="utf-8")
        replace = os.replace
        calls = 0

        def cancel_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise KeyboardInterrupt()
            return replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=cancel_second):
            with self.assertRaises(KeyboardInterrupt):
                self.run_cli("update", "--all")
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_second_process_rejects_live_lock(self):
        ready = self.base / "ready"
        code = ("import sys,time; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
                "import skill_installer as core; root=Path(sys.argv[2]); "
                "\nwith core.locked(root):\n Path(sys.argv[3]).write_text('ready'); time.sleep(30)\n")
        process = subprocess.Popen([sys.executable, "-c", code, str(lifecycle.REPO / "scripts"), str(self.root), str(ready)])
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail("Lock holder exited before acquiring its lock")
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            self.run_cli("install", "--all", expected=1)
            self.assertTrue((self.root.parent / installer.LOCK).exists())
            self.assertFalse(self.root.exists())
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_real_opencode_discovery(self):
        # 覆盖继承的 Agent 专属测试；这里读取显式用户包，不下载运行时。
        runtime = os.environ.get("FORGESTEWARD_DEEPSEEK")
        if not runtime:
            self.skipTest("Set FORGESTEWARD_DEEPSEEK to a DeepSeek Harness package directory for actual Provider discovery")
        executable = os.environ.get("FORGESTEWARD_DEEPSEEK_NODE", "node")
        user = self.base / "provider-user"
        with mock.patch.dict(os.environ, {"DSH_HOME": str(user)}):
            self.run_cli("install", "--all")
            self.run_cli("install", "--all", user=True)
            result = subprocess.run([executable, str(lifecycle.REPO / "tests/deepseek_provider_probe.mjs"),
                                     str(Path(runtime).resolve()), str(self.project), str(user),
                                     sys.executable, str(lifecycle.REPO / "scripts/deepseek.py")],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS", result.stdout)
            self.run_cli("uninstall", "--all")
            self.run_cli("uninstall", "--all", user=True)
