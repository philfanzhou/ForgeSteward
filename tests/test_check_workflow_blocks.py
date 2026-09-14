"""check-workflow 旧版区块删除脚本的确定性与幂等契约；不调用模型、Agent 或托管平台。"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
SCRIPT = SKILL / "scripts/remove_workflow_blocks.py"
BOM = b"\xef\xbb\xbf"


def block(name, body="## ForgeSteward\n\n- rule\n"):
    return "<!-- forge-steward:%s begin lang=zh-CN -->\n%s<!-- forge-steward:%s end -->\n" % (name, body, name)


class RemoveWorkflowBlocksTests(unittest.TestCase):
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

    def test_repository_without_blocks_is_untouched(self):
        self.assertIn("No forge-steward", self.run_script("--check"))
        self.write("AGENTS.md", "# Rules\n\n- one PR per issue\n")
        self.write("CLAUDE.md", "@AGENTS.md\n")
        before = self.state()
        self.run_script("--check")
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_blocks_are_removed_and_outside_text_is_byte_identical(self):
        prefix, suffix = "# Project\n\nKeep  this exact text. \n\n", "\n## Later\ntrailing"
        self.write("AGENTS.md", prefix + block("workflow") + "\n" + block("claude-rules") + suffix)
        self.write("CLAUDE.md", "Rules\n\n@AGENTS.md\n")
        self.assertIn("AGENTS.md", self.run_script("--check", expected=1))
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), prefix + "## Later\ntrailing")
        self.assertEqual(self.read("CLAUDE.md"), "Rules\n\n@AGENTS.md\n")
        before = self.state()
        self.run_script("--check")
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_trailing_block_leaves_existing_rules_without_extra_blank_lines(self):
        self.write("AGENTS.md", "# Rules\nUse make test.\n\n" + block("workflow"))
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "# Rules\nUse make test.\n")

    def test_leading_block_does_not_leave_a_blank_first_line(self):
        self.write("AGENTS.md", block("workflow") + "\n## Tail\n")
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "## Tail\n")

    def test_duplicate_blocks_are_all_removed(self):
        self.write("AGENTS.md", "A\n\n" + block("workflow") + "\nB\n\n" + block("workflow") + "\nC\n")
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "A\n\nB\n\nC\n")

    def test_block_only_agents_and_import_only_claude_are_deleted(self):
        self.write("AGENTS.md", block("workflow"))
        self.write("CLAUDE.md", "@AGENTS.md\n")
        output = self.run_script("--check", expected=1)
        self.assertIn("AGENTS.md: delete file", output)
        self.assertIn("CLAUDE.md: delete file", output)
        self.run_script("--write")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_claude_with_other_rules_keeps_them_when_agents_is_deleted(self):
        self.write("AGENTS.md", block("workflow") + "\n" + block("claude-rules"))
        self.write("CLAUDE.md", "# Claude rules\nRun pytest.\n\n@AGENTS.md\n```\n@AGENTS.md\n```\n")
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(self.read("CLAUDE.md"), "# Claude rules\nRun pytest.\n\n```\n@AGENTS.md\n```\n")
        self.run_script("--check")

    def test_markers_inside_code_fence_are_ignored(self):
        example = "```md\n<!-- forge-steward:workflow begin lang=zh-CN -->\n```\n"
        self.write("AGENTS.md", example)
        before = self.state()
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_malformed_markers_are_rejected_without_writing(self):
        begin = "<!-- forge-steward:workflow begin lang=zh-CN -->\n"
        for content in (begin + "x\n", begin + begin + "<!-- forge-steward:workflow end -->\n",
                        "<!-- forge-steward:workflow end -->\n"):
            with self.subTest(content=content):
                self.write("AGENTS.md", content)
                before = self.state()
                self.run_script("--write", expected=2)
                self.assertEqual(self.state(), before)

    def test_unclosed_code_fence_is_rejected_without_writing(self):
        self.write("AGENTS.md", block("workflow") + "Rules\n```sh\nmake test\n")
        before = self.state()
        self.assertIn("AGENTS.md: Unclosed code fence", self.run_script("--write", expected=2))
        self.assertEqual(self.state(), before)

    def test_crlf_mixed_endings_and_bom_are_preserved(self):
        prefix, suffix = b"# Rules\r\nLF line\n\r\n", b"\r\nTail\r\nLast"
        body = block("workflow").encode("utf-8").replace(b"\n", b"\r\n")
        (self.root / "AGENTS.md").write_bytes(BOM + prefix + body + suffix)
        self.run_script("--write")
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), BOM + prefix + b"Tail\r\nLast")
        self.run_script("--check")

    def test_symlinked_agents_is_not_managed(self):
        self.write("RULES.md", block("workflow"))
        try:
            os.symlink("RULES.md", str(self.root / "AGENTS.md"))
        except (OSError, NotImplementedError):
            self.skipTest("当前环境不能创建符号链接")
        self.run_script("--write")
        self.assertEqual(self.read("RULES.md"), block("workflow"))

    def test_override_warning_and_legacy_output_encoding(self):
        self.write("AGENTS.override.md", "override\n")
        self.assertIn("Warning: AGENTS.override.md", self.run_script("--check"))
        environment = dict(os.environ, PYTHONIOENCODING="cp1252")
        output = self.run_script("--check", repo=self.root / "缺失目录", expected=2, env=environment)
        self.assertNotIn("codec can't encode", output)


if __name__ == "__main__":
    unittest.main()
