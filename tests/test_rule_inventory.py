"""Exercise complete bounded rule reads and truthful recovery in isolated packages."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/rule_inventory.py"
SPEC = importlib.util.spec_from_file_location("rule_inventory", SCRIPT)
RULES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RULES)


class RuleInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="implement-213-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "package"
        (self.root / "references").mkdir(parents=True)
        self.write("SKILL.md", "# Entry\nRead [first](references/first.md), then [second](references/second.md).\n")
        self.write("references/first.md", "# First\n[cycle](second.md)\n")
        self.write("references/second.md", "# Second\n[back](first.md)\n[entry](../SKILL.md)\n")
        self.required = ["SKILL.md", "references/first.md", "references/second.md"]

    def write(self, relative, text):
        (self.root / relative).write_bytes(text.encode("utf-8"))

    def plan(self, **kwargs):
        return RULES.plan(self.root, "implement", self.required, 1024, 80, **kwargs)

    def test_inventory_order_hash_bytes_lines_and_cycle_deduplication(self):
        inv = RULES.inventory(self.root)
        self.assertEqual([f["path"] for f in inv["files"]], self.required)
        for file in inv["files"]:
            raw = (self.root / file["path"]).read_bytes()
            self.assertEqual(file["sha256"], RULES.digest(raw))
            self.assertEqual(file["bytes"], len(raw))
            self.assertEqual(file["lines"], len(raw.decode().splitlines()))
        self.assertEqual(inv, RULES.inventory(self.root))

    def test_small_budget_covers_every_byte_once_with_unicode_long_lines_crlf_and_wrappers(self):
        # Explicit Unicode code points are technical boundary data, not maintained prose.
        body = "# First\r\n" + (chr(0x4E2D) + chr(0x1F600)) * 700 + "\r\n" + "x\n" * 500
        self.write("references/first.md", body)
        manifest = self.plan()
        bodies = {name: b"" for name in self.required}
        for group in manifest["groups"]:
            output = RULES.read_range(manifest, group)
            self.assertLessEqual(len(output) + 80, 1024)
            self.assertTrue(output.startswith(b"BEGIN "))
            self.assertIn(b"\nEND ", output)
            self.assertEqual(group["start"], len(bodies[group["path"]]))
            raw = (self.root / group["path"]).read_bytes()[group["start"]:group["end"]]
            raw.decode("utf-8")  # No split character, including a long line.
            self.assertIn(raw, output)
            bodies[group["path"]] += raw
        self.assertGreater(len(manifest["groups"]), len(self.required))
        self.assertEqual(bodies, {name: (self.root / name).read_bytes() for name in self.required})
        receipt = RULES.attest(manifest, "context-1", manifest["groups"])
        self.assertTrue(receipt["complete"])
        self.assertIsNone(receipt["next_missing"])
        self.assertEqual(self.plan(receipt=receipt, context="context-1")["groups"], [])

    def test_partial_tool_output_recovers_missing_suffix_only_to_eof(self):
        self.write("references/first.md", "# Long\n" + "a" * 2400 + "\n")
        manifest = self.plan()
        first = manifest["groups"][1]
        output = RULES.read_range(manifest, first)
        truncated = output[:len(output) // 2]
        self.assertNotIn(b"\nEND ", truncated)
        # Simulate caller detecting a missing footer and attesting only a known text prefix.
        header_size = output.index(b"\n") + 1
        observed_end = first["start"] + len(truncated) - header_size
        observed = [manifest["groups"][0], {**first, "end": observed_end}]
        receipt = RULES.attest(manifest, "context-1", observed)
        self.assertFalse(receipt["complete"])
        self.assertEqual(receipt["next_missing"]["start"], observed_end)
        recovery = self.plan(receipt=receipt, context="context-1")
        self.assertEqual(recovery["groups"][0]["start"], observed_end)
        self.assertTrue(all(g["path"] != "SKILL.md" for g in recovery["groups"]))
        final = RULES.attest(recovery, "context-1", recovery["groups"], receipt)
        self.assertTrue(final["complete"])

    def test_gaps_overlaps_interruptions_and_cancellation_never_infer_coverage(self):
        manifest = self.plan()
        no_read = RULES.attest(manifest, "context-1")
        for group in manifest["groups"]:
            RULES.read_range(manifest, group)
        self.assertFalse(no_read["complete"])
        group = manifest["groups"][0]
        partial = RULES.attest(manifest, "context-1", [dict(group, start=5, end=10)])
        self.assertEqual(partial["next_missing"], dict(group, end=5))
        overlap = RULES.attest(manifest, "context-1", [dict(group, end=8)], partial)
        self.assertEqual(overlap["observed"][group["path"]], [[0, 10]])

    def test_compaction_preserves_identity_but_requires_missing_current_stage_text(self):
        manifest = self.plan()
        complete = RULES.attest(manifest, "before", manifest["groups"])
        recovered = self.plan(receipt=complete, context="after")
        self.assertEqual(recovered["groups"], manifest["groups"])
        self.assertEqual(recovered["package_hash"], complete["package_hash"])
        context = RULES.attest(manifest, "after", previous=complete)
        self.assertFalse(context["complete"])
        self.assertEqual(context["observed"], {})
        with self.assertRaisesRegex(ValueError, "context"):
            self.plan(receipt=complete)

    def test_optional_other_stage_rules_are_inventory_only(self):
        self.write("references/optional.md", "# Later stage\n" + "x" * 2000)
        manifest = self.plan()
        self.assertIn("references/optional.md", [f["path"] for f in manifest["files"]])
        self.assertNotIn("references/optional.md", [g["path"] for g in manifest["groups"]])
        self.assertTrue(RULES.attest(manifest, "now", manifest["groups"])["complete"])

    def test_changed_package_file_stage_and_selection_invalidate_receipts(self):
        manifest = self.plan()
        complete = RULES.attest(manifest, "now", manifest["groups"])
        changed_stage = RULES.plan(self.root, "review", self.required, 1024)
        with self.assertRaisesRegex(ValueError, "identity/stage/selection"):
            RULES.attest(changed_stage, "now", previous=complete)
        changed_selection = RULES.plan(self.root, "implement", self.required[:1], 1024)
        with self.assertRaisesRegex(ValueError, "identity/stage/selection"):
            RULES.attest(changed_selection, "now", previous=complete)
        self.write("references/first.md", "# Changed\n")
        for call in (lambda: RULES.read_range(manifest, manifest["groups"][0]),
                     lambda: RULES.attest(manifest, "now", previous=complete),
                     lambda: self.plan(receipt=complete, context="now")):
            with self.assertRaisesRegex(ValueError, "changed"):
                call()

    def test_missing_and_unreadable_files_stop_with_exact_path(self):
        missing = self.root / "references/second.md"
        missing.unlink()
        with self.assertRaisesRegex(ValueError, re.escape(str(missing))):
            self.plan()
        self.write("references/second.md", "Rules\n")
        original = Path.read_bytes

        def denied(path):
            if path == missing:
                raise PermissionError("fixture permission denied")
            return original(path)

        with mock.patch.object(Path, "read_bytes", denied):
            with self.assertRaisesRegex(ValueError, re.escape(str(missing))):
                self.plan()

    def test_escaping_absolute_hidden_markdown_and_symlink_edges_are_rejected(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("Outside\n")
        for target in ("../../outside.md", "%2e%2e/%2e%2e/outside.md", str(outside), "../hidden.md"):
            with self.subTest(target=target):
                self.write("references/first.md", f"[bad]({target})\n")
                self.write("hidden.md", "Hidden\n")
                with self.assertRaises(ValueError):
                    self.plan()
        self.write("references/first.md", "[resource](../data.txt)\n")
        link = self.root / "data.txt"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this platform")
        with self.assertRaisesRegex(ValueError, "data.txt"):
            self.plan()
        link.unlink()
        (self.root / "references/alias").symlink_to(self.root / "references", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "alias"):
            self.plan()

    def test_nonregular_invalid_utf8_and_missing_selected_file_fail(self):
        self.write("references/first.md", "[directory](.)\n")
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            self.plan()
        (self.root / "references/first.md").write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            self.plan()
        self.write("references/first.md", "Rules\n")
        with self.assertRaisesRegex(ValueError, "missing.md"):
            RULES.plan(self.root, "test", ["references/missing.md"], 1024)

    def test_budget_character_range_and_input_boundaries(self):
        for budget, reserve in ((0, 0), (100, 100), (100, -1), (1, 0)):
            with self.subTest(budget=budget, reserve=reserve), self.assertRaises(ValueError):
                RULES.plan(self.root, "test", self.required, budget, reserve)
        self.write("references/first.md", chr(0x1F600))
        manifest = self.plan()
        for start, end in ((0, 1), (1, 4), (0, 5), (-1, 2), (0, 0)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                RULES.attest(manifest, "now", [{"path": "references/first.md", "start": start, "end": end}])
        group = {"path": "references/first.md", "start": 1, "end": 4}
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            RULES.read_range(manifest, group)
        with self.assertRaisesRegex(ValueError, "not selected"):
            RULES.read_range(manifest, {"path": "other.md", "start": 0, "end": 1})

    def test_cli_end_to_end_read_only_and_failure_exit_status(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

        def cli(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, timeout=30)

        result = cli("plan", "--package", self.root, "--stage", "test", "--required", "SKILL.md",
                     "--budget-bytes", 1024, "--reserve-bytes", 80)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        path = self.root.parent / "manifest.json"
        path.write_text(json.dumps(manifest))
        read = cli("read", "--manifest", path, "--group", 0)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(read.stdout, RULES.read_range(manifest, manifest["groups"][0]))
        receipt = cli("receipt", "--manifest", path, "--context", "now", "--observed",
                      "SKILL.md:0:" + str(manifest["files"][0]["bytes"]))
        self.assertEqual(receipt.returncode, 0, receipt.stderr)
        self.assertTrue(json.loads(receipt.stdout)["complete"])
        self.assertEqual(cli("inventory", "--package", self.root).returncode, 0)
        bad = cli("read", "--manifest", path, "--group", -1)
        self.assertEqual(bad.returncode, 2)
        (self.root / "references/second.md").unlink()
        missing = cli("inventory", "--package", self.root)
        self.assertEqual(missing.returncode, 2)
        self.assertIn(str(self.root / "references/second.md").encode(), missing.stderr)
        self.write("references/second.md", before[Path("references/second.md")].decode())
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_malformed_receipts_cannot_claim_complete_coverage(self):
        manifest = self.plan()
        complete = RULES.attest(manifest, "now", manifest["groups"])
        for ranges in ([[[-1, 200]]], [[[0, 100000]]], [[[5, 10], [0, 5]]], [[[0, 5], [4, 10]]]):
            previous = dict(complete, observed={"SKILL.md": ranges[0]})
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                self.plan(receipt=previous, context="now")

    def test_independent_receipts_do_not_share_observed_coverage(self):
        manifest = self.plan()
        first = RULES.attest(manifest, "task-1", manifest["groups"])
        second = RULES.attest(manifest, "task-2")
        self.assertTrue(first["complete"])
        self.assertFalse(second["complete"])
        self.assertEqual(second["observed"], {})

    def test_symlink_components_are_rejected_even_before_dot_segments(self):
        link = self.root / "alias"
        try:
            link.symlink_to(self.root / "references", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this platform")
        self.write("references/first.md", "[hidden symlink](../alias/../SKILL.md)\n")
        with self.assertRaisesRegex(ValueError, "alias"):
            self.plan()
        link.unlink()
        link.symlink_to(link)
        self.write("references/first.md", "[loop](../alias)\n")
        with self.assertRaisesRegex(ValueError, "alias"):
            self.plan()

    def test_actual_stage_inventory_and_small_budget_are_complete(self):
        package = SCRIPT.parent.parent
        inv = RULES.inventory(package)
        required = [file["path"] for file in inv["files"]]
        manifest = RULES.plan(package, "fixture-all-rules", required, 1024, 80)
        self.assertTrue(manifest["groups"])
        for group in manifest["groups"]:
            self.assertLessEqual(len(RULES.read_range(manifest, group)) + 80, 1024)
        self.assertTrue(RULES.attest(manifest, "fixture", manifest["groups"])["complete"])


if __name__ == "__main__":
    unittest.main()
