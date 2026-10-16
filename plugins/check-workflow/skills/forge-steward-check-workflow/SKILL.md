---
name: forge-steward-check-workflow
description: Check branch cleanup settings and releases read-only, remove duplicate ForgeSteward workflow rules, and consolidate tracked root Claude instructions into a surviving root AGENTS.md when safe. Submit cleanup as a PR or MR without merging. Preserve project conventions; report release findings only. Explicit check-only requests remain read-only.
---

# Check Workflow

## Load the rules

Before checking, read [Skill-owned rules and deletion](references/skill-owned-rules.md), [Check, migrate, and submit](references/procedure.md), [Claude entry migration](references/agent-entrypoints.md), and [Release pipeline audit](references/release-audit.md) in full, then follow the authorized mode. Read-only checks need these rules too; never act from this summary alone. When comparing another skill's equivalent rules, also inspect the rule files linked from its entry.

These references are required rules. Resolve paths relative to this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Purpose and authorization

Workflow policy belongs only in ForgeSteward's prepare-work, execute-work, review-and-merge, and fix-feedback skills: Issue start conditions, task size, Change Request scope, feedback classification/rounds, repair scope, merge/task closure, handoffs and authorization. Project copies, whatever their strictness or author, create conflicting sources and grow stale as skills change. Remove them.

For version-controlled project files, delete workflow policy. The sole addition exception is the verbatim consolidation of tracked root Claude instructions into an existing root `AGENTS.md` under [Claude entry migration](references/agent-entrypoints.md); add no new rules, marked blocks, reading instructions, Agent entries, or replacement clauses. Preserve conventions that the project still needs and the skills explicitly leave to the repository; see [Project conventions](references/skill-owned-rules.md#project-conventions-preserve). Also check the hosting platform's automatic source-branch deletion setting read-only and record enabled, disabled, or unknown; do not change repository settings. Actual post-merge branch cleanup belongs to `review-and-merge`; this skill neither merges nor deletes branches.

An explicit invocation, including selecting the skill with no prompt, authorizes the default flow: check → delete/migrate → verify → commit, push, and create a Change Request (PR/MR), never merge. Explicit limits in the current request take precedence: check-only means report candidates without editing or creating a branch; local-only means no commit or push. Automatic skill selection, mentioning its name, or asking about usage does not authorize external publication. Respect target-repository permissions, approvals, and branch protection; the default flow never overrides them.

## Scope

- **Delete workflow policy text:** rule sentences, list items, sections, template instructions, and checkboxes classified as [Skill-owned workflow policy](references/skill-owned-rules.md#skill-owned-workflow-policy), whether written by the project or added by older versions.
- **Delete legacy marked blocks:** deterministically remove the `forge-steward:workflow` and `forge-steward:claude-rules` blocks that `0.2.5` and `0.2.6` inserted in root `AGENTS.md`, using the script.
- **Consolidate Claude entries:** after policy deletion, follow [Claude entry migration](references/agent-entrypoints.md) for tracked root `CLAUDE.md` and `.claude/CLAUDE.md`; report unsafe/nested entries unchanged.
- **Delete dangling references:** delete documents containing only workflow policy, together with links, contents entries, and reading instructions pointing to deleted documents or sections.

See [Deletion rules](references/skill-owned-rules.md) for locations, classification, exclusions and methods. Do not modify business code, dependencies, tests, CI, branch protection, or global/user Agent configuration. Preserve entry mechanisms except this defined migration or imports whose target this cleanup deletes. Do not install plugins, organize Issues, invoke other skills automatically, or merge.

### Release pipeline audit (read-only)

Each check also follows the [release audit rules](references/release-audit.md) to compare release tags, announcements (Releases), package feeds, prerelease flags, latest pointers, and recent release runs. Use the target repository's own release documentation for expectations and scope. Missing documented expectations are findings and make the corresponding judgment “unknown.” Include results only in the final report. The audit and policy deletion do not block each other; retain the existing invocation and infrequent work-cycle schedule.

## Report and change summary

Before finishing, read [Reporting and change summary](references/reporting.md) in full. Report deletions, migrations, and delivery from actual file state; separately list release conclusions, findings, unknowns, and inapplicable checks. Audit-only and other zero-change runs must explicitly say “No project files were changed.” Do not include audit findings in the cleanup Change Request body, file them, or fix them. Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts.
