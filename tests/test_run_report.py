"""Check work-cycle reports with byte-for-byte fixtures, field errors, and a single specification."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle"
CHECK_WORKFLOW = REPO / "plugins/check-workflow/skills/forge-steward-check-workflow"
SCRIPT = SKILL / "scripts/run_record.py"
RULES = SKILL / "references/report.md"
FIXTURES = REPO / "tests/fixtures/run_report"
spec_loader = importlib.util.spec_from_file_location("run_record_for_report", SCRIPT)
record = importlib.util.module_from_spec(spec_loader)
spec_loader.loader.exec_module(record)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def expected(name):
    # Windows checkouts may convert fixtures to CRLF; report output always uses LF.
    return (FIXTURES / name).read_bytes().replace(b"\r\n", b"\n")


class RunReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        git("init", "-q", cwd=self.repo)
        git("config", "user.name", "Test", cwd=self.repo)
        git("config", "user.email", "test@example.test", cwd=self.repo)
        git("commit", "--allow-empty", "-qm", "initial", cwd=self.repo)
        self.spec = record.load_report_spec()
        # Control the running package version so repository versions do not affect injected releases or fixtures.
        self.skill = Path(self.temporary.name) / "skill"
        (self.skill / "scripts").mkdir(parents=True)
        (self.skill / "references").mkdir()
        self.script = self.skill / "scripts/run_record.py"
        self.package_version = self.skill / "scripts/VERSION"
        shutil.copyfile(str(SCRIPT), str(self.script))
        shutil.copyfile(str(RULES), str(self.skill / "references/report.md"))
        self.package_version.write_text("0.2.21\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments, script=None):
        # Read bytes to avoid Windows console encoding effects; -B avoids __pycache__ in skill directories.
        return subprocess.run([sys.executable, "-B", str(script or self.script), "--repo", str(self.repo), *arguments],
                              capture_output=True)

    def make_run(self, handoff, events=None):
        result = self.run_cli("start", "--cycles", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = Path(json.loads(result.stdout)["path"])
        if isinstance(handoff, str):
            shutil.copyfile(str(FIXTURES / handoff), str(path / "handoff.json"))
        else:
            (path / "handoff.json").write_text(json.dumps(handoff, ensure_ascii=False), encoding="utf-8")
        if events:
            shutil.copyfile(str(FIXTURES / events), str(path / "events.jsonl"))
        return path

    def report(self, path):
        return self.run_cli("report", "--run", path.name)

    def assert_golden(self, handoff, events, golden):
        path = self.make_run(handoff, events)
        first = self.report(path)
        self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8", "replace"))
        saved = (path / "report.md").read_bytes()
        second = self.report(path)
        self.assertEqual(first.stdout, expected(golden))
        self.assertEqual(saved, first.stdout)
        self.assertEqual(second.stdout, first.stdout)
        self.assertEqual((path / "report.md").read_bytes(), saved)
        self.assertFalse((path / ".report.md.tmp").exists())
        return first.stdout.decode("utf-8")

    def test_full_sample_covers_every_result_paused_items_and_exceptions(self):
        text = self.assert_golden("full.json", "full.jsonl", "full.md")
        table = [line for line in text.splitlines() if line.startswith("| ") and "[#" in line or line.startswith("| None")]
        self.assertEqual(sorted({line.split(" | ")[2] for line in table}), sorted(self.spec["results"]))
        self.assertIn("2. PR [#108](https://example.test/pr/108) Paused: ", text)
        self.assertIn("3. Issue #88 Paused: ", text)
        self.assertIn("- Review subagent creation hit the thread limit. Recovery: ", text)

    def test_empty_sections_and_zero_durations(self):
        text = self.assert_golden("empty.json", "zero.jsonl", "empty-zero.md")
        self.assertIn("- Total 0 min: Preparation 0 (minutes)\n- Including Waiting for CI 0 min, Waiting for local resources 0 min\n", text)
        self.assertEqual(text.count("- None\n"), 3)

    def test_release_audit_finding_and_unknown_reach_run_overview(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["release_audit"] = {
            "result": "findings",
            "summary": "Release v1.2.3 has one finding and one unknown",
            "evidence": ".git/forge-steward/runs/run-1/check-workflow/result.md",
            "findings": ["Tag v1.2.3 has no matching announcement"],
            "unknowns": ["The package feed query timed out"],
        }
        path = self.make_run(data)
        source = (path / "handoff.json").read_bytes()
        first = self.report(path)
        self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8", "replace"))
        text = first.stdout.decode("utf-8")
        self.assertIn("\n- Release audit: ", text)
        line = next(line for line in text.splitlines() if line.startswith("- Release audit: "))
        self.assertIn("Release v1.2.3 has one finding and one unknown", line)
        self.assertIn("Result: Findings", line)
        self.assertIn("Findings: Tag v1.2.3 has no matching announcement", line)
        self.assertIn("Unknowns: The package feed query timed out", line)
        self.assertIn("Evidence: .git/forge-steward/runs/run-1/check-workflow/result.md", line)
        self.assertLess(text.index("- Startup check:"), text.index("- Release audit:"))
        self.assertLess(text.index("- Release audit:"), text.index("- Existing PRs:"))
        self.assertEqual((path / "handoff.json").read_bytes(), source)
        self.assertEqual(self.report(path).stdout, first.stdout)

    def test_release_audit_result_display_names(self):
        cases = (("clean", "Clean", {}), ("findings", "Findings", {"findings": ["A finding"]}),
                 ("incomplete", "Incomplete", {}), ("not-run", "Not run", {}))
        for state, display, extra in cases:
            with self.subTest(state=state):
                data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
                data["release_audit"] = dict({"result": state, "summary": "Audit summary", "evidence": "result.md"}, **extra)
                self.assertEqual(record.check_handoff(data, self.spec), [])
                path = self.make_run(data)
                outcome = self.report(path)
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
                self.assertIn("- Release audit: Audit summary; Result: " + display + ";", outcome.stdout.decode("utf-8"))

    def test_handoff_without_release_audit_keeps_golden_output(self):
        path = self.make_run("empty.json", "zero.jsonl")
        outcome = self.report(path)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(outcome.stdout, expected("empty-zero.md"))
        self.assertNotIn("Release audit:", outcome.stdout.decode("utf-8"))

    def test_release_audit_malformed_values_fail_with_field_errors(self):
        base = {"result": "clean", "summary": "Coverage was complete", "evidence": "result.md"}
        cases = (
            ({"result": "pending"}, 'release_audit.result must be one of: clean, findings, incomplete, not-run: "pending"'),
            ({"result": "findings"}, "release_audit.findings must list at least one finding when result is findings"),
            ({"summary": " "}, "release_audit.summary must be nonempty text"),
            ({"evidence": ""}, "release_audit.evidence must be nonempty text"),
            ({"findings": "one"}, "release_audit.findings must be a list"),
            ({"unknowns": [""]}, "release_audit.unknowns[0] must be nonempty text"),
            ({"summary": "Leaked api_key=example-value"}, "release_audit.summary must contain redacted text only"),
            ({"extra": "x"}, "release_audit has unknown fields: extra"),
        )
        for patch, problem in cases:
            with self.subTest(patch=patch):
                data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
                data["release_audit"] = dict(base, **patch)
                path = self.make_run(data)
                result = self.report(path)
                self.assertEqual(result.returncode, 1)
                self.assertIn(problem, result.stderr.decode("utf-8"))
                self.assertEqual(result.stdout, b"")
                self.assertFalse((path / "report.md").exists())

    def test_no_events_reports_no_record(self):
        text = self.assert_golden("empty.json", None, "empty-no-events.md")
        self.assertIn("### Time spent\n- No record\n", text)

    def test_required_sections_always_appear_optional_section_is_last(self):
        for golden in ("full.md", "empty-zero.md", "empty-no-events.md", "empty-agents.md"):
            lines = expected(golden).decode("utf-8").splitlines()
            headings = [line[4:] for line in lines if line.startswith("### ")]
            self.assertEqual(headings, self.spec["sections"][1:] if golden == "empty-agents.md" else self.spec["sections"][1:6])
            self.assertTrue(lines[2].startswith(self.spec["sections"][0] + ": "))

    def test_agent_check_result_fills_last_section(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["agent_check"] = {"file": "agent-check.json"}
        path = self.make_run(data)
        shutil.copyfile(str(FIXTURES / "agent-check.json"), str(path / "agent-check.json"))
        saved_check = (path / "agent-check.json").read_bytes()
        first = self.report(path)
        self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8", "replace"))
        self.assertEqual(first.stdout, expected("empty-agents.md"))
        self.assertEqual(self.report(path).stdout, first.stdout)
        self.assertEqual((path / "report.md").read_bytes(), first.stdout)
        self.assertEqual((path / "agent-check.json").read_bytes(), saved_check)

    def test_agent_check_problems_only_change_last_section(self):
        cases = [{"unavailable": "Timed out."}, {"file": "missing.json"}, {"file": "broken.json"},
                 {"file": "bad-fields.json"}, {"file": "bad-utf8.json"}]
        base = expected("empty-no-events.md")
        for check in cases:
            with self.subTest(check=check):
                data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
                data["agent_check"] = check
                path = self.make_run(data)
                files = {"broken.json": b"{", "bad-fields.json": b'{"schema": 2}', "bad-utf8.json": b"\xff"}
                for name, content in files.items():
                    (path / name).write_bytes(content)
                result = self.report(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, base)
                for name, content in files.items():
                    self.assertEqual((path / name).read_bytes(), content)

    def test_upgrade_projection_and_session_version_matrix(self):
        current = {"name": "A", "status": "Current", "other_scopes": ["project"]}
        offers = [{"name": "B", "status": "Missing", "other_scopes": ["project"]},
                  {"name": "C", "status": "Incomplete", "missing": ["work-cycle"]},
                  {"name": "D", "status": "Behind", "versions": ["0.2.8", "0.2.8"]}]
        inactive = [current, {"name": "E", "status": "Unknown", "reason": "Timed out"},
                    {"name": "F", "status": "Ahead of latest release"}, {"name": "G", "status": "Agent not installed"}]
        cases = [
            ("0.2.10", "0.2.10", inactive, False, 0),
            ("0.2.10", None, offers, False, 0),
            ("0.2.10", "bad", offers, False, 0),
            ("0.2.10", "0.2.10", inactive + offers, False, 3),
            ("0.2.9", "0.2.10", [current], True, 0),
            ("0.2.9", "0.2.10", [], True, 0),
            ("0.2.9", "0.2.10", inactive + offers, True, 3),
            ("0.2.11", "0.2.10", inactive, False, 0),
            ("0.2.11", "0.2.10", offers, False, 3),
            (None, "0.2.10", offers, False, 3),
            ("bad", "0.2.10", offers, False, 3),
            ("v0.2.9", "0.2.10", [], False, 0),
        ]
        for package, latest, agents, old, count in cases:
            with self.subTest(package=package, latest=latest, agents=agents):
                if package is None:
                    self.package_version.unlink(missing_ok=True)
                else:
                    self.package_version.write_text(package + "\n", encoding="utf-8")
                data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
                data["agent_check"] = {"file": "agent-check.json"}
                path = self.make_run(data)
                check = path / "agent-check.json"
                check.write_text(json.dumps({"schema": 1, "latest": {"version": latest}, "agents": agents}), encoding="utf-8")
                original = check.read_bytes()
                first = self.report(path)
                self.assertEqual(first.returncode, 0, first.stderr)
                text = first.stdout.decode("utf-8")
                base = expected("empty-no-events.md")
                self.assertTrue(first.stdout.startswith(base))
                self.assertEqual(text.count("### Updates available"), int(old or count > 0))
                self.assertEqual(text.count("This session uses older version"), int(old))
                self.assertEqual(text.count("now?"), int(old or count > 0))
                self.assertNotIn("A: ", text)
                for name in ("E", "F", "G"):
                    self.assertNotIn(name + ": ", text)
                if count:
                    for name in ("B", "C", "D"):
                        self.assertEqual(text.count(name + ": "), 1)
                    self.assertIn("B: Not installed (latest v0.2.10) (also installed outside user scope)", text)
                    self.assertIn("D: v0.2.8, behind latest v0.2.10", text)
                if old:
                    self.assertIn("### Updates available\n- This session uses older version v0.2.9; latest is v0.2.10\n", text)
                self.assertEqual(self.report(path).stdout, first.stdout)
                self.assertEqual(check.read_bytes(), original)

    def test_legacy_result_names_and_mixed_input_are_equivalent(self):
        # Exact pre-migration input code points; these are compatibility data, not output text.
        pairs = [((0x5DF2, 0x5408, 0x5E76), "Merged"),
                 ((0x7B49, 0x4F60, 0x5BA1, 0x6279), "Awaiting your approval"),
                 ((0x7B49, 0x5F85, 0x20, 0x43, 0x49), "Waiting for CI"),
                 ((0x7B49, 0x5F85, 0x5916, 0x90E8, 0x5BA1, 0x6279), "Waiting for external approval"),
                 ((0x5DF2, 0x6682, 0x505C), "Paused"),
                 ((0x5DF2, 0x5173, 0x95ED, 0x672A, 0x5408, 0x5E76), "Closed without merge"),
                 ((0x672A, 0x5F00, 0x59CB), "Not started")]
        aliases = {"".join(map(chr, points)): current for points, current in pairs}
        self.assertEqual(self.spec["result_aliases"], aliases)
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["change_requests"] = [dict(url="https://example.test/pr/" + str(n), number=n,
                                       issues=[n], result=value, reason="A reason", next="Next action")
                                   for n, value in enumerate(aliases.values(), 1)]
        data["issues_without_change_request"] = [dict(issue=8, result="Paused", reason="Blocked", next=""),
                                                 dict(issue=9, result="Not started", reason="", next="")]
        current_path = self.make_run(data, "full.jsonl")
        expected_output = self.report(current_path).stdout
        for mixed in (False, True):
            legacy = deepcopy(data)
            inverse = {value: key for key, value in aliases.items()}
            for index, item in enumerate(legacy["change_requests"] + legacy["issues_without_change_request"]):
                if not mixed or index % 2:
                    item["result"] = inverse[item["result"]]
            original = deepcopy(legacy)
            self.assertEqual(record.check_handoff(legacy, self.spec), [])
            self.assertEqual(legacy, original)
            path = self.make_run(legacy, "full.jsonl")
            before = (path / "handoff.json").read_bytes()
            for _ in range(2):
                outcome = self.report(path)
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
                self.assertEqual(outcome.stdout, expected_output)
                self.assertEqual((path / "handoff.json").read_bytes(), before)

    def test_every_legacy_agent_status_and_mixed_checks_are_equivalent(self):
        # Seven old status inputs, each independently paired with its current meaning.
        pairs = [((0x672A, 0x5B89, 0x88C5, 0x20, 0x41, 0x67, 0x65, 0x6E, 0x74), "Agent not installed"),
                 ((0x7F3A, 0x5C11), "Missing"), ((0x4E0D, 0x5B8C, 0x6574), "Incomplete"),
                 ((0x843D, 0x540E), "Behind"), ((0x6700, 0x65B0), "Current"),
                 ((0x9AD8, 0x4E8E, 0x6700, 0x65B0, 0x6B63, 0x5F0F, 0x7248), "Ahead of latest release"),
                 ((0x65E0, 0x6CD5, 0x5224, 0x65AD), "Unknown")]
        aliases = {"".join(map(chr, points)): current for points, current in pairs}
        self.assertEqual(self.spec["agents"]["aliases"], aliases)
        for old, current in aliases.items():
            check = {"schema": 1, "latest": {"version": "0.2.21"},
                     "agents": [{"name": "A", "status": old, "versions": ["0.2.20"], "missing": ["work-cycle"]}]}
            before = deepcopy(check)
            new = deepcopy(check)
            new["agents"][0]["status"] = current
            self.assertEqual(record.agent_lines(check, self.spec), record.agent_lines(new, self.spec))
            self.assertEqual(check, before)
        check = {"schema": 1, "latest": {"version": "0.2.21"},
                 "agents": [dict(name="Agent " + str(n), status=old if n % 2 else current,
                                 versions=["0.2.20"], missing=["work-cycle"])
                            for n, (old, current) in enumerate(aliases.items())]}
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["agent_check"] = {"file": "agent-check.json"}
        path = self.make_run(data)
        source = path / "agent-check.json"
        source.write_text(json.dumps(check, ensure_ascii=False), encoding="utf-8")
        before = source.read_bytes()
        current = deepcopy(check)
        for item in current["agents"]:
            item["status"] = aliases.get(item["status"], item["status"])
        expected_lines = record.agent_lines(current, self.spec, session_version="0.2.21")
        outcome = self.report(path)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertTrue(outcome.stdout.decode().endswith("\n".join("- " + line for line in expected_lines) + "\n"))
        self.assertEqual(source.read_bytes(), before)

    def test_legacy_free_text_is_preserved_without_machine_translation(self):
        # Two CJK code points stand for user-authored legacy free text.
        text = "".join(map(chr, (0x65E7, 0x6587)))
        data = json.loads((FIXTURES / "full.json").read_text(encoding="utf-8"))
        data["change_requests"][2]["reason"] = text
        data["change_requests"][2]["next"] = text
        normalized = record.normalize_handoff(data, self.spec)
        self.assertEqual(normalized["change_requests"][2]["reason"], text)
        self.assertEqual(normalized["change_requests"][2]["next"], text)
        path = self.make_run(data)
        original = (path / "handoff.json").read_bytes()
        result = self.report(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(text + "; Next: " + text, result.stdout.decode("utf-8"))
        self.assertEqual((path / "handoff.json").read_bytes(), original)

    def test_unknown_agent_status_is_explicit_but_optional_section_remains_optional(self):
        check = {"schema": 1, "latest": {"version": "0.2.21"},
                 "agents": [{"name": "A", "status": "Unexpected"}]}
        with self.assertRaisesRegex(ValueError, r"agents\[0\].status is not a known Agent status"):
            record.agent_lines(check, self.spec)
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["agent_check"] = {"file": "agent-check.json"}
        path = self.make_run(data)
        (path / "agent-check.json").write_text(json.dumps(check), encoding="utf-8")
        result = self.report(path)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(result.stdout, expected("empty-no-events.md"))

    def test_failed_validation_or_atomic_replace_keeps_prior_report_and_inputs(self):
        path = self.make_run("full.json", "full.jsonl")
        old = record.build_report(path)
        source = path / "handoff.json"
        before = source.read_bytes()
        with mock.patch.object(record.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                record.build_report(path)
        self.assertEqual((path / "report.md").read_text(encoding="utf-8"), old)
        self.assertEqual(source.read_bytes(), before)
        # Existing behavior may retain the complete temporary file; no rollback promise is added.
        self.assertEqual((path / ".report.md.tmp").read_text(encoding="utf-8"), old)
        invalid = json.loads(before)
        invalid["change_requests"][0]["result"] = "Unexpected"
        source.write_text(json.dumps(invalid), encoding="utf-8")
        result = self.report(path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual((path / "report.md").read_text(encoding="utf-8"), old)

    def test_alias_targets_cannot_add_new_states_or_chains(self):
        text = RULES.read_text(encoding="utf-8")
        for key in ("result_aliases", "agents"):
            spec = deepcopy(self.spec)
            aliases = spec[key] if key == "result_aliases" else spec[key]["aliases"]
            aliases[next(iter(aliases))] = "Unexpected"
            rewritten = re.sub(r"```json report-spec\n.*?\n```",
                               lambda _: "```json report-spec\n" + json.dumps(spec) + "\n```", text, flags=re.S)
            path = self.skill / "references/report.md"
            path.write_text(rewritten, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Malformed report-spec"):
                record.load_report_spec(path)

    def test_agent_check_field_must_name_one_file_or_reason(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        for check, problem in (([], "agent_check must be an object"),
                               ({"file": "a.json", "unavailable": "x"}, "agent_check must contain exactly one of file or unavailable"),
                               ({"file": "../a.json"}, "agent_check.file must be a filename in the run directory"),
                               ({"unavailable": " "}, "agent_check.unavailable must be nonempty text")):
            with self.subTest(check=check):
                self.assertEqual(record.check_handoff(dict(data, agent_check=check), self.spec), [problem])

    def test_bad_data_lists_each_field_and_writes_nothing(self):
        data = json.loads((FIXTURES / "full.json").read_text(encoding="utf-8"))
        data["change_requests"][2]["result"] = "Pending merge"
        data["change_requests"][3].pop("next")
        data["change_requests"][5]["reason"] = " "
        data["change_requests"][0]["issues"] = [0]
        data["issues_without_change_request"][1]["result"] = "Merged"
        data["concurrency"] = {"enabled": True}
        data["startup_queue"] = []
        data["completed_cycles"] = True
        del data["stop_reason"]
        data["exceptions"] = ["oops"]
        data["needs_you"] = [""]
        path = self.make_run(data, "full.jsonl")
        result = self.report(path)
        self.assertEqual(result.returncode, 1)
        message = result.stderr.decode("utf-8")
        for field in ('change_requests[2].result is not a known result: "Pending merge"',
                      "change_requests[3].next is required",
                      "change_requests[5].reason must not be empty when result is Paused",
                      "change_requests[0].issues[0] must be an Issue number or nonempty text",
                      'issues_without_change_request[1].result must be one of: Paused, Not started: "Merged"',
                      "concurrency.agent_limit is required",
                      "startup_queue must be an object",
                      "completed_cycles must be an integer greater than or equal to 0",
                      "stop_reason is required",
                      "exceptions[0] must be an object",
                      "needs_you[0] must be nonempty text"):
            self.assertIn("- " + field + "\n", message)
        self.assertEqual(result.stdout, b"")
        self.assertFalse((path / "report.md").exists())

    def test_serial_mode_needs_reason_and_top_level_must_be_object(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        del data["concurrency"]["serial_reason"]
        self.assertEqual(record.check_handoff(data, self.spec), ["concurrency.serial_reason is required"])
        self.assertEqual(record.check_handoff([], self.spec), ["handoff.json top level must be an object"])

    def test_environment_errors_return_two(self):
        self.assertEqual(self.run_cli("report", "--run", "20261010T000000Z-ffff").returncode, 2)
        missing = self.make_run("empty.json")
        (missing / "handoff.json").unlink()
        self.assertEqual(self.report(missing).returncode, 2)
        broken = self.make_run("empty.json")
        (broken / "handoff.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.report(broken).returncode, 2)
        self.assertFalse((broken / "report.md").exists())

    def test_missing_spec_block_returns_two(self):
        copy = Path(self.temporary.name) / "broken-skill"
        (copy / "scripts").mkdir(parents=True)
        (copy / "references").mkdir()
        shutil.copyfile(str(SCRIPT), str(copy / "scripts/run_record.py"))
        (copy / "references/report.md").write_text("# Final report\n\nNo specification block.\n", encoding="utf-8")
        path = self.make_run("empty.json")
        result = self.run_cli("report", "--run", path.name, script=copy / "scripts/run_record.py")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"report-spec", result.stderr)


class SingleDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.spec = record.load_report_spec()

    def test_result_words_are_not_hardcoded_in_script(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for word in self.spec["results"]:
            self.assertNotIn(word, source)

    def test_hand_template_matches_spec(self):
        text = RULES.read_text(encoding="utf-8")
        template = re.search(r"```markdown\n(.*?)```", text, re.S).group(1).splitlines()
        self.assertEqual(template[0], "## " + self.spec["title"])
        self.assertEqual([line[4:] for line in template if line.startswith("### ")], self.spec["sections"][1:])
        self.assertTrue(template[2].startswith(self.spec["sections"][0] + ": "))
        self.assertIn("The first six sections always appear in order", text)
        self.assertIn("Omit the entire section when there is no action available", text)
        for word in self.spec["results"]:
            self.assertIn("- " + word, text)

    def test_only_report_rules_define_the_format(self):
        files = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        for path in files:
            text = path.read_text(encoding="utf-8")
            if path != RULES:
                # Section headings and outcome vocabulary appear only in report.md.
                self.assertNotIn(self.spec["sections"][-1], text, path.name)
                self.assertNotIn("Waiting for external approval", text, path.name)
        for name in ("SKILL.md", "references/run-record.md", "references/cycles.md",
                     "references/concurrency.md", "references/subagent-lifecycle.md"):
            self.assertIn("report.md", (SKILL / name).read_text(encoding="utf-8"), name)


class ReleaseAuditRuleTests(unittest.TestCase):
    """The audit-only limit and the startup recording obligation stay explicit in the rules."""

    def sentence_with(self, path, phrase):
        text = path.read_text(encoding="utf-8")
        self.assertIn(phrase, text, path)
        return next(sentence for sentence in re.split(r"(?<=\.)\s+", text) if phrase in sentence)

    def test_entry_limits_release_audit_only_to_a_read_only_report(self):
        sentence = self.sentence_with(CHECK_WORKFLOW / "SKILL.md", "release-audit-only")
        self.assertIn("only the read-only audit and report", sentence)
        self.assertIn("no project changes", sentence)
        self.assertIn("delivery", sentence)

    def test_procedure_finishes_audit_only_with_zero_project_writes(self):
        sentence = self.sentence_with(CHECK_WORKFLOW / "references/procedure.md", "release-audit-only")
        self.assertIn("Reporting", sentence)
        self.assertIn("zero project writes", sentence)
        self.assertIn("never fix, file, or deliver", sentence)

    def test_reporting_names_audit_only_as_a_zero_change_run(self):
        text = (CHECK_WORKFLOW / "references/reporting.md").read_text(encoding="utf-8")
        self.assertIn("release-audit-only", text)
        self.assertIn("No project files were changed", text)

    def test_startup_records_release_audit_before_cleanup(self):
        text = (SKILL / "references/startup.md").read_text(encoding="utf-8")
        self.assertIn("`release_audit`", text)
        self.assertIn("result.md", text)
        self.assertIn("never infer a clean audit", text)
        self.assertIn("never blocks", text)


if __name__ == "__main__":
    unittest.main()
