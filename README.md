# ForgeSteward

ForgeSteward is a collection of cross-agent skills for maintaining software repositories. It is designed to help Claude Code, OpenCode, Codex, ZCode, and other compatible coding agents move work safely from an actionable issue to a reviewed and merge-ready change request.

The current source targets **0.2.7**, with five independent plugins: `check-workflow`, `prepare-work`, `execute-work`, `review-and-merge`, and `fix-feedback`. A source version is not proof of publication: confirm the matching tag and non-draft [GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases). See the [v0.2.7 version matrix, changes and installation guide](docs/releases/v0.2.7.md). This release keeps all workflow policy in the four work skills, turns check-workflow into a cleanup that removes project rules duplicating them, and makes review-and-merge and fix-feedback leave change requests with three or more feedback rounds for human handling.

The five-plugin split shipped in [v0.2.3](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.3): `prepare-work` replaces `find-work` and returns only a single-line issue list; `execute-work` implements that list and opens independent change requests. When migrating from v0.2.1 or earlier, follow the rename instructions in the selected Release, not just a tag substitution in the historical commands below.

## Install and use — ZCode development preview

ZCode reuses our Claude-compatible marketplace and plugin manifests; no separate skill copies, ZCode-specific plugin manifests, or Python installer are needed. This preview is included from **v0.2.3**, not in the historical v0.2.1 examples below. Packaging and bundled-CLI discovery were checked with ZCode desktop **3.11.2** (bundled CLI **0.16.5**); desktop marketplace installation and model behavior remain unverified. See [ZCode setup and verification](docs/zcode.md).

