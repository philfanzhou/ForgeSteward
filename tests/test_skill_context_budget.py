"""校验跨 Agent 预算、Unicode 边界、资源完整性与实际命令退出状态。"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/check_skill_limits.py"
SPEC = importlib.util.spec_from_file_location("skill_limits", SCRIPT)
LIMITS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIMITS)


class SkillContextBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.skill = self.repo / "plugins/example/skills/example"
        self.skill.mkdir(parents=True)
        self.entry = self.skill / "SKILL.md"
        self.write_skill()

    def write_skill(self, description="Example skill", body="# Instructions\n"):
        self.entry.write_text(f"---\nname: example\ndescription: {description}\n---\n\n{body}", encoding="utf-8")

    def errors(self):
        return LIMITS.check_repository(self.repo)[1]

    def test_repository_satisfies_shared_policy(self):
        rows, errors, _ = LIMITS.check_repository(REPO)
        self.assertTrue(rows)
        self.assertEqual(errors, [])

    def test_entry_byte_boundary_includes_frontmatter_and_multibyte_text(self):
        self.write_skill(body="中\n")
        raw = self.entry.read_bytes()
        raw += b"x" * (LIMITS.ENTRYPOINT_BYTES - len(raw))
        self.entry.write_bytes(raw)
        self.assertEqual(self.errors(), [])
        self.entry.write_bytes(raw + b"x")
        self.assertTrue(any("6001 UTF-8 bytes > 6000" in error for error in self.errors()))

    def test_crlf_bytes_are_not_normalized_before_counting(self):
        self.write_skill(body="x\n" * 100)
        raw = self.entry.read_bytes()
        raw += b"x" * (LIMITS.ENTRYPOINT_BYTES - len(raw))
        self.entry.write_bytes(raw.replace(b"\n", b"\r\n"))
        self.assertTrue(any("UTF-8 bytes >" in error for error in self.errors()))

    def test_short_bytes_do_not_bypass_line_budget(self):
        raw = self.entry.read_bytes()
        raw += b"\n" * (LIMITS.ENTRYPOINT_LINES - len(raw.splitlines()))
        self.entry.write_bytes(raw)
        self.assertEqual(self.errors(), [])
        self.entry.write_bytes(raw + b"\n")
        self.assertTrue(any("500 lines > 499" in error for error in self.errors()))

    def test_description_counts_javascript_utf16_units(self):
        for valid, invalid in (("a" * 1024, "a" * 1025), ("中" * 1024, "中" * 1025),
                               ("😀" * 512, "😀" * 513)):
            with self.subTest(character=valid[0]):
                self.write_skill(description=valid)
                self.assertEqual(self.errors(), [])
                self.write_skill(description=invalid)
                self.assertTrue(any("description" in error and "UTF-16 units >" in error
                                    for error in self.errors()))

    def test_unsupported_frontmatter_cannot_hide_long_description(self):
        for description in ("", ">\n  long text", "|\n  long text", '"quoted"',
                            "short\n  continuation", "*alias", "text # comment"):
            with self.subTest(description=description):
                self.write_skill(description=description)
                self.assertTrue(self.errors())
        self.write_skill()
        self.entry.write_text(self.entry.read_text().replace("description:", "description: duplicate\ndescription:"))
        self.assertTrue(self.errors())

    def test_names_must_match_portable_format_and_directory(self):
        for name in ("other", "bad--name", "UPPER", "x" * 65):
            self.write_skill()
            self.entry.write_text(self.entry.read_text().replace("name: example", "name: " + name))
            self.assertTrue(self.errors())

    def reference(self, body="Rules\n"):
        self.write_skill(body="Read [rules](references/rules.md) before acting.\n")
        reference = self.skill / "references/rules.md"
        reference.parent.mkdir(exist_ok=True)
        reference.write_text(body, encoding="utf-8")
        return reference

    def test_reference_has_separate_byte_and_line_budgets(self):
        reference = self.reference("x" * LIMITS.REFERENCE_BYTES)
        self.assertEqual(self.errors(), [])
        reference.write_text("x" * (LIMITS.REFERENCE_BYTES + 1))
        self.assertTrue(any("8001 UTF-8 bytes > 8000" in error for error in self.errors()))
        reference.write_text("x\n" * LIMITS.REFERENCE_LINES)
        self.assertEqual(self.errors(), [])
        reference.write_text("x\n" * (LIMITS.REFERENCE_LINES + 1))
        self.assertTrue(any("500 lines > 499" in error for error in self.errors()))

    def test_missing_external_and_unreachable_references_fail(self):
        reference = self.reference()
        reference.unlink()
        self.assertTrue(self.errors())
        self.write_skill(body="[outside](../../../../outside.md)\n")
        (self.repo / "outside.md").write_text("Outside")
        self.assertTrue(self.errors())
        self.reference()
        self.write_skill()
        self.assertTrue(self.errors())

    def test_markdown_outside_reference_directory_cannot_bypass_budget(self):
        (self.skill / "hidden.md").write_text("x" * 10_000)
        self.write_skill(body="[rules](hidden.md)\n")
        self.assertTrue(self.errors())

    def test_reference_cycles_and_links_back_to_entry_are_allowed(self):
        reference = self.reference("[next](next.md)\n[entry](../SKILL.md#instructions)\n")
        (reference.parent / "next.md").write_text("[back](rules.md)\n")
        self.assertEqual(self.errors(), [])

    def test_future_plugin_is_discovered_without_allowlist(self):
        other = self.repo / "plugins/future/skills/future/SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("---\nname: future\ndescription: Future skill\n---\n" + "x" * 6_000)
        self.assertTrue(any(str(other) in error for error in self.errors()))

    def test_empty_repository_and_invalid_utf8_fail(self):
        self.entry.unlink()
        self.assertTrue(self.errors())
        self.entry.write_bytes(b"\xff")
        self.assertTrue(self.errors())

    def test_cli_is_read_only_and_returns_failure(self):
        self.reference()
        before = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo), "--check"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bytes", result.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()})
        self.write_skill(body="x" * 6_001)
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo)],
                                capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, PYTHONIOENCODING="cp1252"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("UTF-8 bytes", result.stderr)


if __name__ == "__main__":
    unittest.main()
