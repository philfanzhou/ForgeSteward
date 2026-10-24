## Read logs and wait for checks

This file defines phase diagnosis, the saved check handoff, and the single CI wait limit. Stage rules still decide retry eligibility; diagnosis grants no new authorization or retry.

### Wait limit

Use one limit for all required checks of the current Change Request:

- Recent runs are the last 10 successful completed runs of that required check on the default mainline that finished within 90 days.
- Use twice the median completed duration of the recent runs. If no run qualifies, use 30 minutes.
- Cap the limit for each required check at 60 minutes, then use the largest capped limit across all required checks.
- A rerun shares the original limit and does not start a new one. One long historical run cannot raise the limit past the cap.

### Save and restore the check handoff

Before waiting, save the original wait start and absolute deadline, current head, required-check set, each check/run link and result, retry count and original/rerun links in the existing Issue/Change Request or authorized task record. Include phase evidence, unfinished verification, recovery action and its owner. Use public identifiers and redacted relevant log excerpts; never copy secrets or full logs.

Before reinspection, retry, a head change, or handoff between implementation, review, repair and merge-lane inspection, restore and update that same record. Preserve the original deadline and retry history: switching stages, pushing a new head, rerunning, or doing independent work cannot reset them. Verify the required checks on every current head; older green results do not cover a new head. If the record is missing, reconstruct it from run timestamps/history before acting. If it cannot be recovered, report the missing evidence and wait for external action; do not invent a fresh budget or unused retry.

At or beyond the deadline, read current results without starting another wait or retry. Completed green current-head checks may satisfy verification; otherwise retain Waiting for CI with the exact unfinished checks, evidence, next action and owner.

### Find and classify the failure

1. Identify the check, current head, run/attempt, failed or cancelled step, and phase: queue, setup, network, build, test or final verification. Read that step's log backward from the error; expand backward in sections or inspect other relevant steps if needed. Inspect any position needed, never the entire log at once.
2. Record which phases completed, failed, were cancelled or never started. Start local test output with failures, using repository/framework options. Quote only nearby redacted error lines and the run link in the handoff.
3. Apply this table before choosing repair, a permitted retry or external wait. Unknown cause remains unknown. Phase alone does not identify cause: a setup error caused by changed code/configuration still follows repair; claim an external cause only with proof. Cancellation is incomplete verification, not proof that a failure is unrelated.

| Phase and evidence | Verification result | Action under existing stage policy |
| --- | --- | --- |
| All required jobs/steps green on current head | Verified | Continue ordinary stage/merge conditions. |
| Queued, or proven setup/network failure before tests | Later covering verification unverified | Record the cause and specific recovery action/owner, such as restoring runner access or a dependency endpoint. Retry only when stage policy and remaining budget permit. |
| Deterministic code/test/build failure covering the change | Failed | Normal repair with the relevant error evidence. |
| Tests and image build pass; final container startup cancelled | Container startup unverified | Preserve earlier passes and the cancelled verification separately; no overall pass or unrelated claim. |
| Timeout/cancellation or insufficient/ambiguous logs | Name unknown/unverified portions | Obtain missing evidence within the budget or hand off for external action; do not guess a setup or code cause. |
| Authorized unrelated retry passes or fails | Green counts as passed; otherwise unfinished | Retain both run links and consumed retry count; a failed retry waits externally, never takes a second retry. |
| Reinspection or another stage/head | Restore original deadline/retry record | Inspect current-head checks without resetting the continuing budget. |

A proven setup failure never makes a required covering job unrelated: the failed test/job must neither cover the change nor depend on changed code to use the stage's unrelated retry. Related or uncertain failures cannot use that shortcut. Deterministic in-scope code failures follow repair; proven external/setup problems without an authorized retry retain Waiting for CI and a precise recovery action. Do not optimize repository CI, weaken required checks, or increase wait caps to handle these outcomes.

### Wait for completion

1. Prefer platform commands that return when checks finish. Discard repeated non-terminal table refreshes and inspect only exit status per segment; query final results once on completion. Use the platform adapter's commands, such as GitHub's `gh pr checks <number> --watch --interval 60` or `gh run watch <run-id> --exit-status --interval 60`.
2. If a call exceeds the execution tool's duration limit, run it in the background or resume in segments. Count all segments toward the original deadline; preserve the handoff before returning.
3. If no checks exist yet, check again no sooner than 1 minute later and mark waiting for external checks after the limit.
4. Without a wait-until-finished command, query at intervals of at least 1 minute, fetching only running/failed counts. Read the full final result once after completion.
