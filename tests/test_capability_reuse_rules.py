"""Executable walkthrough of the documented capability contract, not a cache API.

The fake adapter calls no tools, services, Agent, real clock, or credentials.
Counters compare fresh discovery at every stage with the documented reuse policy.
Static guards connect that model to the installed rules; neither proves real
Agent compliance, production speed, or a working platform integration.
"""

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[1]
RULES = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/references"
NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
IDENTITY = {
    "adapter": "fixture", "host": "public-forge", "repository": "repo-id",
    "tool": "fixture-cli", "tool_version": "1", "runtime": "macos",
    "runtime_version": "1", "config_fingerprint": "safe-profile-revision-1",
    "auth_mechanism": "cli-session",
}
FIELDS = {"identity", "capability", "observed_at", "revalidate_by", "choice",
          "result", "coverage", "revalidate_when"}


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


class FakeAdapter:
    """Only identifier allowlists cross the fixture's persistence boundary."""

    CANDIDATES = {
        "bounded-wait": (("timeout-command", "unsupported"), ("bounded-process", "working")),
        "pagination": (("unsupported-pagination-flag", "unsupported"), ("explicit-pages", "working")),
        "repository-read": (("unauthenticated-route", "denied"), ("authenticated-api", "working")),
        "alert-read": (("alert-endpoint", "denied"),),
        "optional-flag": (("unsupported-optional-flag", "unsupported"),),
    }

    def __init__(self):
        self.identity = copy.deepcopy(IDENTITY)
        self.identity_known = True
        self.permission_revision = "unchanged"
        self.probes = 0
        self.failed_invocations = 0
        self.identity_checks = 0
        self.mutable_reads = 0
        self.raw_output = ""
        self.fail_reuse = False
        self.history = []

    def cheap_identity(self):
        self.identity_checks += 1
        return copy.deepcopy(self.identity) if self.identity_known else None

    def discover(self, capability, now):
        for choice, result in self.CANDIDATES[capability]:
            self.probes += 1
            self.history.append(choice)
            self.failed_invocations += result != "working"
            if result == "working":
                break
        # Raw output is deliberately excluded, even if it looks useful.
        return {
            "identity": copy.deepcopy(self.identity), "capability": capability,
            "observed_at": stamp(now), "revalidate_by": stamp(now + timedelta(hours=1)),
            "choice": choice, "result": result,
            "coverage": "fixture-source" if result == "working" else "uncovered:fixture-source",
            "revalidate_when": "identity-or-permission-change:" + self.permission_revision,
        }

    def current_read(self, choice):
        self.mutable_reads += 1
        return {"revision": self.mutable_reads, "method": choice}


def usable(record, run, identity, capability, now, permission_revision):
    if not identity or set(identity) != set(IDENTITY) or not all(identity.values()):
        return None
    if not isinstance(record, dict) or record.get("schema") != 1 or record.get("run") != run:
        return None
    entries = record.get("entries")
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        return None
    matches = [e for e in entries if e.get("capability") == capability and e.get("identity") == identity]
    if len(matches) != 1:
        return None
    entry = matches[0]
    if set(entry) != FIELDS or any(not entry[key] for key in FIELDS):
        return None
    try:
        observed = datetime.fromisoformat(entry["observed_at"].replace("Z", "+00:00"))
        deadline = datetime.fromisoformat(entry["revalidate_by"].replace("Z", "+00:00"))
        if observed.tzinfo != timezone.utc or deadline.tzinfo != timezone.utc or not observed <= now < deadline:
            return None
    except (TypeError, ValueError, AttributeError):
        return None
    if (entry["result"] not in ("working", "unsupported", "denied")
            or entry["revalidate_when"] != "identity-or-permission-change:" + permission_revision):
        return None
    if (entry["choice"], entry["result"]) not in FakeAdapter.CANDIDATES[capability]:
        return None
    return copy.deepcopy(entry)


def stage(adapter, capability, record=None, run="fixture-run", now=NOW, stop=False):
    """A stage returns a proposed observation; it never mutates shared state."""
    if stop:
        return {"decision": "stopped", "proposal": None, "remote": None}
    identity = adapter.cheap_identity()
    entry = usable(record, run, identity, capability, now, adapter.permission_revision)
    decision = "reuse" if entry else "discover"
    if entry and adapter.fail_reuse:
        adapter.fail_reuse = False
        adapter.failed_invocations += 1
        entry = None
        decision = "rediscover-after-failure"
    proposal = None
    if entry is None:
        entry = adapter.discover(capability, now)
        # Unknown identity must not become an apparently reusable observation.
        proposal = entry if identity else None
    remote = adapter.current_read(entry["choice"]) if entry["result"] == "working" else None
    return {"decision": decision, "proposal": proposal, "remote": remote,
            "result": entry["result"], "coverage": entry["coverage"]}


