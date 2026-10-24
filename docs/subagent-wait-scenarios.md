# Subagent waiting scenarios

Issue [#207](https://github.com/philfanzhou/ForgeSteward/issues/207) changes the work-cycle orchestrator's normal waiting instructions. The installed rules are [Normal waits](../plugins/work-cycle/skills/forge-steward-work-cycle/references/subagent-lifecycle.md#normal-waits) and the [scheduling table](../plugins/work-cycle/skills/forge-steward-work-cycle/references/concurrency.md#scheduling-table). Recovery still belongs to the existing bounded error flow. No executable production scheduler or runtime API is introduced.

Run the deterministic, standard-library fixture:

```bash
python3 -m unittest discover -s tests -p 'test_subagent_wait_rules.py' -v
python3 tests/test_subagent_wait_rules.py --report
```

The [fixture](../tests/test_subagent_wait_rules.py) advances a simulated clock; it calls no Agent, network, real clock, or token collector. It compares an explicitly modeled baseline of ten-second event waits plus a summary query after every timeout with the new policy. This comparison does not reconstruct every historical wait or assert that every previous caller made an extra query. The source Issue's historical counts are observations, not fixture outputs.

## Measured walkthrough

The default fixture host requires updates every 60 seconds and permits event waits of at most 60 seconds. The policy waits up to that bound, returning early on events. A snapshot-only host queries after 30 seconds, then doubles the interval to 60 seconds after an unchanged read. Its commentary deadlines interrupt sleep segments using saved state, without bringing the next status query forward. A shorter runtime bound also limits each wait. These are fixture host inputs, not universal Agent limits; an adapter must use its actual capabilities and leave time to produce the required update.

Verification and dispatch take zero simulated time, so event-mode latency below is a scheduling result. Real communication, remote verification and dispatch overhead are unmeasured. Snapshot-mode delay measures detection as well as dispatch. Wait/sleep segments include commentary interruptions; status queries, unchanged queries, and timeout returns are separate counters. An unchanged event timeout is not a status query.

| Scenario | Wait/sleep segments | Timeout wakeups | Status queries | Unchanged queries | Completion-to-dispatch delay, seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline, completion at 600 seconds | 60 | 59 | 59 | 59 | 0 |
| Event policy, completion at 600 seconds | 10 | 9 | 0 | 0 | 0 |
| Snapshot policy, completion at 600 seconds | 21 | 0 | 11 | 10 | 30 |
| Event policy, completion at 125 seconds | 3 | 2 | 0 | 0 | 0 |
| Snapshot policy, completion at 125 seconds | 5 | 0 | 3 | 2 | 25 |
| Warning at 5, completion at 125 seconds | 4 | 2 | 0 | 0 | 0 |
| Actual wait error at 5 seconds | 1 | 0 | 0 | 0 | Not dispatched |
| Host update bound 20, completion at 125 seconds | 7 | 6 | 0 | 0 | 0 |

The event trace for the long unchanged stage wakes at 60, 120, ..., 600 seconds. Its nine timeouts retain the original child, owner, evidence path, and last meaningful revision while saving each returned cursor. None rereads full history or `result.md`. The snapshot trace reads at 30, 90, ..., 630 seconds; updates at 60, 120, ..., 600 introduce no extra queries. Its maximum detection delay remains one 60-second polling interval. There is no ten-second loop in either new-policy trace for this host.

At 125 seconds the event completion interrupts the pending wait immediately, rather than waiting until 180 seconds. After normal result/remote verification, that child can advance while an independent child's 600-second stage continues. Existing ownership, dependency, concurrency, review and merge conditions still decide whether its next stage is eligible.

## Outcome and recovery coverage

| Input | Concrete assertion or walkthrough outcome |
| --- | --- |
| Meaningful progress and duplicate revision | Snapshot revisions at 20 and 40 both numbered 1 apply once; the duplicate is an unchanged query. Duplicate completion at the same instant dispatches once. |
| Ordinary timeout | Two waits through 120 leave the child running with no recovery entry, original ownership and saved cursor. |
| Quota warning | One warning is counted; zero recovery entries; completion still dispatches at 125. A warning/duplicate snapshot does not reset backoff. |
| Actual wait error | One recovery entry, state “needs recovery,” original owner retained, zero dispatches. The fixture hands off to the existing recovery flow; it neither retries creation nor replaces the child. Existing three-round recovery rules are unchanged. |
| No cursor/event support | Compact snapshots back off to the host bound; cursor remains absent. Detection delay is reported, including the 25-second mid-wait example, rather than described as immediate. |
| Host deadline or smaller runtime limit | A 20-second host produces updates at 20 through 120 without summary probes. A runtime bound of 15 with a host bound of 60 splits event waits at 15-second boundaries and updates at 60 and 120. |
| Compaction | JSON-round-trip the compact state at 120; the event resume saves cursor 3 and dispatches at 125 without loading evidence. The snapshot resume preserves its next read at 150, requiring one query rather than resetting its deadline. |
| Explicit stop | Stop at 75 prevents the completion at 125 from dispatching and preserves owner/evidence for recovery. It does not claim cancellation of the child. |

Compact state contains only task/owner, cursor if available, last meaningful revision, state, interval/next polling deadline, and evidence path. Full trace output remains in task evidence, outside the scheduling handoff. After compaction the caller also restores missing current-stage rules under the existing entry-point instructions. User updates draw from saved state; they need no history read.

## Token evidence and limits

The report provides four separate fields: `cumulative_input`, `cached_input`, `uncached_input`, and `child_total`. Every field is `null` (unknown) in this simulation because it invokes no model and supplies no token trace. It does not treat unknown as zero, estimate tokens from the number of waits, subtract rounded historical figures, or infer a bill or unique text size. Existing supplied traces can support individual categories; they do not authorize a new global collector.

The table demonstrates fewer coordination calls in this fixture, with completion still waking event waits promptly. It is not a measured production speedup, token-saving percentage, wall-time improvement, or guarantee that an Agent follows the instructions. A real-runtime performance test is unavailable here and remains an explicit verification gap. Core rules stay platform-neutral; adapters select existing APIs. Authorization, untrusted-content handling, required checks, independent reviewers, branch protection, and secrets rules are unchanged. No credential, installation, version, release, persistent protocol, background automation, or configuration migration is included.
