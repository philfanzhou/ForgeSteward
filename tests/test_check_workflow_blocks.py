"""Determinism and idempotence of legacy check-workflow block removal, without model, Agent, or hosting-platform calls."""

import os
from pathlib import Path
import shutil
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
        self.git("init", "-q")
        self.git("config", "user.name", "ForgeSteward Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.root), *arguments],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commit(self, message="baseline"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def run_script(self, *arguments, expected=0, repo=None, env=None):
        # -B avoids __pycache__ in the skill directory, which would enter installation snapshots.
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo or self.root), *arguments],
                                capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def write(self, name, content):
        (self.root / name).write_bytes(content.encode("utf-8"))

    def read(self, name):
        return (self.root / name).read_bytes().decode("utf-8")

    def state(self):
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir() if p.name != ".git"}

    def test_repository_without_blocks_is_untouched(self):
        self.assertIn("No forge-steward", self.run_script("--check"))
        self.write("AGENTS.md", "# Rules\n\n- one PR per issue\n")
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.commit()
        before = self.state()
        self.run_script("--check")
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_blocks_are_removed_and_outside_text_is_byte_identical(self):
        prefix, suffix = "# Project\n\nKeep  this exact text. \n\n", "\n## Later\ntrailing"
        self.write("AGENTS.md", prefix + block("workflow") + "\n" + block("claude-rules") + suffix)
        self.write("CLAUDE.md", "Rules\n\n@AGENTS.md\n")
        self.commit()
        before = self.state()
        self.assertIn("AGENTS.md", self.run_script("--check", expected=1))
        self.assertEqual(self.state(), before)
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), prefix + "## Later\ntrailing")
        self.assertEqual(self.read("CLAUDE.md"), "Rules\n\n@AGENTS.md\n")
        before = self.state()
        self.run_script("--check")
        self.run_script("--write")
        self.assertEqual(self.state(), before)

    def test_trailing_block_leaves_existing_rules_without_extra_blank_lines(self):
        self.write("AGENTS.md", "# Rules\nUse make test.\n\n" + block("workflow"))
        self.commit()
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "# Rules\nUse make test.\n")

    def test_leading_block_does_not_leave_a_blank_first_line(self):
        self.write("AGENTS.md", block("workflow") + "\n## Tail\n")
        self.commit()
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "## Tail\n")

    def test_duplicate_blocks_are_all_removed(self):
        self.write("AGENTS.md", "A\n\n" + block("workflow") + "\nB\n\n" + block("workflow") + "\nC\n")
        self.commit()
        self.run_script("--write")
        self.assertEqual(self.read("AGENTS.md"), "A\n\nB\n\nC\n")

    def test_block_only_agents_and_import_only_claude_are_deleted(self):
        self.write("AGENTS.md", block("workflow"))
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.commit()
        output = self.run_script("--check", expected=1)
        self.assertIn("AGENTS.md: delete file", output)
        self.assertIn("CLAUDE.md: delete file", output)
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertEqual({path.name for path in self.root.iterdir()}, {".git"})

    def test_claude_with_other_rules_keeps_them_when_agents_is_deleted(self):
        self.write("AGENTS.md", block("workflow") + "\n" + block("claude-rules"))
        self.write("CLAUDE.md", "# Claude rules\nRun pytest.\n\n@AGENTS.md\n```\n@AGENTS.md\n```\n")
        self.commit()
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(self.read("CLAUDE.md"), "# Claude rules\nRun pytest.\n\n```\n@AGENTS.md\n```\n")
        self.run_script("--check")

    def test_markers_inside_code_fence_are_ignored(self):
        example = "```md\n<!-- forge-steward:workflow begin lang=zh-CN -->\n```\n"
        self.write("AGENTS.md", example)
        self.commit()
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
        self.commit()
        self.run_script("--write")
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), BOM + prefix + b"Tail\r\nLast")
        self.run_script("--check")

    def test_symlinked_agents_is_refused_without_writing(self):
        self.write("RULES.md", block("workflow"))
        try:
            os.symlink("RULES.md", str(self.root / "AGENTS.md"))
        except (OSError, NotImplementedError):
            self.skipTest("This environment cannot create symlinks")
        output = self.run_script("--write", expected=2)
        self.assertNotIn("No forge-steward", output)
        self.assertEqual(self.read("RULES.md"), block("workflow"))
        self.assertTrue((self.root / "AGENTS.md").is_symlink())

    def test_symlinked_claude_is_refused_without_changes(self):
        self.write("RULES.md", "# Rules\n")
        try:
            os.symlink("RULES.md", str(self.root / "CLAUDE.md"))
        except (OSError, NotImplementedError):
            self.skipTest("This environment cannot create symlinks")
        self.run_script("--check", expected=2)
        self.run_script("--write", expected=2)
        self.assertEqual(self.read("RULES.md"), "# Rules\n")

    def test_symlinked_claude_blocks_agents_deletion(self):
        self.write("AGENTS.md", block("workflow"))
        self.commit()
        self.write("RULES.md", "# Rules\n")
        try:
            os.symlink("RULES.md", str(self.root / "CLAUDE.md"))
        except (OSError, NotImplementedError):
            self.skipTest("This environment cannot create symlinks")
        self.run_script("--write", expected=2)
        self.assertEqual(self.read("AGENTS.md"), block("workflow"))
        self.assertEqual(self.read("RULES.md"), "# Rules\n")
        self.assertTrue((self.root / "CLAUDE.md").is_symlink())

    def test_dangling_import_removal_preserves_blank_runs_and_trailing_blanks(self):
        self.write("AGENTS.md", block("workflow"))
        self.write("CLAUDE.md", "# Claude\n\n\n\n@AGENTS.md\n\n\n")
        self.commit()
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"# Claude\n\n\n\n\n\n")

    def test_single_blank_on_each_side_loses_one_blank_with_the_import(self):
        self.write("AGENTS.md", block("workflow"))
        self.write("CLAUDE.md", "# C\n\n@AGENTS.md\n\n# T\n")
        self.commit()
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"# C\n\n# T\n")

    def test_dangling_import_removal_preserves_bom_and_crlf(self):
        self.write("AGENTS.md", block("workflow"))
        (self.root / "CLAUDE.md").write_bytes(BOM + b"# C\r\n\r\n@AGENTS.md\r\n\r\n")
        self.commit()
        self.run_script("--write")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), BOM + b"# C\r\n\r\n")

    def test_untracked_agents_is_reported_unsafe_and_kept(self):
        content = block("workflow")
        self.write("AGENTS.md", content)
        output = self.run_script("--check", expected=2)
        self.assertNotIn("Needs change", output)
        self.run_script("--write", expected=2)
        self.assertEqual(self.read("AGENTS.md"), content)

    def test_modified_claude_is_reported_unsafe_and_changes_neither_file(self):
        agents = block("workflow")
        self.write("AGENTS.md", agents)
        self.write("CLAUDE.md", "Rules\n\n@AGENTS.md\n")
        self.commit()
        self.write("CLAUDE.md", "Rules changed by the user\n\n@AGENTS.md\n")
        before = self.state()
        self.run_script("--write", expected=2)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.read("AGENTS.md"), agents)

    def test_staged_change_is_not_clean(self):
        agents = block("workflow")
        self.write("AGENTS.md", agents)
        self.write("CLAUDE.md", "Rules\n\n@AGENTS.md\n")
        self.commit()
        self.write("CLAUDE.md", "Staged rules\n\n@AGENTS.md\n")
        self.git("add", "CLAUDE.md")
        before = self.state()
        self.run_script("--write", expected=2)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.read("AGENTS.md"), agents)

    def test_no_git_worktree_is_refused_without_writing(self):
        directory = tempfile.TemporaryDirectory(prefix="forgesteward-nogit-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        content = block("workflow")
        (root / "AGENTS.md").write_bytes(content.encode("utf-8"))
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, text=True, timeout=30)
        if probe.returncode == 0:
            self.skipTest("The temporary directory is inside a Git worktree")
        self.run_script("--check", expected=2, repo=root)
        self.run_script("--write", expected=2, repo=root)
        self.assertEqual((root / "AGENTS.md").read_bytes(), content.encode("utf-8"))

    def test_git_unavailable_is_refused_without_writing(self):
        content = block("workflow")
        self.write("AGENTS.md", content)
        self.commit()
        directory = tempfile.TemporaryDirectory(prefix="forgesteward-path-")
        self.addCleanup(directory.cleanup)
        environment = dict(os.environ, PATH=str(Path(directory.name)))
        if shutil.which("git", path=environment["PATH"]):
            self.skipTest("Git is resolvable without the normal PATH")
        self.run_script("--write", expected=2, env=environment)
        self.assertEqual(self.read("AGENTS.md"), content)

    def test_override_warning_and_legacy_output_encoding(self):
        self.write("AGENTS.override.md", "override\n")
        self.assertIn("Warning: AGENTS.override.md", self.run_script("--check"))
        environment = dict(os.environ, PYTHONIOENCODING="cp1252")
        # CJK path code points preserve non-ASCII error-output coverage.
        output = self.run_script("--check", repo=self.root / "".join(map(chr, (0x7F3A, 0x5931, 0x76EE, 0x5F55))), expected=2, env=environment)
        self.assertNotIn("codec can't encode", output)


if __name__ == "__main__":
    unittest.main()
