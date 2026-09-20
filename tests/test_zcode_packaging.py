"""ZCode 共用清单契约与可选的真实 CLI 发现；不进行模型调用。"""

import importlib.util
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sync_marketplace", REPO / "scripts/sync_marketplace.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class ZCodePackagingTests(unittest.TestCase):
    def test_marketplace_versions_are_derived_from_manifests(self):
        actual = json.loads((REPO / SYNC.MARKETPLACE).read_text(encoding="utf-8"))
        self.assertEqual(actual, SYNC.expected_marketplace(REPO))

    def test_flat_skills_and_portable_frontmatter(self):
        for plugin in sorted((REPO / "plugins").iterdir()):
            if not plugin.is_dir():
                continue
            with self.subTest(plugin=plugin.name):
                manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
                self.assertRegex(manifest["name"], r"^[a-z0-9][a-z0-9._-]{0,127}$")
                self.assertEqual(manifest["skills"], "./skills/")
                flat = list((plugin / "skills").glob("*/SKILL.md"))
                self.assertEqual(len(flat), 1)
                self.assertEqual(set(flat), set((plugin / "skills").rglob("SKILL.md")))
                skill = flat[0]
                content = skill.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"))
                _, frontmatter, body = content.split("---", 2)
                # 本仓库采用顶层单行标量；不把此检查宣传为通用 YAML 解析器。
                name = re.findall(r"^name: (.+)$", frontmatter, re.MULTILINE)
                description = re.findall(r"^description: (.+)$", frontmatter, re.MULTILINE)
                self.assertEqual(name, [skill.parent.name])
                self.assertEqual(len(description), 1)
                # 长度与 Unicode 单位统一由 check_skill_limits.py 及其测试维护。
                for reference in re.findall(r"\]\((references/[^)#]+)(?:#[^)]*)?\)", content):
                    target = (skill.parent / reference).resolve()
                    self.assertIn(skill.parent.resolve(), target.parents)
                    self.assertTrue(target.is_file(), reference)

    def fixture(self, root):
        shutil.copytree(REPO / "plugins", root / "plugins")
        shutil.copytree(REPO / ".claude-plugin", root / ".claude-plugin")
        shutil.copyfile(REPO / "VERSION", root / "VERSION")

    def test_sync_repairs_versions_preserves_metadata_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-") as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / SYNC.MARKETPLACE
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["plugins"][0].pop("version")
            catalog["plugins"][1]["version"] = "0.0.0"
            catalog["plugins"][0]["tags"] = ["preserve-me"]
            path.write_text(json.dumps(catalog), encoding="utf-8")
            expected = SYNC.expected_marketplace(root)
            self.assertEqual(expected["plugins"][0]["tags"], ["preserve-me"])
            for before, after in zip(catalog["plugins"], expected["plugins"]):
                self.assertEqual({k: v for k, v in before.items() if k != "version"},
                                 {k: v for k, v in after.items() if k != "version"})
            path.write_text(json.dumps(expected), encoding="utf-8")
            self.assertEqual(expected, SYNC.expected_marketplace(root))

    def test_sync_rejects_incomplete_duplicate_and_external_sources(self):
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-") as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / SYNC.MARKETPLACE
            original = path.read_text(encoding="utf-8")
            for defect in ("missing", "duplicate", "external"):
                with self.subTest(defect=defect):
                    catalog = json.loads(original)
                    if defect == "missing":
                        catalog["plugins"].pop()
                    elif defect == "duplicate":
                        catalog["plugins"].append(catalog["plugins"][0])
                    else:
                        catalog["plugins"][0]["source"] = "../external"
                    path.write_text(json.dumps(catalog), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        SYNC.expected_marketplace(root)

    def test_sync_refuses_to_hide_plugin_version_drift(self):
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-") as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "plugins/check-workflow/.claude-plugin/plugin.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["version"] = "0.0.0"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                SYNC.expected_marketplace(root)

    def test_command_check_is_read_only_and_write_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-") as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / SYNC.MARKETPLACE
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["plugins"][0].pop("version")
            path.write_text(json.dumps(catalog), encoding="utf-8")
            before = path.read_bytes()
            with patch.object(SYNC, "REPO", root), redirect_stdout(io.StringIO()):
                with patch("sys.argv", ["sync_marketplace.py", "--check"]):
                    self.assertEqual(SYNC.main(), 1)
                    self.assertEqual(path.read_bytes(), before)
                with patch("sys.argv", ["sync_marketplace.py", "--write"]):
                    self.assertEqual(SYNC.main(), 0)
                    written = path.read_bytes()
                    modified_at = path.stat().st_mtime_ns
                    self.assertEqual(SYNC.main(), 0)
                    self.assertEqual(path.read_bytes(), written)
                    self.assertEqual(path.stat().st_mtime_ns, modified_at)
                with patch("sys.argv", ["sync_marketplace.py", "--check"]):
                    self.assertEqual(SYNC.main(), 0)

    def test_cli_supports_non_utf8_redirected_output(self):
        import sys
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-") as directory:
            root = Path(directory)
            self.fixture(root)
            script = root / "scripts/sync_marketplace.py"
            script.parent.mkdir()
            shutil.copyfile(REPO / "scripts/sync_marketplace.py", script)
            path = root / SYNC.MARKETPLACE
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["plugins"][0].pop("version")
            path.write_text(json.dumps(catalog), encoding="utf-8")
            environment = dict(os.environ, PYTHONIOENCODING="cp1252")
            for argument, expected in (("--help", 0), ("--check", 1), ("--write", 0), ("--check", 0)):
                with self.subTest(argument=argument, expected=expected):
                    result = subprocess.run([sys.executable, str(script), argument], env=environment,
                                            capture_output=True, encoding="cp1252", timeout=30)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertNotIn("codec can't encode", result.stderr)


@unittest.skipUnless(os.environ.get("FORGESTEWARD_ZCODE_CLI"), "未指定 ZCode CLI；不代表真实发现已通过")
class ZCodeRuntimeTests(unittest.TestCase):
    def test_documented_loader_boundaries_in_temporary_skill(self):
        cli = Path(os.environ["FORGESTEWARD_ZCODE_CLI"]).resolve()
        node = shutil.which("node")
        self.assertIsNotNone(node)
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-limits-") as directory:
            root = Path(directory).resolve()
            name = "forgesteward-size-probe"
            skill = root / ".agents/skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True)

            def run(*arguments):
                # 大体积探针写入文件，避免 Node 管道退出时丢失 stdout 尾部。
                with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
                    result = subprocess.run([node, str(cli), *arguments, "--cwd", str(root), "--json"],
                                            cwd=root, stdout=output, stderr=subprocess.PIPE, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output.seek(0)
                    return json.load(output)

            # 已核对的 CLI 按整个文件的十进制字节数截断，包含 frontmatter。
            prefix = f"---\nname: {name}\ndescription: Boundary probe\n---\n".encode()
            for size in (100_000, 100_001):
                skill.write_bytes(prefix + b"x" * (size - len(prefix)))
                loaded = run("skills", "inspect", name)["skill"]
                self.assertEqual(loaded["sizeBytes"], size)
                self.assertEqual(loaded["bytesRead"], min(size, 100_000))
                self.assertEqual(loaded["truncated"], size > 100_000)
            for count in (512, 513):
                skill.write_text(f"---\nname: {name}\ndescription: {'😀' * count}\n---\nProbe\n", encoding="utf-8")
                listed = run("skills", "list")
                found = [item for item in listed["skills"] if Path(item["path"]).resolve() == skill]
                self.assertEqual(len(found), 1 if count == 512 else 0)

    def test_bundled_cli_discovers_and_reads_relocated_plugins(self):
        cli = Path(os.environ["FORGESTEWARD_ZCODE_CLI"]).resolve()
        self.assertTrue(cli.is_file())
        node = shutil.which("node")
        self.assertIsNotNone(node, "ZCode bundled CLI 需要 Node.js")
        with tempfile.TemporaryDirectory(prefix="forgesteward-zcode-runtime-") as directory:
            root = Path(directory).resolve()
            shutil.copytree(REPO / "plugins", root / "plugins")
            configuration = root / ".zcode/config.json"
            configuration.parent.mkdir()
            plugins = sorted(p for p in (root / "plugins").iterdir() if p.is_dir())
            configuration.write_text(json.dumps({"plugins": {
                "enabled": True,
                "dirs": [str(p) for p in plugins],
                "enabledPlugins": {p.name + "@inline": True for p in plugins},
            }}), encoding="utf-8")

            def run(*arguments):
                result = subprocess.run([node, str(cli), *arguments, "--cwd", str(root), "--json"],
                                        cwd=root, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            installed = run("plugins", "list")
            # 0.16.9 直接返回列表，0.16.5 返回含 plugins 的对象。
            installed_plugins = installed if isinstance(installed, list) else installed["plugins"]
            actual = {item["name"]: item for item in installed_plugins
                      if root in Path(item["rootPath"]).resolve().parents}
            self.assertEqual(set(actual), {p.name for p in plugins})
            version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
            for item in actual.values():
                self.assertTrue(item["enabled"])
                self.assertEqual(item["version"], version)
                self.assertEqual(Path(item["manifestPath"]).parent.name, ".claude-plugin")
            listed = run("skills", "list")
            # 不改 HOME 或用户配置；仅断言本次临时目录的项目插件，不输出其他技能。
            found = {item["name"]: item for item in listed["skills"]
                     if root in Path(item["path"]).resolve().parents}
            self.assertEqual(set(found), {"forge-steward-" + p.name for p in plugins})
            for name, item in found.items():
                with self.subTest(skill=name):
                    inspected = run("skills", "inspect", item.get("qualifiedName", name))["skill"]
                    self.assertEqual(Path(inspected["metadata"]["path"]).resolve(), Path(item["path"]).resolve())
                    self.assertFalse(inspected["truncated"])
                    source = Path(item["path"])
                    expected = source.read_text(encoding="utf-8").split("---", 2)[2].strip()
                    self.assertEqual(inspected["content"], expected)
                    self.assertEqual(inspected["sizeBytes"], source.stat().st_size)
                    for reference in (source.parent / "references").rglob("*.md"):
                        self.assertTrue((Path(inspected["baseDirectory"]) / reference.relative_to(source.parent)).is_file())
            configuration.write_text(json.dumps({"plugins": {"enabled": False}}), encoding="utf-8")
            disabled = run("skills", "list")
            self.assertFalse(any(root in Path(item["path"]).resolve().parents for item in disabled["skills"]))
