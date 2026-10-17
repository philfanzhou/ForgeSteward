---
name: forge-steward-review-and-merge
description: Freeze and review the current open change requests, merge only those that satisfy their scope, acceptance criteria, checks, and repository policy, then reconcile linked tasks and clean up safely. Use when asked to review an open PR or MR queue and merge eligible changes, not for review-only requests that forbid merging.
---

# Review And Merge

## Load the rules

Before freezing and reviewing the queue, read [Freeze and review](references/review.md) in full. Before any merge, read [Post-merge completion and cleanup](references/post-merge.md) and [Merge lane](references/merge-lane.md) in full to establish post-merge checks and cleanup boundaries. Before writing handoffs, read [Handoff records](references/handoff.md). If the caller identifies a concurrent invocation (task identifier, lock commands, etc.), also read [Concurrent invocation](references/concurrent.md) before reviewing. Hand off unmerged items and continue the queue as this entry requires. After the frozen list and before the final summary, read and execute [Leftover branch cleanup](references/branch-cleanup.md) in full.

These references are required rules. Resolve paths relative to this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Authorization and scope

Review Change Requests already open at the start of this round in mainline priority order, merging eligible ones. Change Request is platform-neutral and includes GitHub Pull Requests, GitLab Merge Requests, and equivalents.

Explicit invocation, including selecting the skill without a prompt, authorizes: freeze → review → directly merge requests meeting all conditions → complete tasks and clean up. This skill governs review scope, feedback classification, rounds, merge decisions, and completion, replacing separate repository rules for the same workflow. Follow repository conventions for merge method, required checks/approvals, branch protection, language, and templates. Explicit invocation authorizes eligible merges; merge after approval without another per-item confirmation or repeated authorization across conversations. Current explicit limits take precedence: review-only, no-merge, or named-item scope must be honored. Automatic selection, mentioning the name, or asking about usage does not authorize merging. Never bypass protection, required approvals, or platform permissions, or change request code merely to make checks green (a conflict-free mainline merge in the merge lane is not a code modification). Do not add requests opened after the freeze.

## Merge conditions

Merge only when all apply:

- Every original in-scope acceptance criterion is met.
- All applicable required checks pass, or an exception expressly permitted by repository rules is recorded and authorized.
- No unresolved in-scope blocking feedback remains; resolved blocking threads need a fix commit or maintainer acceptance.
- The base is the default mainline unless the user explicitly named another target.
- Required approvals, conflict state, and branch protection satisfy repository policy.
- The head fetched immediately before merging equals the reviewed head; pin it at merge where supported, or verify the merged commit equals it and record an incident if not.

When these hold, merge immediately without another user confirmation. Otherwise record the unmet conditions and do not merge. Use the repository's required merge method, or its/platform default if unspecified. Do not proactively use admin bypass or force-push, or enable auto-merge or a merge queue. If a merge queue is already enabled, or policy requires an up-to-date branch and being behind is an approved item's only merge blocker, follow [Merge lane](references/merge-lane.md). Otherwise merge directly after approval. Record permission, protection, or platform failures accurately; never report them as successful merges.

## Handoff

After each item, including unmerged or blocked ones, follow [Handoff records](references/handoff.md) before continuing the queue.

## Output

After processing the entire frozen list, summarize:

- The initial list, baseline, and processing order.
- Final review and merge results after repair round 3; requests paused for remaining in-scope required changes, with current head, round count, and evidence.
- Each request's review conclusion and evidence.
- Actual reviews, merges, closures, and cleanup; distinguish reviewed, approved, merged, and unmerged.
- Actual local/remote source-branch cleanup, the automatic-deletion setting, and branches retained for safety or permissions with reasons.
- Linked tasks/parents closed and remaining scope.
- Deduplication and classification of newly discovered issues.
- Completion and remainder of tasks predating this cleanup, tasks created during cleanup, rework, parent closures, and removed blockers. “This cleanup” starts at the tracker/handoff's cleanup baseline, persists across runs, and is not this invocation's start. Link acceptance gaps missed in closed tasks to their original task and Change Request and count them as rework.
- Remaining blockers, accepted limits, and next steps.

Do not add newly opened requests, treat green CI as acceptance, or call failed merges delivery. Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts.
