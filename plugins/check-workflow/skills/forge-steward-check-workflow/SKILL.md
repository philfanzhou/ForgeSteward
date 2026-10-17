---
name: forge-steward-check-workflow
description: Check branch cleanup settings and releases read-only, remove duplicate ForgeSteward workflow rules, safely consolidate root Claude instructions, and configure English collaboration defaults in an existing root entry. Submit cleanup as a PR or MR without merging. Preserve other project conventions; report release findings only. Explicit check-only requests remain read-only.
---

# Check Workflow

## Load the rules

Before checking, read [Skill-owned rules and deletion](references/skill-owned-rules.md), [Check, migrate, and submit](references/procedure.md), [Claude entry migration](references/agent-entrypoints.md), [Collaboration language](references/collaboration-language.md), and [Release pipeline audit](references/release-audit.md) in full, then follow the authorized mode. Read-only checks need these rules too; never act from this summary alone. When comparing another skill's equivalent rules, also inspect the rule files linked from its entry.

These rules are required. Resolve paths from this `SKILL.md`, not the target repository or working directory. If a rule-file read is truncated, continue by line or section through the end (this does not apply to CI logs, test output, or other tool results). If a file is missing or unreadable, identify its path and impact; do not continue affected actions with incomplete rules. After context compaction, reload any missing rules for the current stage.

## Purpose and authorization

ForgeSteward's four work skills alone define Issue readiness/size, Change Request scope, feedback/rounds, repair, merge/closure, handoffs and authorization. Project copies create conflicting sources and grow stale, regardless of strictness or author. Remove them.

For version-controlled project files, delete workflow policy. The only addition/replacement exceptions are verbatim [Claude entry migration](references/agent-entrypoints.md) and the fixed [English collaboration default](references/collaboration-language.md). Add no other rules, marked blocks, reading instructions, Agent entries, or replacement clauses. Preserve [Project conventions](references/skill-owned-rules.md#project-conventions-preserve). Read the hosting platform's automatic branch-deletion setting; record enabled, disabled or unknown; do not change repository settings. Actual post-merge branch cleanup belongs to `review-and-merge`; this skill neither merges nor deletes branches.

An explicit invocation, including selecting the skill with no prompt, authorizes the default flow: check → delete/migrate/configure language → verify → commit, push, and create a Change Request (PR/MR), never merge. Explicit limits in the current request take precedence: check-only means report candidates without editing or creating a branch; local-only means no commit or push; release-audit-only means only the read-only audit and report, with no project changes or delivery. Implicit selection or usage discussion does not authorize publication. Respect target-repository permissions, approvals, and branch protection; the default flow never overrides them.

## Scope

- **Delete workflow policy text:** rule sentences, list items, sections, template instructions, and checkboxes classified as [Skill-owned workflow policy](references/skill-owned-rules.md#skill-owned-workflow-policy), whether written by the project or added by older versions.
- **Delete legacy marked blocks:** deterministically remove the `forge-steward:workflow` and `forge-steward:claude-rules` blocks that `0.2.5` and `0.2.6` inserted in root `AGENTS.md`, using the script.
- **Consolidate Claude entries:** after policy deletion, follow [Claude entry migration](references/agent-entrypoints.md) for tracked root `CLAUDE.md` and `.claude/CLAUDE.md`; report unsafe/nested entries unchanged.
- **Configure collaboration language:** after migration, apply [Collaboration language](references/collaboration-language.md) in a safe existing root entry; report unresolved conflicts unchanged.
- **Delete dangling references:** delete documents containing only workflow policy, together with links, contents entries, and reading instructions pointing to deleted documents or sections.

See [Deletion rules](references/skill-owned-rules.md) for locations and methods. Do not modify business code, dependencies, tests, CI, branch protection, or global/user Agent configuration. Preserve entry mechanisms except this defined migration or imports whose target this cleanup deletes. Do not install plugins, organize Issues, invoke other skills automatically, or merge.

### Release pipeline audit (read-only)

Follow [release audit rules](references/release-audit.md) for tags, announcements, package feeds, prerelease flags, latest pointers and recent runs against the repository's release documentation. Missing documented expectations are findings and make the corresponding judgment “unknown.” Include results only in the final report. The audit and policy deletion do not block each other; retain the existing invocation and infrequent work-cycle schedule.

## Report and change summary

Before finishing, read [Reporting and change summary](references/reporting.md) in full. Report deletions, migrations, language additions/replacements, and delivery from actual file state; separately list release conclusions, findings, unknowns, and inapplicable checks. Audit-only and other zero-change runs must explicitly say “No project files were changed.” Do not include audit findings in the cleanup Change Request body, file them, or fix them. Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts.
