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

    def installed(self, name="find-work"):
        return self.root / (installer.PREFIX + name)

    def source_skill(self, name="find-work"):
        return self.source / "plugins" / name / "skills" / (installer.PREFIX + name)

    def contents(self, directory):
        return {p.relative_to(directory).as_posix(): p.read_bytes()
                for p in directory.rglob("*") if p.is_file()}

    def assert_no_transactions(self):
        self.assertFalse(list(self.root.parent.glob(".forge-steward-*")))

    def test_list_and_subprocess_help(self):
        self.assertEqual(self.run_cli("list").count("0.2.0"), 4)
        result = subprocess.run([sys.executable, str(REPO / "scripts/opencode.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("uninstall", result.stdout)

    def test_single_install_and_full_name(self):
        self.run_cli("install", "forge-steward-find-work")
        self.assertEqual([p.name for p in self.root.iterdir()], ["forge-steward-find-work"])
        self.assertEqual((self.installed() / "SKILL.md").read_bytes(), (self.source_skill() / "SKILL.md").read_bytes())
        receipt = json.loads((self.installed() / installer.RECEIPT).read_text())
        self.assertEqual(receipt["files"], installer.snapshot(self.source_skill()))

    def test_install_all_has_matching_frontmatter_and_resources(self):
        self.run_cli("install", "--all")
        self.assertEqual(len(list(self.root.iterdir())), 4)
        for path in self.root.iterdir():
            self.assertIn("name: " + path.name + "\n", (path / "SKILL.md").read_text())
        self.assertTrue((self.installed("check-workflow") / "references/agent-entrypoints.md").is_file())
        self.assert_no_transactions()

    def test_repeat_install_is_byte_and_mtime_identical(self):
        self.run_cli("install", "find-work")
        before = self.contents(self.root)
        mtime = (self.installed() / installer.RECEIPT).stat().st_mtime_ns
        self.assertIn("Already installed", self.run_cli("install", "find-work"))
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
        self.run_cli("install", "find-work")
        extra = self.installed() / "notes.txt"
        extra.write_text("keep", encoding="utf-8")
        self.run_cli("uninstall", "find-work", expected=1)
        extra.unlink()
        extra.mkdir()
        self.run_cli("uninstall", "find-work", expected=1)
        extra.rmdir()
        (self.installed() / "SKILL.md").unlink()
        self.run_cli("update", "find-work", expected=1)

    def test_unmanaged_collision_prevents_partial_batch(self):
        self.installed("review-and-merge").mkdir(parents=True)
        (self.installed("review-and-merge") / "mine.txt").write_text("keep", encoding="utf-8")
        self.run_cli("install", "--all", expected=1)
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.assert_no_transactions()

    def test_explicit_update_replaces_content_and_removes_obsolete_files(self):
        obsolete = self.source_skill() / "obsolete.txt"
        obsolete.write_text("old", encoding="utf-8")
        self.run_cli("install", "find-work")
        obsolete.unlink()
        new = self.source_skill() / "new.txt"
        new.write_text("new", encoding="utf-8")
        manifest_path = self.source / "plugins/find-work/plugin.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = "0.3.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.run_cli("install", "find-work", expected=1)
        self.assertIn("0.2.0 -> 0.3.0", self.run_cli("update", "find-work"))
        self.assertFalse((self.installed() / "obsolete.txt").exists())
        self.assertEqual((self.installed() / "new.txt").read_text(), "new")
        self.assertIn("installed 0.3.0", self.run_cli("status", "find-work"))

    def test_update_missing_requires_install(self):
        self.assertIn("use install first", self.run_cli("update", "find-work", expected=1))

    def test_uninstall_keeps_unrelated_skills_and_no_receipts(self):
        self.run_cli("install", "--all")
        unrelated = self.root / "other-skill"
        unrelated.mkdir()
        (unrelated / "notes.txt").write_text("keep", encoding="utf-8")
        self.run_cli("uninstall", "find-work")
        self.assertFalse(self.installed().exists())
        self.run_cli("uninstall", "--all")
        self.assertEqual(self.contents(self.root), {"other-skill/notes.txt": b"keep"})
        self.assert_no_transactions()

    def test_uninstall_does_not_need_original_source(self):
        self.run_cli("install", "find-work")
        shutil.rmtree(self.source / "plugins")
        self.run_cli("uninstall", "--all")
        self.assertFalse(self.installed().exists())

    def test_missing_uninstall_is_idempotent_and_read_only(self):
        self.run_cli("uninstall", "--all")
        self.run_cli("uninstall", "find-work")
        self.assertFalse(self.root.parent.exists())

    def test_status_does_not_create_directories(self):
        self.assertIn("not installed", self.run_cli("status", "--all"))
        self.assertFalse(self.root.parent.exists())

    def test_receipt_corruption_is_preserved(self):
        self.run_cli("install", "find-work")
        receipt = self.installed() / installer.RECEIPT
        receipt.write_text("not json", encoding="utf-8")
        self.run_cli("uninstall", "find-work", expected=1)
        self.assertEqual(receipt.read_text(), "not json")

    def test_path_traversal_and_unknown_selection(self):
        for name in ("../outside", "/absolute", "missing", "--all"):
            if name == "--all":
                self.run_cli("install", "find-work", name, expected=1)
            else:
                self.run_cli("install", name, expected=1)
        self.assertFalse(self.root.exists())

    def test_user_scope_respects_xdg(self):
        config = self.base / "custom-config"
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
            self.run_cli("install", "find-work", user=True)
            self.assertTrue((config / "opencode/skills/forge-steward-find-work/SKILL.md").is_file())
            self.run_cli("uninstall", "--all", user=True)
        self.assertFalse(self.root.exists())

    def test_user_scope_respects_opencode_config_dir(self):
        config = self.base / "opencode-custom"
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_DIR": str(config)}):
            self.run_cli("install", "find-work", user=True)
            self.assertTrue((config / "skills/forge-steward-find-work/SKILL.md").is_file())
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
            result = subprocess.run([executable, "debug", "skill", "--pure"], cwd=self.project,
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            return {item["name"]: item for item in json.loads(result.stdout)
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
                self.run_cli("install", "find-work", user=True)
                items = discovered()
                self.assertEqual(set(items), {"forge-steward-find-work"})
                expected = (custom if custom else Path(env["XDG_CONFIG_HOME"]) / "opencode") / "skills/forge-steward-find-work/SKILL.md"
                self.assertEqual(Path(items["forge-steward-find-work"]["location"]).resolve(), expected)
                self.run_cli("uninstall", "--all", user=True)
                self.assertEqual(discovered(), {})

    def make_link(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest("Symlinks unavailable: " + str(error))

    def test_symlink_target_cannot_redirect_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.make_link(self.project / ".opencode", outside, True)
        self.run_cli("install", "find-work", expected=1)
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_cannot_redirect_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.project / ".opencode"), str(outside)],
                       check=True, capture_output=True)
        self.run_cli("install", "find-work", expected=1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_inside_install_is_protected(self):
        self.run_cli("install", "find-work")
        outside = self.base / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        self.make_link(self.installed() / "link", outside)
        self.run_cli("uninstall", "find-work", expected=1)
        self.assertEqual(outside.read_text(), "keep")

    def test_symlink_source_is_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        self.make_link(self.source_skill() / "link", outside)
        self.run_cli("install", "find-work", expected=1)
        self.assertFalse(self.root.exists())

    def test_name_mismatch_is_rejected(self):
        skill = self.source_skill() / "SKILL.md"
        skill.write_text(skill.read_text().replace("name: forge-steward-find-work", "name: different"), encoding="utf-8")
        self.run_cli("install", "find-work", expected=1)
        self.assertFalse(self.root.exists())

    def test_lock_preserves_other_installers_work(self):
        self.root.parent.mkdir()
        lock = self.root.parent / installer.LOCK
        lock.write_text("pid=12345", encoding="utf-8")
        self.run_cli("install", "--all", expected=1)
        self.assertEqual(lock.read_text(), "pid=12345")
        self.assertFalse(self.root.exists())

    def test_interrupted_transaction_is_not_overwritten(self):
        leftover = self.root.parent / ".forge-steward-txn-interrupted"
        leftover.mkdir(parents=True)
        (leftover / "backup.txt").write_text("keep", encoding="utf-8")
        self.assertIn("Recover the interrupted", self.run_cli("install", "--all", expected=1))
        self.assertEqual((leftover / "backup.txt").read_text(), "keep")
        self.assertFalse((self.root.parent / installer.LOCK).exists())

    def test_invalid_receipt_schema_reports_error(self):
        self.run_cli("install", "find-work")
        (self.installed() / installer.RECEIPT).write_text("[]", encoding="utf-8")
        self.assertIn("Invalid installation receipt", self.run_cli("uninstall", "find-work", expected=1))

    def test_status_reports_same_version_content_change(self):
        self.run_cli("install", "find-work")
        (self.source_skill() / "new.txt").write_text("new source", encoding="utf-8")
        self.assertIn("checkout differs", self.run_cli("status", "find-work"))

    def test_copy_failure_changes_no_existing_install(self):
        self.run_cli("install", "find-work")
        before = self.contents(self.root)
        with mock.patch.object(installer.shutil, "copytree", side_effect=OSError("disk full")):
            self.run_cli("install", "check-workflow", expected=1)
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_failure_mid_commit_rolls_back_entire_batch(self):
        self.run_cli("install", "--all")
        before = self.contents(self.root)
        for skill in self.source.glob("plugins/*/skills/*/SKILL.md"):
            skill.write_text(skill.read_text() + "\nextra source content\n", encoding="utf-8")
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
        self.run_cli("install", "find-work")
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
                self.run_cli("update", "find-work")
        self.assertEqual(before, self.contents(self.root))
        self.assert_no_transactions()

    def test_failed_rollback_keeps_recovery_backup(self):
        self.run_cli("install", "find-work")
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
            self.assertIn("Rollback incomplete", self.run_cli("update", "find-work", expected=1))
        transaction = next(self.root.parent.glob(".forge-steward-txn-*"))
        self.assertEqual(before, self.contents(transaction / "old-forge-steward-find-work"))
        self.assertIn("Recover the interrupted", self.run_cli("install", "find-work", expected=1))


if __name__ == "__main__":
    unittest.main()
