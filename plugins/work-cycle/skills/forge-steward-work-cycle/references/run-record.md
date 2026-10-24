## Run records and timing

Store handoffs, evidence, and stage timings in the target repository's Git common directory at `forge-steward/runs/<run-id>/`, shared by all worktrees. Never change tracked files or use `/tmp`. Use this package's `scripts/run_record.py`:

```bash
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> start --cycles <count>
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> event --run <run-id> --task <task-id> --stage <stage> --status <status> [--wait <wait-type>] [--detail <description>] [--attempt <attempt>] [--event-id <id>] [--wait-id <id>]
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> task-dir --run <run-id> --task <task-id> [--attempt <attempt>]
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> summary --run <run-id>
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> report --run <run-id>
```

Statuses: `started`, `finished`, `failed`, `suspended`, `resumed`, `wait-start`, `wait-end`; waits: `ci`, `lock`, `review`, `external`, `other`. `report` exit `1` means invalid `handoff.json` data; any command's exit `2` means argument/environment error.

### Files in a run directory

Read [Capability reuse](capabilities.md) in full for optional run-scoped `capabilities.json`. Only the orchestrator aggregates adapter observations; pass its path to stages.

`run.json` holds the run ID and cycle limit, `events.jsonl` the append-only stage events, and one attempt-scoped evidence directory for each dispatched task. Attempt 1 uses `<task-id>/`, later attempts `<task-id>-r<attempt>/`; attempts are whole numbers 1–9999, default 1. `--task` remains the stage-and-item identifier such as `review-pr-45`; schema-2 events and summaries also retain the numbered attempt. Never overwrite an earlier attempt's `result.md`; read the earlier attempt directories before writing the next result. `handoff.json` is the short orchestration handoff that `report` validates, `cleanup.md` is the cleanup stage's per-resource audit, and `workspaces.json` is this run's workspace ownership record.

Before writing `workspaces.json`, read [Workspace ownership](workspace-ownership.md) in full. This JSON list of entries has `task`, `branch`, absolute `workspace` path, owning `stage`, `status`, and `updated_at`; detached identity uses a null branch plus `detached` and `head`. The orchestrator updates it before dispatch (`active`) and after confirmed completion (`finished`, `failed`, or `paused`). It changes no tracked files, does not change the `handoff.json` schema, and never infers ownership from a path. The linked format defines optional `disposable: true`. Keep cleanup's `disposal.json`, ownership, handoffs, evidence, and audit in shared Git metadata after reclamation.

Event appends take a short-lived `.events.lock` directory in the run directory. Before appending, the writer stores `owner.json` in it with its process ID, start time when readable, acquisition time, and purpose. Writers wait at most ten seconds; on timeout the error names the recorded owner and the recovery step. A killed writer leaves the guard; appends fail until recovery. Confirm no event writer is running, then remove only that `.events.lock` directory. Never remove it while a writer may run, and never expect automatic removal.

### Event identity and timing

New events have `schema: 2`, `event_id`, and `attempt`. IDs are 1–128 ASCII letters/digits plus `.`, `_`, `:`, `-`, starting with a letter/digit; generate a fresh ID per new event. For an ambiguous append retry, supply the same `--event-id`, `--at`, and all original fields; identical content returns the saved event without appending. Conflicting content fails with exit `2` and leaves records intact. Never reuse an ID for a new transition. The append guard serializes this check across writers.

Stages own only `wait-start`/`wait-end`. A wait pair uses the same attempt, type, and `--wait-id`; omitted wait ID defaults to its type, permitting one open wait per type. Distinct IDs allow simultaneous waits of one type. Match waits entirely within a running interval; end them before suspend/terminal transitions. The orchestrator owns lifecycle events. `started` opens an absent attempt, `suspended` closes its active interval, `resumed` opens the next interval, and `finished`/`failed` closes a running attempt. A terminal attempt cannot resume; another dispatch uses the next attempt. Record a redacted suspension reason in `--detail`; never store credentials.

`summary` sums completed active intervals per attempt and stage; the latest numbered attempt supplies a task's current result. A running/suspended attempt has no completed duration and cannot inherit an earlier terminal result. Wall time is first-to-last event, including gaps. `active_wall_seconds` unions completed active intervals only when accounting is complete; otherwise it is null and `completed_active_wall_seconds` gives known coverage. Stage time can exceed wall time through concurrency. Matched waits remain in stage occupancy, accumulate by type, and expose union/overlap separately; never subtract them twice. Suspension is separately accumulated and excludes suspended gaps from active totals. These measure occupancy, not CPU time.

Readers deduplicate identical event IDs and flag conflicts, malformed/unmatched transitions, open waits, and ambiguous legacy lifecycles. `attempts`, `accounting_complete`, and `diagnostics` explain incomplete totals; valid completed intervals may still contribute partial totals. Legacy schema/attempt-free records remain readable: infer only one unambiguous start/end pair; repeated boundaries are ambiguous. Mixed legacy/numbered events cannot assign old events to an attempt. Never rewrite raw events or earlier evidence directories. Older readers can miscount schema-2 events; rollback uses a matching reader and retained originals. See [Final report](report.md) for timing labels and manual fallback.

### Find usable Python

Try `python3 --version`, `py -3 --version`, then `python --version`; use the first working Python 3.9+ command, avoiding Windows stubs that only open the store. Substitute it for `python3` throughout these rules. Check before `start`. If none works, record it in the handoff, continue delivery, and use [Final report](report.md)'s manual fallback.

### Orchestrator responsibilities

1. After the startup check, run `start` for a run identifier/directory. It retains its latest 20 script-created directories; other files stay untouched.
2. Only the orchestrator records lifecycle events: `started` before dispatch, `finished` or `failed` after confirmed completion, and `suspended`/`resumed` around a confirmed user/capacity suspension. Subagents must not duplicate these events. Close stage-owned waits before suspension or completion; ordinary CI/lock waits remain stage occupancy, not suspension. Stages are `check-workflow`, `prepare`, `implement`, `review`, `fix`, `merge`, `cleanup`. Task identifiers match [Resource locks](verification.md).
3. Give subagents the run ID and attempt's `task-dir`. Require `event` records for `wait-start`/`wait-end` during CI, lock, approval, and other external waits. Each subagent's evidence/handoff files belong in its own directory.
4. Save [Cycles, handoffs, and stopping](cycles.md)'s short orchestration handoff as run-directory `handoff.json`, populating [Final report](report.md)'s required fields. Read it first after compaction/interruption.
5. At completion run `report` and paste output unchanged. It reads handoff/events, takes timings from `summary`, and saves run-directory `report.md`. See [Final report](report.md) for invalid-data retries and manual fallback.

If the script cannot run or exits `2`, explain in the conversation handoff and continue delivery. Never relocate evidence to `/tmp`; a conversation handoff is acceptable.
