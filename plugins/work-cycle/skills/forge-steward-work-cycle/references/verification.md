## Concurrent local verification

Separate workspaces isolate code, but concurrent implementation/review/repair may still contend for ports, databases, containers, simulators, remote environments, and computing capacity. Apply isolation, queuing, then contention diagnosis, with an overall limit. Change timing/execution method, never verification standards.

### Resource locks

Use this package's `scripts/resource_lock.py`. Locks live in the target's Git common directory at `forge-steward/locks/`, shared by worktrees without tracked-file changes:

```bash
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> acquire <resource> --holder <task-id> [--capacity <capacity>] [--wait <seconds>]
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> release <resource> --holder <task-id>
python3 <skill-directory>/scripts/resource_lock.py --repo <target-repository> status [<resource>]
```

`acquire` exits `0` when acquired (same-holder repeats return `HELD`), `1` when still occupied after waiting, and `2` on argument/environment errors. Only the holder may release. Resource names use lowercase letters, digits, `.`, `_`, and `-`:

- `port-<number>`, `db`, `docker`, `simulator`, `browser-profile`, `path-<short-name>` (fixed path/global configuration), `remote-<environment>` (shared remote tests/accounts, always exclusive).
- `local-suite`: a full local suite with unclear resources.
- `heavy`: compilation/full suites and similar heavy work; capacity equals this run's heavy-work limit, default 2 and no greater than subagent concurrency.
- `issue-registry`: search/filing before new Issues; `merge`: one merge at a time. See [Move completed items forward](concurrency.md).

Use unique per-subagent task identifiers in the form “stage-Issue-or-PR-number,” such as `implement-123` or `review-pr-45`.

### Orchestrator responsibilities

1. Run `status` once before concurrency to confirm availability. If unavailable or exit `2`, run stages serially under [Cycles, handoffs, and stopping](cycles.md).
2. Provide each subagent its identifier, actual paths for the three commands, queued resources from the Issue's shared-verification inventory and this run's recorded contention, and `heavy` capacity.
3. After a subagent completes, fails, or is confirmed stopped, run `status`. Release its remaining locks using its identifier. Do not release active subagents' locks or manually delete lock directories. Report unknown holders without cleanup.
4. Record any resource contention reported by subagents; require later tasks to queue for that resource.

### Subagent rules

Each stage's concurrent-invocation rules enforce the same isolation, queuing, and diagnosis. Use task identifiers for temporary directories, container names, test databases, and ports with existing configuration only. Lock shared-resource/heavy checks and release regardless of outcome. Take multiple locks in resource-name order; release held locks when another is unavailable. For unclear checks, take every known shared-resource lock and `local-suite`. Rerun concurrent failures alone with all relevant locks (`local-suite` when unclear). A solo pass is contention, not a code defect or review round. After over 30 minutes accumulated lock wait, return waiting-for-resources status.

### Limit total work

Run relevant checks locally and leave full suites to CI unless repository rules require local execution; then queue as heavy work. Do not rerun locally the same check already passing CI on the same commit.
