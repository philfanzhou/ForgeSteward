---
name: forge-steward-check-workflow
description: Check branch cleanup settings, reconcile release tags, announcements and package feeds read-only, and remove workflow rules that duplicate the ForgeSteward skills from agent instructions, contributor docs and issue or change-request templates. Submit any deletion as a PR or MR without merging. Project conventions remain intact; release findings are reported only. Explicit check-only requests remain read-only.
---

# Check Workflow

## Load the rules

Before checking, read [Skill-owned rules and deletion](references/skill-owned-rules.md), [Check, delete, and submit](references/procedure.md), and [Release pipeline audit](references/release-audit.md) in full, then follow the authorized mode. Read-only checks need these decision and execution rules too; never select deletions from the entry summary alone. When comparing another skill's equivalent rules, also inspect the rule files linked from its entry.

These references are required rules. Resolve paths relative to this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Purpose and authorization

Workflow policy belongs only in ForgeSteward's prepare-work, execute-work, review-and-merge, and fix-feedback skills: conditions for starting Issues, task size, Change Request scope, feedback classification and rounds, repair scope, merging and closing tasks, handoffs, and authorization. A second set in the project, whether identical, stricter, or looser, creates conflicting sources and becomes outdated as skills change. This skill removes that second source.

For version-controlled project files, this skill only deletes: add no rules, marked blocks, reading instructions, Agent entries, or replacement clauses. Preserve conventions that the project still needs and the skills explicitly leave to the repository; see [Project conventions](references/skill-owned-rules.md#project-conventions-preserve). Also check the hosting platform's automatic source-branch deletion setting read-only and record enabled, disabled, or unknown; do not change repository settings. Actual post-merge branch cleanup belongs to `review-and-merge`; this skill neither merges nor deletes branches.

An explicit invocation, including selecting the skill with no prompt, authorizes the default flow: check → delete → verify → commit, push, and create a Change Request (PR/MR), never merge. Explicit limits in the current request take precedence: check-only means report candidates without editing or creating a branch; local-only means no commit or push. Automatic skill selection, mentioning its name, or asking about usage does not authorize external publication. Respect target-repository permissions, approvals, and branch protection; the default flow never overrides them.

## Scope

- **Delete workflow policy text:** rule sentences, list items, sections, template instructions, and checkboxes classified as [Skill-owned workflow policy](references/skill-owned-rules.md#skill-owned-workflow-policy), whether written by the project or added by older versions.
- **Delete legacy marked blocks:** deterministically remove the `forge-steward:workflow` and `forge-steward:claude-rules` blocks that `0.2.5` and `0.2.6` inserted in root `AGENTS.md`, using the script.
- **Delete dangling references:** delete documents containing only workflow policy, together with links, contents entries, and reading instructions pointing to deleted documents or sections.

See [Skill-owned rules and deletion](references/skill-owned-rules.md) for candidate locations, classification, exclusions, and deletion methods. Do not modify business code, dependencies, tests, CI, branch protection, or global/user Agent configuration. Preserve entry imports such as `CLAUDE.md`'s `@AGENTS.md` unless this deletion removes their target. Do not install plugins, organize Issues, invoke other skills automatically, or merge.

### Release pipeline audit (read-only)

Each check also follows the [release audit rules](references/release-audit.md) to compare release tags, announcements (Releases), package feeds, prerelease flags, latest pointers, and recent release runs. Use the target repository's own release documentation for expectations and scope. Missing documented expectations are findings and make the corresponding judgment “unknown.” Include results only in the final report. The audit and policy deletion do not block each other; retain the existing invocation and infrequent work-cycle schedule.

## Report and change summary

Before finishing, read [Reporting and change summary](references/reporting.md) in full. Report deletions and delivery from actual file state; separately list release conclusions, findings, unknowns, and inapplicable checks. Audit-only and other zero-change runs must explicitly say “No project files were changed.” Do not include audit findings in the cleanup Change Request body, file them, or fix them. Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts.
