"""Discrete-event walkthrough of the normal-wait rules, not a runtime scheduler.

No Agent, clock, network, or token collector is called. --report prints the same
scenario measurements checked below, separately from static rule/link guards.
"""

import copy
import json
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[1]
RULES = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/references"
TOKEN_FIELDS = ("cumulative_input", "cached_input", "uncached_input", "child_total")


def simulate(events, mode="event", host_bound=60, runtime_bound=60,
             end=660, start=0, restored=None):
    """Replay (second, kind, revision) events against explicitly stated policies.

    The comparison baseline uses ten-second event waits plus a summary query on
    each timeout. The new event policy uses the host/runtime bound and no timeout
    query. Snapshot-only hosts query after half-bound, then doubled intervals.
    Communication, verification and dispatch take zero simulated time; real-world
    latency must be measured separately. Stops are interruptible in this fixture.
    """
    bound = min(host_bound, runtime_bound)
    if bound <= 0 or mode not in ("baseline", "event", "snapshot"):
        raise ValueError("positive bounds and a known mode are required")
    state = copy.deepcopy(restored) if restored else {
        "task": "implement-fixture", "owner": "child-1", "cursor": None,
        "revision": 0, "state": "running", "interval": bound / 2,
        "next_poll": start + bound / 2 if mode == "snapshot" else None,
        "evidence": "implement-fixture/result.md",
    }
    metrics = dict.fromkeys(("wait_calls", "timeout_wakeups", "status_queries",
                            "unchanged_queries", "warnings", "recovery_entries",
                            "full_evidence_reads"), 0)
    metrics.update(dispatch_latency=None, token_categories=dict.fromkeys(TOKEN_FIELDS))
    now, position, cursor = start, 0, state["cursor"] or 0
    trace, updates, dispatched = [], [], []
    deadline = start + host_bound
    next_poll = state["next_poll"]
    events = sorted(events)
    while now < end and state["state"] == "running":
        before = state["revision"]
        interval = min(10, bound) if mode == "baseline" else bound
        if mode == "snapshot":
            interval = min(state["interval"], bound)
        until = min(next_poll if mode == "snapshot" else now + interval, deadline, end)
        available = [e for e in events[position:] if e[0] <= until]
        # An event host wakes immediately. Snapshot hosts cannot see completion
        # until a read, but explicit user cancellation still interrupts a wait.
        waking = available if mode != "snapshot" else [e for e in available if e[1] == "stop"]
        if waking:
            until = waking[0][0]
        now = until
        metrics["wait_calls"] += 1
        if mode == "snapshot" and waking:
            state["state"] = "stopped"
            trace.append({"at": now, "cursor": None,
                          "revision": state["revision"], "state": state["state"]})
            break
        if mode == "snapshot" and now < next_poll:
            # Commentary uses saved state. Its deadline does not cause a query
            # or reset the independently scheduled snapshot/backoff interval.
            if now >= deadline:
                updates.append(now)
                deadline = now + host_bound
            continue
        delivered = []
        while position < len(events) and events[position][0] <= now:
            delivered.append(events[position])
            position += 1
        if mode != "snapshot":
            # A runtime may return an updated opaque cursor even on a timeout.
            cursor += 1
            state["cursor"] = cursor
            if not delivered:
                metrics["timeout_wakeups"] += 1
                if mode == "baseline":
                    metrics["status_queries"] += 1
                    metrics["unchanged_queries"] += 1
        else:
            metrics["status_queries"] += 1
        for at, kind, revision in delivered:
            if kind == "warning":
                metrics["warnings"] += 1
            elif kind == "error":
                metrics["recovery_entries"] += 1
                state["state"] = "needs recovery"
            elif kind == "stop":
                state["state"] = "stopped"
            elif revision > state["revision"] and state["state"] == "running":
                state["revision"] = revision
                if kind == "complete":
                    state["state"] = "complete"
                    dispatched.append(now)
                    metrics["dispatch_latency"] = now - at
        if mode == "snapshot":
            if state["revision"] == before:
                metrics["unchanged_queries"] += 1
                state["interval"] = min(state["interval"] * 2, bound)
            else:
                state["interval"] = bound / 2
            next_poll = now + state["interval"]
            state["next_poll"] = next_poll
        trace.append({"at": now, "cursor": state["cursor"],
                      "revision": state["revision"], "state": state["state"]})
        if now >= deadline:
            updates.append(now)
            deadline = now + host_bound
    return {"state": state, "metrics": metrics, "trace": trace,
            "updates": updates, "dispatched": dispatched}


