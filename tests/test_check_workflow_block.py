"""check-workflow 标准区块同步脚本的确定性与幂等契约；不调用模型、Agent 或托管平台。"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
SCRIPT = SKILL / "scripts/sync_workflow_block.py"
BOM = b"\xef\xbb\xbf"


def block(name, language):
    body = (SKILL / "assets" / (name + "." + language + ".md")).read_text(encoding="utf-8").strip("\n")
    return "<!-- forge-steward:%s begin lang=%s -->\n%s\n<!-- forge-steward:%s end -->\n" % (
        name, language, body, name)


class WorkflowBlockTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="forgesteward-block-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def run_script(self, *arguments, expected=0, repo=None, env=None):
        # -B 避免在技能目录生成 __pycache__，否则会进入安装快照。
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo or self.root), *arguments],
                                capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def write(self, name, content):
        (self.root / name).write_bytes(content.encode("utf-8"))

    def read(self, name):
        return (self.root / name).read_bytes().decode("utf-8")

    def state(self):
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}

    def test_empty_repository_requires_language_then_converges(self):
        self.run_script("--check", expected=2)
        self.run_script("--check", "--lang", "zh-CN", expected=1)
        self.assertEqual(list(self.root.iterdir()), [])
        self.run_script("--write", "--lang", "zh-CN")
        self.assertEqual(self.read("AGENTS.md"), block("workflow", "zh-CN"))
        self.assertEqual(self.read("CLAUDE.md"), "@AGENTS.md\n")
        before = self.state()
        self.assertIn("in sync", self.run_script("--check"))
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_differing_block_is_replaced_and_outside_text_is_byte_identical(self):
        prefix, suffix = "# Project\n\nKeep  this exact text. \n\n", "\n## Later\ntrailing"
        stale = block("workflow", "zh-CN").replace("### 修复", "### 修复（本地改写）")
        self.write("AGENTS.md", prefix + stale + suffix)
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.assertIn("AGENTS.md", self.run_script("--check", expected=1))
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), prefix + block("workflow", "zh-CN") + suffix + "\n")
        self.assertEqual(self.read("CLAUDE.md"), "@AGENTS.md\n")
        self.run_script("--check")

    def test_missing_block_is_appended_after_existing_rules(self):
        self.write("AGENTS.md", "# Rules\nUse make test.\n\n\n")
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.run_script("--write", "--lang", "en")
        self.assertEqual(self.read("AGENTS.md"), "# Rules\nUse make test.\n\n" + block("workflow", "en"))
        self.run_script("--check")

    def test_claude_rules_get_import_and_pointer_until_only_import_remains(self):
        self.write("CLAUDE.md", "# Claude rules\nRun pytest.\n")
        self.run_script("--write", "--lang", "en")
        self.assertEqual(self.read("AGENTS.md"), block("workflow", "en") + "\n" + block("claude-rules", "en"))
        self.assertEqual(self.read("CLAUDE.md"), "# Claude rules\nRun pytest.\n\n@AGENTS.md\n")
        self.run_script("--check")
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.run_script("--check", expected=1)
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), block("workflow", "en"))
        self.run_script("--check")

    def test_pointer_is_inserted_between_block_and_following_rules(self):
        self.write("AGENTS.md", block("workflow", "zh-CN") + "## Tail\n")
        self.write("CLAUDE.md", "Rules\n\n@AGENTS.md\n")
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"),
                         block("workflow", "zh-CN") + "\n" + block("claude-rules", "zh-CN") + "\n## Tail\n")
        self.run_script("--check")

    def test_import_inside_code_fence_does_not_count(self):
        self.write("AGENTS.md", block("workflow", "zh-CN"))
        self.write("CLAUDE.md", "```\n@AGENTS.md\n```\n")
        self.assertIn("CLAUDE.md", self.run_script("--check", expected=1))
        self.run_script("--write")
        self.assertEqual(self.read("CLAUDE.md"), "```\n@AGENTS.md\n```\n\n@AGENTS.md\n")
        self.run_script("--check")

    def test_duplicate_blocks_collapse_to_first_position(self):
        current = block("workflow", "en")
        self.write("AGENTS.md", "A\n\n" + current + "\nB\n\n" + current + "\nC\n")
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "A\n\n" + current + "\nB\n\nC\n")
        self.run_script("--check")

    def test_malformed_markers_are_rejected_without_writing(self):
        begin = "<!-- forge-steward:workflow begin lang=zh-CN -->\n"
        for content in (begin + "x\n", begin + begin + "<!-- forge-steward:workflow end -->\n",
                        "<!-- forge-steward:workflow end -->\n"):
            with self.subTest(content=content):
                self.write("AGENTS.md", content)
                before = self.state()
                self.run_script("--write", "--lang", "zh-CN", expected=2)
                self.assertEqual(self.state(), before)

    def test_markers_inside_code_fence_are_ignored(self):
        example = "```md\n<!-- forge-steward:workflow begin lang=zh-CN -->\n```\n"
        self.write("AGENTS.md", example)
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.run_script("--write", "--lang", "zh-CN")
        self.assertEqual(self.read("AGENTS.md"), example + "\n" + block("workflow", "zh-CN"))
        self.run_script("--check")

    def test_crlf_and_bom_are_preserved(self):
        (self.root / "AGENTS.md").write_bytes(BOM + b"# Rules\r\nKeep\r\n")
        (self.root / "CLAUDE.md").write_bytes(b"@AGENTS.md\r\n")
        self.run_script("--write", "--lang", "en")
        data = (self.root / "AGENTS.md").read_bytes()
        self.assertTrue(data.startswith(BOM))
        text = data[len(BOM):].decode("utf-8")
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertEqual(text.replace("\r\n", "\n"), "# Rules\nKeep\n\n" + block("workflow", "en"))
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"@AGENTS.md\r\n")
        self.run_script("--check")

    def test_explicit_language_replaces_existing_language(self):
        self.run_script("--write", "--lang", "zh-CN")
        self.run_script("--write", "--lang", "en")
        self.assertEqual(self.read("AGENTS.md"), block("workflow", "en"))
        self.run_script("--check")

    def test_claude_symlink_to_agents_is_not_written_through(self):
        self.write("AGENTS.md", "# Rules\n")
        try:
            os.symlink("AGENTS.md", str(self.root / "CLAUDE.md"))
        except (OSError, NotImplementedError):
            self.skipTest("当前环境不能创建符号链接")
        self.run_script("--write", "--lang", "en")
        self.assertTrue((self.root / "CLAUDE.md").is_symlink())
        self.assertEqual(self.read("AGENTS.md"), "# Rules\n\n" + block("workflow", "en"))
        self.run_script("--check")

    def test_override_warning_and_legacy_output_encoding(self):
        self.run_script("--write", "--lang", "en")
        self.write("AGENTS.override.md", "override\n")
        self.assertIn("Warning: AGENTS.override.md", self.run_script("--check"))
        environment = dict(os.environ, PYTHONIOENCODING="cp1252")
        output = self.run_script("--check", repo=self.root / "缺失目录", expected=2, env=environment)
        self.assertNotIn("codec can't encode", output)

    def test_templates_share_structure_and_contain_no_markers(self):
        for name in ("workflow", "claude-rules"):
            with self.subTest(template=name):
                shapes = []
                for language in ("zh-CN", "en"):
                    text = (SKILL / "assets" / (name + "." + language + ".md")).read_text(encoding="utf-8")
                    self.assertNotIn("forge-steward:", text)
                    shapes.append([line.split(" ", 1)[0] for line in text.splitlines()
                                   if line.startswith("#") or line.lstrip().startswith("- ")])
                self.assertEqual(shapes[0], shapes[1])


if __name__ == "__main__":
    unittest.main()
