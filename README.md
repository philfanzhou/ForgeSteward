# ForgeSteward

ForgeSteward is a collection of cross-agent skills for maintaining software repositories. It is designed to help Claude Code, OpenCode, Codex, and other compatible coding agents move work safely from an actionable issue to a reviewed and merge-ready change request.

## The name

**Forge** literally means a workshop where metal is shaped, or the act of creating something through deliberate effort. In software development, a forge is also a platform where source code is hosted and collaboratively developed, such as GitHub, GitLab, or Gitea. Here it represents both the repository platform and the process of shaping an issue into dependable code.

**Steward** means a trusted caretaker: someone responsible for looking after a system, applying its rules, and keeping work moving without claiming unchecked ownership. Here it reflects a careful repository maintainer that inspects project state, protects code quality, and keeps consequential actions subject to explicit policy and human control.

Together, **ForgeSteward** means a trusted steward for the software forge: an agent-assisted toolkit that helps maintainers move repository work forward while respecting review gates, project policy, and human judgment.

## Planned skills

| Skill | Purpose |
| --- | --- |
| `find-work` | Find open issues that are sufficiently clear and unblocked to begin work. |
| `review-and-merge` | Review an open change request, verify required quality and policy gates, and merge only when the configured conditions are satisfied. |
| `fix-feedback` | Identify actionable review feedback, update the code, run relevant checks, and report what was addressed. |

Each skill is intended to remain independently installable and versioned, while sharing a common core where behavior is genuinely portable across supported agents.

The skill names and core workflows use provider-neutral terminology. Platform adapters map a **change request** to a GitHub pull request, a GitLab merge request, or the equivalent concept on another forge, and map **review feedback** to that platform's comments, discussions, or review threads.

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
