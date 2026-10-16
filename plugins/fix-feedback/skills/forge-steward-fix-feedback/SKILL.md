---
name: forge-steward-fix-feedback
description: Freeze the current repairable change-request queue, resolve only required review feedback, deterministic in-scope CI failures, and confirmed acceptance gaps, then commit and push each original branch without merging. Use for repairing PRs or MRs that need changes, not for items merely awaiting re-review.
---

# Fix Feedback

## Load the rules

Before repairing, verifying, or pushing any frozen repair candidate, read [Per-item repair](references/repair.md) in full. Use this entry for read-only classification and skips; never change code, push, or resolve a Review Thread from the summary alone.

These references are required rules. Resolve paths relative to this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Authorization and boundaries

Repair currently open Change Requests that actually need changes. Change Request is platform-neutral and includes GitHub Pull Requests, GitLab Merge Requests, and equivalents.

This skill governs repair scope, feedback classification, and review rounds, replacing separate repository rules for the same workflow. Follow repository conventions for language, commit format, verification commands, and branch protection.

Perform external writes only when the user has authorized code changes and pushes to the original branch and that authorization remains valid for this task. Do not request it again merely because the conversation changed. This skill must never merge a Change Request or describe “pushed” as “accepted” or “merged and delivered.” Use available connectors, CLIs, or platform APIs without requiring a particular host.

## Freeze the repair queue

1. Read repository conventions, mainline, and the previous handoff; fetch open Change Requests, reviews, checks, and linked tasks. Preserve the cleanup cycle's original task list and unfinished scope; repair commits do not reset goals or increase delivery counts.
2. Freeze this round's repair list with time, base/head commits, and selection reasons. Do not automatically add later Change Requests.
3. Include only Change Requests with at least one required change:
   - Explicit, unresolved Review Feedback within the original scope.
   - A reproducible, deterministic CI failure caused by this branch and within scope.
   - A confirmed unmet original acceptance criterion.
   - A mainline conflict, or an outdated branch where repository policy requires it current; see [Sync with mainline](references/repair.md#sync-with-mainline).
4. Skip requests only awaiting re-review or triggered checks, containing only optional suggestions, already addressed at the current head, or having no deterministic fix. Explain the evidence for skipping. Reuse prior classification when head, feedback, and checks are unchanged.
5. Skip requests with repeated review/repair rounds. A round means change-requesting Review Feedback (a review, Comment, Discussion, or Review Thread) followed by the author's responsive commit push; a mainline-only sync does not count. Count from platform history and handoff records, taking the larger count if they disagree; never reset across conversations. Exclude items at 3 or more rounds from repair (items awaiting final review may only sync mainline): no edits, pushes, replies, thread resolution, or labels. Send an unreviewed third-round head to review-and-merge for final review. If required in-scope issues remain afterward, only that item awaits human action. Record its link, count, and evidence only in the output. If the count is unknown, use normal classification and mark it unknown. An explicit user request naming that item in this round is an exception.

## Handoff

Before reading the previous handoff and freezing the queue, and before writing a handoff or final output, read [Handoff records](references/handoff.md) in full.

## Completion conditions

An item finishes this round when:

- All confirmed required changes are fixed, appropriately verified, committed, and successfully pushed; or
- A concrete blocker prevents progress, with facts, attempted solutions, and an actionable next step recorded; or
- Rechecking confirms no repair is needed, with supporting evidence recorded.

One branch push does not end the batch. Continue until every frozen item reaches one of these states.

## Output

After processing the entire frozen list, summarize:

- The initial repair list and baseline, actual repair items, and skips.
- Requests skipped at 3 or more rounds, distinguishing final-review waits, required-check/approval waits, and human action after failed final review; include counts and evidence.
- Each request's required changes, edits, verification, commits, and push links or identifiers.
- Requests ready for re-review but not yet accepted.
- Unresolved blockers, concurrent changes, permission issues, and next steps.
- Deduplication and classification of newly discovered issues.

Distinguish “changed and pushed,” “awaiting re-review,” “acceptance met,” and “merged”; this skill must not produce the last state. Use clear, everyday Chinese for final user replies/reports and questions requiring a user decision, unless the user explicitly requests another language. Progress, internal subagent prompts/results, handoffs and run records may stay in English. Hosting-platform titles, bodies, Comments and Review Feedback follow the owning repository's language rules, otherwise English. Avoid internal jargon; explain unfamiliar terms on first use; prefer plain terms such as “build output”.
