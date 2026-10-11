"""校验 work-cycle 最终汇报：固定样例逐字节比对、数据错误提示、规格只有一份。"""

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle"
SCRIPT = SKILL / "scripts/run_record.py"
RULES = SKILL / "references/report.md"
FIXTURES = REPO / "tests/fixtures/run_report"
spec_loader = importlib.util.spec_from_file_location("run_record_for_report", SCRIPT)
record = importlib.util.module_from_spec(spec_loader)
spec_loader.loader.exec_module(record)


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def expected(name):
    # Windows 检出可能把样例换成 CRLF；汇报本身固定用 LF。
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

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments, script=SCRIPT):
        # 按字节读取，避免 Windows 控制台编码影响比对；-B 避免在技能目录生成 __pycache__。
        return subprocess.run([sys.executable, "-B", str(script), "--repo", str(self.repo), *arguments],
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
        table = [line for line in text.splitlines() if line.startswith("| ") and "[#" in line or line.startswith("| 无")]
        self.assertEqual(sorted({line.split(" | ")[2] for line in table}), sorted(self.spec["results"]))
        self.assertIn("2. PR [#108](https://example.test/pr/108) 已暂停：", text)
        self.assertIn("3. Issue #88 已暂停：", text)
        self.assertIn("- 创建审查子 Agent 时返回线程上限。处理：", text)

    def test_empty_sections_and_zero_durations(self):
        text = self.assert_golden("empty.json", "zero.jsonl", "empty-zero.md")
        self.assertIn("- 总计 0 分：准备 0（分钟）\n- 其中等 CI 0 分，等本地资源 0 分\n", text)
        self.assertEqual(text.count("- 无\n"), 3)

    def test_no_events_reports_no_record(self):
        text = self.assert_golden("empty.json", None, "empty-no-events.md")
        self.assertIn("### 耗时\n- 无记录\n", text)

    def test_sections_always_appear_in_spec_order(self):
        for golden in ("full.md", "empty-zero.md", "empty-no-events.md", "empty-agents.md"):
            lines = expected(golden).decode("utf-8").splitlines()
            headings = [line[4:] for line in lines if line.startswith("### ")]
            self.assertEqual(headings, self.spec["sections"][1:])
            self.assertTrue(lines[2].startswith(self.spec["sections"][0] + "："))

    def test_agent_check_result_fills_last_section(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        data["agent_check"] = {"file": "agent-check.json"}
        path = self.make_run(data)
        shutil.copyfile(str(FIXTURES / "agent-check.json"), str(path / "agent-check.json"))
        first = self.report(path)
        self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8", "replace"))
        self.assertEqual(first.stdout, expected("empty-agents.md"))
        self.assertEqual(self.report(path).stdout, first.stdout)
        self.assertEqual((path / "report.md").read_bytes(), first.stdout)

    def test_agent_check_problems_only_change_last_section(self):
        cases = ({"unavailable": "超时。"}, "- 无法检查：超时\n"), \
                ({"file": "agent-check.json"}, "- 无法检查：找不到检查结果文件 agent-check.json\n"), \
                ({"file": "broken.json"}, "- 无法检查：检查结果格式无法识别\n")
        base = expected("empty-no-events.md").decode("utf-8")
        for check, line in cases:
            with self.subTest(check=check):
                data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
                data["agent_check"] = check
                path = self.make_run(data)
                (path / "broken.json").write_text("{", encoding="utf-8")
                result = self.report(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.decode("utf-8"), base.replace("- 未检查\n", line))

    def test_agent_check_field_must_name_one_file_or_reason(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        for check, problem in (([], "agent_check 应为对象"),
                               ({"file": "a.json", "unavailable": "x"}, "agent_check 只能有 file 或 unavailable 其中一个"),
                               ({"file": "../a.json"}, "agent_check.file 只能是运行目录下的文件名"),
                               ({"unavailable": " "}, "agent_check.unavailable 应为非空文本")):
            with self.subTest(check=check):
                self.assertEqual(record.check_handoff(dict(data, agent_check=check), self.spec), [problem])

    def test_bad_data_lists_each_field_and_writes_nothing(self):
        data = json.loads((FIXTURES / "full.json").read_text(encoding="utf-8"))
        data["change_requests"][2]["result"] = "待合并"
        data["change_requests"][3].pop("next")
        data["change_requests"][5]["reason"] = " "
        data["change_requests"][0]["issues"] = [0]
        data["issues_without_change_request"][1]["result"] = "已合并"
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
        for field in ('change_requests[2].result 不在结果词表中："待合并"',
                      "change_requests[3].next 缺少必填字段",
                      "change_requests[5].reason 结果为已暂停时不能为空",
                      "change_requests[0].issues[0] 应为 Issue 编号或非空文本",
                      'issues_without_change_request[1].result 只能是已暂停、未开始："已合并"',
                      "concurrency.agent_limit 缺少必填字段",
                      "startup_queue 应为对象",
                      "completed_cycles 应为不小于 0 的整数",
                      "stop_reason 缺少必填字段",
                      "exceptions[0] 应为对象",
                      "needs_you[0] 应为非空文本"):
            self.assertIn("- " + field + "\n", message)
        self.assertEqual(result.stdout, b"")
        self.assertFalse((path / "report.md").exists())

    def test_serial_mode_needs_reason_and_top_level_must_be_object(self):
        data = json.loads((FIXTURES / "empty.json").read_text(encoding="utf-8"))
        del data["concurrency"]["serial_reason"]
        self.assertEqual(record.check_handoff(data, self.spec), ["concurrency.serial_reason 缺少必填字段"])
        self.assertEqual(record.check_handoff([], self.spec), ["handoff.json 顶层应为对象"])

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
        copy = Path(self.temporary.name) / "skill"
        (copy / "scripts").mkdir(parents=True)
        (copy / "references").mkdir()
        shutil.copyfile(str(SCRIPT), str(copy / "scripts/run_record.py"))
        (copy / "references/report.md").write_text("# 最终汇报\n\n没有规格块。\n", encoding="utf-8")
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
        self.assertTrue(template[2].startswith(self.spec["sections"][0] + "："))
        self.assertIn("- " + self.spec["agents"]["unchecked"], template)
        for word in self.spec["results"]:
            self.assertIn("- " + word, text)

    def test_only_report_rules_define_the_format(self):
        files = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
        for path in files:
            text = path.read_text(encoding="utf-8")
            if path != RULES:
                # 章节标题和结果词表只在 report.md 出现。
                self.assertNotIn(self.spec["sections"][-1], text, path.name)
                self.assertNotIn("等待外部审批", text, path.name)
        for name in ("SKILL.md", "references/run-record.md", "references/cycles.md",
                     "references/concurrency.md", "references/agents.md"):
            self.assertIn("report.md", (SKILL / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
