# Skill-owned rules and deletion

## Principle

ForgeSteward's four skills alone define workflow policy. Project policies neither supplement nor replace them. check-workflow removes this second source, preserving conventions explicitly left to the repository.

After deletion, constraints apply only on skill invocation. Other conversations/contributors no longer find them in project documents. This is intentional, not a retention reason.

## Skill-owned workflow policy

Delete rules in these dimensions regardless of strictness or authorship, including rules from older check-workflow:

| Dimension | Owning skill | Common project clauses |
| --- | --- | --- |
| Stages and authorization | All | Preparation/implementation/review/repair stages; authorization for reading, Issue edits, code changes, pushes, Change Requests, and merges; read-only analysis leaves files unchanged; preserve existing user work |
| Conditions before starting an Issue | prepare-work | Readiness requires scope, exclusions, design, implementation repository/dependencies, individually verifiable acceptance and applicable failure/cancellation/security/migration/concurrency outcomes, compatibility/rollback; guarantees, non-guarantees, caller responsibilities; code/test/contract/configuration/migration-history/deployment-path audits; closed prerequisites and consistent dependency links/labels; separately filed and linked adjacent issues; no empty required template sections; adding/removing ready labels |
| Task size and splitting | prepare-work, execute-work | One Issue per Change Request; split a second independent contract, migration, or interface group; feature-size thresholds; tracker/task split; no implementation Change Request for a tracker; authoritative semantic model and end-to-end scenarios for complex protocol/state work |
| Implementation discipline | execute-work | Independent branches from latest mainline without stacking unmerged work; binding exclusions; no incidental refactors, renames, dependency updates, or adjacent fixes; acceptance checked item by item; verify failure/cancellation/security/concurrency with implementation; green CI is not acceptance; link Change Request to Issue and record actual verification |
| New findings | All | Deduplicate; file/link adjacent or pre-existing defects separately; missed work in closed tasks counts as rework; do not refile accepted non-guarantees |
| Feedback classification and rounds | review-and-merge, fix-feedback | Distinguish introduced from pre-existing issues; whether optional suggestions block; scope disputes; review-round cap, third-round scope/semantic audit, stop incremental patching and remove ready status |
| Merge and task closure | review-and-merge | Acceptance, checks, and matching head before merge; confirm state, close Issues, reconcile parents after merge; delete remote branches, clean worktrees/local branches, update mainline |
| Repair scope | fix-feedback | Only required in-scope feedback, deterministic CI failures, and acceptance gaps; push original branch; repair never merges |
| Handoff and state | All | Persist Issue/Change Request, baseline, acceptance evidence, review rounds, and blockers across conversations; never reset rounds; distinguish ready, submitted, accepted, merged, closed |

## Project conventions (preserve)

Preserve conventions explicitly left to the repository:

- Languages for documentation, Issues, Change Requests, reviews, and code comments; Issue/Change Request title, commit-message, and branch-name formats.
- Issue/Change Request template structure and completion guidance, such as “Scope,” “Acceptance criteria,” “Verification,” and “Compatibility impact” headings and their expected contents.
- Merge methods, required checks, approval counts, and branch protection settings.
- Build, test, migration, smoke-check, and other verification commands, plus engineering requirements to run particular checks or add certain tests for a class of change.
- Architecture boundaries, security constraints, compatibility/migration requirements, configuration/deployment contracts, documentation updates, versioning, and release processes.
- Agent entry and loading mechanisms, such as `CLAUDE.md` importing `@AGENTS.md`.

When a rule mixes workflow policy and project conventions, delete only its policy portion under the methods below.

## Candidate locations

- Root/nested `AGENTS.md` and `CLAUDE.md`; report `AGENTS.override.md` without editing it.
- `CONTRIBUTING.md` and documents in `docs/` or elsewhere about collaboration, delivery, review, or Agent workflows.
- Issue/Change Request templates, such as `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `.gitlab/issue_templates/`, and `.gitlab/merge_request_templates/`.

Do not search business code, tests, CI, or non-document configuration. Historical process descriptions in ADRs, changelogs, release notes, and retrospectives are not current rules; preserve them. Product business processes, such as authentication or approval workflows, are not this workflow policy.

## Cases to retain

Retain these for maintainer decision, explaining why in the Change Request:

- Classification under the table is uncertain, or policy and conventions are intertwined so deletion alone cannot preserve the convention.
- Content has references outside candidate locations, such as README, a code comment, or a script. If the referrer itself is a candidate, remove its reference too.
- Maintainers explicitly retained the content in an earlier Change Request review/discussion. Later runs report it without another deletion.

## Deletion methods

- **Whole section:** if entirely policy, delete from its heading to the next equal/higher heading, including the extra blank line.
- **List item or sentence:** delete only policy items/lines/sentences in a mixed section. If deleting a middle numbered item would break numbering, mark it undecided.
- **Clause:** when conventions and policy are coordinated by commas, semicolons, or “and,” delete only the policy clause, preserving all other characters. For a final clause, change its preceding comma/semicolon to a period; this is the sole allowed character replacement. If the result is ungrammatical or needs connective changes, mark it undecided.
- **Template:** preserve section headings and completion guidance; delete policy sentences, comments, and checkboxes. If all checks under a section are policy, delete that entire section.
- **Whole document:** delete an entirely policy document, along with reading instructions, links, and contents entries pointing only to it.
- **Legacy blocks:** use `scripts/remove_workflow_blocks.py`. If root `AGENTS.md` has no other content after deletion, delete it and its import in `CLAUDE.md`; if `CLAUDE.md` is then empty, delete it too.
- Never rewrite, combine, or reformat retained text, relocate deleted rules, or write replacement clauses.

## Records and repeated runs

Record each item's file, original line range, heading/first line, dimension and owning skill, equivalent skill clause, deletion method, and outcome (deleted, or undecided with reason).

Before deleting, compare each clause to its owning skill's full text. If equivalent semantics are absent (for example, the project requires caller responsibilities but the skill only requires guarantees/non-guarantees), still delete under these rules since skills do not adopt project policy. Separately list a “skill gap” in the Change Request, quoting the original and missing semantics for maintainers to add to the skill. A same-dimension rule is no substitute for clause-by-clause comparison. Once deletion merges, repeated runs no longer find that content. Unchanged undecided items are reported again without a diff. New policy dimensions in a skill version may yield new candidates next run; that is a version change, not repeated editing.
