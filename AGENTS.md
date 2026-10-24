# ForgeSteward Project Guide

## Source of rules

- This file is the single source of truth for repository-level Agent instructions.
- Codex, OpenCode, and ZCode read this file directly. ZCode uses the repository root as its workspace and does not depend on subdirectory scanning or `@import`.
- Claude Code imports this file through `CLAUDE.md` at the repository root.
- Do not duplicate these shared rules in platform adapter files. Maintain them only here to avoid drift.

## Delivery to the main branch

- Update this repository's `main` and default branch only through Pull Requests. Create a working branch before making changes; commit and push on that branch, never directly on the main branch.
- Do not bypass, disable, or weaken remote main-branch rules to complete delivery.
- Remote rules prohibit direct updates, force pushes, and deletion of the protected main branch, with no bypass list. These rules are managed on GitHub; this file does not replace remote protection.

## Project purpose

ForgeSteward is a set of repository-maintenance Skills for multiple coding Agents and code-hosting platforms. They remove workflow rules that duplicate the Skills, prepare Issues for implementation, implement supplied Issue lists and submit Change Requests, review and merge eligible Change Requests, and repair code in response to Review Feedback.

Each Skill must remain independently installable, with a shared version across all plugins. Skill names and core workflows must not depend on a particular platform such as GitHub, GitLab, or Gitea. Share only behavior that is truly common across Agents and hosting platforms. Keep platform-specific APIs, terminology, manifests, directories, and invocation methods in their adapters.

Use these platform-neutral terms throughout the core design:

- `Issue`: an issue or work item on a hosting platform.
- `Change Request`: a change awaiting review and merge, such as a GitHub Pull Request or GitLab Merge Request.
- `Review Feedback`: a Comment, Discussion, or Review Thread on a Change Request.

## Unified version

- The root `VERSION` is the single source of truth for the current source target version, without a `v` prefix. It does not mean that version has been released.
- Versions in every plugin's `plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/plugin.json`, including future plugins, must exactly match `VERSION`. Do not version plugins independently.
- Claude Code and ZCode share `.claude-plugin/marketplace.json`. Each plugin's `version` there is derived metadata for ZCode update detection and must match `VERSION` and the plugin manifests. Synchronize it with `python3 scripts/sync_marketplace.py --write`; CI validates it with `--check`. Do not add unsupported version fields to the Codex marketplace or maintain separate ZCode Skill text or a marketplace index.
- Bump all plugins together for each release, including plugins with no functional changes. Documentation-only and installer-only releases follow the same rule. Individual development commits do not require a bump; an unreleased target version may continue to evolve.
- Agents must not change version numbers on their own. Whether or not `VERSION` is already released, change it only when the user explicitly requests a bump for this work, and synchronize all plugin manifests and the shared marketplace. Otherwise keep the version unchanged; at most mention that the current version is already released and let the user decide whether to bump it.
- If the user requests a bump without a target version, increment only `Z` in `X.Y.Z`, keeping `X.Y` unchanged. Do not independently bump minor or major for new Skills, renames, or incompatible changes. Change another component only when the user explicitly specifies it or the target version. Still document migration for incompatible changes. Adding or changing prerelease suffixes or release channels also requires an explicit user request; do not use a suffix to evade this limit.
- Release Tags must be `v` followed by `VERSION`, and every plugin version in the Release mapping table must match. Follow `docs/releasing.md` before releasing. CI must check that all plugin manifests match `VERSION`.
- Keep published Tags and historical version mapping tables unchanged. Do not rewrite history to adopt new rules; fixes require a new version. Changing version rules does not authorize merging, releasing, or upgrading the user's installation.

## Skill length and compatibility across Agents

- All existing and new Skills share one entry point and supporting rules, without Agent-specific copies. When editing an entry point, description, or referenced file, follow the [cross-Agent Skill compatibility agreement](docs/skill-compatibility.md) and run `python3 scripts/check_skill_limits.py --check`. CI must run the same check.
- `scripts/check_skill_limits.py` is the only numeric source for enforced budgets. Check raw UTF-8 bytes, lines, and description UTF-16 length separately. Do not substitute character counts or estimated tokens for bytes, or describe one platform's recommendation as a universal hard limit.
- New or edited Skill `description` fields must meet the shared description budget in the script so they appear in full in the default discovery lists of the checked Agents. DeepSeek Harness `0.2.0-rc.2` displays at most 500 JavaScript UTF-16 units by default, shortening longer descriptions and adding an ellipsis. This is not a body-loading limit. Put purpose, triggers, and key exclusions in the short description; keep detailed steps in the body or references. Do not increase client configuration limits to evade maintenance budgets. See the compatibility document for versions, units, configurability, and verification boundaries.
- If content exceeds a budget, split it by stage into the Skill package's `references/`, preserving authorization boundaries, stage navigation, and output contracts. The entry point must say which files must be read in full and when, and address truncated tool output, missing files, and context recovery. Do not remove business constraints, read only a body prefix, hide rules in unchecked files, or ask users to increase client budgets to pass validation.
- Use checkable relative Markdown links for referenced rules and include them in each Skill's independent installation. Keep `name` and `description` as single-line plain scalars under repository conventions. Complex YAML or new resource layouts require matching validator and compatibility-evidence updates, not a bypass of validation.
- When adding an Agent, changing a verified version or budget, or encountering a new truncation warning, update the compatibility document's official sources, version/commit, units, verification scope, and unverified areas, and add boundary tests. Passing static checks does not guarantee arbitrary client settings, total context across all Skills, or model behavior.

## Documentation language

- Write all project-maintained documentation, including README files, in clear English.
- This includes architecture descriptions, designs, specifications, decision records, implementation plans, and design documents under `docs/`.
- Preserve code identifiers, API names, commands, file paths, and technical terms accurately, explaining unfamiliar terms in plain English when needed.

## Hosting-platform collaboration language

- Write Issue titles in English.
- Write Change Request titles in English, including GitHub Pull Requests, GitLab Merge Requests, and their equivalents on other platforms.
- Write Issue and Change Request bodies in English.
- Write Comments, Discussions, and Review Threads on Issues, Change Requests, and Reviews in English.
- Quoted code, logs, or external source text may retain their original language; write analysis, conclusions, and action descriptions in English.

## User-facing wording

- Skill requirements for user-facing or hosting-platform content, including final replies and reports, Issue and Change Request bodies, Comments, and Review Feedback replies, must default to clear, everyday English. Honor an explicit language requirement from the user or target repository.
- Rules may use concise internal terminology, but output contracts must not require repeating it verbatim. Explain a necessary unfamiliar term in one sentence on first use.
- Project-maintained content throughout the repository must be English. Keep technical Unicode test inputs and known legacy status aliases narrowly identified as data; do not hide untranslated prose in escapes. `tests/test_skill_wording.py` enforces the content policy and the existing prohibition on `triage` in file or directory names under `plugins/`.
- Prefer familiar descriptions such as “build output” when they make an artifact's purpose clearer.
- The same wording requirements apply to this repository's Issue and Change Request bodies and Comments.

## English working environment

Write in English: project-maintained documentation (README and docs), Issue and Change Request titles and bodies, Comments, Discussions, Review Threads, and future commit messages, unless a maintainer explicitly requests another language. Preserve historical Issues, Change Requests, and comments. Do not translate code, commands, paths, identifiers, logs, technical data, or quoted external text. Preserve other project conventions.
