# ForgeSteward

ForgeSteward is a collection of cross-agent skills for maintaining software repositories. It is designed to help Claude Code, OpenCode, Codex, and other compatible coding agents move work safely from an actionable issue to a reviewed and merge-ready change request.

## Install and use

Choose your agent below. The four plugins install independently: `check-workflow`, `find-work`, `review-and-merge`, and `fix-feedback`. Their skill names share the `forge-steward-` prefix. Install only the ones you need, then start a new agent session in the repository you want to maintain.

The examples pin the `v0.2.0` repository snapshot. See its [release version matrix](docs/releases/v0.2.0.md), [fixed-version installation and rollback guide](docs/versioned-installation.md), and [release policy](docs/releasing.md). Verify the tag is published on the [GitHub Releases page](https://github.com/philfanzhou/ForgeSteward/releases); a document on `main` alone is not a published release. If you already configured the `forge-steward` marketplace, follow the switching guide before adding another ref with the same name. Omit the ref only when intentionally following development on the default branch.

For removal, see [Uninstall and verify](#uninstall-and-verify), including scopes, caches, and manual-copy leftovers.

### Codex

Run these commands in your terminal (requires a Codex CLI with `plugin` support):

```bash
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.0
codex plugin add check-workflow@forge-steward
codex plugin add find-work@forge-steward
codex plugin add review-and-merge@forge-steward
codex plugin add fix-feedback@forge-steward
codex plugin list
```

In a new session, type `$` to select a skill, for example:

```text
$forge-steward-find-work Find up to 10 actionable issues and generate an execution prompt.
```

### Claude Code

Run these commands one at a time in the Claude Code conversation:

```text
/plugin marketplace add philfanzhou/ForgeSteward@v0.2.0
/plugin install check-workflow@forge-steward
/plugin install find-work@forge-steward
/plugin install review-and-merge@forge-steward
/plugin install fix-feedback@forge-steward
```

Restart the session and invoke the plugin's namespaced skill:

```text
/find-work:forge-steward-find-work Find up to 10 actionable issues and generate an execution prompt.
```

### OpenCode

Use the included installer with Python 3.9 or newer. It copies each complete skill from this checkout into OpenCode's native search paths, including references, and needs no Python packages, model credentials, or running OpenCode process. OpenCode does not consume the Claude or Codex marketplaces.

On macOS or Linux, obtain the source once (skip this if you already have this checkout):

```bash
mkdir -p "$HOME/code"
git clone --branch v0.2.0 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward"
```

From the repository you want to maintain, install all four skills with one command:

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" install --all --project .
```

Or install only one:

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" install find-work --project .
```

The installer accepts either a plugin short name or the full skill name. `--project .` writes to the current directory's `.opencode/skills/`; the project directory must already exist. To make the skills available across your projects, use `--user` instead of `--project .`. User installs use `OPENCODE_CONFIG_DIR/skills` when set, otherwise `XDG_CONFIG_HOME/opencode/skills`, or `~/.config/opencode/skills` by default. The resolved target is printed before changes.

On native Windows with Python 3.9+ and Git installed, use PowerShell (substitute your checkout path):

```powershell
py -3 "$HOME\code\ForgeSteward\scripts\opencode.py" install --all --project .
```

The same script supports all three operating systems; the CI matrix checks macOS, Linux, and Windows. Actual OpenCode discovery is tested with `1.18.30` on macOS locally and Linux in CI. There is no separate native-Windows OpenCode runtime test.

Restart OpenCode in the target repository and ask:

```text
Load the forge-steward-find-work skill and find actionable issues in this repository.
```

With OpenCode installed, `opencode debug skill` lists the discovered names and locations. See [installation maintenance and troubleshooting](#opencode-installation-maintenance) for updates, uninstalling, version selection, and conflicts.

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

Starting with plugin version `0.2.1`, Codex plugin and skill display names use `<Task> - ForgeSteward`, for example `Find Work - ForgeSteward`. These human-facing labels are separate from the installation IDs and skill invocation names below. This display-name fix is pending the next repository release; the pinned `v0.2.0` installation examples still install the previous labels. Updating requires selecting a release containing the fix, not reinstalling the unchanged `v0.2.0` snapshot; see the [version switching guide](docs/versioned-installation.md).

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

OpenCode loads these names through its native `skill` tool; use the natural-language example in the installation section. The Claude command syntax is not a shared cross-agent interface.

For review and merge, include authorization in your request, for example: "Review the current open change requests and merge those that meet acceptance and repository requirements."

See the official [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills), [Claude Code skill namespaces](https://code.claude.com/docs/en/skills), and [OpenCode skill loading](https://opencode.ai/docs/skills/) documentation for the host-specific interfaces.

### Migrating from 0.1.x

Each plugin moves to `0.2.0` for this invocation-name change. Update the installed plugins through your agent's plugin manager, then start a new session and select the prefixed skills. Update saved prompts and shortcuts: the old unprefixed skill names are no longer provided as aliases. Plugin installation identifiers remain unchanged.

For manually installed skills, replace each old skill directory with the corresponding `forge-steward-<name>` directory, including its bundled resources. Preserve any local modifications before replacing files, and remove the old copy only after verifying the new installation. Keeping both copies exposes both skill names.

## OpenCode installation maintenance

Run these commands from the target project. Use `--user` in place of `--project .` for a user-level install:

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" list
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status --all --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" update find-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" uninstall find-work --project .
```

Replace `find-work` with `--all` to update all skills or uninstall all managed skills. `update` requires selected skills to be installed; if you installed only one, update it by name. `uninstall --all` removes only directories with this installer's receipt, even if their source no longer exists in the checkout. It preserves unrelated skills and may leave empty `.opencode/skills` containers. It also reports matching unmanaged or legacy-name candidates in that target; exit code `2` means leftovers need inspection, not that they were deleted. See [Uninstall and verify](#uninstall-and-verify) for the complete boundary.

The installer uses the current local checkout and does not fetch or execute remote installation commands. Tagged installs use a detached checkout: fetch tags, select the next reviewed tag or commit, then run `update` as described in the [switching guide](docs/versioned-installation.md). Do not run `git pull` on a detached checkout. Only a clean development checkout tracking `main` should use `git -C "$HOME/code/ForgeSteward" pull --ff-only` before updating. An explicit `update` follows the selected checkout, including an intentional downgrade. Use a separate clean checkout if your source has local work.

Each installed skill contains `.forge-steward-install.json`, recording its plugin version, source commit (when Git is available), source dirty state, and content hashes. Repeating an identical install makes no changes. A changed source/version requires `update`; even when the version string is unchanged, content changes are detected.

If a target was copied manually, its receipt is damaged, or its files have been edited, installation/update/uninstall stops with the affected path. There is no `--force` overwrite. Back up or move the complete conflicting directory outside OpenCode's skill search paths, inspect and preserve your edits, then install again. Existing `.agents/skills` or `.claude/skills` copies are not adopted or removed; use `opencode debug skill` to check for duplicate names or unexpected locations. Symlink sources, symlink install paths, and linked content are not managed by this installer.

Selected targets are checked and staged before changing installed skills. Ordinary copy/rename failures roll back the batch. A lock prevents overlapping installer processes; avoid editing installed files while an operation runs. Forced termination or power loss can leave `.forge-steward.lock` and `.forge-steward-txn-*` beside the `skills` directory. Confirm the installer has stopped, preserve the entire transaction directory, and inspect its `old-<skill>` backups before restoring missing installations or moving conflicting copies aside. Once recovery is complete, move the transaction outside the config directory and remove the stale lock before retrying. No crash-durable or hostile-concurrent-writer guarantee is made.

If OpenCode does not discover the skills, confirm the printed target and run `status`, then `opencode debug skill` from the target project. Check OpenCode's skill permissions, custom configuration, and any duplicate manual installs. The installer never changes agent permissions or configuration files.

Development checks: `python3 -m unittest discover -s tests -v`. Set `FORGESTEWARD_OPENCODE` to an OpenCode executable to include actual discovery and removal checks in isolated temporary configuration directories; otherwise that test is explicitly skipped. See the Chinese [installer design and verification notes](docs/opencode-installer.md).

## Uninstall and verify

Uninstall in the same agent environment and scope used for installation. Stop active skill-driven work first, then start a fresh session after removal: an existing conversation can still contain previously loaded instructions. Disabling a plugin is not uninstalling it. Do not delete an entire agent configuration or cache directory to remove these four skills.

### Codex removal

Run in your terminal, selecting only the plugins you installed:

```bash
codex plugin remove check-workflow@forge-steward
codex plugin remove find-work@forge-steward
codex plugin remove review-and-merge@forge-steward
codex plugin remove fix-feedback@forge-steward
codex plugin list --json
```

The `remove` command removes the plugin and its local cache (command syntax checked with Codex CLI `0.154.0`). If you no longer want this marketplace, remove its source after uninstalling the plugins:

```bash
codex plugin marketplace remove forge-steward
codex plugin marketplace list
```

Alternatively, use the plugin browser's **Uninstall plugin** action. Check installed state rather than merely seeing a plugin in the available catalog. Start a new session and confirm the `forge-steward-` skills are absent. Repeat for other Codex environments where you installed them. Administrator-managed installations require the administrator's action. See [official plugin removal guidance](https://learn.chatgpt.com/docs/plugins#remove-a-plugin); use `codex plugin remove --help` to check the CLI version in your environment.

### Claude Code removal

For user-scope installations, run in your terminal:

```bash
claude plugin uninstall check-workflow@forge-steward --scope user
claude plugin uninstall find-work@forge-steward --scope user
claude plugin uninstall review-and-merge@forge-steward --scope user
claude plugin uninstall fix-feedback@forge-steward --scope user
claude plugin list
```

If installed at `project` or `local` scope, run the corresponding commands with that scope from each affected project. When no longer needed, remove the marketplace declaration and check the result:

```bash
claude plugin marketplace remove forge-steward
claude plugin marketplace list
```

Check all applicable scopes and a new session's skill list. CLI syntax was checked with Claude Code `2.1.269`. The final-scope uninstall deletes plugin persistent data by default; `--keep-data` explicitly retains it. Old plugin versions can remain in the cache pending background cleanup, so successful uninstall is not an immediate zero-disk-residue guarantee. If immediate disk cleanup is needed, close relevant sessions and inspect only ForgeSteward-owned cache entries before removing confirmed unused copies; never delete a shared cache wholesale. See the official [uninstall reference](https://code.claude.com/docs/en/plugins-reference#plugin-uninstall) and [cache lifecycle](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution).

### OpenCode removal

From each target project, remove all installer-managed skills (or replace `--all` with one short or full skill name):

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" uninstall --all --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status --all --project .
opencode debug skill
```

For user-level installations, separately run:

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" uninstall --all --user
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status --all --user
```

Use the same `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` values as when installing. On Windows, replace `python3` with `py -3` and use your checkout's Windows path, as in the installation example above. Keep the installer checkout until removal is verified.

The uninstall report is deliberately bounded:

- It checks only immediate entries in the printed target, not every project, user directory, ancestor, compatibility path, or custom search path. `--all` reports `forge-steward-*` entries and the four historical names `check-workflow`, `find-work`, `review-and-merge`, `fix-feedback`. Named uninstall checks only the selected names and their known historical counterparts; intentionally retained plugins do not make that operation fail.
- Managed, unchanged installations are removed with resources and receipts. Modified or corrupt selected installations still block the entire planned batch. Missing-receipt/manual copies are not automatically adopted or deleted; `--all` can remove valid managed installations while reporting such leftovers. Historical names are only **candidates**, because another author's skill can have the same name.
- Exit `0` means no matching candidates remain **within that limited scan**. Exit `1` means the operation or scan failed. Exit `2` means removal finished but matching candidates remain (argument-parser usage errors also use `2`; distinguish them by the message). A failed uninstall also reports residues when the target can still be inspected. Empty skill/config containers are allowed; no crash-recovery guarantee is added.

Inspect each reported path, preserve user edits, and move only confirmed copies outside all skill search paths or delete them with explicit ownership confirmation. Do not reinstall a removed skill just to clear a warning. Re-run uninstall to verify its limited report, then `opencode debug skill` to verify actual discovery. `status --all` checks current checkout names, not every legacy or retired name.

OpenCode also discovers project/user `.agents/skills` and `.claude/skills` copies. Check those separately, along with ancestor and custom paths and any old unprefixed installations; the installer does not remove them. A scope being clean does not prove the skill is unavailable elsewhere. See [OpenCode discovery paths](https://opencode.ai/docs/skills/).

### What removal does not undo

Uninstall removes availability, not work already performed. Changes made by `check-workflow` to project rules or agent entry documents, code commits, issues, PRs, comments, and conversation history remain project/user assets. Reverting those requires a separate reviewed change; do not delete `AGENTS.md` or `CLAUDE.md` wholesale. Independently configured credentials, integrations and automation are not revoked by skill removal either. A downloaded ForgeSteward source checkout is separate from installed copies; retain it if you develop the project, or remove it only after checking for local work and completing uninstall verification.

## The name

**Forge** literally means a workshop where metal is shaped, or the act of creating something through deliberate effort. In software development, a forge is also a platform where source code is hosted and collaboratively developed, such as GitHub, GitLab, or Gitea. Here it represents both the repository platform and the process of shaping an issue into dependable code.

**Steward** means a trusted caretaker: someone responsible for looking after a system, applying its rules, and keeping work moving without claiming unchecked ownership. Here it reflects a careful repository maintainer that inspects project state, protects code quality, and keeps consequential actions subject to explicit policy and human control.

Together, **ForgeSteward** means a trusted steward for the software forge: an agent-assisted toolkit that helps maintainers move repository work forward while respecting review gates, project policy, and human judgment.

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
