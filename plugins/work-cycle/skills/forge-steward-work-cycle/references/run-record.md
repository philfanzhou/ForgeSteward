## Run records and timing

Store handoffs, evidence, and stage timings in the target repository's Git common directory at `forge-steward/runs/<run-id>/`, shared by all worktrees. Do not change tracked files or use `/tmp`. Use this package's `scripts/run_record.py`:

```bash
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> start --cycles <count>
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> event --run <run-id> --task <task-id> --stage <stage> --status <status> [--wait <wait-type>] [--detail <description>] [--attempt <attempt>]
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> task-dir --run <run-id> --task <task-id> [--attempt <attempt>]
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> summary --run <run-id>
python3 <skill-directory>/scripts/run_record.py --repo <target-repository> report --run <run-id>
```

Statuses: `started`, `finished`, `failed`, `wait-start`, `wait-end`. Wait types: `ci`, `lock`, `review`, `external`, `other`. `report` exit `1` means invalid `handoff.json` data; any command's exit `2` means argument/environment error.

### Files in a run directory

`run.json` holds the run identifier and cycle limit, `events.jsonl` the append-only stage events, and one attempt-scoped evidence directory for each dispatched task. Attempt 1 uses `<task-id>/` and later attempts use `<task-id>-r<attempt>/`; the attempt is a whole number from 1 to 9999 and defaults to 1. The attempt scopes only the directory: `--task` still uses the stage-and-item identifier such as `review-pr-45`, and events keep grouping by that identifier. Never overwrite an earlier attempt's `result.md`; read the earlier attempt directories before writing the next result. `handoff.json` is the short orchestration handoff that `report` validates, `cleanup.md` is the cleanup stage's per-resource audit, and `workspaces.json` is this run's workspace ownership record.

`workspaces.json` is a JSON list of entries with `task`, `branch`, absolute `workspace` path, owning `stage`, `status`, and `updated_at` (UTC). Before dispatch the orchestrator records an entry, replacing any match for the same workspace, with status `active`; after confirmed completion it sets `finished`, `failed`, or `paused`. The file stays in Git metadata, changes no tracked files, and does not change the `handoff.json` schema. Cleanup reads it as ownership evidence and never infers ownership from a path.

Event appends take a short-lived `.events.lock` directory in the run directory. Before appending, the writer stores `owner.json` in it with its process ID, start time when readable, acquisition time, and purpose. Writers wait at most ten seconds; on timeout the error names the recorded owner and the recovery step. A killed writer leaves the guard behind, and later appends keep failing until recovery: confirm that no event writer is running, then remove only that `.events.lock` directory. Never remove it while a writer may run, and never expect automatic removal.

### Find usable Python

Try `python3 --version`, `py -3 --version`, then `python --version`; use the first working Python 3.9+ command, avoiding Windows stubs that only open the store. Substitute it for `python3` throughout these rules. Check before `start`. If none works, record it in the handoff, continue delivery, and use [Final report](report.md)'s manual fallback.

### Orchestrator responsibilities

1. After the startup check, run `start` for a run identifier/directory. It retains only the latest 20 directories created by this script, leaving other files untouched.
2. Before each dispatch record `started`; after confirmed completion record `finished` or `failed`. Stages are `check-workflow`, `prepare`, `implement`, `review`, `fix`, `merge`, `cleanup`. Task identifiers match [Resource locks](verification.md).
3. Give subagents the run identifier and the attempt's `task-dir` evidence directory. Require `event` records for `wait-start`/`wait-end` during CI, lock, approval, and other external waits. Each subagent's evidence/handoff files belong in its own directory.
4. Save [Cycles, handoffs, and stopping](cycles.md)'s short orchestration handoff as run-directory `handoff.json`, populating [Final report](report.md)'s required fields. Read it first after compaction/interruption.
5. At completion run `report` and paste output unchanged. It reads handoff/events, takes timings from `summary`, and saves run-directory `report.md`. See [Final report](report.md) for invalid-data retries and manual fallback.

If the script cannot run or exits `2`, explain in the conversation handoff and continue. Record failure must not interrupt delivery. Do not relocate evidence to `/tmp`; a conversation handoff is acceptable.
