"""默认有限行为回归；原生工具和付费模型均有显式 opt-in。"""
import json
import os
import queue
import shutil
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
from deepseek_work_cycle_probe import Sdk, preflight, validate
from fixtures.deepseek_platform import Platform, seed


class PlatformBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fs41-")
        self.root = Path(self.tmp.name).resolve() / "repo"

    def tearDown(self):
        self.tmp.cleanup()

    def platform(self, scenario="repair"):
        seed(self.root, scenario)
        return Platform(self.root)

    def test_existing_test_root_cannot_be_reseeded_or_retried(self):
        platform = self.platform("uncertain")
        before = platform.file.read_bytes()
        with self.assertRaises(FileExistsError):
            seed(self.root, "uncertain")
        self.assertEqual(platform.file.read_bytes(), before)

    def test_execute_requires_complete_original_list_and_single_write(self):
        platform = self.platform("rounds")
        with self.assertRaisesRegex(ValueError, "原 Issue 清单"):
            platform.call("create", "I1")
        self.assertEqual(platform.call("prepare"), ["I1", "I2"])
        platform.call("create", "I1")
        with self.assertRaisesRegex(ValueError, "不重复"):
            platform.call("create", "I1")
        platform.call("create", "I2")
        self.assertEqual(list(platform.state["prs"]), ["I1", "I2"])

    def test_repair_invalidates_review_then_merge_and_local_bare_cleanup(self):
        platform = self.platform()
        platform.call("prepare")
        pr = platform.call("create", "I1")
        platform.call("review", "I1")
        with self.assertRaises(ValueError):
            platform.call("merge", "I1", pr["head"])
        platform.call("repair", "I1")
        with self.assertRaises(ValueError):
            platform.call("merge", "I1", pr["head"])
        pr = platform.call("review", "I1")
        platform.call("merge", "I1", pr["head"])
        platform.call("delete", "I1")
        self.assertTrue(pr["merged"] and pr["deleted"])
        self.assertEqual(platform.git("ls-remote", "--heads", "origin", "fixture/I1"), "")
        self.assertEqual(platform.git("rev-parse", "main"), pr["head"])

    def test_each_platform_gate_blocks_merge(self):
        platform = self.platform("uncertain")
        platform.state["uncertain"] = False
        platform.call("prepare")
        pr = platform.call("create", "I1")
        platform.call("review", "I1")
        for gate in ("checks", "approval", "protected"):
            with self.subTest(gate=gate):
                platform.state[gate] = False
                with self.assertRaisesRegex(ValueError, "门禁"):
                    platform.call("merge", "I1", pr["head"])
                self.assertFalse(pr["merged"])
                platform.state[gate] = True
        with self.assertRaisesRegex(ValueError, "head"):
            platform.call("merge", "I1", "stale-head")
        with self.assertRaisesRegex(ValueError, "未合并"):
            platform.call("delete", "I1")

    def test_unknown_write_is_reconciled_once(self):
        platform = self.platform("uncertain")
        platform.call("prepare")
        with self.assertRaisesRegex(ValueError, "回包未知"):
            platform.call("create", "I1")
        recovered = Platform(self.root).call("view")
        self.assertIn("I1", recovered["prs"])
        self.assertEqual(sum(op["operation"] == "create" for op in recovered["operations"]), 1)
        with self.assertRaisesRegex(ValueError, "不重复"):
            Platform(self.root).call("create", "I1")

    def test_three_round_pause_does_not_block_independent_item(self):
        platform = self.platform("rounds")
        platform.call("prepare")
        for item in ("I1", "I2"):
            platform.call("create", item)
        for _ in range(3):
            platform.call("review", "I1")
            platform.call("repair", "I1")
        platform.call("review", "I1")
        with self.assertRaisesRegex(ValueError, "第四"):
            platform.call("repair", "I1")
        pr = platform.call("review", "I2")
        platform.call("merge", "I2", pr["head"])
        self.assertFalse(platform.state["prs"]["I1"]["merged"])
        self.assertTrue(platform.state["prs"]["I2"]["merged"])

    def test_constraints_and_stop_reject_writes(self):
        platform = self.platform("constraints")
        original = platform.git("rev-parse", "main")
        for action in ("prepare", "create", "review", "repair", "merge", "delete"):
            with self.assertRaisesRegex(ValueError, "用户只读"):
                platform.call(action, "P0")
        platform.state["constraints"] = False
        platform.state["stopped"] = True
        with self.assertRaisesRegex(ValueError, "用户已停止"):
            platform.call("create", "I1")
        self.assertEqual(platform.git("rev-parse", "main"), original)

    def test_trace_rejects_receipt_partial_no_child_and_overlap(self):
        platform = self.platform("waiting")
        for frames in ([], [{"method": "subagent.started", "params": {
                "parentSessionId": "parent", "childSessionId": "child"}}]):
            with self.assertRaises(AssertionError):
                validate(self.root, frames, "parent", "waiting")
        frames = [
            {"method": "subagent.started", "params": {"parentSessionId": "parent", "childSessionId": "child"}},
            {"method": "subagent.finished", "params": {"childSessionId": "child", "stopReason": "max-tokens"}}]
        with self.assertRaisesRegex(AssertionError, "partial"):
            validate(self.root, frames, "parent", "waiting")

    def test_installed_skill_preflight_missing_reference_and_mixed_version(self):
        self.platform("waiting")
        subprocess.run([sys.executable, str(REPO / "scripts/deepseek.py"), "install", "--all",
                        "--project", str(self.root)], check=True, stdout=subprocess.DEVNULL)
        self.assertEqual(preflight(self.root), (REPO / "VERSION").read_text().strip())
        directory = self.root / ".dsh/skills/forge-steward-fix-feedback"
        receipt_file = directory / ".forge-steward-install.json"
        receipt = json.loads(receipt_file.read_text())
        receipt["version"] = "0.0.0"
        receipt_file.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "Mixed"):
            preflight(self.root)
        resource = next(directory.glob("references/*.md"))
        resource.unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            preflight(self.root)

    def test_timeout_is_failure_even_when_frames_are_queued(self):
        sdk = Sdk.__new__(Sdk)
        sdk.messages = queue.Queue()
        sdk.frames = []
        sdk.messages.put({"method": "session.status", "params": {"status": "running"}})
        with self.assertRaisesRegex(TimeoutError, "do not re-dispatch"):
            sdk.receive(time.monotonic() - 1)
        self.assertEqual(sdk.frames, [])

    def test_stop_receipt_without_termination_proof_is_not_success(self):
        self.platform("stop")
        frames = [{"method": "subagent.started", "params": {
            "parentSessionId": "parent", "childSessionId": "child"}}]
        with self.assertRaisesRegex(AssertionError, "native termination"):
            validate(self.root, frames, "parent", "stop")

    def missing_trace(self):
        self.platform("missing")
        subprocess.run([sys.executable, str(REPO / "scripts/deepseek.py"), "install", "--all",
                        "--project", str(self.root)], check=True, stdout=subprocess.DEVNULL)
        shutil.rmtree(self.root / ".dsh/skills/forge-steward-fix-feedback")
        directory = self.root / ".dsh/skills/forge-steward-work-cycle"
        frames = []

        def event(kind, data):
            frames.append({"method": "session.event", "params": {"sessionId": "parent", "event": {"type": kind, "data": data}}})

        def tool(name, args, text, error=False, lines=None):
            cid = str(len(frames))
            event("tool/call", {"name": name, "arguments": json.dumps(args), "callId": cid})
            event("tool/result", {"message": {"toolCallId": cid, "isError": error,
                                            "content": [{"type": "text", "text": text}]},
                                  "meta": {"lines": [{"number": n} for n in (lines or [])]}})

        tool("skill", {"name": "forge-steward-work-cycle"}, directory.joinpath("SKILL.md").read_text(encoding="utf-8").split("---", 2)[2].strip())
        for filename in ("startup.md", "cycles.md"):
            file = directory / "references" / filename
            text = file.read_text(encoding="utf-8")
            tool("read", {"file_path": str(file)}, text, lines=range(1, len(text.splitlines()) + 1))
        tool("read", {"file_path": str(self.root / ".dsh/skills/forge-steward-fix-feedback/SKILL.md")}, "File not found", error=True)
        event("assistant/message", {"message": {"content": [{"type": "text", "text": "缺少 forge-steward-fix-feedback；写入前停止。"}]}})
        event("turn/end", {"reason": {"kind": "completed"}})
        return frames

    def test_missing_rejects_empty_completed_trace(self):
        self.platform("missing")
        frames = [{"method": "session.event", "params": {"sessionId": "parent", "event": {
            "type": "turn/end", "data": {"reason": {"kind": "completed"}}}}}]
        with self.assertRaises(AssertionError):
            validate(self.root, frames, "parent", "missing")

    def test_missing_requires_complete_preflight_observed_absence_and_stop_terminal(self):
        frames = self.missing_trace()
        self.assertEqual(validate(self.root, frames, "parent", "missing")["parentTerminal"], "completed")
        for defect in ("body", "startup", "cycles", "diagnostic", "report", "terminal", "no-terminal"):
            bad = json.loads(json.dumps(frames))
            if defect == "body":
                bad[1]["params"]["event"]["data"]["message"]["content"][0]["text"] = "partial body"
            elif defect in ("startup", "cycles"):
                bad[3 if defect == "startup" else 5]["params"]["event"]["data"]["meta"]["lines"].pop()
            elif defect == "diagnostic":
                bad[7]["params"]["event"]["data"]["message"]["isError"] = False
            elif defect == "report":
                bad[-2]["params"]["event"]["data"]["message"]["content"][0]["text"] = "Done"
            elif defect == "terminal":
                bad[-1]["params"]["event"]["data"]["reason"]["kind"] = "max-tokens"
            else:
                bad.pop()
            with self.subTest(defect=defect), self.assertRaises(AssertionError):
                validate(self.root, bad, "parent", "missing")

    def test_missing_rejects_stage_calls_and_persisted_operations(self):
        frames = self.missing_trace()
        for action in ("prepare", "create", "review", "repair", "merge", "delete", "handoff"):
            bad = json.loads(json.dumps(frames))
            bad[6]["params"]["event"]["data"].update(name="bash", arguments=json.dumps({"command": "python3 fixture.py " + action}))
            with self.subTest(action=action), self.assertRaises(AssertionError):
                validate(self.root, bad, "parent", "missing")
        for action in ("prepare", "create", "review", "repair", "merge", "delete", "handoff"):
            platform = Platform(self.root)
            platform.state["operations"] = [{"operation": action}]
            platform.file.write_text(json.dumps(platform.state))
            with self.subTest(persisted=action), self.assertRaisesRegex(AssertionError, "stage writes"):
                validate(self.root, frames, "parent", "missing")

    def test_missing_rejects_known_external_search_read_and_unrecognized_shell(self):
        frames = self.missing_trace()
        outside = self.root.parent / "other-root/SKILL.md"
        outside.parent.mkdir()
        outside.write_text("another installed skill")
        (self.root / "linked-skill").symlink_to(outside)
        commands = ["find / -maxdepth 6 -iname '*forge-steward-fix*'",
                    "cat /private/tmp/forgesteward-cycle2.tIPDCu/.dsh/skills/forge-steward-fix-feedback/SKILL.md",
                    "cat ../other-root/SKILL.md", "cat linked-skill", "python3 -c 'print(1)'",
                    "python3 fixture.py view; cat /outside/SKILL.md", "cat $(echo /outside/SKILL.md)"]
        for name, args in [("bash", {"command": command}) for command in commands] + [
                ("read", {"file_path": str(outside)}), ("read", {"file_path": "linked-skill"}),
                ("write", {"file_path": "local.txt", "content": "write"})]:
            bad = json.loads(json.dumps(frames))
            bad[6]["params"]["event"]["data"].update(name=name, arguments=json.dumps(args))
            with self.subTest(name=name, args=args), self.assertRaises(AssertionError):
                validate(self.root, bad, "parent", "missing")

    def test_opt_in_missing_is_skip_but_incomplete_input_is_fail(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("FORGESTEWARD_DEEPSEEK_")}
        result = subprocess.run([sys.executable, str(REPO / "tests/deepseek_work_cycle_probe.py")],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("SKIP", result.stdout)
        result = subprocess.run([sys.executable, str(REPO / "tests/deepseek_work_cycle_probe.py"),
                                 "--cli", "missing-cli"], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)


class NativeSubagentTests(unittest.TestCase):
    def test_actual_subagent_tool_with_controlled_provider(self):
        runtime = os.environ.get("FORGESTEWARD_DEEPSEEK")
        if not runtime:
            self.skipTest("Set FORGESTEWARD_DEEPSEEK for native tool/provider assertions (no model)")
        result = subprocess.run([os.environ.get("FORGESTEWARD_DEEPSEEK_NODE", "node"),
                                 str(REPO / "tests/deepseek_subagent_probe.mjs"), str(Path(runtime).resolve())],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
