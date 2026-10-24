"""Verify run workspace ownership rules and the read-only worktree inventory.

The fixture tests create temporary Git repositories with linked worktrees and
check the inventory and every removal exclusion it can observe. The static
tests check that the rules and documents require the ownership record, the
outside-directory exception, and every exclusion. They do not prove that a
cleanup Agent follows the rules or actually removes a real worktree.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
WORK_CYCLE = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle"
REVIEW = REPO / "plugins/review-and-merge/skills/forge-steward-review-and-merge"
CONCURRENCY = WORK_CYCLE / "references/concurrency.md"
RUN_RECORD = WORK_CYCLE / "references/run-record.md"
OWNERSHIP = WORK_CYCLE / "references/workspace-ownership.md"
BRANCH_CLEANUP = REVIEW / "references/branch-cleanup.md"
POST_MERGE = REVIEW / "references/post-merge.md"
INVENTORY = REVIEW / "scripts/worktree_inventory.py"
README = REPO / "README.md"
SCENARIOS = REPO / "docs/work-cycle-scenarios.md"
CLEANUP_SCENARIOS = REPO / "docs/branch-cleanup-scenarios.md"


def normalized(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip().lower()


def same_path(left, right):
    return (os.path.normcase(os.path.realpath(os.path.abspath(str(left))))
            == os.path.normcase(os.path.realpath(os.path.abspath(str(right)))))


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=str(cwd), check=True, capture_output=True)


class InventoryFixture(unittest.TestCase):
    """Temporary repository with worktrees in and outside the conventional directory."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git("init", "-q", cwd=self.repo)
        git("config", "user.name", "Test", cwd=self.repo)
        git("config", "user.email", "test@example.test", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.repo)
        git("commit", "-qm", "initial", cwd=self.repo)
        self.conventional = self.root / "repo-forge-steward"
        self.conventional.mkdir()
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.sequence = 0

    def worktree(self, branch, parent=None, detach=False):
        self.sequence += 1
        path = (self.root / "outside" if parent is None else parent) / ("wt-%d" % self.sequence)
        path.parent.mkdir(parents=True, exist_ok=True)
        arguments = ["worktree", "add", "-q"]
        if detach:
            arguments.append("--detach")
        else:
            arguments.extend(["-b", branch])
        arguments.append(str(path))
        git(*arguments, cwd=self.repo)
        return path

    def ownership(self, entries):
        path = self.run_dir / "workspaces.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return path

    def entry(self, workspace, status="finished", **overrides):
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(workspace),
                                check=True, capture_output=True, text=True).stdout.strip()
        entry = {"task": "implement-42", "branch": branch, "workspace": str(workspace),
                 "stage": "implement", "status": status, "updated_at": "2026-10-17T13:00:00Z"}
        entry.update(overrides)
        return entry

    def run_inventory(self, *arguments, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", str(INVENTORY), "--repo", str(self.repo), *arguments],
            capture_output=True, text=True, cwd=str(cwd or self.root))

    def report(self, *arguments):
        result = self.run_inventory(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def item(self, report, path):
        for worktree in report["worktrees"]:
            if same_path(worktree["path"], path):
                return worktree
        self.fail("worktree not in inventory: %s" % path)


class WorktreeInventoryTests(InventoryFixture):
    def test_inventory_lists_every_worktree_with_its_facts(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        report = self.report("--deletable-branch", "issue-42")

        self.assertEqual(len(report["worktrees"]), 2)
        self.assertEqual(report["ownership_entries"], 0)
        self.assertEqual(os.path.realpath(report["conventional_root"]),
                         os.path.realpath(self.conventional))
        item = self.item(report, outside)
        self.assertEqual(item["branch"], "issue-42")
        self.assertRegex(item["head"], r"^[0-9a-f]{40,64}$")
        self.assertFalse(item["inside_conventional"])
        self.assertFalse(item["detached"])
        self.assertFalse(item["locked"])
        self.assertFalse(item["dirty"])
        self.assertFalse(item["untracked"])
        self.assertIsNone(item["ownership"])
        self.assertIsNone(item["status_error"])
        self.assertFalse(item["removal_allowed"])
        self.assertFalse(self.item(report, self.repo)["removal_allowed"])

    def test_recorded_outside_worktree_is_removable_when_every_condition_holds(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        record = self.ownership([self.entry(outside)])
        report = self.report("--ownership", str(record), "--deletable-branch", "issue-42")

        item = self.item(report, outside)
        self.assertTrue(item["removal_allowed"])
        self.assertEqual(item["retain_reasons"], [])
        self.assertEqual(item["ownership"]["status"], "finished")
        self.assertEqual(len(report["removable"]), 1)
        self.assertTrue(same_path(report["removable"][0], outside))
        self.assertEqual(report["ownership_entries"], 1)

    def test_conventional_worktree_removal_does_not_need_a_record(self):
        inside = self.worktree("issue-43", parent=self.conventional)
        report = self.report("--deletable-branch", "issue-43")
        item = self.item(report, inside)
        self.assertTrue(item["inside_conventional"])
        self.assertIsNone(item["ownership"])
        self.assertTrue(item["removal_allowed"])
        self.assertEqual(item["retain_reasons"], [])

    def test_explicit_detached_identity_is_verified_but_never_removable(self):
        detached = self.worktree(None, detach=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(detached),
                              check=True, capture_output=True, text=True).stdout.strip()
        record = self.ownership([self.entry(detached, branch=None, detached=True, head=head.upper())])
        report = self.report("--ownership", str(record), "--deletable-branch", "issue-42")
        item = self.item(report, detached)
        self.assertIsNone(item["ownership"]["branch"])
        self.assertTrue(item["ownership"]["detached"])
        self.assertEqual(item["ownership"]["head"], head)
        self.assertTrue(item["ownership_identity_verified"])
        self.assertEqual(item["ownership_identity_reasons"], [])
        self.assertEqual(item["retain_reasons"], ["detached HEAD"])
        self.assertFalse(item["removal_allowed"])
        self.assertEqual(report["removable"], [])

    def test_attached_records_remain_compatible_with_optional_identity_fields(self):
        attached = self.worktree("issue-42")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(attached),
                              check=True, capture_output=True, text=True).stdout.strip()
        for fields in ({}, {"detached": False}, {"detached": False, "head": head}):
            with self.subTest(fields=fields):
                record = self.ownership([self.entry(attached, **fields)])
                item = self.item(self.report("--ownership", str(record),
                                             "--deletable-branch", "issue-42"), attached)
                self.assertTrue(item["ownership_identity_verified"])
                self.assertTrue(item["removal_allowed"])

    def test_legacy_and_incomplete_detached_identity_is_readable_and_retained(self):
        detached = self.worktree(None, parent=self.conventional, detach=True)
        for fields in ({"branch": ""}, {"branch": None}, {"branch": "  "},
                       {"branch": None, "detached": True},
                       {"branch": None, "detached": False}):
            with self.subTest(fields=fields):
                record = self.ownership([self.entry(detached, **fields)])
                item = self.item(self.report("--ownership", str(record)), detached)
                self.assertFalse(item["ownership_identity_verified"])
                self.assertTrue(any("unverified ownership" in reason
                                    for reason in item["retain_reasons"]))
                self.assertFalse(item["removal_allowed"])

        attached = self.worktree("issue-42", parent=self.conventional)
        record = self.ownership([self.entry(attached, branch=None)])
        item = self.item(self.report("--ownership", str(record),
                                     "--deletable-branch", "issue-42"), attached)
        self.assertFalse(item["ownership_identity_verified"])
        self.assertFalse(item["removal_allowed"])
        self.assertTrue(any("unverified ownership" in reason for reason in item["retain_reasons"]))

    def test_changed_or_contradictory_identity_is_retained(self):
        attached = self.worktree("issue-42", parent=self.conventional)
        detached = self.worktree(None, detach=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(detached),
                              check=True, capture_output=True, text=True).stdout.strip()
        cases = [(attached, {"branch": None, "detached": True, "head": head}, "attached worktree"),
                 (attached, {"branch": "issue-42", "detached": True}, "flag disagree"),
                 (attached, {"branch": "other"}, "branch does not match"),
                 (detached, {"branch": None, "detached": True, "head": "0" * len(head)},
                  "head does not match")]
        for path, fields, reason in cases:
            with self.subTest(fields=fields):
                record = self.ownership([self.entry(path, **fields)])
                item = self.item(self.report("--ownership", str(record),
                                             "--deletable-branch", "issue-42"), path)
                self.assertFalse(item["ownership_identity_verified"])
                self.assertFalse(item["removal_allowed"])
                self.assertTrue(any(reason in text for text in item["retain_reasons"]))

        record = self.ownership([self.entry(detached, branch=None, detached=True, head=head)])
        (detached / "tracked.txt").write_text("new commit\n", encoding="utf-8")
        git("commit", "-qam", "advance detached head", cwd=detached)
        item = self.item(self.report("--ownership", str(record)), detached)
        self.assertIn("recorded head does not match the worktree head", item["retain_reasons"])

        record = self.ownership([self.entry(detached, branch=None, detached=True, head="a" * 64)])
        item = self.item(self.report("--ownership", str(record)), detached)
        self.assertEqual(item["ownership"]["head"], "a" * 64)
        self.assertFalse(item["removal_allowed"])

    def test_explicit_detached_identity_preserves_all_workspace_exclusions(self):
        detached = self.worktree(None, detach=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(detached),
                              check=True, capture_output=True, text=True).stdout.strip()
        (detached / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (detached / "new.txt").write_text("new\n", encoding="utf-8")
        git("worktree", "lock", str(detached), cwd=self.repo)
        record = self.ownership([self.entry(detached, status="active", branch=None,
                                            detached=True, head=head)])
        item = self.item(self.report("--ownership", str(record), "--current", str(detached),
                                     "--active", str(detached)), detached)
        self.assertTrue(item["ownership_identity_verified"])
        self.assertFalse(item["removal_allowed"])
        for reason in ("detached HEAD", "the owning stage is still active", "locked worktree",
                       "the workspace running this skill", "listed as active by the caller",
                       "uncommitted changes", "untracked files"):
            self.assertIn(reason, item["retain_reasons"])

    def test_removable_verdict_allows_a_real_outside_removal_without_force(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        record = self.ownership([self.entry(outside)])
        report = self.report("--ownership", str(record), "--deletable-branch", "issue-42")
        self.assertTrue(self.item(report, outside)["removal_allowed"])

        git("worktree", "remove", str(outside), cwd=self.repo)
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(self.repo),
                                check=True, capture_output=True, text=True).stdout
        remaining = {os.path.normcase(os.path.realpath(line[len("worktree "):]))
                     for line in listed.splitlines() if line.startswith("worktree ")}
        self.assertNotIn(os.path.normcase(os.path.realpath(str(outside))), remaining)
        git("branch", "-d", "issue-42", cwd=self.repo)

    def test_each_safety_exclusion_retains_the_worktree_with_its_reason(self):
        dirty = self.worktree("issue-44", parent=self.root / "outside")
        (dirty / "tracked.txt").write_text("changed\n", encoding="utf-8")
        untracked = self.worktree("issue-45", parent=self.root / "outside")
        (untracked / "new.txt").write_text("new\n", encoding="utf-8")
        locked = self.worktree("issue-46", parent=self.root / "outside")
        git("worktree", "lock", str(locked), "--reason", "test lock", cwd=self.repo)
        detached = self.worktree(None, parent=self.root / "outside", detach=True)
        current = self.worktree("issue-47", parent=self.root / "outside")
        active = self.worktree("issue-48", parent=self.root / "outside")
        open_request = self.worktree("issue-49", parent=self.root / "outside")
        unmerged = self.worktree("issue-50", parent=self.root / "outside")
        paths = [dirty, untracked, locked, detached, current, active, open_request, unmerged]
        record = self.ownership([self.entry(path) for path in paths])
        report = self.report("--ownership", str(record),
                             "--deletable-branch", "issue-44",
                             "--deletable-branch", "issue-45",
                             "--deletable-branch", "issue-46",
                             "--deletable-branch", "issue-47",
                             "--deletable-branch", "issue-48",
                             "--deletable-branch", "issue-49",
                             "--current", str(current),
                             "--active", str(active),
                             "--open-request", "issue-49")
        expected = {
            dirty: "uncommitted changes",
            untracked: "untracked files",
            locked: "locked worktree",
            detached: "detached HEAD",
            current: "the workspace running this skill",
            active: "listed as active by the caller",
            open_request: "an open change request uses branch issue-49",
            unmerged: "branch is not confirmed deletable",
        }
        for path, phrase in expected.items():
            with self.subTest(phrase=phrase):
                item = self.item(report, path)
                self.assertFalse(item["removal_allowed"])
                self.assertTrue(any(phrase.lower() in reason.lower()
                                    for reason in item["retain_reasons"]),
                                item["retain_reasons"])
        self.assertEqual(report["removable"], [])

    def test_unrecorded_and_other_owned_worktrees_are_retained(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        no_record = self.report("--deletable-branch", "issue-42")
        self.assertTrue(any("no ownership record was supplied" in reason
                            for reason in self.item(no_record, outside)["retain_reasons"]))

        other = self.worktree("issue-43", parent=self.root / "outside" / "other")
        record = self.ownership([self.entry(other)])
        report = self.report("--ownership", str(record), "--deletable-branch", "issue-42",
                             "--deletable-branch", "issue-43")
        self.assertTrue(any("not recorded by this run" in reason
                            for reason in self.item(report, outside)["retain_reasons"]))
        self.assertTrue(self.item(report, other)["removal_allowed"])

        active_record = self.ownership([self.entry(other, status="active")])
        report = self.report("--ownership", str(active_record), "--deletable-branch", "issue-43")
        item = self.item(report, other)
        self.assertFalse(item["removal_allowed"])
        self.assertIn("the owning stage is still active", item["retain_reasons"])

    def test_missing_worktree_directory_is_reported_for_pruning(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        record = self.ownership([self.entry(outside)])
        shutil.rmtree(outside)
        report = self.report("--ownership", str(record), "--deletable-branch", "issue-42")
        item = self.item(report, outside)
        self.assertTrue(item["missing"])
        self.assertFalse(item["removal_allowed"])
        self.assertTrue(any("missing" in reason for reason in item["retain_reasons"]))
        self.assertEqual(report["removable"], [])

    def test_ownership_record_errors_are_argument_errors(self):
        outside = self.worktree("issue-42", parent=self.root / "outside")
        valid = self.entry(outside)
        incomplete = dict(valid)
        incomplete.pop("branch")
        unknown = self.entry(outside, status="handed-off")
        relative = dict(valid)
        relative["workspace"] = "relative/workspace"
        cases = {
            "invalid json": "{",
            "not a list": json.dumps({}),
            "missing field": json.dumps([incomplete]),
            "relative path": json.dumps([relative]),
            "unknown status": json.dumps([unknown]),
            "duplicate workspace": json.dumps([valid, dict(valid, task="implement-43")]),
            "duplicate canonical path": json.dumps([
                valid, dict(valid, workspace=str(outside) + os.sep + ".." + os.sep + outside.name)]),
            "branch type": json.dumps([dict(valid, branch=17)]),
            "detached type": json.dumps([dict(valid, detached="true")]),
            "abbreviated head": json.dumps([dict(valid, branch=None, detached=True, head="a" * 39)]),
            "partial sha256 head": json.dumps([dict(valid, head="a" * 41)]),
            "nonhex head": json.dumps([dict(valid, head="z" * 40)]),
            "null head": json.dumps([dict(valid, head=None)]),
            "missing owner": json.dumps([dict(valid, task="")]),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                path = self.run_dir / "bad.json"
                path.write_text(text, encoding="utf-8")
                result = self.run_inventory("--ownership", str(path))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("ownership record", result.stderr)

    def test_non_repository_and_missing_record_are_argument_errors(self):
        plain = self.root / "plain"
        plain.mkdir()
        result = subprocess.run([sys.executable, "-B", str(INVENTORY), "--repo", str(plain)],
                                capture_output=True, text=True, cwd=str(self.root))
        self.assertEqual(result.returncode, 2)
        result = self.run_inventory("--ownership", str(self.root / "missing.json"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("ownership record", result.stderr)

    def test_inventory_never_changes_repository_or_worktree_state(self):
        inside = self.worktree("issue-43", parent=self.conventional)
        outside = self.worktree("issue-42", parent=self.root / "outside")
        dirty = self.worktree("issue-44", parent=self.root / "outside")
        (dirty / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (outside / "new.txt").write_text("new\n", encoding="utf-8")
        detached = self.worktree(None, detach=True)
        legacy = self.worktree(None, detach=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(detached),
                              check=True, capture_output=True, text=True).stdout.strip()
        record = self.ownership([self.entry(path) for path in (inside, outside, dirty)]
                                + [self.entry(detached, branch=None, detached=True, head=head),
                                   self.entry(legacy, branch=None)])

        def snapshot():
            return {
                "worktrees": subprocess.run(["git", "worktree", "list", "--porcelain"],
                                            cwd=str(self.repo), check=True,
                                            capture_output=True, text=True).stdout,
                "branches": subprocess.run(["git", "branch", "--list"], cwd=str(self.repo),
                                           check=True, capture_output=True, text=True).stdout,
                "status": subprocess.run(["git", "status", "--porcelain"], cwd=str(self.repo),
                                         check=True, capture_output=True, text=True).stdout,
                "outside": (outside / "new.txt").read_text(encoding="utf-8"),
                "dirty": (dirty / "tracked.txt").read_text(encoding="utf-8"),
                "bytes": {str(path.relative_to(self.root)): path.read_bytes()
                          for path in self.root.rglob("*") if path.is_file()},
            }

        before = snapshot()
        self.report("--ownership", str(record), "--deletable-branch", "issue-42",
                    "--deletable-branch", "issue-43", "--deletable-branch", "issue-44")
        self.assertEqual(snapshot(), before)

        source = INVENTORY.read_text(encoding="utf-8")
        for forbidden in ('"worktree", "remove"', '"worktree", "prune"', '"worktree", "lock"',
                          '"worktree", "unlock"', '"worktree", "add"', '"worktree", "move"'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn('"worktree", "list"', source)


class OwnershipRuleTests(unittest.TestCase):
    def test_writer_and_reader_share_the_complete_detached_identity_contract(self):
        for path in (RUN_RECORD, CONCURRENCY):
            with self.subTest(path=path):
                self.assertIn("read [workspace ownership](workspace-ownership.md) in full",
                              normalized(path))
        text = normalized(OWNERSHIP)
        for phrase in ("`branch: null`", "`detached: true`", "`head`", "40- or 64-digit",
                       "before dispatch", "after confirmed completion", "reread its identity",
                       "legacy empty/null", "unverified", "old readers", "retain the worktree",
                       "does not authorize removal", "only the orchestrator writes it"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_concurrency_requires_the_run_scoped_ownership_record(self):
        text = normalized(CONCURRENCY)
        for phrase in ("workspaces.json", "run directory", "one entry per dispatched workspace",
                       "`task`", "`branch`", "absolute `workspace` path", "owning `stage`",
                       "`status`", "before dispatch", "after confirmed completion",
                       "never writes tracked files", "`handoff.json` schema unchanged",
                       "never infer ownership from a path"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_run_record_documents_the_record_fields_and_update_points(self):
        text = normalized(RUN_RECORD)
        for phrase in ("workspaces.json", "json list of entries", "`task`", "`branch`",
                       "absolute `workspace` path", "owning `stage`", "`status`", "`updated_at`",
                       "before dispatch", "after confirmed completion", "`active`", "`finished`",
                       "`failed`", "`paused`", "changes no tracked files",
                       "does not change the `handoff.json` schema",
                       "never infers ownership from a path"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_branch_cleanup_allows_outside_removal_only_with_recorded_ownership(self):
        text = normalized(BRANCH_CLEANUP)
        for phrase in ("this run's ownership record", "names this exact worktree path",
                       "never infer ownership from a path alone", "no uncommitted or untracked files",
                       "unlocked", "not current", "not detached", "not caller-listed active",
                       "no other active stage or run owns it", "no open change request uses it",
                       "matching head", "scripts/worktree_inventory.py", "never deletes or prunes"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_post_merge_uses_the_same_recorded_ownership_exception(self):
        text = normalized(POST_MERGE)
        for phrase in ("caller-supplied run ownership record names this exact worktree path",
                       "never infer ownership from a path alone", "no open request uses it",
                       "leave unrecorded external locations"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_documents_describe_the_record_outside_removal_and_every_exclusion(self):
        readme = normalized(README)
        for phrase in ("workspaces.json", "ownership record", "outside the conventional workspace "
                       "directory", "dirty", "untracked", "locked", "current", "detached",
                       "other-owned", "unmerged", "open-request", "never infers ownership"):
            with self.subTest(document="readme", phrase=phrase):
                self.assertIn(phrase, readme)
        scenarios = normalized(SCENARIOS)
        for phrase in ("workspaces.json", "recorded outside-directory worktree",
                       "unrecorded outside-directory worktree", "worktree safety exclusions",
                       "dirty", "untracked", "locked", "current", "detached", "unmerged",
                       "open change request", "never infer ownership from a path",
                       "every safety condition holds"):
            with self.subTest(document="scenarios", phrase=phrase):
                self.assertIn(phrase, scenarios)
        cleanup = normalized(CLEANUP_SCENARIOS)
        for number in range(28, 39):
            with self.subTest(scenario="b%02d" % number):
                self.assertIn("| b%02d |" % number, cleanup)
        for phrase in ("workspaces.json", "unrecorded", "ownership", "never infer ownership"):
            with self.subTest(document="cleanup scenarios", phrase=phrase):
                self.assertIn(phrase, cleanup)


if __name__ == "__main__":
    unittest.main()