def aggregate(record, observations, run="fixture-run", revalidated=False):
    """The orchestrator collects already sanitized proposals without hiding conflicts."""
    result = copy.deepcopy(record) if record else {"schema": 1, "run": run, "entries": []}
    if revalidated:
        keys = [(e["identity"], e["capability"]) for e in observations if e is not None]
        result["entries"] = [e for e in result["entries"]
                             if (e["identity"], e["capability"]) not in keys]
    for observation in observations:
        if observation is not None and observation not in result["entries"]:
            result["entries"].append(copy.deepcopy(observation))
    return result


def walkthrough(capability, reuse=True):
    adapter, record = FakeAdapter(), None
    decisions = []
    for minute in (0, 1):
        result = stage(adapter, capability, record if reuse else None, now=NOW + timedelta(minutes=minute))
        decisions.append(result["decision"])
        record = aggregate(record, [result["proposal"]])
    return {"probes": adapter.probes, "failed_invocations": adapter.failed_invocations,
            "identity_checks": adapter.identity_checks, "current_reads": adapter.mutable_reads,
            "decisions": decisions}


def scenarios():
    return {capability: {"baseline": walkthrough(capability, False), "reuse": walkthrough(capability)}
            for capability in FakeAdapter.CANDIDATES}


class CapabilityScenarioTests(unittest.TestCase):
    def saved(self, capability="repository-read"):
        adapter = FakeAdapter()
        result = stage(adapter, capability)
        return adapter, aggregate(None, [result["proposal"]])

    def test_unchanged_stages_skip_known_failed_choices_with_cheap_checks(self):
        for capability, counts in scenarios().items():
            with self.subTest(capability=capability):
                baseline, reuse = counts["baseline"], counts["reuse"]
                self.assertEqual(reuse["decisions"], ["discover", "reuse"])
                self.assertEqual(reuse["probes"] * 2, baseline["probes"])
                self.assertEqual(reuse["failed_invocations"], 1)
                self.assertEqual(baseline["failed_invocations"], 2)
                self.assertEqual(reuse["identity_checks"], 2)
        self.assertEqual(scenarios()["bounded-wait"]["reuse"]["probes"], 2)

    def test_working_authenticated_method_and_current_remote_reads_are_reused_separately(self):
        adapter, record = self.saved()
        result = stage(adapter, "repository-read", record, now=NOW + timedelta(minutes=1))
        self.assertEqual(adapter.history, ["unauthenticated-route", "authenticated-api"])
        self.assertEqual(result["remote"], {"revision": 2, "method": "authenticated-api"})
        self.assertEqual(adapter.mutable_reads, 2)
        self.assertNotIn("remote", record["entries"][0])

    def test_every_identity_component_change_invalidates_and_does_not_mutate_saved_evidence(self):
        for key in IDENTITY:
            with self.subTest(key=key):
                adapter, record = self.saved()
                saved = copy.deepcopy(record)
                adapter.identity[key] += "-changed"
                result = stage(adapter, "repository-read", record)
                self.assertEqual(result["decision"], "discover")
                self.assertEqual(adapter.probes, 4)
                self.assertEqual(record, saved)

    def test_missing_old_stale_ambiguous_malformed_and_unknown_records_fall_back(self):
        _, original = self.saved()
        cases = [None, {}, {**original, "run": "other-run"}, {**original, "schema": 2},
                 {**original, "entries": "malformed"}, {**original, "entries": [None]}]
        for field, value in (("observed_at", stamp(NOW + timedelta(seconds=1))),
                             ("revalidate_by", stamp(NOW)), ("revalidate_by", "unknown"),
                             ("revalidate_by", "2026-10-25T00:00:00"), ("choice", "")):
            changed = copy.deepcopy(original)
            changed["entries"][0][field] = value
            cases.append(changed)
        duplicate = copy.deepcopy(original)
        duplicate["entries"].append(copy.deepcopy(duplicate["entries"][0]))
        cases.append(duplicate)
        missing = copy.deepcopy(original)
        del missing["entries"][0]["coverage"]
        cases.append(missing)
        for record in cases:
            with self.subTest(record=record):
                result = stage(FakeAdapter(), "repository-read", record)
                self.assertEqual(result["decision"], "discover")
        adapter = FakeAdapter()
        adapter.identity_known = False
        self.assertIsNone(stage(adapter, "repository-read", original)["proposal"])

    def test_revalidation_replaces_only_affected_entries_and_retains_prior_evidence(self):
        adapter, record = self.saved()
        saved = copy.deepcopy(record)
        result = stage(adapter, "repository-read", record, now=NOW + timedelta(hours=2))
        refreshed = aggregate(record, [result["proposal"]], revalidated=True)
        self.assertEqual(len(refreshed["entries"]), 1)
        self.assertEqual(stage(adapter, "repository-read", refreshed,
                               now=NOW + timedelta(hours=2, minutes=1))["decision"], "reuse")
        self.assertEqual(record, saved)

    def test_permission_denial_remains_uncovered_and_is_not_reprobed_unchanged(self):
        adapter, record = self.saved("alert-read")
        result = stage(adapter, "alert-read", record)
        self.assertEqual((result["decision"], result["result"]), ("reuse", "denied"))
        self.assertEqual(result["coverage"], "uncovered:fixture-source")
        self.assertIsNone(result["remote"])
        self.assertEqual((adapter.probes, adapter.mutable_reads), (1, 0))
        adapter.permission_revision = "safe-permission-change"
        self.assertEqual(stage(adapter, "alert-read", record)["decision"], "discover")
        self.assertEqual(adapter.probes, 2)
        # Expiration prompts revalidation; it does not turn denial into success.
        expired = stage(adapter, "alert-read", record, now=NOW + timedelta(hours=2))
        self.assertEqual(expired["result"], "denied")
        self.assertEqual(expired["coverage"], "uncovered:fixture-source")

    def test_unsupported_gap_and_untrusted_choice_do_not_become_authority(self):
        adapter, record = self.saved("optional-flag")
        result = stage(adapter, "optional-flag", record)
        self.assertEqual((result["decision"], result["result"]), ("reuse", "unsupported"))
        self.assertEqual(adapter.probes, 1)
        self.assertIsNone(result["remote"])
        record["entries"][0]["choice"] = "arbitrary-stored-command"
        self.assertEqual(stage(adapter, "optional-flag", record)["decision"], "discover")
        self.assertNotIn("arbitrary-stored-command", adapter.history)

    def test_sensitive_output_is_omitted_before_evidence_or_record_persistence(self):
        adapter = FakeAdapter()
        adapter.raw_output = "synthetic-sensitive-value private-service-address credential-hash"
        result = stage(adapter, "repository-read")
        record = aggregate(None, [result["proposal"]])
        serialized = json.dumps({"evidence": result, "record": record})
        for value in adapter.raw_output.split():
            self.assertNotIn(value, serialized)
        self.assertEqual(set(record["entries"][0]), FIELDS)
        self.assertEqual(record["entries"][0]["identity"]["auth_mechanism"], "cli-session")

    def test_concurrent_stage_observations_only_aggregate_through_orchestrator(self):
        adapter, record = self.saved()
        saved = copy.deepcopy(record)
        other = FakeAdapter()
        other.identity["tool"] = "other-cli"
        observation = stage(other, "pagination", record)["proposal"]
        self.assertEqual(record, saved)
        combined = aggregate(record, [observation])
        self.assertEqual(len(combined["entries"]), 2)
        self.assertEqual(stage(adapter, "repository-read", combined)["decision"], "reuse")
        conflict = copy.deepcopy(record["entries"][0])
        conflict["result"], conflict["coverage"] = "denied", "uncovered:fixture-source"
        ambiguous = aggregate(record, [conflict])
        self.assertEqual(stage(adapter, "repository-read", ambiguous)["decision"], "discover")
        self.assertEqual(record, saved)

    def test_stop_compaction_new_run_and_failed_reuse_keep_recovery_boundaries(self):
        adapter, record = self.saved()
        counts = adapter.probes, adapter.identity_checks, adapter.mutable_reads
        self.assertEqual(stage(adapter, "repository-read", record, stop=True)["decision"], "stopped")
        self.assertEqual((adapter.probes, adapter.identity_checks, adapter.mutable_reads), counts)
        restored = json.loads(json.dumps(record))
        self.assertEqual(stage(adapter, "repository-read", restored)["decision"], "reuse")
        self.assertEqual(stage(adapter, "repository-read", restored, run="new-run")["decision"], "discover")
        adapter.fail_reuse = True
        self.assertEqual(stage(adapter, "repository-read", restored)["decision"], "rediscover-after-failure")
        self.assertEqual(record, restored)


