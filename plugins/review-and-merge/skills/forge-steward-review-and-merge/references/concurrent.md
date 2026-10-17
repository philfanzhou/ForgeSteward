## Concurrent review and merging

When given one Change Request, handle only it, checking out its head in the caller's workspace. Apply normal round limits, final review, and merge conditions. Do not merge before prerequisites the caller identifies as unmerged.

Once merge conditions hold:

1. Fetch latest mainline as M. If merges since review began overlap this request's files, or both sides touch dependency lockfiles, migrations, registries, generated code, versions, changelogs, localized strings, or shared configuration, locally merge M into a temporary result of this head (without pushing) and rerun affected checks. Failure means sync/repair needed, not a merge. If a platform queue is enabled, follow [Merge lane](merge-lane.md), enqueue/wait without `merge` locking. If policy requires current branches and this one is behind, do not sync independently; return it to the caller awaiting the merge lane.
2. Acquire `merge` with supplied commands, waiting if necessary. Inside the lock, refetch mainline, the request base, and the request head. The base must equal the default mainline unless the user explicitly named another target; otherwise release, retain and report the request, and do not merge. If head differs from reviewed head, release and re-review the new diff. If mainline differs from M and new changes need step-1 inspection, release and return to step 1. Otherwise merge with the reviewed head pinned where the platform supports it, such as `gh pr merge <number> --match-head-commit <sha>`; where it cannot be pinned, read back which head the platform merged and record an incident if it is not the reviewed head.
3. While still locked, complete [Post-merge work](post-merge.md) for a successful merge, cleaning only this item's branch/workspace, then release. If the merge call errors or its result is ambiguous, read the request's remote state before recording: if merged, complete [Post-merge work](post-merge.md) and release; if still queued, record the queue entry and wait without claiming a merge; if not merged, release and record why. Per-item reviews skip [Leftover branch cleanup](branch-cleanup.md); the caller schedules it at run end.

## Concurrent local verification

When given a task identifier, acquire/release commands, and queued resources, follow these rules without changing verification standards:

1. Isolate temporary directories, container project names, test databases, and ports by task identifier; prefer system-assigned ports. Use existing configuration/environment variables, not repository edits for isolation.
2. Acquire supplied locks before listed-resource checks or heavy work such as compilation/full suites (`heavy`); release regardless of result. Take multiple locks in resource-name order, releasing held locks if another is unavailable. Do independent work while waiting. After over 30 minutes accumulated waiting, return waiting-for-resources status. Shared remote test environments are always exclusive. Determine unspecified resources; if unclear, take all listed shared-resource locks and `local-suite`.
3. Rerun concurrent failures alone with every relevant lock (`local-suite` if unclear). A solo pass is resource contention: report it, not an in-scope blocker/change request. Handle persistent failures normally.
4. For a new Issue with supplied lock commands, acquire `issue-registry`, search open/closed records within it, file/append evidence, then release.
5. Run relevant checks locally and leave full suites to CI unless repository rules require local execution; then queue as heavy work. For git lock conflicts, wait a few seconds and retry a bounded number of times.
