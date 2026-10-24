# Leftover branch cleanup scenarios

This document covers review-and-merge's [leftover branch cleanup](../plugins/review-and-merge/skills/forge-steward-review-and-merge/references/branch-cleanup.md) rules (Issues #81, #165, and #210). These are limited walkthroughs of the written rules, not runs against real repositories or evaluations of actual Agent behavior.

## Background

Previously, review-and-merge deleted only the source branch of a Change Request merged during that invocation. It left branches from interrupted Agents or earlier merges untouched: remote branches whose PRs were all merged, local branches whose remotes had already gone, and local branches left by previous sessions. The new rules add a cleanup pass after the frozen queue is processed. Since work-cycle calls review-and-merge each cycle, this takes effect without another stage.

Since Issue #165, the work-cycle orchestrator records every workspace it dispatches in `workspaces.json` in the run directory. Cleanup can therefore remove a worktree outside the conventional directory when this run's record identifies it, but only when every other safety condition also holds. An unrecorded path is never treated as owned, even when its branch looks deletable.

## Scenarios

Unless specified otherwise, the user explicitly invokes review-and-merge and allows merging, the default branch is `main`, and the invocation is not concurrent.

| ID | Input and state | Expected result | Basis |
| --- | --- | --- | --- |
| B01 | Remote and local `feat/a` exist; its PR was merged normally; branch head equals the PR head at merge; no worktree checks it out | Delete remote and local `feat/a`, counting each once; record the commit in the report and note restoration from the PR page | Classification table, row 1 |
| B02 | `feat/b` was squash-merged; its commits are not in `main`, but head equals the PR's recorded head at merge; `git branch -d` refuses | Use the PR record to confirm the merge, delete the remote, and force-delete the local branch after verifying its head; absence from main's ancestry is not a reason to retain it | Classification table, row 1 and its explanation |
| B03 | `feat/c` has a PR closed without merge; both remote and local heads equal its head at closure | Delete both; report restoration through the PR page | Classification table, row 2 |
| B04 | `feat/d` has a PR closed without merge; the remote head equals its head at closure, but the local branch has 2 unpushed commits | Delete the remote; keep the local branch and report unpushed local commits | Classification table, row 3 |
| B05 | Local `claude/agent-x` never had a PR, all commits are in `main`, and no worktree checks it out | Delete the local branch and record its commit; also delete a same-named remote branch if all its commits are in main | Classification table, row 4 |
| B06 | Local `fix/e` has a missing upstream and its head equals a merged PR's final head | Delete the local branch; there is no remote branch to delete | Classification table, row 5 |
| B07 | Local `fix/f` has a missing upstream, no matching PR can be found, and its head is not in main | Keep it and report that the remote is gone and absence of unpushed commits cannot be confirmed | Classification table, row 6 |
| B08 | Remote `wip/g` has 3 commits outside main and never had a PR | List remote and local branches without deleting; explain that they may be leftovers from interrupted work and deletion would prevent recovery | Last classification-table row |
| B09 | `feat/h` has an open PR and an older merged PR for the same branch name | Keep it; the open-PR exclusion takes precedence over the merged PR | Never-delete rule 2; multiple-Change-Request guidance |
| B10 | Two detached-HEAD worktrees are under `~/.codex/worktrees/`; under `.claude/worktrees/`, one checks out merged-PR branch `feat/i` and another is locked | Leave every worktree untouched and report why; retain both remote and local `feat/i` because a worktree ineligible for removal still checks it out; `git worktree prune` also skips locked records | Worktree rule 5; never-delete rule 3 |
| B11 | A clean, unlocked worktree at ForgeSteward's conventional `<repository-parent>/<repository-name>-forge-steward/42` checks out merged-PR branch `forge-steward/issue-42`; another worktree under the same parent has untracked files | Remove the first with `git worktree remove`, then delete its branch; retain the second and its branch and report uncommitted changes | Worktree rule 2 |
| B12 | 40 remote and 25 local branches qualify for deletion | Delete the first 50 in oldest-last-commit order; report the remaining 15 as left for next time; associated worktree removals do not count | Deletion and limit rule 3 |
| B13 | User requests review only, with no merge or modifications; branches like B01, B03, and B05 exist | Delete none and do not run `git worktree prune`; report branches, classifications, and reasons | Timing and mode rule 2 |
| B14 | On the final reread, B01's `feat/a` has a different head or a newly opened PR | Keep it and report the reason | Deletion and limit rule 1 |
| B15 | The PR-list API fails and returns records for only some branches | Process only confirmed branches; keep every branch with unavailable records and report that the query failed and it was not checked | Scope and reading rule 3 |
| B16 | Protection rejects deletion of remote `feat/c`; `feat/j` has already been deleted by someone else | Record the rejection and keep `feat/c`, then continue; record `feat/j` as already absent, not a failure | Deletion and limit rule 2 |
| B17 | work-cycle dispatches concurrent reviews; the schedule identifies execution's active `forge-steward/issue-43` branch and workspace; all its commits happen to be in main | Preserve that branch and workspace; clean other eligible branches normally | Never-delete rule 4; `concurrent.md` step 3 |
| B18 | Concurrent invocation with no caller-provided list of branches used by other stages | List leftover branches without deleting | `concurrent.md` step 3 |
| B19 | Concurrent invocation where this review merges nothing | Do not clean leftover branches | `concurrent.md` step 3 |
| B20 | User requests a stop after the 12th deletion | Stop deleting; report the 12 deleted branches and all unprocessed branches | Timing and mode rule 4 |
| B21 | Repository CI explicitly names remote `release/1.x`; it has no open PR and all commits are in main | List it without deleting | Long-lived branch guidance |
| B22 | Remote `upstream` points to the fork's source repository and contains merged-PR branches | Leave it untouched; it is outside cleanup scope | Scope and reading rule 1 |
| B23 | Post-merge finds a merged PR branch checked out in an unrecorded worktree under `~/.codex/worktrees/` | Leave the worktree untouched, retain its branch, and report the external path; post-merge removal outside the conventional workspace directory requires this run's ownership record | post-merge step 4; worktree rule 5 |
| B24 | Post-merge finds a clean, unlocked conventional worktree for the merged branch with one untracked file | Retain the worktree and its branch; report the untracked file | post-merge step 4 |
| B25 | Post-merge finds a locked conventional worktree for the merged branch | Retain the worktree and its branch; report the lock | post-merge step 4 |
| B26 | Post-merge runs from the conventional worktree that checks out the merged branch, and every other removal condition holds | Switch to the mainline workspace first, then remove the worktree only if every condition still holds; otherwise retain it and its branch and report why | post-merge step 4 |
| B27 | Another active flow or a caller-listed workspace checks out the merged branch in an otherwise eligible conventional worktree | Retain the worktree and its branch; report the owner | post-merge step 4 |
| B28 | A clean, unlocked, attached worktree outside `<repository-parent>/<repository-name>-forge-steward/`; this run's `workspaces.json` names it as a finished task, its branch is a merged PR with matching head, it is not current or caller-listed active, and no open PR uses it | Remove it with `git worktree remove` (never force), delete its branch, and record the outside path, deletion-time commit, and recovery in `cleanup.md` | Worktree rule 2; ownership-record exception |
| B29 | B28's worktree has one modified tracked file | Retain the worktree and its branch and report the uncommitted change | Worktree rule 2 |
| B30 | B28's worktree has one untracked file | Retain the worktree and its branch and report the untracked file | Worktree rule 2 |
| B31 | B28's worktree is locked | Retain it and report the lock; `git worktree prune` also skips it | Worktree rules 1–2 |
| B32 | B28's worktree is the one running cleanup | Do not remove it; if its branch is the merged request's, switch to mainline first, then remove only if every condition still holds | Worktree rule 2; post-merge step 4 |
| B33 | B28's worktree has a detached HEAD without the additional disposable/finished/recovery checks | Retain it and report the missing proof; matching detached identity alone is insufficient | Detached workspace rule |
| B34 | A clean outside worktree checks out a merged-PR branch, but this run's `workspaces.json` does not name it (another run or a user created it) | Retain it and report that this run does not own it; never infer ownership from a path | Worktree rule 5 |
| B35 | B28's worktree is named by the record, but another active stage or a caller list marks it active | Retain it and report the active owner | Worktree rule 2 |
| B36 | B28's worktree's branch has unique commits, is unmerged, or is used by an open PR | Retain the worktree and its branch; report the failed branch condition | Worktree rule 2; classification table |
| B37 | `workspaces.json` is missing, unreadable, or malformed when cleanup runs | Treat every outside-directory worktree as unowned, retain it, and report the unusable record | Worktree rule 2 |
| B38 | The record names a worktree whose directory no longer exists | Prune the stale record with `git worktree prune`; report it as absent, not deleted | Worktree rule 1 |