class CapabilityRuleGuards(unittest.TestCase):
    def test_all_entry_paths_require_complete_rules_and_preserve_existing_contracts(self):
        for name in ("startup.md", "subagent-lifecycle.md", "run-record.md"):
            text = (RULES / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("](capabilities.md)", text)
                self.assertIn("in full", text)
        self.assertIn("Read `result.md` only for capability observations",
                      (RULES / "subagent-lifecycle.md").read_text(encoding="utf-8"))
        rules = (RULES / "capabilities.md").read_text(encoding="utf-8")
        for phrase in ("Only the orchestrator writes/aggregates", "same current run",
                       "before every reuse", "unsupported flag/command", "uncovered",
                       "credential hashes", "private service addresses", "allowlist",
                       "Read mutable remote state now", "contradictory same-key results",
                       "save sanitized observations", "Rollback ignores it",
                       "never resets CI or call-recovery limits", "static rule checks do not prove speed"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules)
        for name in ("startup.md", "subagent-lifecycle.md", "run-record.md", "capabilities.md"):
            raw = (RULES / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertLessEqual(len(raw) + raw.count(b"\n"), 8000, name)


if __name__ == "__main__":
    if sys.argv[1:] == ["--report"]:
        print(json.dumps(scenarios(), indent=2, sort_keys=True))
    else:
        unittest.main()
