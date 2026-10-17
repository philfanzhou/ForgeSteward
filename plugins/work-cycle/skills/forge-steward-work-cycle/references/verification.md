## Concurrent local verification

Separate workspaces isolate code, but concurrent implementation/review/repair may still contend for ports, databases, containers, simulators, remote environments, and computing capacity. Apply isolation, queuing, then contention diagnosis, with an overall limit. Change timing/execution method, never verification standards.

### Resource locks

Use this package's `scripts/resource_lock.py`. Locks live in the target's Git common directory at `forge-steward/locks/`, shared by worktrees without tracked-file changes:

```bash
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> acquire <resource> --run <run-id> --task <task-id> [--attempt <attempt>] [--capacity <capacity>] [--wait <seconds>]
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> release <resource> --run <run-id> --task <task-id> [--attempt <attempt>]
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> status [<resource>]
```

The owner key is `<run-id>/<task-id>/<attempt>`; `--attempt` defaults to 1. `acquire` exits `0` when acquired (a repeat by the same owner key returns `HELD` and takes no new slot), `1` when still occupied after waiting, and `2` on argument/environment errors. Only the exact owner key may release its slot. Resource names use lowercase letters, digits, `.`, `_`, and `-`:

- `port-<number>`, `db`, `docker`, `simulator`, `browser-profile`, `path-<short-name>` (fixed path/global configuration), `remote-<environment>` (shared remote tests/accounts, always exclusive).
- `local-suite`: a full local suite with unclear resources.
- `heavy`: compilation/full suites and similar heavy work; capacity equals this run's heavy-work limit, default 2 and no greater than subagent concurrency.
- `run`: one work-cycle per checkout; acquire it with the run ID before the first stage dispatch. See [Move completed items forward](concurrency.md).
- `issue-registry`: search/filing before new Issues; `merge`: one merge at a time. See [Move completed items forward](concurrency.md).

`holder.json` records the owner key, run, task, attempt, note, `acquired_at`, and the acquiring process's `pid` with `process_start` (or the reason it could not be read). `status` adds the slot's `age_seconds`/`age` and a `liveness` hint (`alive`, `stopped`, or `unknown`) with detail. The recorded process is the helper process that ran `acquire`, not the whole stage; it usually exits immediately. `stopped` therefore does not prove the stage ended. Treat the age and owner as evidence for a manual check, never as proof.

Use the work-cycle run ID for `--run` and a unique per-subagent task identifier for `--task`, such as `implement-123` or `review-pr-45`. A retry of the same dispatch keeps its attempt; a separate dispatch of the same task uses the next attempt.

To recover a stale slot, read `status`, confirm the recorded run/task/attempt and its stage have stopped, then run `release` with that exact key. `release` refuses a slot whose recorded owner process is alive or cannot be confirmed stopped. Never remove a lock automatically; never release a slot while its owner or stage may still run. If `release` refuses because the owner cannot be confirmed stopped, or the slot was created before owner metadata (shown with `"legacy": true`), confirm no stage or orchestration is running, then remove only that slot directory manually.

### Orchestrator responsibilities

1. Run `status` once before concurrency to confirm availability. If unavailable or exit `2`, run stages serially under [Cycles, handoffs, and stopping](cycles.md).
2. Provide each subagent its run ID, task identifier, actual paths for the three commands, queued resources from the Issue's shared-verification inventory and this run's recorded contention, and `heavy` capacity.
3. After a subagent completes, fails, or is confirmed stopped, run `status`. Release its remaining locks using its recorded run/task/attempt key after confirming its owner stopped. Do not release active subagents' locks. Report unknown or legacy holders; only the documented legacy recovery removes a slot manually.
4. Record any resource contention reported by subagents; require later tasks to queue for that resource.

### Subagent rules

Each stage's concurrent-invocation rules enforce the same isolation, queuing, and diagnosis. Use the run ID and task identifiers for temporary directories, container names, test databases, and ports with existing configuration only. Lock shared-resource/heavy checks under the same owner key and release regardless of outcome. Take multiple locks in resource-name order; release held locks when another is unavailable. For unclear checks, take every known shared-resource lock and `local-suite`. Rerun concurrent failures alone with all relevant locks (`local-suite` when unclear). A solo pass is contention, not a code defect or review round. After over 30 minutes accumulated lock wait, return waiting-for-resources status.

### Limit total work

Run relevant checks locally and leave full suites to CI unless repository rules require local execution; then queue as heavy work. Do not rerun locally the same check already passing CI on the same commit.
