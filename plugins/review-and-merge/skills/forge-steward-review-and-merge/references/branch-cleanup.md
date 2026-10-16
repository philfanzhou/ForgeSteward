## Leftover branch cleanup

Clean branches/worktrees left by interrupted runs or post-merge omissions. Delete only confirmed safe, recoverable items; retain and list anything uncertain.

### Timing and modes

- Run once after the whole frozen list and each item's post-merge work, even if nothing merged this round.
- For review-only requests forbidding merges/changes, list only: no deletion or `git worktree prune`. Preserve explicitly retained branches.
- If the caller excludes leftover cleanup (such as per-item orchestration reviews), skip this section while still cleaning each merged item's own branch/workspace. If asked only for leftover cleanup, freeze/review no Change Requests and run this section directly.
- Treat caller-listed branches/workspaces owned by other stages as active. In a concurrent invocation without that list, list only and do not delete.
- On a user stop request, stop subsequent deletions and report deleted/unfinished portions.

### Scope and inspection

- Only this review's repository: its hosted remote branches (only remotes pointing to this repository, never forks/other remotes), local branches, and worktrees in the current local repository.
- Fetch first, then read remote branches/heads, local branches and missing upstreams, `git worktree list --porcelain` including locks/detached HEAD, every open/merged/closed Change Request for each branch name and last heads, and default/protected branches. Platform adapters determine request/protection queries and remote deletion commands.
- With failed/incomplete queries, retain unconfirmed branches and process only confirmed portions.

### Classification

Each branch gets one category. First apply “never delete,” then use the first matching table row.

Never delete the remote/local branch or its worktree when:

- Default/protected, or protection cannot be determined.
- Used by an open Change Request as source or target.
- Checked out in the workspace running this skill, or another worktree failing removal conditions below.
- Listed as active by the caller.
- On a fork, of unknown origin, or unable to satisfy the table's safety conditions.

List only long-lived branches named in documentation/CI, such as `develop` or `release/*`.

| Condition | Remote branch | Local branch |
| --- | --- | --- |
| Change Request merged; branch head equals merge-time head | Delete | Delete |
| Closed without merge; branch head equals closure-time head | Delete | Delete |
| Same closed request, but local branch has additional unpushed commits | As above | Retain and list |
| Never had a Change Request; all commits are in mainline | Delete | Delete |
| Upstream gone; local head is in mainline or equals last head of a merged/closed request | Not applicable | Delete |
| Upstream gone; cannot rule out unpushed commits | Not applicable | Retain and list |
| Unique commits and never had a Change Request | List only | List only |

- Squash/rebase may leave source commits outside mainline. For the first two categories compare recorded request heads, not ancestry. A refused `git branch -d` is not evidence of unmerged status; force-delete locally once verified.
- With multiple requests on one branch name, retain if any is open; otherwise use the latest. If head matches no request, treat as unique commits.
- A closed-unmerged branch can be deleted immediately and restored from the request page. A branch with unique commits and no request is not recoverable by that route; list only.

### Worktrees

- Prune records whose directories no longer exist with `git worktree prune`; git skips locked records.
- Remove with `git worktree remove`, never `--force`, only when all hold: its branch is deletable under the table's merged, closed, or missing-upstream cases; no uncommitted/untracked files; unlocked; not current; not caller-listed active; and beneath ForgeSteward's workspace directory `<repository-parent>/<repository-name>-forge-steward/`. Delete the branch after removing its worktree.
- Leave worktrees elsewhere (such as `~/.codex/worktrees/`, `.claude/worktrees/`, or user-created locations), detached HEAD worktrees, and those used by other conversations/tools untouched; list reasons and retain their branches under “never delete.”

### Deletion and limits

- Immediately before each deletion, reread head and confirm no newly opened request. Retain/report changed items. Verify remote deletion by reading back.
- Record failures such as permissions/protection and continue. If someone already deleted the branch, record absent rather than failed.
- Delete at most 50 branches per run, counting remote/local separately. Associated worktree removals/pruning do not count. Order by oldest last-commit time, then name on ties. List excess items for next time.

### Report

Use everyday English unless the user or repository specifies another language:

- Deleted branches: remote/local, name, deletion-time commit, reason, recovery (request page when available; otherwise recreate from recorded commit).
- Retained/list-only branches and reasons; removed/retained worktrees and reasons; count deferred to next run.
- Unchecked scope due to query/permission failures.

Never include tokens or other sensitive values in reports/comments.
