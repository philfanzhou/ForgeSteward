## Move completed items forward

Avoid making completed items wait for the whole batch. Workload, stage standards, merge conditions, and review-round limits remain unchanged; only dispatch timing changes.

### Enable or fall back

Enable when the runtime can run subagents in the background and read their progress (handoffs, messages, or status) while active, and [Resource locks](verification.md) work. Otherwise run serially under [Cycles, handoffs, and stopping](cycles.md), without treating it as failure or reducing work. After background-dispatch/progress-read failure, apply [Lifecycle and recovery](agents.md). If progress remains unknown, make that portion serial and await its stage before dependent dispatch.

### Concurrency limits and order

- Default to at most 3 implementation/review/repair/preparation subagents combined; use 2 with fewer than 8 logical cores, or 1 with fewer than 4. Compilation/full suites and other heavy work also queue under [Local verification](verification.md)'s `heavy` limit.
- Fill slots in this order: handed-off requests awaiting review/repair, prioritizing those closest to completion → startable Issues in current-cycle list order → next-cycle preparation.
- Review/repair concurrency is per Change Request, one dedicated subagent per request. Each still follows review → repair → new review; separate requests do not wait for each other. These loops may overlap implementation/next-cycle preparation. Startup requests may overlap first-cycle preparation too.

### Scheduling table

For every Issue/Change Request, the orchestrator records current step (Awaiting start, Implementing, Handed off, Reviewing, Awaiting repair, Repairing, Merged, Waiting externally, Paused), owner subagent, workspace, batch relationships, and locks held. After a subagent ends, verify results/remote state, update the table, release its leftover locks, then dispatch under limits/order.

### Concurrent implementation by Issue

- Give each execute-work subagent exactly one Issue, workspace, task identifier, lock commands/queued resources, and expected changes of other active batch items.
- Use Issue handoff relationships: independent items start immediately; code dependencies await prerequisite merges; overlapping items await earlier-listed merges. An overlapping predecessor that pauses, is genuinely blocked, or is confirmed not submitting permits the later item to start; later conflicts go to repair/mainline sync. A code prerequisite that never merges leaves its dependent waiting with reasons, not started.
- Without relationship records, such as older preparation output, treat the Issue as overlapping all others and start in list order.
- If actual changes exceed expectation and overlap another active item, retain workspace/commits and wait for that other item to merge before resuming.
- Dispatch next-cycle preparation only after every current-list item has started, is awaiting prerequisites, or is confirmed unable to start. Provide all assigned unfinished Issues from this run to avoid duplicate selection.

### One stage owns each Change Request at a time

Maintain an ownership table identifying each request's current stage.

- After an item's verification and CI handling, execution marks it handed off. Before that execution owns it; afterward execution cannot push its branch and later changes use review/repair only.
- Review/repair dispatch explicitly lists requests other stages still own. Review also gets other active branch names/workspace paths from the table. Stage skills skip/list those items without review, merge, comment, or push. Items handed off after a review starts wait for the next review dispatch.
- Dispatch a reviewer whenever a slot opens for an unreviewed handed-off request. Required changes/mainline sync lead to its repair subagent, then a new reviewer. Refetching head before merge and comparing to reviewed head remains mandatory.

### One merge at a time

- Give reviewers commands for `merge` capacity 1. Under review-and-merge's concurrent rules they recheck on latest mainline before merging, confirm/merge while locked, and clean up under the lock.
- Identify unmerged prerequisites at dispatch; do not merge before them.
- If policy requires up-to-date branches, approved requests returned only for being behind enter a merge lane. Dispatch only one review-and-merge subagent for it at a time, explicitly limited to that skill's lane rules, with ordered list and `merge` commands. It holds the lock while syncing, waiting for checks, and merging one by one. New returned items wait for the next lane. Lane items sent to repair require re-review afterward. Do not sync every pending item after each merge.
- Release completed subagents' leftover `merge` locks under [Resource locks](verification.md).

### Workspaces and git

- Each stage uses its own workspace, not the user's primary directory or another stage's branch. Default to worktrees outside the repository, such as `<repository-parent>/<repository-name>-forge-steward/<task-id>`, so checks do not scan other copies. Use separate clones for submodules or tools requiring a `.git` directory. Follow repository branch naming, otherwise `forge-steward/issue-<number>`.
- The orchestrator fetches once before each dispatch batch; subagents fetch again only before pushing.
- Execution branches only from freshly fetched remote mainline, never local mainline. Refetch before push/Change Request creation; sync conflicts before submission. Later conflicts follow repair sync rules.
- Post-merge cleanup removes only that request's branches/dedicated workspace, avoiding other active stages. Run leftover cleanup once at run end under [Cycles, handoffs, and stopping](cycles.md). Update local mainline only in a mainline workspace unused by stages.
- Isolate/queue concurrent local checks under [Local verification](verification.md).
- On concurrent git lock conflicts, wait a few seconds and retry a bounded number. If still failing, return the recorded error; do not delete lockfiles or classify it as a business failure.

### Only the orchestrator writes shared records

With concurrent stages, only the orchestrator writes shared progress such as the tracker's current scheduling section. Tell subagents not to write it; return needed content for orchestrator aggregation. Stages still write their own Issues/Change Requests. Before new Issues, acquire [Resource lock](verification.md) `issue-registry`, search open/closed records inside the lock, file/append evidence, then release to avoid duplicate filings.

### Report

Record enabled concurrency, chosen limit, serial-fallback reasons, and CI queuing among simultaneous requests in handoff `concurrency` under [Final report](report.md). Queue delays are not time savings.
