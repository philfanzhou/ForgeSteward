# ForgeSteward

ForgeSteward is a collection of cross-agent skills for maintaining software repositories. It is designed to help Claude Code, OpenCode, Codex, and other compatible coding agents move work safely from an actionable issue to a reviewed and merge-ready change request.

## The name

**Forge** literally means a workshop where metal is shaped, or the act of creating something through deliberate effort. In software development, a forge is also a platform where source code is hosted and collaboratively developed, such as GitHub, GitLab, or Gitea. Here it represents both the repository platform and the process of shaping an issue into dependable code.

**Steward** means a trusted caretaker: someone responsible for looking after a system, applying its rules, and keeping work moving without claiming unchecked ownership. Here it reflects a careful repository maintainer that inspects project state, protects code quality, and keeps consequential actions subject to explicit policy and human control.

Together, **ForgeSteward** means a trusted steward for the software forge: an agent-assisted toolkit that helps maintainers move repository work forward while respecting review gates, project policy, and human judgment.

## Skills

| Skill | Purpose |
| --- | --- |
| [`forge-steward-check-workflow`](plugins/check-workflow/skills/forge-steward-check-workflow/SKILL.md) | Onboard a repository by checking existing policies and adding only missing, non-conflicting workflow constraints and agent entry references. |
| [`forge-steward-find-work`](plugins/find-work/skills/forge-steward-find-work/SKILL.md) | Find open issues that are sufficiently clear and unblocked to begin work, then generate a bounded execution prompt without implementing it. |
| [`forge-steward-review-and-merge`](plugins/review-and-merge/skills/forge-steward-review-and-merge/SKILL.md) | Review a frozen change-request queue and merge only the changes that satisfy their scope, acceptance, checks, and repository policy. |
| [`forge-steward-fix-feedback`](plugins/fix-feedback/skills/forge-steward-fix-feedback/SKILL.md) | Resolve required review feedback and verified gaps on original change-request branches, then push without merging. |

Each skill is intended to remain independently installable and versioned, while sharing a common core where behavior is genuinely portable across supported agents.

For first-time adoption, ask `forge-steward-check-workflow` to add the missing workflow constraints to the target repository. It preserves existing project rules, language, scope, and instruction sources; conflicting requirements are reported without being overwritten. A check-only request produces a report without edits. Adoption changes are limited to workflow documents and necessary agent document references, with commits and publishing governed by your request and repository policy. It never merges changes or installs other skills.

Repositories with equivalent rules need no duplicate template or mandatory onboarding pass before every task. The other skills remain independently usable and must still apply the target repository's policies. Agent-specific loading details and compatibility limits are documented in the bundled [entrypoint reference](plugins/check-workflow/skills/forge-steward-check-workflow/references/agent-entrypoints.md).

The skill names and core workflows use provider-neutral terminology. Platform adapters map a **change request** to a GitHub pull request, a GitLab merge request, or the equivalent concept on another forge, and map **review feedback** to that platform's comments, discussions, or review threads.

Each plugin keeps one canonical `SKILL.md`. A portable root `plugin.json` and a Codex compatibility manifest package it for Codex; a Claude manifest and repository marketplace package the same file for Claude Code. OpenCode can consume that unchanged skill directory from one of its Agent Skills locations, such as `.agents/skills/<name>`. OpenCode does not consume the Claude or Codex marketplace indexes.

## Calling the skills

All skill names use the `forge-steward-` prefix. Plugin names and the `forge-steward` marketplace remain unchanged: each plugin is still independently installed and versioned. For example, the plugin identifier is `find-work@forge-steward`, and its skill name is `forge-steward-find-work`.

Open an agent session in the repository you want to maintain, select a skill, and append your request. In Codex CLI and the IDE extension, type `$` to select a skill or use `/skills`. Claude Code adds the plugin namespace to the skill name:

| Plugin | Codex skill mention | Claude Code plugin command |
| --- | --- | --- |
| `check-workflow` | `$forge-steward-check-workflow` | `/check-workflow:forge-steward-check-workflow` |
| `find-work` | `$forge-steward-find-work` | `/find-work:forge-steward-find-work` |
| `review-and-merge` | `$forge-steward-review-and-merge` | `/review-and-merge:forge-steward-review-and-merge` |
| `fix-feedback` | `$forge-steward-fix-feedback` | `/fix-feedback:forge-steward-fix-feedback` |

If the selector displays a qualified plugin skill name, select that entry. For example:

```text
$forge-steward-find-work Find up to 10 actionable issues and generate an execution prompt.
```

For OpenCode, install the complete skill directory under a supported location such as `.agents/skills/forge-steward-find-work/`, then ask: "Load the forge-steward-find-work skill and find actionable issues in this repository." OpenCode loads it through its native `skill` tool; the Claude command syntax is not a shared cross-agent interface.

For review and merge, include authorization in your request, for example: "Review the current open change requests and merge those that meet acceptance and repository requirements."

See the official [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills), [Claude Code skill namespaces](https://code.claude.com/docs/en/skills), and [OpenCode skill loading](https://opencode.ai/docs/skills/) documentation for the host-specific interfaces.

### Migrating from 0.1.x

Each plugin moves to `0.2.0` for this invocation-name change. Update the installed plugins through your agent's plugin manager, then start a new session and select the prefixed skills. Update saved prompts and shortcuts: the old unprefixed skill names are no longer provided as aliases. Plugin installation identifiers remain unchanged.

For manually installed skills, replace each old skill directory with the corresponding `forge-steward-<name>` directory, including its bundled resources. Preserve any local modifications before replacing files, and remove the old copy only after verifying the new installation. Keeping both copies exposes both skill names.

## Agent instructions

Repository-wide agent guidance has a single source of truth in [`AGENTS.md`](AGENTS.md). Codex and OpenCode load it directly; [`CLAUDE.md`](CLAUDE.md) imports the same file for Claude Code. Platform adapters must not duplicate shared guidance.

Project design documents other than README files are written in Simplified Chinese. Issue and change-request titles are written in English, while their bodies and comments are written in Simplified Chinese.

## Principles

- Prefer evidence from the current repository over assumptions.
- Keep read-only discovery separate from code-changing and merge operations.
- Require explicit gates for consequential actions such as pushing changes or merging a change request.
- Preserve human review and repository branch-protection rules.
- Share portable skill logic while keeping agent-specific packaging and adapters isolated.
- Make actions and decisions observable, reproducible, and easy to audit.

## Status

ForgeSteward is in early development. The skill interfaces, installation methods, and compatibility guarantees may change before the first stable release.

## License

ForgeSteward is licensed under the [MIT License](LICENSE).
