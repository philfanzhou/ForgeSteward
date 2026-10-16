---
name: forge-steward-execute-work
description: Implement a supplied fixed issue list sequentially, using each issue's persisted scope and evidence, and submit independent change requests in the owning repositories without merging. Use when the user hands over issue numbers or URLs for implementation, including a prepare-work result; not for discovering more work, preparing a queue, reviewing merges, or repairing existing review feedback.
---

# Execute Work

## Load the rules

Before implementing, verifying, or submitting any frozen-queue candidate, read [Implementation and submission](references/implementation.md) in full. Use this entry for read-only investigation and missing inputs; never implement or publish from its summary alone. Read [Final report](references/reporting.md) in full before reporting.

These references are required rules. Resolve paths relative to this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Input and authorization

Accept the user's list of Issue numbers, platform-qualified identifiers, or full URLs, such as `#123, #145, #167`. No prepare-work installation, prior run, generated prompt, or previous conversation is required. Use original Issues, persisted evidence, and owning-repository conventions. This skill governs scope, acceptance, and delivery discipline, replacing separate repository rules for the same workflow. Follow repository conventions for language, title/commit formats, templates, build/verification commands, and branch protection.

Explicit invocation with a list requests reading, implementation, verification, commit, push, and Change Request creation for the whole list, not just one PR. Respect narrower read-only, local-only, or no-publication limits. Implicit matching or name discussion grants no additional write permission. This skill never merges; a separately authorized review flow handles merging. Do not invoke other skills automatically.

A standalone invocation without a list requires requesting the missing list, not discovering work. For `[]`, report no work without changing code or creating an empty PR. Resolve short numbers against an unambiguous tracking repository; ask when ambiguous instead of guessing a repository or combining same-numbered tasks. Use the actual platform's available connector, CLI, or API; never hard-code a platform.

## Freeze the complete queue

Before freezing or investigating candidates, read [Freeze the complete queue](references/queue.md) in full. Preserve every input item and its original order, check evidence and existing implementations, and follow that file’s rules for gaps, splitting, and genuine blockers.

## Continue and recover

After each item is submitted, covered by an existing implementation, already complete without changes, or genuinely blocked, continue to the next frozen item until all are handled. Update the queue when the user stops or changes scope. Changing directories, context compaction, or submitting the first PR does not end the batch. Polling external checks must not prevent independent later work.

Use the existing authorized tracker or task record to retain the complete ordered list and each status, original Issue/Change Request links, implementation repository, base/head, branch/workspace, acceptance evidence, valid audits, feedback classification and review rounds, resolved feedback, accepted limits, blockers, and next steps. Without a writable external location, retain a conversation handoff and do not claim persistence. Reload records after context changes; never lose unfinished items or reset review rounds.

Clean only task-owned temporary environments that are clean and contain no unique undelivered work. Retain unmerged PR branches for repairs. Preserve paths and recovery steps for failures, unpushed commits, and necessary experiment outputs; do not delete work to make the environment look clean.

## Final report

Cover all items using [Final report](references/reporting.md). Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts.