## Disposable detached stage workspaces (#210)

The [detached cleanup rule](../plugins/review-and-merge/skills/forge-steward-review-and-merge/references/detached-workspaces.md) changes blanket retention only for this run's explicitly disposable, finished stage environment. All ordinary safety exclusions remain. `disposal.json` is cleanup's final-check record, separate from orchestrator-owned `workspaces.json`.

| ID | Input and state | Expected result | Basis |
| --- | --- | --- | --- |
| B39 | Explicit disposable/finished detached owner, matching full head, saved complete handoff/evidence, confirmed inactive and requests clear, reviewed ignored files, ordinary Git lifecycle, and refreshed durable mainline contains head | No-force removal; read back absence, preserve evidence, record commit/ref and per-resource outcome; isolated fixture recreates the worktree from saved commit | Detached success |
| B40 | B39 with any dirty, untracked, locked, current, active, other-conversation, failed/paused, unknown/legacy owner, or mismatched identity condition | Retain with exact reason, including inside the conventional directory | Detached exclusions |
| B41 | B39 has needed ignored output or a changed ignored listing | Retain until needed output is preserved in run metadata and every remaining ignored file is freshly inspected as dispensable | Ignored-file review |
| B42 | Detached commit exists only in local reflog/branch or differs from recorded request head; request is open or host cannot restore | Retain unrecoverable/unknown work; accept a matching restorable closed/merged request head even after squash/rebase | Durable recovery |
| B43 | B39 becomes active, changes owner/head, or gets an open associated request before action | Refresh facts and inventory; retain changed resources | Final checks |
| B44 | Host-managed disposable workspace has supported archive API and artifact identity | Call only host adapter archive, verify archived metadata, preserve recovery/evidence; fake adapter fixture confirms this flow | Host lifecycle |
| B45 | Host API unavailable/denied or result ambiguous | Retain unsupported/denied resource; resolve ambiguity by readback before retry and never substitute raw Git/filesystem removal | Host failure |
| B46 | Stop after inventory or no-force removal fails because new untracked data arrived | Stop further detached reclamation; preserve data/evidence and record completed/remaining outcomes | Stop/failure |
| B47 | Saved handoff/evidence missing, still inside workspace, incomplete, or facts malformed/stale | Retain or report unusable checks; never claim removal or invent facts | Evidence and compatibility |

The isolated Git fixture tests execute B39–B43 and B46–B47 conditions; a fake host adapter exercises supported archive and response-loss readback for B44–B45. Rule walkthroughs cover denied API calls and per-resource audit reporting. They do not certify a real host or Agent. Report inventoried, reclaimed, and retained counts from actual outcomes; never claim unmeasured disk savings.

## Recovery and rollback

- Restore deleted branches with a Change Request through its page. A branch without a Change Request is deleted only if all commits are in main; recreate it from the commit recorded in the report.
- This is new behavior; older versions do not clean leftover branches. Roll back by reverting the PR introducing these rules.

## Limitations

- Cleanup does not guarantee removal of every leftover branch; uncertain cases are retained.
- Ownership comes only from this run's record and the caller's active list; cleanup does not scan other runs' records or infer ownership from a path.
- It does not inspect same-named branches in other people's local clones, handle fork branches, or change repository settings.