def scenarios():
    return {
        "long_baseline": simulate([(600, "complete", 1)], "baseline"),
        "long_event": simulate([(600, "complete", 1)]),
        "long_snapshot": simulate([(600, "complete", 1)], "snapshot"),
        "midwait_event": simulate([(125, "complete", 1)]),
        "midwait_snapshot": simulate([(125, "complete", 1)], "snapshot"),
        "warning_event": simulate([(5, "warning", 0), (125, "complete", 1)]),
        "actual_error": simulate([(5, "error", 0)]),
        "short_host": simulate([(125, "complete", 1)], host_bound=20),
    }


class WaitScenarioTests(unittest.TestCase):
    def test_unchanged_long_stage_has_bounded_waits_and_no_repeated_status_reads(self):
        baseline, event = scenarios()["long_baseline"], scenarios()["long_event"]
        self.assertEqual((baseline["metrics"]["wait_calls"], baseline["metrics"]["timeout_wakeups"],
                          baseline["metrics"]["unchanged_queries"]), (60, 59, 59))
        self.assertEqual((event["metrics"]["wait_calls"], event["metrics"]["timeout_wakeups"],
                          event["metrics"]["status_queries"]), (10, 9, 0))
        self.assertEqual([x["at"] for x in event["trace"]], list(range(60, 601, 60)))
        self.assertEqual(event["metrics"]["full_evidence_reads"], 0)
        self.assertEqual(event["state"]["cursor"], 10)
        self.assertEqual(event["state"]["owner"], "child-1")

    def test_completion_interrupts_the_wait_and_does_not_wait_for_another_child(self):
        fast = scenarios()["midwait_event"]
        self.assertEqual(fast["dispatched"], [125])
        self.assertEqual(fast["metrics"]["dispatch_latency"], 0)
        self.assertEqual([x["at"] for x in fast["trace"]], [60, 120, 125])
        slow = scenarios()["long_event"]
        self.assertLess(fast["dispatched"][0], slow["dispatched"][0])

    def test_snapshot_fallback_backs_off_and_reports_its_detection_delay(self):
        long = scenarios()["long_snapshot"]
        self.assertEqual([x["at"] for x in long["trace"]], list(range(30, 631, 60)))
        self.assertEqual(long["metrics"]["status_queries"], 11)
        self.assertEqual(long["metrics"]["unchanged_queries"], 10)
        result = scenarios()["midwait_snapshot"]
        self.assertEqual(result["dispatched"], [150])
        self.assertEqual(result["metrics"]["dispatch_latency"], 25)
        self.assertLessEqual(result["metrics"]["dispatch_latency"], 60)
        self.assertEqual(result["state"]["cursor"], None)

    def test_warnings_timeouts_and_errors_have_distinct_outcomes(self):
        warning = scenarios()["warning_event"]
        self.assertEqual(warning["metrics"]["warnings"], 1)
        self.assertEqual(warning["metrics"]["recovery_entries"], 0)
        self.assertEqual(warning["dispatched"], [125])
        timeout = simulate([], end=120)
        self.assertEqual(timeout["state"]["state"], "running")
        self.assertEqual(timeout["metrics"]["recovery_entries"], 0)
        failure = scenarios()["actual_error"]
        self.assertEqual(failure["state"]["state"], "needs recovery")
        self.assertEqual(failure["metrics"]["recovery_entries"], 1)
        self.assertEqual(failure["dispatched"], [])
        self.assertEqual(failure["state"]["owner"], "child-1")

    def test_host_and_runtime_bounds_allow_updates_without_extra_queries(self):
        result = scenarios()["short_host"]
        self.assertEqual(result["updates"], [20, 40, 60, 80, 100, 120])
        self.assertEqual(result["metrics"]["status_queries"], 0)
        self.assertEqual(result["dispatched"], [125])
        smaller_runtime = simulate([], host_bound=60, runtime_bound=15, end=120)
        self.assertEqual([x["at"] for x in smaller_runtime["trace"]], list(range(15, 121, 15)))
        self.assertEqual(smaller_runtime["updates"], [60, 120])
        snapshot = simulate([], "snapshot", end=120)
        self.assertEqual([x["at"] for x in snapshot["trace"]], [30, 90])
        self.assertEqual(snapshot["updates"], [60, 120])
        self.assertEqual(snapshot["metrics"]["status_queries"], 2)

    def test_meaningful_revisions_apply_once_and_warnings_do_not_reset_backoff(self):
        result = simulate([(20, "progress", 1), (40, "progress", 1),
                           (55, "warning", 0)], "snapshot", end=60)
        self.assertEqual([x["revision"] for x in result["trace"]], [1, 1])
        self.assertEqual(result["state"]["interval"], 60)
        self.assertEqual(result["metrics"]["unchanged_queries"], 1)
        duplicate = simulate([(5, "complete", 1), (5, "complete", 1)])
        self.assertEqual(duplicate["dispatched"], [5])

    def test_compaction_restores_compact_state_without_loading_full_evidence(self):
        first = simulate([], end=120)
        saved = json.loads(json.dumps(first["state"]))
        resumed = simulate([(125, "complete", 1)], start=120, restored=saved)
        self.assertEqual(resumed["dispatched"], [125])
        self.assertEqual(resumed["state"]["cursor"], 3)
        self.assertEqual(resumed["state"]["owner"], saved["owner"])
        self.assertEqual(resumed["state"]["evidence"], saved["evidence"])
        self.assertEqual(resumed["metrics"]["full_evidence_reads"], 0)
        self.assertLess(len(json.dumps(saved)), 250)
        snapshot = simulate([], "snapshot", end=120)
        resumed_snapshot = simulate([(125, "complete", 1)], "snapshot", start=120,
                                    restored=json.loads(json.dumps(snapshot["state"])))
        self.assertEqual(resumed_snapshot["dispatched"], [150])
        self.assertEqual(resumed_snapshot["metrics"]["status_queries"], 1)
        stopped = simulate([(75, "stop", 0), (125, "complete", 1)])
        self.assertEqual(stopped["state"]["state"], "stopped")
        self.assertEqual(stopped["dispatched"], [])
        self.assertEqual(stopped["state"]["evidence"], saved["evidence"])

    def test_token_categories_stay_separate_and_unknown_without_a_trace(self):
        categories = scenarios()["long_event"]["metrics"]["token_categories"]
        self.assertEqual(set(categories), set(TOKEN_FIELDS))
        self.assertTrue(all(value is None for value in categories.values()))


class WaitRuleGuards(unittest.TestCase):
    def test_policy_links_and_semantic_boundaries_remain_in_installed_rules(self):
        lifecycle = (RULES / "subagent-lifecycle.md").read_text(encoding="utf-8")
        for phrase in ("## Normal waits", "actual adapter APIs", "host's required user update",
                       "Resume from the returned cursor", "start at half that bound",
                       "double the interval", "no full history or `result.md`",
                       "actual errors use recovery below", "on explicit stop",
                       "unknown stays unknown", "Full traces stay outside the compact handoff"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, lifecycle)
        concurrency = (RULES / "concurrency.md").read_text(encoding="utf-8")
        self.assertIn("](subagent-lifecycle.md#normal-waits)", concurrency)
        for name in ("subagent-lifecycle.md", "concurrency.md"):
            raw = (RULES / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertLessEqual(len(raw) + raw.count(b"\n"), 8000,
                                 "Reference must fit the existing budget on CRLF checkouts")


if __name__ == "__main__":
    if sys.argv[1:] == ["--report"]:
        print(json.dumps(scenarios(), indent=2, sort_keys=True))
    else:
        unittest.main()
