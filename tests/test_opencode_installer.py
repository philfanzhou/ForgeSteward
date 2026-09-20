"""验证真实文件操作、事务回滚及 OpenCode 所需的安装结构。"""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installer", REPO / "scripts/opencode.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "source"
        shutil.copytree(REPO / "plugins", self.source / "plugins")
        self.project = self.base / "project with spaces"
        self.project.mkdir()
        self.root = self.project / ".opencode/skills"
        self.environment = mock.patch.dict(os.environ, {})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("OPENCODE_CONFIG_DIR", None)

    def run_cli(self, command, *selection, expected=0, user=False):
        args = [command, *selection]
        if command != "list":
            args += ["--user"] if user else ["--project", str(self.project)]
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = installer.main(args, repo=self.source)
        self.assertEqual(code, expected, output.getvalue())
        return output.getvalue()

    def installed(self, name="prepare-work"):
        return self.root / (installer.PREFIX + name)

    def source_skill(self, name="prepare-work"):
        return self.source / "plugins" / name / "skills" / (installer.PREFIX + name)

    def contents(self, directory):
        return {p.relative_to(directory).as_posix(): p.read_bytes()
                for p in directory.rglob("*") if p.is_file()}

    def assert_no_transactions(self):
        self.assertFalse(list(self.root.parent.glob(".forge-steward-*")))

    def test_list_and_subprocess_help(self):
        expected = []
        for path in sorted((self.source / "plugins").glob("*/plugin.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            expected.append(installer.PREFIX + manifest["name"] + " " + manifest["version"])
        self.assertEqual(self.run_cli("list").splitlines(), expected)
        for encoding in ("utf-8", "cp1252"):
            with self.subTest(encoding=encoding):
                environment = dict(os.environ, PYTHONIOENCODING=encoding)
                result = subprocess.run(
                    [sys.executable, str(REPO / "scripts/opencode.py"), "--help"],
                    capture_output=True, text=True, encoding=encoding, env=environment,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("uninstall", result.stdout)

    def test_single_install_and_full_name(self):
        self.run_cli("install", "forge-steward-prepare-work")
        self.assertEqual([p.name for p in self.root.iterdir()], ["forge-steward-prepare-work"])
        self.assertEqual((self.installed() / "SKILL.md").read_bytes(), (self.source_skill() / "SKILL.md").read_bytes())
        # prepare-work 的门禁等规则位于引用文件，安装不得只复制入口。
        for relative, content in self.contents(self.source_skill()).items():
            with self.subTest(resource=relative):
                self.assertEqual((self.installed() / relative).read_bytes(), content)
        receipt = json.loads((self.installed() / installer.RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual(receipt["files"], installer.snapshot(self.source_skill()))

    def test_install_all_has_matching_frontmatter_and_resources(self):
        self.run_cli("install", "--all")
        self.assertEqual(len(list(self.root.iterdir())), 5)
        for path in self.root.iterdir():
            self.assertIn("name: " + path.name + "\n", (path / "SKILL.md").read_text(encoding="utf-8"))
        for resource in ("references/skill-owned-rules.md", "scripts/remove_workflow_blocks.py"):
            self.assertTrue((self.installed("check-workflow") / resource).is_file())
        self.assert_no_transactions()

    def test_repeat_install_is_byte_and_mtime_identical(self):
        self.run_cli("install", "prepare-work")
        before = self.contents(self.root)
        mtime = (self.installed() / installer.RECEIPT).stat().st_mtime_ns
        self.assertIn("Already installed", self.run_cli("install", "prepare-work"))
        self.assertEqual(before, self.contents(self.root))
        self.assertEqual(mtime, (self.installed() / installer.RECEIPT).stat().st_mtime_ns)

    def test_modified_content_blocks_update_and_uninstall(self):
        self.run_cli("install", "--all")
        (self.installed() / "SKILL.md").write_text("user changes", encoding="utf-8")
        before = self.contents(self.root)
        for command in ("install", "update", "uninstall"):
            self.assertIn("Back up/move", self.run_cli(command, "--all", expected=1))
            self.assertEqual(before, self.contents(self.root))
        self.assertIn("Locally modified", self.run_cli("status", "--all", expected=1))
        self.assert_no_transactions()

    def test_added_and_deleted_files_and_empty_dirs_are_protected(self):
        self.run_cli("install", "prepare-work")
        extra = self.installed() / "notes.txt"
        extra.write_text("keep", encoding="utf-8")
        self.run_cli("uninstall", "prepare-work", expected=1)
        extra.unlink()
        extra.mkdir()
        self.run_cli("uninstall", "prepare-work", expected=1)
        extra.rmdir()
        (self.installed() / "SKILL.md").unlink()
        self.run_cli("update", "prepare-work", expected=1)

    def test_unmanaged_collision_prevents_partial_batch(self):
        self.installed("review-and-merge").mkdir(parents=True)
        (self.installed("review-and-merge") / "mine.txt").write_text("keep", encoding="utf-8")
        self.run_cli("install", "--all", expected=1)
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.assert_no_transactions()

    def test_explicit_update_replaces_content_and_removes_obsolete_files(self):
        obsolete = self.source_skill() / "obsolete.txt"
        obsolete.write_text("old", encoding="utf-8")
        self.run_cli("install", "prepare-work")
        obsolete.unlink()
        new = self.source_skill() / "new.txt"
        new.write_text("new", encoding="utf-8")
        manifest_path = self.source / "plugins/prepare-work/plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        old_version = manifest["version"]
        manifest["version"] = "0.2.4"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.run_cli("install", "prepare-work", expected=1)
        self.assertIn(old_version + " -> 0.2.4", self.run_cli("update", "prepare-work"))
        self.assertFalse((self.installed() / "obsolete.txt").exists())
        self.assertEqual((self.installed() / "new.txt").read_text(encoding="utf-8"), "new")
        self.assertIn("installed 0.2.4", self.run_cli("status", "prepare-work"))

    def test_update_missing_requires_install(self):
        self.assertIn("use install first", self.run_cli("update", "prepare-work", expected=1))

    def install_retired_find_work(self):
        # 模拟旧 catalog；安装收据由真实安装器生成，不手工伪造归属。
        plugin = self.source / "plugins/find-work"
        shutil.copytree(self.source / "plugins/prepare-work", plugin)
        skill = plugin / "skills/forge-steward-prepare-work"
        skill.rename(plugin / "skills/forge-steward-find-work")
        document = plugin / "skills/forge-steward-find-work/SKILL.md"
        document.write_text(document.read_text(encoding="utf-8").replace(
            "name: forge-steward-prepare-work", "name: forge-steward-find-work"), encoding="utf-8")
        manifest = plugin / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data.update(name="find-work", version="0.2.1")
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.run_cli("install", "find-work")
        shutil.rmtree(plugin)

    def test_retired_name_migrates_without_alias_or_source(self):
        self.install_retired_find_work()
        before = self.contents(self.root)
        self.run_cli("install", "find-work", expected=1)
        self.run_cli("update", "--all", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.run_cli("uninstall", "find-work")
        self.assertFalse(self.installed("find-work").exists())
        self.run_cli("install", "prepare-work", "execute-work")
        self.assertCountEqual([p.name for p in self.root.iterdir()],
                              ["forge-steward-prepare-work", "forge-steward-execute-work"])
        for name in ("prepare-work", "execute-work"):
            installed = self.contents(self.installed(name))
            installed.pop(installer.RECEIPT)
            self.assertEqual(installed, self.contents(self.source_skill(name)))

    def test_retired_modified_skill_is_preserved_during_migration(self):
        self.install_retired_find_work()
        document = self.installed("find-work") / "SKILL.md"
        document.write_text("local customization", encoding="utf-8")
        before = self.contents(self.root)
        self.run_cli("uninstall", "find-work", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.run_cli("install", "prepare-work", "execute-work")
        self.assertEqual(document.read_text(encoding="utf-8"), "local customization")

    def test_uninstall_keeps_unrelated_skills_and_no_receipts(self):
        self.run_cli("install", "--all")
        unrelated = self.root / "other-skill"
        unrelated.mkdir()
        (unrelated / "notes.txt").write_text("keep", encoding="utf-8")
        self.run_cli("uninstall", "prepare-work")
        self.assertFalse(self.installed().exists())
        self.run_cli("uninstall", "--all")
        self.assertEqual(self.contents(self.root), {"other-skill/notes.txt": b"keep"})
        self.assert_no_transactions()

    def test_uninstall_does_not_need_original_source(self):
        self.run_cli("install", "prepare-work")
        shutil.rmtree(self.source / "plugins")
        self.run_cli("uninstall", "--all")
        self.assertFalse(self.installed().exists())

    def test_missing_uninstall_is_idempotent_and_read_only(self):
        output = self.run_cli("uninstall", "--all")
        self.assertIn("No residual candidates", output)
        self.assertIn("Other projects", output)
        self.run_cli("uninstall", "prepare-work")
        self.assertFalse(self.root.parent.exists())

    def test_normal_uninstall_reports_no_residues(self):
        self.run_cli("install", "--all")
        output = self.run_cli("uninstall", "--all")
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIn("No residual candidates", output)
        self.assert_no_transactions()

    def test_missing_receipt_is_reported_without_deleting_manual_content(self):
        self.run_cli("install", "--all")
        (self.installed() / installer.RECEIPT).unlink()
        before = self.contents(self.installed())
        output = self.run_cli("uninstall", "--all", expected=2)
        self.assertIn("Unmanaged directory", output)
        self.assertIn(str(self.installed()), output)
        self.assertIn("NOT deleted", output)
        self.assertEqual(before, self.contents(self.installed()))
        self.assertEqual([p.name for p in self.root.iterdir()], [self.installed().name])
        self.assert_no_transactions()
        # 幂等重跑仍然报告残留，不因“无托管项”变成成功。
        self.run_cli("uninstall", "--all", expected=2)

    def test_unmanaged_and_legacy_names_are_only_candidates(self):
        self.root.mkdir(parents=True)
        for name in ("forge-steward-custom", *installer.LEGACY_NAMES, "other-skill"):
            directory = self.root / name
            directory.mkdir()
            (directory / "notes.txt").write_text("user content", encoding="utf-8")
        before = self.contents(self.root)
        shutil.rmtree(self.source / "plugins")
        output = self.run_cli("uninstall", "--all", expected=2)
        for name in ("forge-steward-custom", *installer.LEGACY_NAMES):
            self.assertIn(str(self.root / name), output)
        self.assertIn("ownership unverified", output)
        self.assertNotIn("other-skill", output)
        self.assertEqual(before, self.contents(self.root))

    def test_named_uninstall_leaves_intentionally_installed_skills(self):
        self.run_cli("install", "--all")
        legacy = self.root / "review-and-merge"
        legacy.mkdir()
        output = self.run_cli("uninstall", "prepare-work")
        self.assertIn("No residual candidates", output)
        self.assertNotIn(str(legacy), output)
        self.assertTrue(self.installed("fix-feedback").is_dir())
        legacy = self.root / "find-work"
        legacy.mkdir()
        output = self.run_cli("uninstall", "forge-steward-find-work", expected=2)
        self.assertIn(str(legacy), output)

    def test_failed_uninstall_also_reports_all_residues_and_preserves_batch(self):
        self.run_cli("install", "--all")
        (self.installed() / installer.RECEIPT).write_text("broken", encoding="utf-8")
        legacy = self.root / "find-work"
        legacy.mkdir()
        before = self.contents(self.root)
        output = self.run_cli("uninstall", "--all", expected=1)
        self.assertIn("Residual: " + str(self.installed()), output)
        self.assertIn("Residual: " + str(legacy), output)
        self.assertIn("managed installation remains", output)
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_dangling_link_residue_is_not_followed(self):
        self.root.mkdir(parents=True)
        link = self.installed()
        self.make_link(link, self.base / "missing", True)
        output = self.run_cli("uninstall", "--all", expected=2)
        self.assertIn("link/reparse point; not followed", output)
        self.assertTrue(link.is_symlink())

    def test_user_residue_scan_does_not_cross_scopes(self):
        config = self.base / "custom-config"
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_DIR": str(config)}):
            self.run_cli("install", "prepare-work", user=True)
            manual = config / "skills/find-work"
            manual.mkdir()
            output = self.run_cli("uninstall", "--all", user=True, expected=2)
            self.assertIn(str(manual), output)
            self.assertTrue(manual.is_dir())
            output = self.run_cli("uninstall", "--all")
            self.assertIn("were NOT checked", output)
            self.assertNotIn(str(manual), output)
        self.assertFalse(self.root.parent.exists())

    def test_residue_scan_failure_is_not_reported_as_clean(self):
        self.root.mkdir(parents=True)
        with mock.patch.object(installer, "report_uninstall_residues", side_effect=PermissionError("scan denied")):
            output = self.run_cli("uninstall", "--all", expected=1)
        self.assertIn("scan denied", output)
        self.assertNotIn("No residual candidates", output)

    def test_unreadable_residue_returns_scan_failure(self):
        self.installed().mkdir(parents=True)
        with mock.patch.object(installer, "read_install", side_effect=PermissionError("entry denied")):
            output = self.run_cli("uninstall", "--all", expected=1)
        self.assertIn("scan failed: entry denied", output)
        self.assertTrue(self.installed().is_dir())

    def test_same_named_file_is_preserved_and_reported(self):
        self.root.mkdir(parents=True)
        path = self.installed()
        path.write_text("not a skill", encoding="utf-8")
        output = self.run_cli("uninstall", "--all", expected=2)
        self.assertIn(str(path), output)
        self.assertEqual(path.read_text(encoding="utf-8"), "not a skill")

    def test_uninstall_rename_failure_rolls_back_and_reports(self):
        self.run_cli("install", "--all")
        before = self.contents(self.root)
        replace = os.replace
        calls = 0

        def fail_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("uninstall rename failure")
            return replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=fail_once):
            output = self.run_cli("uninstall", "--all", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.assertEqual(output.count("managed installation remains"), 5)
        self.assert_no_transactions()

    def test_subprocess_residue_exit_code(self):
        self.installed().mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/opencode.py"), "uninstall", "--all",
             "--project", str(self.project)], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Residual:", result.stdout)
        self.assertTrue(self.installed().is_dir())

    def test_status_does_not_create_directories(self):
        self.assertIn("not installed", self.run_cli("status", "--all"))
        self.assertFalse(self.root.parent.exists())

    def test_receipt_corruption_is_preserved(self):
        self.run_cli("install", "prepare-work")
        receipt = self.installed() / installer.RECEIPT
        receipt.write_text("not json", encoding="utf-8")
        self.run_cli("uninstall", "prepare-work", expected=1)
        self.assertEqual(receipt.read_text(encoding="utf-8"), "not json")

    def test_path_traversal_and_unknown_selection(self):
        for name in ("../outside", "/absolute", "missing", "--all"):
            if name == "--all":
                self.run_cli("install", "prepare-work", name, expected=1)
            else:
                self.run_cli("install", name, expected=1)
        self.assertFalse(self.root.exists())

    def test_user_scope_respects_xdg(self):
        config = self.base / "custom-config"
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
            self.run_cli("install", "prepare-work", user=True)
            self.assertTrue((config / "opencode/skills/forge-steward-prepare-work/SKILL.md").is_file())
            self.run_cli("uninstall", "--all", user=True)
        self.assertFalse(self.root.exists())

    def test_user_scope_respects_opencode_config_dir(self):
        config = self.base / "opencode-custom"
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_DIR": str(config)}):
            self.run_cli("install", "prepare-work", user=True)
            self.assertTrue((config / "skills/forge-steward-prepare-work/SKILL.md").is_file())
            self.run_cli("uninstall", "--all", user=True)

    def test_real_opencode_discovery(self):
        executable = os.environ.get("FORGESTEWARD_OPENCODE") or shutil.which("opencode")
        if not executable:
            self.skipTest("Set FORGESTEWARD_OPENCODE to run actual OpenCode discovery")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENCODE_", "XDG_"))}
        for key, suffix in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                            ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"),
                            ("OPENCODE_TEST_HOME", "home")):
            target = self.base / ("isolated-" + suffix)
            target.mkdir()
            env[key] = str(target)
        env.update(OPENCODE_DISABLE_AUTOUPDATE="true", OPENCODE_DISABLE_MODELS_FETCH="true")
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)

        def discovered():
            # OpenCode 在 macOS 上写管道时会在 65536 字节处截断输出，改为写入临时文件再读取。
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout:
                result = subprocess.run([executable, "debug", "skill", "--pure"], cwd=self.project,
                                        env=env, stdout=stdout, stderr=subprocess.PIPE, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                stdout.seek(0)
                return {item["name"]: item for item in json.load(stdout)
                        if item["name"].startswith(installer.PREFIX)}

        self.run_cli("install", "--all")
        skills = discovered()
        self.assertEqual(set(skills), set(installer.catalog(self.source)))
        for name, item in skills.items():
            self.assertEqual(Path(item["location"]).resolve(), self.root / name / "SKILL.md")
        self.run_cli("uninstall", "--all")
        self.assertEqual(discovered(), {})
        # 同一可执行程序还须发现默认 XDG 和自定义配置目录的用户级安装。
        for custom in (None, self.base / "custom-user-config"):
            user_env = {"XDG_CONFIG_HOME": env["XDG_CONFIG_HOME"]}
            if custom:
                user_env["OPENCODE_CONFIG_DIR"] = str(custom)
                env["OPENCODE_CONFIG_DIR"] = str(custom)
            with mock.patch.dict(os.environ, user_env):
                self.run_cli("install", "prepare-work", user=True)
                items = discovered()
                self.assertEqual(set(items), {"forge-steward-prepare-work"})
                expected = (custom if custom else Path(env["XDG_CONFIG_HOME"]) / "opencode") / "skills/forge-steward-prepare-work/SKILL.md"
                self.assertEqual(Path(items["forge-steward-prepare-work"]["location"]).resolve(), expected)
                self.run_cli("uninstall", "--all", user=True)
                self.assertEqual(discovered(), {})
        # 命令失败/有残留与真实发现一致：不能把缺失收据的副本当成已卸载。
        self.run_cli("install", "prepare-work")
        (self.installed() / installer.RECEIPT).unlink()
        self.assertIn("Residual:", self.run_cli("uninstall", "--all", expected=2))
        self.assertEqual(set(discovered()), {"forge-steward-prepare-work"})

    def make_link(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest("Symlinks unavailable: " + str(error))

    def test_symlink_target_cannot_redirect_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.make_link(self.project / ".opencode", outside, True)
        self.run_cli("install", "prepare-work", expected=1)
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_cannot_redirect_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.project / ".opencode"), str(outside)],
                       check=True, capture_output=True)
        self.run_cli("install", "prepare-work", expected=1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_inside_install_is_protected(self):
        self.run_cli("install", "prepare-work")
        outside = self.base / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        self.make_link(self.installed() / "link", outside)
        self.run_cli("uninstall", "prepare-work", expected=1)
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")

    def test_symlink_source_is_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        self.make_link(self.source_skill() / "link", outside)
        self.run_cli("install", "prepare-work", expected=1)
        self.assertFalse(self.root.exists())

    def test_name_mismatch_is_rejected(self):
        skill = self.source_skill() / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace("name: forge-steward-prepare-work", "name: different"), encoding="utf-8")
        self.run_cli("install", "prepare-work", expected=1)
        self.assertFalse(self.root.exists())

    def test_lock_preserves_other_installers_work(self):
        self.root.parent.mkdir()
        lock = self.root.parent / installer.LOCK
        lock.write_text("pid=12345", encoding="utf-8")
        self.run_cli("install", "--all", expected=1)
        self.assertEqual(lock.read_text(encoding="utf-8"), "pid=12345")
        self.assertFalse(self.root.exists())

    def test_interrupted_transaction_is_not_overwritten(self):
        leftover = self.root.parent / ".forge-steward-txn-interrupted"
        leftover.mkdir(parents=True)
        (leftover / "backup.txt").write_text("keep", encoding="utf-8")
        self.assertIn("Recover the interrupted", self.run_cli("install", "--all", expected=1))
        self.assertEqual((leftover / "backup.txt").read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.root.parent / installer.LOCK).exists())

    def test_invalid_receipt_schema_reports_error(self):
        self.run_cli("install", "prepare-work")
        (self.installed() / installer.RECEIPT).write_text("[]", encoding="utf-8")
        self.assertIn("Invalid installation receipt", self.run_cli("uninstall", "prepare-work", expected=1))

    def test_status_reports_same_version_content_change(self):
        self.run_cli("install", "prepare-work")
        (self.source_skill() / "new.txt").write_text("new source", encoding="utf-8")
        self.assertIn("checkout differs", self.run_cli("status", "prepare-work"))

    def test_copy_failure_changes_no_existing_install(self):
        self.run_cli("install", "prepare-work")
        before = self.contents(self.root)
        with mock.patch.object(installer.shutil, "copytree", side_effect=OSError("disk full")):
            self.run_cli("install", "check-workflow", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_failure_mid_commit_rolls_back_entire_batch(self):
        self.run_cli("install", "--all")
        before = self.contents(self.root)
        for skill in self.source.glob("plugins/*/skills/*/SKILL.md"):
            skill.write_text(skill.read_text(encoding="utf-8") + "\nextra source content\n", encoding="utf-8")
        replace = os.replace
        calls = 0

        def fail_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("injected rename failure")
            return replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=fail_once):
            self.run_cli("update", "--all", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_interrupt_rolls_back(self):
        self.run_cli("install", "prepare-work")
        before = self.contents(self.root)
        (self.source_skill() / "new.txt").write_text("new", encoding="utf-8")
        replace = os.replace
        calls = 0

        def interrupt_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=interrupt_once):
            with self.assertRaises(KeyboardInterrupt):
                self.run_cli("update", "prepare-work")
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_failed_rollback_keeps_recovery_backup(self):
        self.run_cli("install", "prepare-work")
        before = self.contents(self.installed())
        (self.source_skill() / "new.txt").write_text("new", encoding="utf-8")
        replace = os.replace
        calls = 0

        def fail_commit_and_restore(source, destination):
            nonlocal calls
            calls += 1
            if calls in (2, 3):
                raise OSError("injected I/O failure")
            return replace(source, destination)

        with mock.patch.object(installer.os, "replace", side_effect=fail_commit_and_restore):
            self.assertIn("Rollback incomplete", self.run_cli("update", "prepare-work", expected=1))
        transaction = next(self.root.parent.glob(".forge-steward-txn-*"))
        self.assertEqual(before, self.contents(transaction / "old-forge-steward-prepare-work"))
        self.assertIn("Recover the interrupted", self.run_cli("install", "prepare-work", expected=1))


if __name__ == "__main__":
    unittest.main()