1. Open the repository you want to maintain in ZCode. Go to **Settings → Plugins → Create → Add marketplace** (some versions use **Discover → +**).
2. For development testing, add the **absolute root path of a reviewed ForgeSteward checkout containing this guide**, not its `.claude-plugin` subdirectory. Adding `philfanzhou/ForgeSteward` instead follows the remote default branch; it does not select a release or include unmerged local changes. For a fixed release, use the [snapshot procedure](docs/zcode.md#固定版本与回退), after confirming that release exists.
3. Under the `forge-steward` marketplace, install and enable any of the five plugins listed above. Verify installed versions and source paths, then confirm the skills in **Settings → Skills**.
4. In a new task, type `$` and select `forge-steward-prepare-work`; `/` also has a Skills group. If the picker shows a plugin-qualified name, select that entry. You do not need to paste the skill's instructions again. Execution still needs the issue list: `$forge-steward-execute-work #123, #145`.

ZCode's picker is not guaranteed to display Codex's `<Task> - ForgeSteward` label. Use the stable `forge-steward-` name and verify the source. Git/forge authentication, repository permissions and explicit task limits still apply. For updates, rollback and removal, follow [Upgrade ZCode skills](#upgrade-zcode-skills) and [ZCode removal](#zcode-removal); upgrading ZCode itself does not upgrade ForgeSteward.

## Install and use — published v0.2.1

The following examples install the historical v0.2.1 snapshot; they do not include prepare-work or execute-work. Its four plugins install independently: `check-workflow`, `find-work`, `review-and-merge`, and `fix-feedback`. Their skill names share the `forge-steward-` prefix. Install only the ones you need, then start a new agent session in the repository you want to maintain.

The examples pin the `v0.2.1` repository snapshot. See its [release version matrix](docs/releases/v0.2.1.md), [fixed-version installation and rollback guide](docs/versioned-installation.md), and [release policy](docs/releasing.md). Verify the tag is published on the [GitHub Releases page](https://github.com/philfanzhou/ForgeSteward/releases); a document on `main` alone is not a published release. If you already configured the `forge-steward` marketplace, follow the switching guide before adding another ref with the same name. Omit the ref only when intentionally following development on the default branch.

Already installed? See [Upgrade and keep only the selected version](#upgrade-and-keep-only-the-selected-version). To remove everything, see [Uninstall and verify](#uninstall-and-verify). Both cover Codex, Claude Code, OpenCode and the ZCode preview; upgrading the agent application itself does not upgrade a pinned ForgeSteward release.

### Codex

Run these commands in your terminal (requires a Codex CLI with `plugin` support):

```bash
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
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
/plugin marketplace add philfanzhou/ForgeSteward@v0.2.1
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
git clone --branch v0.2.1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward"
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

## Upgrade and keep only the selected version

Choose the newest **published, non-prerelease** tag you want from [GitHub Releases](https://github.com/philfanzhou/ForgeSteward/releases), then read its plugin version matrix and migration notes. The commands below target `v0.2.1`; confirm that its Tag and Release are published before running them: **replace it with your chosen published tag before upgrading**. Reusing `v0.2.1` reinstalls that snapshot; it does not install unpublished fixes from a PR or `main`. A repository tag selects the whole marketplace snapshot. Under the unified version policy, tag `vX.Y.Z` contains only plugin packages versioned `X.Y.Z`, including plugins with unchanged functionality. `find-work@forge-steward` is a plugin/marketplace ID, not a version selector.

Before removal, confirm the target release exists and is compatible, record your current ref, installed subset and scopes, and back up local modifications and any plugin data you need **outside all agent discovery/cache directories**. Stop active skill-driven work. Run each step only after the previous step succeeds; if reinstallation fails, restore the recorded release using the same procedure. Do not delete backups until the new installation is verified.

| Agent | How the selected release replaces the old one | What may still remain |
| --- | --- | --- |
| Codex | Uninstall installed ForgeSteward plugins, replace the marketplace ref, reinstall the same subset. | Other environments, manual skill copies, or untracked caches need separate inspection. |
| Claude Code | Uninstall in the recorded scopes, replace the marketplace ref, reinstall in those scopes. | Old version caches can await background cleanup; other scopes and manual copies are separate. |
| OpenCode | Select the source tag, then `update` the installed skills in each intended scope. | Other scopes, retired names and manually copied skills are not removed by `update`. |
| ZCode | Refresh a moving marketplace and update installed plugins; for a fixed snapshot, switch the local marketplace source and reinstall the selected subset. | Imported skills, retired names, other workspaces/hosts and unused caches need separate inspection. |

### Upgrade Codex

In the terminal for the Codex environment you actually use, inspect the current installation:

```bash
codex plugin marketplace list
codex plugin list --json
```

The following example assumes all four plugins are installed. For a partial install, omit both the removal and reinstallation lines for plugins you do not use. Remove **all installed plugins from this marketplace** before replacing its ref, not just `find-work`:

```bash
codex plugin remove check-workflow@forge-steward
codex plugin remove find-work@forge-steward
codex plugin remove review-and-merge@forge-steward
codex plugin remove fix-feedback@forge-steward
codex plugin marketplace remove forge-steward
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
codex plugin add check-workflow@forge-steward
codex plugin add find-work@forge-steward
codex plugin add review-and-merge@forge-steward
codex plugin add fix-feedback@forge-steward
codex plugin marketplace list
codex plugin list --json
```

Check the selected source/ref, installed state and local package versions against the Release matrix, then verify the skills in a new session. If the CLI is managing the same Codex environment used by the desktop app, no separate desktop reinstall is needed; start a new task and reopen the app if its picker remains stale. A different host, account or configuration environment must be checked separately. Administrator/project-controlled sources must be changed through their owning policy, not bypassed. See [Codex removal](#codex-removal) and the [official plugin guide](https://learn.chatgpt.com/docs/plugins#remove-a-plugin). CLI syntax was checked with `0.154.0`; use `--help` if your CLI differs.

### Upgrade Claude Code

Run `claude plugin list` and `claude plugin marketplace list` first. The terminal example below assumes the marketplace and all four plugins are installed **only at user scope**. For a partial install, omit the corresponding uninstall/install lines. `--keep-data` preserves persistent data during reinstallation; it does not retain the old version as an active installation.

```bash
claude plugin uninstall check-workflow@forge-steward --scope user --keep-data
claude plugin uninstall find-work@forge-steward --scope user --keep-data
claude plugin uninstall review-and-merge@forge-steward --scope user --keep-data
claude plugin uninstall fix-feedback@forge-steward --scope user --keep-data
claude plugin marketplace remove forge-steward --scope user
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.1 --scope user
claude plugin install check-workflow@forge-steward --scope user
claude plugin install find-work@forge-steward --scope user
claude plugin install review-and-merge@forge-steward --scope user
claude plugin install fix-feedback@forge-steward --scope user
claude plugin marketplace list
claude plugin list
```

For `project`/`local` or mixed-scope installs, first record all affected projects and declarations, uninstall in each original scope, and follow the [scope-aware switching guide](docs/versioned-installation.md#切换或回退). Marketplace scope and plugin installation scope are separate. Removing a marketplace can uninstall its plugins; omitting `--scope` removes marketplace declarations from every scope in current CLI behavior. Restore only the intended declarations and plugin scopes, coordinating any shared project changes with the team. Do not apply the user-only recipe to a shared or administrator-managed setup.

Confirm source/ref and installed versions, then restart Claude Code. Refreshing a marketplace pinned to an old tag does not select a newer tag. Old caches may remain pending background cleanup; neither a successful upgrade nor `plugin prune` guarantees immediate deletion of old version directories (`prune` concerns unused dependencies). See [Claude Code removal](#claude-code-removal) and the official [cache lifecycle](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution). CLI syntax was checked with `2.1.269`.

### Upgrade OpenCode

Use the checkout created during installation. First inspect it and fetch tags:

```bash
git -C "$HOME/code/ForgeSteward" status --short
git -C "$HOME/code/ForgeSteward" fetch origin --tags
```

Continue only with a clean checkout and no branch work you need to preserve; otherwise use a separate clean clone. Replace `v0.2.1` with your chosen release, then compare the resulting SHA with that Release before updating any installed copy:

```bash
git -C "$HOME/code/ForgeSteward" checkout --detach v0.2.1
git -C "$HOME/code/ForgeSteward" rev-parse HEAD
```

From the repository you want to maintain, update the installed subset (here, only `find-work`):

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status find-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" update find-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status find-work --project .
opencode debug skill
```

Repeat for your other installed skills, or use `update --all` only if every skill in the selected checkout is already installed. Newly selected skills need `install`, not `update`. For user-level copies, use `--user` with the same `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` as before; update or uninstall old copies in other projects/scopes separately. On Windows, use `py -3` instead of `python3` and your actual Windows checkout path; Git commands are unchanged apart from that path.

`update` replaces each selected managed directory, including obsolete files inside it; it does not create side-by-side version directories. It does not fetch source, remove retired skill names, or clean other discovery paths. Uninstall retired managed names explicitly; move confirmed manual/legacy copies outside discovery paths only after preserving edits. Modified or corrupt installations require inspection, not forced deletion. Verify versions/content with `status`, check the actual paths reported by `opencode debug skill`, and restart OpenCode. See [OpenCode installation maintenance](#opencode-installation-maintenance) for receipts and recovery.

### Upgrade ZCode skills

For a moving development source, first refresh the `forge-steward` marketplace, then use **Manage installed → Check for updates** and update the installed subset. ZCode compares marketplace entry versions with installed plugin versions; this repository derives those entry versions from `VERSION` and checks them in CI. Refreshing the marketplace alone does not prove installed content changed. Changes within the same unreleased version may require uninstall/reinstall, not a version bump or a fabricated update badge.

For a fixed release or rollback, prepare and verify a separate clean checkout of the chosen published tag first. Record installed plugins and their old source, preserve custom changes outside discovery paths, stop active work, uninstall the selected marketplace's installed plugins, remove the old market source, add the new checkout root, and reinstall the intended subset. Keep the old checkout until recovery is no longer needed. Do not assume Codex `--ref` or Claude `@tag` syntax works in ZCode's source field. See the [fixed-snapshot procedure and verification limits](docs/zcode.md#固定版本与回退).

Check the actual installed versions, files and skill paths in a new task. When moving from historical `find-work`, uninstall the retired plugin and any imported copy before selecting `prepare-work` / `execute-work`; a new name does not replace an old one automatically. Repeat for each intended scope and remote host. Do not link ZCode skills into another agent's versioned plugin cache, which can disappear during that agent's upgrade.

### Verify that only the intended version remains

There are two separate goals: **only the selected version is available in new sessions**, and **no obsolete files remain on disk**. A successful install alone proves neither.

1. Verify each intended environment/scope against the selected Release matrix. Inspect local installed manifests/content, not just the marketplace catalog. Every selected plugin must match the target release's unified package version; unchanged functionality is not a reason to retain an older package version.
2. Check for duplicates or stale copies in other scopes and manual discovery paths, including old unprefixed names. A picker showing one name may hide another copy; inspect its source path and configuration. Keep one intended discovery source per skill per environment unless you deliberately manage multiple scopes.
3. For disk cleanup, close relevant sessions, identify exact ForgeSteward-owned obsolete paths, and confirm no scope/configuration still references them. Use the agent's uninstall command for registered installations; move confirmed unused manual/cache copies to a backup outside all discovery paths before deleting them after verification. Do not delete a whole `.codex`, `.claude`, `.agents`, `.opencode`, or shared cache directory. Claude Code may retain orphaned version caches until its background sweep; no cross-agent one-command immediate cache purge is promised.
4. Verify again in a new session. Keep the source checkout needed by OpenCode and any local-path marketplace; old downloaded clones are separate from installed skills and can be removed only after checking local work and references. Skill removal does not revert project rules, code, issues or PRs.

To remove ForgeSteward entirely instead of upgrading, follow [Uninstall and verify](#uninstall-and-verify) for each agent and **do not run the reinstall steps**. Rollback uses the same switching procedure with the previous published tag; it does not undo work already performed by a skill.

## Skills

| Skill | Purpose |
| --- | --- |
| [`forge-steward-check-workflow`](plugins/check-workflow/skills/forge-steward-check-workflow/SKILL.md) | Remove workflow policy rules that duplicate the ForgeSteward skills from agent instructions, contributor docs and templates, then submit a PR or MR without merging. |
| [`forge-steward-prepare-work`](plugins/prepare-work/skills/forge-steward-prepare-work/SKILL.md) | Resolve actionable preparation blockers, persist scope and evidence in issues, and return only a single-line ready issue list. |
| [`forge-steward-execute-work`](plugins/execute-work/skills/forge-steward-execute-work/SKILL.md) | Implement the complete supplied issue list sequentially and submit independent change requests without merging. |
| [`forge-steward-review-and-merge`](plugins/review-and-merge/skills/forge-steward-review-and-merge/SKILL.md) | Review a frozen change-request queue and merge only the changes that satisfy their scope, acceptance, checks, and repository policy. |
| [`forge-steward-fix-feedback`](plugins/fix-feedback/skills/forge-steward-fix-feedback/SKILL.md) | Resolve required review feedback and verified gaps on original change-request branches, then push without merging. |

Each skill remains independently installable, while all plugins are versioned together. The root [VERSION](VERSION) defines the current source's target version; all plugin manifests must match it, and the release tag must be `v` followed by that version. The unified policy was introduced in the `0.2.2` development baseline and does not rewrite historical releases. Automatic version changes increment only the last component unless the user explicitly specifies otherwise; incompatible changes still require migration notes. A target version in source does not mean it has been published. See the [release policy](docs/releasing.md). Skills share a common core where behavior is genuinely portable across supported agents.

Since **v0.2.3**, carrying forward the check-workflow change from the `0.2.2` development baseline, explicitly selecting the skill without extra text requests the complete workflow: check, fill missing constraints and necessary agent entry references, validate, commit, push, and open a PR or MR. It should not stop at a report or local diff when delivery is permitted. The pinned `v0.2.1` examples above still install the earlier behavior; v0.2.4 additionally aligns onboarding with the preparation/execution handoff.

Since **v0.2.5**, check-workflow no longer drafts rules for each repository. It owns one marked block in the root `AGENTS.md` (`<!-- forge-steward:workflow begin lang=... -->` through `<!-- forge-steward:workflow end -->`) whose text comes verbatim from a bundled `zh-CN` or `en` template, an `@AGENTS.md` import in `CLAUDE.md`, and, when `CLAUDE.md` holds other rules, a short pointer block for agents that do not read `CLAUDE.md`. The bundled `scripts/sync_workflow_block.py --check|--write` adds a missing block, replaces a block that differs from the template, and leaves everything outside the markers byte-for-byte unchanged, so repeated runs of the same version produce no diff and no empty PR. Put project-specific rules outside the block; the template states that those rules take precedence. Edits inside the block are overwritten on the next run.

Explicit check-only requests remain read-only, and local-only/no-publish requests stop at that boundary. Implicit skill selection does not authorize publishing beyond the actual request. Repository permissions and approval gates still apply. It never changes business code, tests, CI or permissions, never merges, and never installs other skills. Supplementary rules written by earlier versions (0.2.4 and before) carry no markers. In **v0.2.6**, the skill removed those it could confirm from both their content and git history as earlier check-workflow additions, in the same PR or MR as the block sync, and kept rules the project wrote itself. Whenever a run modifies project files, the skill reports a per-file summary of the operation, the changes, line counts and the delivery status; otherwise it states that no project files were modified.

Since **v0.2.7**, workflow policy lives only in the four work skills: issue readiness and task granularity, including acceptance dimensions, guarantees with caller responsibilities, feature-level splitting and a canonical semantic model for complex protocol or state work, in `prepare-work` and `execute-work`; review classification and round counting in `review-and-merge` and `fix-feedback`, which audit each commit before the third review or fix and leave change requests with three or more feedback rounds for human handling. The skills no longer defer to repository rules of the same kind, while repository conventions such as language, title and commit formats, templates, merge method, required checks, branch protection and build commands still apply. check-workflow therefore adds nothing to projects. It removes the workflow blocks written by v0.2.5 and v0.2.6 with `scripts/remove_workflow_blocks.py --check|--write`, and deletes workflow policy rules in agent instructions, contributor docs and issue or change-request templates that duplicate the skills, whether the project wrote them or an earlier version added them. Project conventions are kept, ambiguous text is listed for maintainers, and nothing outside the deleted text is rewritten. See the bundled [skill-owned rules reference](plugins/check-workflow/skills/forge-steward-check-workflow/references/skill-owned-rules.md). After the cleanup, these constraints apply only when the skills are invoked.

The skill names and core workflows use provider-neutral terminology. Platform adapters map a **change request** to a GitHub pull request, a GitLab merge request, or the equivalent concept on another forge, and map **review feedback** to that platform's comments, discussions, or review threads.

Each plugin keeps one canonical `SKILL.md`. A portable root `plugin.json` and a Codex compatibility manifest package it for Codex; a Claude manifest and repository marketplace package the same file for Claude Code and ZCode. OpenCode can consume that unchanged skill directory from one of its Agent Skills locations, such as `.agents/skills/<name>`. OpenCode does not consume the Claude or Codex marketplace indexes.

## Calling the skills

Starting with plugin version `0.2.1`, Codex plugin and skill display names use `<Task> - ForgeSteward`, for example `Find Work - ForgeSteward`. These human-facing labels are separate from the installation IDs and skill invocation names below. The `v0.2.1` snapshot contains this display-name fix. Existing `v0.2.0` installations retain the previous labels until you switch to the new snapshot; see the [version switching guide](docs/versioned-installation.md).

All skill names use the `forge-steward-` prefix and the marketplace remains `forge-steward`. The current target retires the `find-work` plugin ID in favor of `prepare-work` and adds `execute-work`; no old-name alias is provided. Each plugin remains independently installable, with a shared version. The table below describes current source, not the v0.2.1 installation examples.

Open an agent session in the repository you want to maintain, select a skill, and append your request. In Codex CLI and the IDE extension, type `$` to select a skill or use `/skills`. Claude Code adds the plugin namespace to the skill name:

| Plugin | Codex / ZCode skill mention (select the actual picker entry) | Claude Code plugin command |
| --- | --- | --- |
| `check-workflow` | `$forge-steward-check-workflow` | `/check-workflow:forge-steward-check-workflow` |
| `prepare-work` | `$forge-steward-prepare-work` | `/prepare-work:forge-steward-prepare-work` |
| `execute-work` | `$forge-steward-execute-work` | `/execute-work:forge-steward-execute-work` |
| `review-and-merge` | `$forge-steward-review-and-merge` | `/review-and-merge:forge-steward-review-and-merge` |
| `fix-feedback` | `$forge-steward-fix-feedback` | `/fix-feedback:forge-steward-fix-feedback` |

If the selector displays a qualified plugin skill name, select that entry. Prepare work first:

```text
$forge-steward-prepare-work
```

Preparation persists its plan, audit and investigation evidence in the original issues. Its final response is only one line, for example `#123, #145, #167`, or `[]` when no issue meets the gates. Cross-repository tracking uses unambiguous qualified identifiers or full issue URLs on the same line. Copy that list to the independently usable execution skill:

```text
$forge-steward-execute-work #123, #145, #167
```

Execution processes the complete list, continues independent items when one is blocked, and submits separate PRs or MRs without merging. It reads the issues and owning repository policies itself; it needs neither an execution prompt nor the previous conversation. Preparation includes actionable technical investigation and experiments, but no production implementation. Genuine external blockers are recorded during preparation rather than hidden by a ready label.

OpenCode loads these names through its native `skill` tool; use the natural-language example in the installation section. The Claude command syntax is not a shared cross-agent interface.

ZCode supports `$` skill selection and the `/` menu's Skills group; `@` refers to workspace files. A plugin-qualified entry may appear instead of the bare name in the table. Its `agents/openai.yaml` display metadata is not a ZCode compatibility guarantee. See [ZCode skill invocation](https://zcode.z.ai/en/docs/skill).

Explicitly invoking review and merge, even without an extra prompt, authorizes it to merge every change request that passes review, acceptance and repository requirements without asking for confirmation. To review without merging, say so explicitly, for example: "Review the current open change requests, but do not merge."

See the official [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills), [Claude Code skill namespaces](https://code.claude.com/docs/en/skills), and [OpenCode skill loading](https://opencode.ai/docs/skills/) documentation for the host-specific interfaces.

### Historical migration from 0.1.x to 0.2.0

Each plugin moves to `0.2.0` for this invocation-name change. Update the installed plugins through your agent's plugin manager, then start a new session and select the prefixed skills. Update saved prompts and shortcuts: the old unprefixed skill names are no longer provided as aliases. Plugin installation identifiers remain unchanged.

For manually installed skills, replace each old skill directory with the corresponding `forge-steward-<name>` directory, including its bundled resources. Preserve any local modifications before replacing files, and remove the old copy only after verifying the new installation. Keeping both copies exposes both skill names.

## OpenCode installation maintenance

The commands below use a current-source checkout with `prepare-work`; pinned v0.2.1 still uses `find-work`. Follow the [rename migration](docs/prepare-execute-migration.md) before changing names. Run these commands from the target project. Use `--user` in place of `--project .` for a user-level install:

```bash
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" list
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status --all --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" update prepare-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" uninstall prepare-work --project .
```

Replace `prepare-work` with `--all` to update all skills or uninstall all managed skills. `update` requires selected skills to be installed; if you installed only one, update it by name. `uninstall --all` removes only directories with this installer's receipt, even if their source no longer exists in the checkout. It preserves unrelated skills and may leave empty `.opencode/skills` containers. It also reports matching unmanaged or legacy-name candidates in that target; exit code `2` means leftovers need inspection, not that they were deleted. See [Uninstall and verify](#uninstall-and-verify) for the complete boundary.

The installer uses the current local checkout and does not fetch or execute remote installation commands. Tagged installs use a detached checkout: fetch tags, select the next reviewed tag or commit, then run `update` as described in the [switching guide](docs/versioned-installation.md). Do not run `git pull` on a detached checkout. Only a clean development checkout tracking `main` should use `git -C "$HOME/code/ForgeSteward" pull --ff-only` before updating. An explicit `update` follows the selected checkout, including an intentional downgrade. Use a separate clean checkout if your source has local work.

Each installed skill contains `.forge-steward-install.json`, recording its plugin version, source commit (when Git is available), source dirty state, and content hashes. Repeating an identical install makes no changes. A changed source/version requires `update`; even when the version string is unchanged, content changes are detected.

If a target was copied manually, its receipt is damaged, or its files have been edited, installation/update/uninstall stops with the affected path. There is no `--force` overwrite. Back up or move the complete conflicting directory outside OpenCode's skill search paths, inspect and preserve your edits, then install again. Existing `.agents/skills` or `.claude/skills` copies are not adopted or removed; use `opencode debug skill` to check for duplicate names or unexpected locations. Symlink sources, symlink install paths, and linked content are not managed by this installer.

Selected targets are checked and staged before changing installed skills. Ordinary copy/rename failures roll back the batch. A lock prevents overlapping installer processes; avoid editing installed files while an operation runs. Forced termination or power loss can leave `.forge-steward.lock` and `.forge-steward-txn-*` beside the `skills` directory. Confirm the installer has stopped, preserve the entire transaction directory, and inspect its `old-<skill>` backups before restoring missing installations or moving conflicting copies aside. Once recovery is complete, move the transaction outside the config directory and remove the stale lock before retrying. No crash-durable or hostile-concurrent-writer guarantee is made.

If OpenCode does not discover the skills, confirm the printed target and run `status`, then `opencode debug skill` from the target project. Check OpenCode's skill permissions, custom configuration, and any duplicate manual installs. The installer never changes agent permissions or configuration files.

Development checks: `python3 -m unittest discover -s tests -v`. Set `FORGESTEWARD_OPENCODE` to an OpenCode executable to include actual discovery and removal checks in isolated temporary configuration directories; otherwise that test is explicitly skipped. See the Chinese [installer design and verification notes](docs/opencode-installer.md).

## Uninstall and verify

Uninstall in the same agent environment and scope used for installation. Stop active skill-driven work first, then start a fresh session after removal: an existing conversation can still contain previously loaded instructions. Disabling a plugin is not uninstalling it. Do not delete an entire agent configuration or cache directory to remove ForgeSteward skills.

The named Codex and Claude commands below show the published v0.2.1 IDs. For current-source installations, remove `prepare-work@forge-steward` and `execute-work@forge-steward` as applicable; also remove `find-work@forge-steward` if retained from an older release. Use the actual installed subset and scope. OpenCode `uninstall --all` also handles retired managed IDs.

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

### ZCode removal

Stop skill-driven tasks, preserve local changes, then open **Settings → Plugins → Manage installed**. Uninstall each installed ForgeSteward plugin from its details, including historical `find-work` if present. Removing or disabling the marketplace alone is not the uninstall verification step. After plugin removal, remove the `forge-steward` marketplace source if you no longer need it.

In **Settings → Skills**, inspect the actual paths of remaining `forge-steward-*` and legacy skills. Imported copies or symlinks are independent of plugin installations: preserve edits, confirm ownership, and move only the redundant copy/link outside discovery paths. Do not follow a symlink and delete another agent's source. Check project/user `.zcode/skills`, `.agents/skills`, configured roots and remote environments as applicable; verify in a new task that removed skills are absent. Keep intentionally installed skills.

An uninstall is not a promise of immediate zero disk residue. Inspect only confirmed unused ForgeSteward cache/source paths before cleanup; never delete a whole `.zcode` or shared plugins directory. See [ZCode cleanup and recovery](docs/zcode.md#卸载与只保留目标版本).

### What removal does not undo

Uninstall removes availability, not work already performed. Changes made by `check-workflow` to project rules or agent entry documents, code commits, issues, PRs, comments, and conversation history remain project/user assets. Reverting those requires a separate reviewed change; do not delete `AGENTS.md` or `CLAUDE.md` wholesale. Independently configured credentials, integrations and automation are not revoked by skill removal either. A downloaded ForgeSteward source checkout is separate from installed copies; retain it if you develop the project, or remove it only after checking for local work and completing uninstall verification.

## The name

**Forge** literally means a workshop where metal is shaped, or the act of creating something through deliberate effort. In software development, a forge is also a platform where source code is hosted and collaboratively developed, such as GitHub, GitLab, or Gitea. Here it represents both the repository platform and the process of shaping an issue into dependable code.

**Steward** means a trusted caretaker: someone responsible for looking after a system, applying its rules, and keeping work moving without claiming unchecked ownership. Here it reflects a careful repository maintainer that inspects project state, protects code quality, and keeps consequential actions subject to explicit policy and human control.

Together, **ForgeSteward** means a trusted steward for the software forge: an agent-assisted toolkit that helps maintainers move repository work forward while respecting review gates, project policy, and human judgment.

## Agent instructions

Repository-wide agent guidance has a single source of truth in [`AGENTS.md`](AGENTS.md). Codex, OpenCode and ZCode load it directly; [`CLAUDE.md`](CLAUDE.md) imports the same file for Claude Code. Open this repository root as the ZCode workspace: ZCode does not recursively load nested `AGENTS.md` or expand `@import` / `@include`. Platform adapters must not duplicate shared guidance.

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
