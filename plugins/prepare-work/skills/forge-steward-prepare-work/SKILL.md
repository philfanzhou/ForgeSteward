---
name: forge-steward-prepare-work
description: Prepare repository issues for implementation by investigating blockers and recording scope, acceptance criteria, and evidence. Use for work discovery, issue preparation, or advancing blocked tasks; not implementation or review repair. Return only a single-line list of independent ready issues, prioritizing baseline backlog and its prerequisites before newly created work. Default to at most 10 issues unless the user specifies a count; do not implement or generate an execution prompt.
---

# Prepare Work

## Load the rules before preparation

This file is the entry; detailed rules live in its skill directory's `references/`. Resolve relative paths from this `SKILL.md`, not the target repository or working directory. Use available file-reading tools to read each stage's files in full before acting. These are required rules, not optional examples; the entry summary alone cannot establish readiness.

1. Before preparation, read [Queue and initial screening](references/queue-and-screening.md), [Readiness requirements](references/readiness.md), and [Batch relationships and verification resources](references/batch-relations.md). Freeze the queue and audit baseline, then screen and order against all requirements. Default to at most 10 items, unless the user requests another count; prioritize existing backlog before work added during the cycle.
2. Before handling preparation gaps, mainline blockers, or existing candidates marked blocked, read [Advance and recheck blockers](references/blockers.md). Continue all investigation and experiments that can proceed autonomously; do not skip backlog based on stale blockers.
3. Before the first Issue update, saving intermediate evidence, or switching tasks, read [Handoff and recovery](references/handoff.md). Read it again before final output, together with the queue file's recheck requirements, to confirm a complete handoff.

Check every rule-file read for completeness. If truncated, read further by line or section through the end; a truncated result does not count as a full read (this does not apply to CI logs, test output, or other tool results). If a reference is missing or unreadable, identify its path and impact; do not continue affected preparation or selection with incomplete rules. After context compaction, reload missing current-stage rules.

## Purpose and authorization

Advance original Issues until the next implementer can start from the Issue alone. Candidate discovery, technical investigation, minimal experiments, narrowing the design, and Issue updates form one preparation flow. Do not hand the user an independently actionable next step after just one investigation pass. Do not implement production changes, create implementation branches or Change Requests, or generate/execute an implementation prompt.

Explicit invocation without scope limits includes necessary investigation and original Issue updates. Respect read-only, discussion-only, and write-location limits. Implicit matching or mentioning the skill grants no new authorization. Select the connector, CLI, or hosting API from the actual remote; do not require a platform. Reads, experiments, and writes must respect user authorization, owning-repository conventions, and environment permissions.

This skill governs Issue readiness, task size, and preparation handoff, replacing separate repository rules for the same workflow. Follow repository conventions for language, title format, Issue template structure, and platform permissions.

## Final output contract

The final reply must be one ordered Issue list on a single line, separated by comma and space, with no heading, explanation, summary, Markdown links, code fence, prompt, or manual line break. For one unambiguous tracking repository, use `#123, #145, #167`. Across tracking repositories, use platform-supported fully qualified identifiers. If these do not uniquely identify platform/repository, use original Issue full URLs on the same line. Cross-repository implementation does not change the original Issue identity; record the owning repository inside the Issue.

Output `[]` when none meet the requirements. First finish actionable preparation and explain genuine blockers, missing permissions, an empty queue, or all work being complete in the Issue or progress updates. `[]` is no substitute for preparation that can still proceed. Give progress and necessary questions during the work, not again in the final line. Preparation is not feature delivery; do not close a task merely because it is ready.

Apart from this one-line format, use clear, everyday Chinese for final user replies/reports and questions requiring a user decision, unless the user explicitly requests another language. Progress, internal subagent prompts/results, handoffs and run records may stay in English. Hosting-platform titles, bodies, Comments and Review Feedback follow the owning repository's language rules, otherwise English. Avoid internal jargon; explain unfamiliar terms on first use; prefer plain terms such as “build output”.
