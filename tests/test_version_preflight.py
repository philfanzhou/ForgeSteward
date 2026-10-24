"""Stage-skill version preflight: matching, mixed, missing, and usage behavior.

work-cycle passes its bundled expected version and the command to every stage
dispatch; the stage runs it against its own skill directory before its first
write. These tests use temporary directories; they do not prove that an Agent
model stops as the rule requires.
"""

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/preflight_versions.py"
STARTUP = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/references/startup.md"


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()


class VersionPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="forgesteward-preflight-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def stage(self, name, version):
        directory = self.root / name
        directory.mkdir()
        if version is not None:
            (directory / "VERSION").write_text(version + "\n", encoding="utf-8")
        return directory

    def run_preflight(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, timeout=30)

    @staticmethod
    def command(expected, directories):
        args = ["--expected", expected]
        for directory in directories:
            args += ["--skill-dir", str(directory)]
        return args

    def test_matching_stage_versions_pass(self):
        first = self.stage("check-workflow", "0.2.25")
        second = self.stage("execute-work", "0.2.25")
        result = self.run_preflight(*self.command("0.2.25", [first, second]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn(str(first / "VERSION"), result.stdout)
        self.assertIn(str(second / "VERSION"), result.stdout)

    def test_mixed_and_missing_versions_report_every_gap(self):
        good = self.stage("good", "0.2.25")
        old = self.stage("old", "0.2.24")
        missing = self.stage("missing", None)
        result = self.run_preflight(*self.command("0.2.25", [good, old, missing]))
        self.assertEqual(result.returncode, 1)
        self.assertIn("version mismatch: " + str(old / "VERSION") + " is 0.2.24 (expected 0.2.25)",
                      result.stderr)
        self.assertIn("missing VERSION: " + str(missing / "VERSION") + " (expected 0.2.25)",
                      result.stderr)
        self.assertIn("preflight: ok: " + str(good / "VERSION") + " 0.2.25", result.stdout)
        self.assertEqual(len(result.stderr.splitlines()), 2)

    def test_blank_marker_is_a_gap_not_a_pass(self):
        blank = self.stage("blank", "")
        result = self.run_preflight(*self.command("0.2.25", [blank]))
        self.assertEqual(result.returncode, 1)
        self.assertIn("is <empty> (expected 0.2.25)", result.stderr)

    def test_usage_errors_exit_two(self):
        stage = self.stage("stage", "0.2.25")
        cases = (
            (),
            ("--expected", "0.2.25"),
            ("--skill-dir", str(stage)),
            ("--expected", "0.2", "--skill-dir", str(stage)),
            ("--expected", "", "--skill-dir", str(stage)),
            ("--expected", "0.2.25", "--skill-dir", str(stage), "--unknown"),
        )
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(self.run_preflight(*args).returncode, 2)

    def test_retained_identity_options_are_paired_and_missing_manifest_stops(self):
        stage = self.stage("stage", "0.2.25")
        args = self.command("0.2.25", [stage])
        for extra in (("--rules-manifest", str(self.root / "rules/manifest.json")),
                      ("--rules-identity", "0" * 64)):
            self.assertEqual(self.run_preflight(*args, *extra).returncode, 2)
        missing = self.root / "rules/manifest.json"
        result = self.run_preflight(*args, "--rules-manifest", str(missing),
                                    "--rules-identity", "0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(missing), result.stderr)
        self.assertIn("preserve run state", result.stderr)


class StartupPreflightRuleTests(unittest.TestCase):
    def test_startup_requires_the_preflight_before_the_first_stage_write(self):
        text = normalized(STARTUP)
        for phrase in (
            "`VERSION` beside each stage `SKILL.md`",
            "preflight_versions.py --expected <value> --skill-dir <stage-skill-directory>",
            "runs it against its own skill directory before its first write",
            "stops that stage without writing",
            "missing or mismatched path and values",
            "exit `2` is a usage error",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
