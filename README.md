# ForgeSteward

ForgeSteward is a collection of cross-agent skills for maintaining software repositories. It is designed to help Claude Code, OpenCode, Codex, ZCode, and other compatible coding agents move work safely from an actionable issue to a reviewed and merge-ready change request.

The current release is **0.2.27**, with six independently installable plugins: `check-workflow`, `prepare-work`, `execute-work`, `review-and-merge`, `fix-feedback`, and `work-cycle`. The [installation commands](#supported-agents-and-installation) install exactly this release; the matching tag and non-draft [GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases) confirm it is published. See the [v0.2.27 version matrix, changes, and migration notes](docs/releases/v0.2.27.md). The orchestration skill reviews existing open change requests before running bounded issue work cycles through mandatory stage subagents; the five stage skills retain their independent entrypoints and complete bundled rules. Preparation includes a read-only check of available automated security alerts within the authorized repository scope, with deduplication and the existing frozen-queue boundaries. Check-workflow also reconciles release evidence read-only against each repository's release contract; findings appear only in the final report. The current source defaults skill reports and forge comments to clear, everyday English instead of internal rule terms; see the [English migration and saved-record compatibility notes](docs/work-cycle-scenarios.md#english-migration-and-record-compatibility-118). Work cycles avoid idle waits and repeated checks: repairs watch their own CI, branch syncs are handled without consuming review rounds, unchanged items keep earlier conclusions, and finished change requests can move to review before the whole batch is done when the agent runtime supports background subagents. With that support, work cycles also implement, review and repair independent issues and change requests concurrently (three stage subagents by default) in worktrees outside the repository, queue local verification on shared resources through Git-metadata locks, and merge one change request at a time. When a repository requires up-to-date branches, approved change requests go through a single merge lane (or the repository's own merge queue when it is already enabled); CI failures unrelated to a change are re-run once; each run keeps per-stage timings in Git metadata; repository language and commit conventions take precedence over the everyday-English default. The final work-cycle report is rendered from run records in a fixed format; it includes a read-only check of which ForgeSteward version each local agent has installed and, only after the user agrees, installs or upgrades the agents that are missing or behind.

The five-plugin split shipped in [v0.2.3](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.3): `prepare-work` replaces `find-work` and returns only a single-line issue list; `execute-work` implements that list and opens independent change requests. When migrating from v0.2.1 or earlier, uninstall `find-work` as described in the [rename migration](docs/prepare-execute-migration.md); the historical v0.2.1 commands are kept in the [fixed-version guide](docs/versioned-installation.md).

For contributors: run `python3 scripts/check_skill_limits.py --check` after changing skills. Descriptions must stay within **500 UTF-16 units** to fit the default DeepSeek Harness catalog display. See the [cross-agent loading limits and authoring budgets](docs/skill-compatibility.md) for Codex, Claude Code, OpenCode, ZCode, and the DeepSeek Harness investigation; managed DeepSeek installation is available in current source; end-to-end workflows remain separately tracked.

## Supported agents and installation

| Agent | Verified with | How the commands install ForgeSteward | Local source checkout |
| --- | --- | --- | --- |
| [Claude Code](#claude-code) | 2.1.269 on macOS | Marketplace `philfanzhou/ForgeSteward@v0.2.27`, one command per plugin | Not needed |
| [Codex](#codex) | CLI 0.157.1 on macOS | Marketplace `philfanzhou/ForgeSteward --ref v0.2.27`, one command per plugin | Not needed |
| [ZCode](#zcode) | Desktop 3.14.5 with bundled CLI 0.16.9 on macOS | Bundled CLI, marketplace `philfanzhou/ForgeSteward@v0.2.27`, one command per plugin | Not needed |
| [OpenCode](#opencode) | 1.18.30 on macOS and in Linux CI | Installer script from a `v0.2.27` clone, `--all` | Only while running the installer |
| [DeepSeek Harness](#deepseek-harness) | 0.2.0-rc.2 on macOS | Installer script from a `v0.2.27` clone, `--all` | Only while running the installer |

Every command block below installs, upgrades to, or removes **all six plugins of the current release**. Run the blocks in a terminal for the agent you use; each block can be copied as a whole. A release exists once its tag and non-draft [GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases) are published; right after a version change is merged, the tag can take a short time to appear. To choose another published release, for example to roll back, see [Upgrade and keep only the selected version](#upgrade-and-keep-only-the-selected-version). Upgrading the agent application itself never upgrades ForgeSteward.

`work-cycle` needs the other five plugins at the same version and an agent that can run subagents. After installing, start a new agent session in the repository you want to maintain and follow [Calling the skills](#calling-the-skills).

These commands, together with how to detect each agent and an existing ForgeSteward installation, are kept in one data file, [`agents.json`](plugins/work-cycle/skills/forge-steward-work-cycle/scripts/agents.json). `tests/test_agent_catalog.py` fails when this README differs from that file, from `VERSION`, or from the plugin directories.

### Claude Code

These commands use the `user` scope, which makes the skills available in every project.

#### Install

```bash
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.27 --scope user
claude plugin install check-workflow@forge-steward --scope user
claude plugin install prepare-work@forge-steward --scope user
claude plugin install execute-work@forge-steward --scope user
claude plugin install review-and-merge@forge-steward --scope user
claude plugin install fix-feedback@forge-steward --scope user
claude plugin install work-cycle@forge-steward --scope user
claude plugin list
```

Inside a Claude Code conversation, `/plugin marketplace add philfanzhou/ForgeSteward@v0.2.27` and `/plugin install <plugin>@forge-steward` do the same. Restart the session, then invoke a skill with its plugin namespace, for example `/prepare-work:forge-steward-prepare-work`.

#### Upgrade

Uninstall the old plugins, replace the marketplace, then install again. `--keep-data` keeps each plugin's data directory; it does not keep the old version active. An "is not installed" error for a plugin you never installed is harmless. If you still have `find-work@forge-steward` from an old release, uninstall it the same way.

```bash
claude plugin uninstall check-workflow@forge-steward --scope user --keep-data
claude plugin uninstall prepare-work@forge-steward --scope user --keep-data
claude plugin uninstall execute-work@forge-steward --scope user --keep-data
claude plugin uninstall review-and-merge@forge-steward --scope user --keep-data
claude plugin uninstall fix-feedback@forge-steward --scope user --keep-data
claude plugin uninstall work-cycle@forge-steward --scope user --keep-data
claude plugin marketplace remove forge-steward --scope user
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.27 --scope user
claude plugin install check-workflow@forge-steward --scope user
claude plugin install prepare-work@forge-steward --scope user
claude plugin install execute-work@forge-steward --scope user
claude plugin install review-and-merge@forge-steward --scope user
claude plugin install fix-feedback@forge-steward --scope user
claude plugin install work-cycle@forge-steward --scope user
claude plugin list
```

Refreshing a marketplace pinned to an old tag does not move it to a newer tag, which is why the marketplace is replaced. For `project` or `local` scope installations, run the matching commands with that scope from each affected project and follow the [scope-aware switching guide](docs/versioned-installation.md#switching-or-rolling-back); marketplace scope and plugin scope are separate, and `marketplace remove` without `--scope` removes the declaration from every scope.

#### Uninstall

```bash
claude plugin uninstall check-workflow@forge-steward --scope user
claude plugin uninstall prepare-work@forge-steward --scope user
claude plugin uninstall execute-work@forge-steward --scope user
claude plugin uninstall review-and-merge@forge-steward --scope user
claude plugin uninstall fix-feedback@forge-steward --scope user
claude plugin uninstall work-cycle@forge-steward --scope user
claude plugin marketplace remove forge-steward --scope user
claude plugin list
```

Uninstalling from the last scope deletes the plugin's data unless you add `--keep-data`. Old version caches can stay on disk until Claude Code's background cleanup; see the official [uninstall reference](https://code.claude.com/docs/en/plugins-reference#plugin-uninstall) and [cache lifecycle](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution).

### Codex

The Codex CLI and desktop app share the same environment, so installing from the terminal is enough for both. A different host, account or configuration environment needs its own installation.

#### Install

```bash
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.27
codex plugin add check-workflow@forge-steward
codex plugin add prepare-work@forge-steward
codex plugin add execute-work@forge-steward
codex plugin add review-and-merge@forge-steward
codex plugin add fix-feedback@forge-steward
codex plugin add work-cycle@forge-steward
codex plugin list --json
```

In a new session, type `$` and select a skill, for example `$forge-steward-prepare-work`.

#### Upgrade

Remove all ForgeSteward plugins before replacing the marketplace ref, then add them again. A "not installed" error for a plugin you never installed is harmless; also remove `find-work@forge-steward` if an old release left it behind.

```bash
codex plugin remove check-workflow@forge-steward
codex plugin remove prepare-work@forge-steward
codex plugin remove execute-work@forge-steward
codex plugin remove review-and-merge@forge-steward
codex plugin remove fix-feedback@forge-steward
codex plugin remove work-cycle@forge-steward
codex plugin marketplace remove forge-steward
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.27
codex plugin add check-workflow@forge-steward
codex plugin add prepare-work@forge-steward
codex plugin add execute-work@forge-steward
codex plugin add review-and-merge@forge-steward
codex plugin add fix-feedback@forge-steward
codex plugin add work-cycle@forge-steward
codex plugin list --json
```

Start a new task afterwards; reopen the desktop app if its picker still shows old entries. Administrator- or project-managed marketplace sources must be changed through their owner.

#### Uninstall

```bash
codex plugin remove check-workflow@forge-steward
codex plugin remove prepare-work@forge-steward
codex plugin remove execute-work@forge-steward
codex plugin remove review-and-merge@forge-steward
codex plugin remove fix-feedback@forge-steward
codex plugin remove work-cycle@forge-steward
codex plugin marketplace remove forge-steward
codex plugin list --json
```

`remove` uninstalls the plugin and deletes its local cache. Check the installed list, not just the available catalog. See the official [plugin removal guide](https://learn.chatgpt.com/docs/plugins#remove-a-plugin).

### ZCode

ZCode reads the same Claude-compatible marketplace. The commands use ZCode's bundled CLI, run with Node.js; the path below is the default macOS location, so change `ZCODE_CLI` if ZCode is installed elsewhere. The marketplace comes straight from GitHub at the release tag, so no local copy of this repository is needed. This was run in an isolated home directory with the bundled CLI 0.16.9 and installed exactly the tagged files. The desktop **Settings → Plugins → Add marketplace** field writes to the same plugin directory (`~/.zcode/cli/plugins`), and entering `philfanzhou/ForgeSteward@v0.2.27` there should be equivalent, but that desktop flow has not been tested. Restart ZCode after any change. See [ZCode setup and verification](docs/zcode.md).

#### Install

```bash
ZCODE_CLI="/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"
node "$ZCODE_CLI" plugins marketplace add philfanzhou/ForgeSteward@v0.2.27
node "$ZCODE_CLI" plugins install check-workflow@forge-steward
node "$ZCODE_CLI" plugins install prepare-work@forge-steward
node "$ZCODE_CLI" plugins install execute-work@forge-steward
node "$ZCODE_CLI" plugins install review-and-merge@forge-steward
node "$ZCODE_CLI" plugins install fix-feedback@forge-steward
node "$ZCODE_CLI" plugins install work-cycle@forge-steward
node "$ZCODE_CLI" plugins list --json
```

In a new task, type `$` and select `forge-steward-prepare-work`; `/` also has a Skills group. Select the plugin-qualified entry if the picker shows one.

#### Upgrade

`--force` only skips the "confirm uninstall" prompt, which the CLI otherwise refuses to show in a non-interactive terminal; `--keep-data` keeps each plugin's data directory. Removing the marketplace does not uninstall its plugins, so plugins are uninstalled first. An error for a plugin you never installed is harmless; also uninstall `find-work@forge-steward` if an old release left it behind. This also replaces a marketplace that still points to a local directory from older instructions; that directory is no longer needed afterwards.

```bash
ZCODE_CLI="/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"
node "$ZCODE_CLI" plugins uninstall check-workflow@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins uninstall prepare-work@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins uninstall execute-work@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins uninstall review-and-merge@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins uninstall fix-feedback@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins uninstall work-cycle@forge-steward --force --keep-data
node "$ZCODE_CLI" plugins marketplace remove forge-steward
node "$ZCODE_CLI" plugins marketplace add philfanzhou/ForgeSteward@v0.2.27
node "$ZCODE_CLI" plugins install check-workflow@forge-steward
node "$ZCODE_CLI" plugins install prepare-work@forge-steward
node "$ZCODE_CLI" plugins install execute-work@forge-steward
node "$ZCODE_CLI" plugins install review-and-merge@forge-steward
node "$ZCODE_CLI" plugins install fix-feedback@forge-steward
node "$ZCODE_CLI" plugins install work-cycle@forge-steward
node "$ZCODE_CLI" plugins list --json
```

`plugins update` follows whatever version the marketplace points to, including a downgrade, and does not add plugins that are new in the release, so this guide reinstalls instead.

#### Uninstall

```bash
ZCODE_CLI="/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"
node "$ZCODE_CLI" plugins uninstall check-workflow@forge-steward --force
node "$ZCODE_CLI" plugins uninstall prepare-work@forge-steward --force
node "$ZCODE_CLI" plugins uninstall execute-work@forge-steward --force
node "$ZCODE_CLI" plugins uninstall review-and-merge@forge-steward --force
node "$ZCODE_CLI" plugins uninstall fix-feedback@forge-steward --force
node "$ZCODE_CLI" plugins uninstall work-cycle@forge-steward --force
node "$ZCODE_CLI" plugins marketplace remove forge-steward
node "$ZCODE_CLI" plugins list --json
```

Without `--keep-data` the plugin data directories are deleted too. Skills imported by copy or symlink in **Settings → Skills** are separate from plugins; see [ZCode cleanup](docs/zcode.md#uninstalling-and-keeping-only-the-target-version).

### OpenCode

OpenCode does not read the Claude or Codex marketplaces. The commands clone the release into its own directory and run the included installer with Python 3.9 or newer, copying each complete skill into OpenCode's user skill directory: `$OPENCODE_CONFIG_DIR/skills`, else `$XDG_CONFIG_HOME/opencode/skills`, else `~/.config/opencode/skills`. Installed skills do not depend on the clone, but keep it until you have checked the result. To install into one project only, run from that project with `--project .` in place of `--user`. On Windows use `py -3` instead of `python3` and a Windows path for the clone. Skip the `git clone` line when that directory already exists.

#### Install

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" install --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" status --all --user
```

Restart OpenCode and ask, for example: `Load the forge-steward-prepare-work skill and prepare actionable issues in this repository.` `opencode debug skill` lists the discovered skills and their locations.

#### Upgrade

`uninstall --all` removes every skill this installer placed in that directory, including retired names, and then the new release is installed. If an installed copy has local edits, the installer stops without changing anything; back up the edits first. Exit code `2` from uninstall means removal finished but other matching copies remain for you to inspect.

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" uninstall --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" install --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" status --all --user
```

#### Uninstall

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/opencode.py" uninstall --all --user
```

Use the same `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` as when installing. What the uninstall report covers is described in [Uninstall and verify](#uninstall-and-verify); receipts, recovery and partial installs are in [OpenCode installation maintenance](#opencode-installation-maintenance).

### DeepSeek Harness

DeepSeek Harness uses the same kind of installer as OpenCode. The commands copy each complete skill into `$DSH_HOME/skills`, or `~/.dsh/skills` when `DSH_HOME` is not set; if Harness's own `dshHome` setting overrides the environment, set `DSH_HOME` to that same directory. With `--project .` in place of `--user`, skills go into `.dsh/skills` at the nearest Git root. Installed skills do not depend on the clone. On Windows use `py -3` instead of `python3`. Skip the `git clone` line when that directory already exists.

#### Install

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" install --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" status --all --user
```

Start a new Harness session, check the discovered names and sources, and load `forge-steward-prepare-work`. Native Windows Harness and the desktop interface have not been verified.

#### Upgrade

As with OpenCode, the old managed copies are removed and the new release is installed; copies with local edits stop the installer without changes, and exit code `2` means other matching copies remain for you to inspect.

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" uninstall --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" install --all --user
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" status --all --user
```

#### Uninstall

```bash
git clone --branch v0.2.27 --depth 1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.27"
python3 "$HOME/code/ForgeSteward-v0.2.27/scripts/deepseek.py" uninstall --all --user
```

Other discovery roots can still hold copies the installer does not manage. See the [DeepSeek installation, recovery and verification guide](docs/deepseek-installer.md) for exact boundaries.

## Upgrade and keep only the selected version

The upgrade steps in each agent section move to the current release. To choose a different published release, for example to roll back, pick a **published, non-prerelease** tag from [GitHub Releases](https://github.com/philfanzhou/ForgeSteward/releases), read its plugin version matrix and migration notes, replace `0.2.27` in that agent's upgrade commands with the chosen version, and install only the plugins that release contains. A tag selects the whole marketplace snapshot, and every plugin in tag `vX.Y.Z` has package version `X.Y.Z`. Releases before v0.2.3 used `find-work` instead of `prepare-work` and `execute-work`; the historical v0.2.1 commands remain in the [fixed-version installation and rollback guide](docs/versioned-installation.md).

Before upgrading, record the installed plugins, scopes and sources, back up local edits and plugin data you need **outside all agent discovery and cache directories**, and stop active skill-driven work. Run each step only after the previous one succeeds; if reinstallation fails, reinstall the recorded release the same way.

| Agent | What the upgrade replaces | What may still remain |
| --- | --- | --- |
| Claude Code | Plugins and marketplace in the scope you ran it for. | Old version caches awaiting background cleanup; other scopes and manual copies. |
| Codex | Plugins and the marketplace ref in that Codex environment. | Other environments, manual skill copies, or untracked caches. |
| ZCode | Plugins and the marketplace source. | Imported skill copies or links, other workspaces or remote hosts, unused caches. |
| OpenCode | Every installer-managed skill in the chosen scope. | Other scopes, `.agents/skills` or `.claude/skills` copies, manual copies. |
| DeepSeek Harness | Every installer-managed skill in the chosen scope. | Other scopes and discovery roots, manual copies. |

### Verify that only the intended version remains

There are two separate goals: **only the selected version is available in new sessions**, and **no obsolete files remain on disk**. A successful install alone proves neither.

1. Verify each intended environment/scope against the selected Release matrix. Inspect local installed manifests/content, not just the marketplace catalog. Every selected plugin must match the target release's unified package version; unchanged functionality is not a reason to retain an older package version.
2. Check for duplicates or stale copies in other scopes and manual discovery paths, including old unprefixed names and the retired `find-work`. A picker showing one name may hide another copy; inspect its source path and configuration. Keep one intended discovery source per skill per environment unless you deliberately manage multiple scopes.
3. For disk cleanup, close relevant sessions, identify exact ForgeSteward-owned obsolete paths, and confirm no scope/configuration still references them. Use the agent's uninstall command for registered installations; move confirmed unused manual/cache copies to a backup outside all discovery paths before deleting them after verification. Do not delete a whole `.codex`, `.claude`, `.agents`, `.opencode`, `.zcode`, `.dsh` or shared cache directory. Claude Code may retain orphaned version caches until its background sweep; no cross-agent one-command immediate cache purge is promised.
4. Verify again in a new session. The installations above do not depend on a local checkout, so a release clone can be removed after checking it holds no local work. A ZCode or Claude Code marketplace that still points to a local directory from older instructions does depend on it until you upgrade as above. Skill removal does not revert project rules, code, issues or PRs.

To remove ForgeSteward entirely instead of upgrading, run each agent's **Uninstall** commands and do not reinstall. Rollback does not undo work already performed by a skill.

## Work-cycle agent check and upgrade offer

Only the `work-cycle` orchestration does this; the five stage skills and stage subagents never check, ask or install.

- **When it checks:** once at the start of every run, read-only. `scripts/agent_install.py check` in the work-cycle skill finds which ForgeSteward plugins each supported agent has at user level and compares them with the latest published, non-prerelease GitHub Release. The final report lists the result in its last section.
- **When it asks:** at the end of the report, only when the latest release is known and some agent is missing ForgeSteward, has only part of it, or has an older version. It asks every run; nothing is remembered from an earlier answer.
- **What happens if you agree:** the orchestration runs `agent_install.py apply --version X.Y.Z --agents <ids>` for exactly the agents and version you agreed to. It checks again first and stops without changes if the latest release changed or another apply is running. Agents already current or newer are skipped (no downgrade). Each agent is handled separately and judged by checking it again afterwards. The commands come from the same agent data file as the instructions above.
- **What it may change:** user-level plugins and the `forge-steward` marketplace setting of Claude Code, Codex and ZCode (project or local installs are left alone); the user skill directories of OpenCode and DeepSeek Harness, through the bundled installers, which never overwrite modified, unrecorded or linked copies; and, in the system temporary directory, a lock directory plus a temporary clone of the release tag (its commit is verified against the release; both are removed afterwards). A local Claude Code marketplace clone is reused instead of downloading when it is clean and at the release commit. Nothing is written to the repository being maintained.
- **How to decline:** say no, or simply do not answer. Nothing is changed.

A failed step stops only that agent and is reported with the state found afterwards; there is no automatic rollback, so agree again after fixing the cause to complete it. An agent upgraded while it is running uses the new version from its next new session. See the [work-cycle scenarios](docs/work-cycle-scenarios.md) for every case.

## Skills

| Skill | Purpose |
| --- | --- |
| [`forge-steward-check-workflow`](plugins/check-workflow/skills/forge-steward-check-workflow/SKILL.md) | Inspect branch cleanup settings, reconcile releases read-only, remove duplicate ForgeSteward workflow rules, safely consolidate root Claude instructions, configure English collaboration defaults, convert project documentation and About to English by default, and submit cleanup as a PR or MR without merging. Release findings are reported only; check-only, review-only, and audit-only runs write nothing. |
| [`forge-steward-prepare-work`](plugins/prepare-work/skills/forge-steward-prepare-work/SKILL.md) | Resolve actionable preparation blockers, persist scope and evidence in issues, and return only a single-line ready issue list filled with backlog issues before newly created ones. |
| [`forge-steward-execute-work`](plugins/execute-work/skills/forge-steward-execute-work/SKILL.md) | Implement the complete supplied issue list sequentially and submit independent change requests without merging. |
| [`forge-steward-review-and-merge`](plugins/review-and-merge/skills/forge-steward-review-and-merge/SKILL.md) | Review a frozen change-request queue and merge only the changes that satisfy their scope, acceptance, checks, and repository policy. |
| [`forge-steward-fix-feedback`](plugins/fix-feedback/skills/forge-steward-fix-feedback/SKILL.md) | Resolve required review feedback and verified gaps on original change-request branches, then push without merging. |
| [`forge-steward-work-cycle`](plugins/work-cycle/skills/forge-steward-work-cycle/SKILL.md) | Review existing open change requests, then run up to ten issue work cycles by default through stage subagents and merge eligible changes. |

Each skill remains independently installable, while all plugins are versioned together. The root [VERSION](VERSION) defines the current source's target version; all plugin manifests must match it, and the release tag must be `v` followed by that version. The unified policy was introduced in the `0.2.2` development baseline and does not rewrite historical releases. Automatic version changes increment only the last component unless the user explicitly specifies otherwise; incompatible changes still require migration notes. A target version in source does not mean it has been published. See the [release policy](docs/releasing.md). Skills share a common core where behavior is genuinely portable across supported agents.

Since **v0.2.3**, carrying forward the check-workflow change from the `0.2.2` development baseline, explicitly selecting the skill without extra text requests the complete workflow: check, fill missing constraints and necessary agent entry references, validate, commit, push, and open a PR or MR. It should not stop at a report or local diff when delivery is permitted. The historical `v0.2.1` snapshot still installs the earlier behavior; v0.2.4 additionally aligns onboarding with the preparation/execution handoff.

Since **v0.2.5**, check-workflow no longer drafts rules for each repository. It owns one marked block in the root `AGENTS.md` (`<!-- forge-steward:workflow begin lang=... -->` through `<!-- forge-steward:workflow end -->`) whose text comes verbatim from a bundled `zh-CN` or `en` template, an `@AGENTS.md` import in `CLAUDE.md`, and, when `CLAUDE.md` holds other rules, a short pointer block for agents that do not read `CLAUDE.md`. The bundled `scripts/sync_workflow_block.py --check|--write` adds a missing block, replaces a block that differs from the template, and leaves everything outside the markers byte-for-byte unchanged, so repeated runs of the same version produce no diff and no empty PR. Put project-specific rules outside the block; the template states that those rules take precedence. Edits inside the block are overwritten on the next run.

Explicit check-only requests remain read-only, and local-only/no-publish requests stop at that boundary. Implicit skill selection does not authorize publishing beyond the actual request. Repository permissions and approval gates still apply. It never changes business code, tests, CI or permissions, never merges, and never installs other skills. Supplementary rules written by earlier versions (0.2.4 and before) carry no markers. In **v0.2.6**, the skill removed those it could confirm from both their content and git history as earlier check-workflow additions, in the same PR or MR as the block sync, and kept rules the project wrote itself. Whenever a run modifies project files, the skill reports a per-file summary of the operation, the changes, line counts and the delivery status; otherwise it states that no project files were modified.

Since **v0.2.7**, workflow policy lives in the four work skills: issue readiness and task granularity, including acceptance dimensions, guarantees with caller responsibilities, feature-level splitting and a canonical semantic model for complex protocol or state work, in `prepare-work` and `execute-work`; review classification and round counting in `review-and-merge` and `fix-feedback`. In current source, a third repair push receives one final review: an eligible change is merged, while a change with required in-scope problems is paused individually for human handling. The skills do not defer to repository rules of the same kind, while repository conventions such as language, title and commit formats, templates, merge method, required checks, branch protection and build commands still apply. check-workflow therefore adds no workflow policy to projects. It removes the workflow blocks written by v0.2.5 and v0.2.6 with `scripts/remove_workflow_blocks.py --check|--write`, and deletes workflow policy rules in agent instructions, contributor docs and issue or change-request templates that duplicate the skills, whether the project wrote them or an earlier version added them. Project conventions are kept, ambiguous text is listed for maintainers, and retained policy-adjacent text is not rewritten. See the bundled [skill-owned rules reference](plugins/check-workflow/skills/forge-steward-check-workflow/references/skill-owned-rules.md). After the cleanup, these constraints apply only when the skills are invoked.

The current source adds three narrow exceptions to deletion-only cleanup. First, after workflow-policy removal, safe tracked root `CLAUDE.md` and `.claude/CLAUDE.md` content is moved verbatim into a surviving root `AGENTS.md`, under source-specific headings, before deleting each source. Root-resolving import-only files and exact symlinks are deleted without appending content. Exact duplicate paragraphs and effective root imports are omitted; other conventions, including language rules, are preserved during migration. Unsafe moves, changed relative import/link targets, nested pairs, and tracked `CLAUDE.local.md` are reported unchanged. Migration-only, language-only, or rule-only work still produces the same cleanup PR; repeated completed runs do nothing. Direct Claude loading requires v2.1.277 or later with AGENTS.md support enabled and a compatible instruction mode/session; ancestor or local Claude entries may prevent fallback. Older or restricted sessions can restore root `CLAUDE.md` containing `@AGENTS.md`. See [migration rules](plugins/check-workflow/skills/forge-steward-check-workflow/references/agent-entrypoints.md) and the [decision and fixture walkthroughs](docs/check-workflow-scenarios.md#root-claude-entry-consolidation-125). Second, after migration, [language rules](plugins/check-workflow/skills/forge-steward-check-workflow/references/collaboration-language.md) configure English for Issue and Change Request titles/bodies, Comments, Discussions and Review Feedback replies, with explicit maintainer overrides and quoted-text exceptions. Add the fixed section only for missing coverage, or replace separable conflicting collaboration clauses in the existing root entry: AGENTS.md, otherwise CLAUDE.md, otherwise .claude/CLAUDE.md when it supplies the entry. Never create an entry for this rule. Third, the [English working environment rule](plugins/check-workflow/skills/forge-steward-check-workflow/references/english-conversion.md) replaces that fixed collaboration section with one rule covering project-maintained documentation, Issue and Change Request text, Comments, Discussions, Review Threads, and future commit messages. It replaces separable conflicting non-English rules without duplicate sections and preserves historical records, code, commands, paths, identifiers, logs, technical data, quoted external text, code-comment languages, and other conventions. Inseparable and external conflicts stay unchanged and are reported for maintainer decision; no enforcement or model-compliance guarantee is implied. See the [English working environment walkthroughs](docs/check-workflow-scenarios.md#english-working-environment-rule-and-no-write-modes-183). Language additions/replacements are reported separately from policy deletion and migration, with exact replaced originals. Check-only, review-only, and audit-only write nothing; local-only stops at the local diff. See the [language walkthroughs](docs/check-workflow-scenarios.md#english-collaboration-defaults-126). These source changes publish no release or installation upgrade.

Release reconciliation in the current source compares release tags, announcements and required package feeds, prerelease flags, latest pointers and release runs against the repository's own documented contract. Missing access or incomplete coverage is reported as unable to confirm; explicitly unused feeds or release automation are not applicable. Findings are listed separately in the final report, never registered or repaired by this skill or included in a cleanup PR. It keeps the same work-cycle gate and deletion authorization. See the bundled [release audit rules](plugins/check-workflow/skills/forge-steward-check-workflow/references/release-audit.md).

The skill names and core workflows use provider-neutral terminology. Platform adapters map a **change request** to a GitHub pull request, a GitLab merge request, or the equivalent concept on another forge, and map **review feedback** to that platform's comments, discussions, or review threads.

Each plugin keeps one canonical `SKILL.md`. A portable root `plugin.json` and a Codex compatibility manifest package it for Codex; a Claude manifest and repository marketplace package the same file for Claude Code and ZCode. OpenCode can consume that unchanged skill directory from one of its Agent Skills locations, such as `.agents/skills/<name>`. OpenCode does not consume the Claude or Codex marketplace indexes.

## Calling the skills

Starting with plugin version `0.2.1`, Codex plugin and skill display names use `<Task> - ForgeSteward`, for example `Find Work - ForgeSteward`. These human-facing labels are separate from the installation IDs and skill invocation names below. The `v0.2.1` snapshot contains this display-name fix. Existing `v0.2.0` installations retain the previous labels until you switch to the new snapshot; see the [version switching guide](docs/versioned-installation.md).

All skill names use the `forge-steward-` prefix and the marketplace remains `forge-steward`. The current target retires the `find-work` plugin ID in favor of `prepare-work` and adds `execute-work`; no old-name alias is provided. Each plugin remains independently installable, with a shared version. The table below describes the current release.

Open an agent session in the repository you want to maintain, select a skill, and append your request. In Codex CLI and the IDE extension, type `$` to select a skill or use `/skills`. Claude Code adds the plugin namespace to the skill name:

| Plugin | Codex / ZCode skill mention (select the actual picker entry) | Claude Code plugin command |
| --- | --- | --- |
| `check-workflow` | `$forge-steward-check-workflow` | `/check-workflow:forge-steward-check-workflow` |
| `prepare-work` | `$forge-steward-prepare-work` | `/prepare-work:forge-steward-prepare-work` |
| `execute-work` | `$forge-steward-execute-work` | `/execute-work:forge-steward-execute-work` |
| `review-and-merge` | `$forge-steward-review-and-merge` | `/review-and-merge:forge-steward-review-and-merge` |
| `fix-feedback` | `$forge-steward-fix-feedback` | `/fix-feedback:forge-steward-fix-feedback` |
| `work-cycle` | `$forge-steward-work-cycle` | `/work-cycle:forge-steward-work-cycle` |

If the selector displays a qualified plugin skill name, select that entry. Prepare work first:

```text
$forge-steward-prepare-work
```

Preparation persists its plan, audit and investigation evidence in the original issues. Its final response is only one line, for example `#123, #145, #167`, or `[]` when no issue meets the gates. Cross-repository tracking uses unambiguous qualified identifiers or full issue URLs on the same line. Copy that list to the independently usable execution skill:

```text
$forge-steward-execute-work #123, #145, #167
```

Execution processes the complete list, continues independent items when one is blocked, and submits separate PRs or MRs without merging. It reads the issues and owning repository policies itself; it needs neither an execution prompt nor the previous conversation. Preparation includes actionable technical investigation and experiments, but no production implementation. Genuine external blockers are recorded during preparation rather than hidden by a ready label.

To run the full workflow, install all six plugins from the same version in an environment that can create and wait for subagents, then explicitly select `$forge-steward-work-cycle`. It accepts one optional positive integer, for example `$forge-steward-work-cycle 5`; omitting it defaults to ten work cycles. Each stage is performed by its own subagent. Low-quota warnings do not stop the workflow; actual creation or wait errors require state reconciliation and bounded recovery before stopping. Completed threads are released when the runtime supports it, and uncertain creation results are checked before retrying to avoid duplicate work. Existing open PRs are reviewed before the first issue preparation cycle, including when `prepare-work` later returns `[]`; eligible merges include safe local and remote source branch cleanup. A PR still blocked after its third repair and final review is paused individually while independent work continues. Invocation authorizes eligible merges under the repository's checks, approvals, and branch protection. The automatic `check-workflow` step runs only on first use or after both a version change and a seven-day cooldown; ordinary commits and PR activity do not trigger it. Its local record lives in Git metadata and is not shared across fresh clones. After all other stages finish, one cleanup-only `review-and-merge` pass records the `cleanup` stage and writes a durable `cleanup.md` audit in the run directory, listing every branch and worktree checked and whether it was deleted, retained, failed, or could not be queried, plus any branches deferred by the 50-branch limit; the report's cleanup summary must agree with that audit. The orchestrator also keeps a `workspaces.json` ownership record in the run directory for every task, branch, workspace path, owning stage, and status, updated at dispatch and completion without changing tracked files or the `handoff.json` format. Attached records keep their real branch; detached records use `branch: null`, `detached: true`, and a full Git object ID in `head`. Legacy empty/null branches without complete detached identity are readable but unverified and retained; mismatched identities are retained too. The [ownership format](plugins/work-cycle/skills/forge-steward-work-cycle/references/workspace-ownership.md) documents writer updates and rollback. A verified detached identity alone cannot be removed. Only an explicitly disposable, finished detached stage workspace can qualify under the [detached cleanup rules](plugins/review-and-merge/skills/forge-steward-review-and-merge/references/detached-workspaces.md), with complete saved evidence, confirmed inactivity, reviewed ignored files, an exact head, and durable recovery. Cleanup keeps final checks in separate `disposal.json` beside the ownership record; ordinary Git removal uses no force, and host-managed workspaces use supported archive APIs with metadata readback. Cleanup may remove a worktree outside the conventional workspace directory only when this run's record names it and every safety condition holds, and never infers ownership from a path; dirty, untracked, locked, current, unqualified detached, other-owned, unmerged, or open-request worktrees are retained and the failed condition is reported. Its per-resource audit preserves recovery and saved records, reports retained counts, and claims no unmeasured disk savings. An explicit stop skips cleanup deletion and says so in the report, and a run deletes at most 50 branches, deferring the rest. See the [orchestration scenarios](docs/work-cycle-scenarios.md).

OpenCode loads these names through its native `skill` tool; ask in natural language, as in the [OpenCode installation example](#opencode). The Claude command syntax is not a shared cross-agent interface.

ZCode supports `$` skill selection and the `/` menu's Skills group; `@` refers to workspace files. A plugin-qualified entry may appear instead of the bare name in the table. Its `agents/openai.yaml` display metadata is not a ZCode compatibility guarantee. See [ZCode skill invocation](https://zcode.z.ai/en/docs/skill).

Explicitly invoking review and merge, even without an extra prompt, authorizes it to merge every change request that passes review, acceptance and repository requirements without asking for confirmation. To review without merging, say so explicitly, for example: "Review the current open change requests, but do not merge."

See the official [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills), [Claude Code skill namespaces](https://code.claude.com/docs/en/skills), and [OpenCode skill loading](https://opencode.ai/docs/skills/) documentation for the host-specific interfaces.

### Historical migration from 0.1.x to 0.2.0

Each plugin moves to `0.2.0` for this invocation-name change. Update the installed plugins through your agent's plugin manager, then start a new session and select the prefixed skills. Update saved prompts and shortcuts: the old unprefixed skill names are no longer provided as aliases. Plugin installation identifiers remain unchanged.

For manually installed skills, replace each old skill directory with the corresponding `forge-steward-<name>` directory, including its bundled resources. Preserve any local modifications before replacing files, and remove the old copy only after verifying the new installation. Keeping both copies exposes both skill names.

## OpenCode installation maintenance

The OpenCode and DeepSeek Harness installers share these rules; replace `opencode.py` with `deepseek.py` for Harness. `SRC` below is a clean clone of the release you want, such as the one created in [OpenCode](#opencode). Use `--project .` in place of `--user` for a project-level installation:

```bash
SRC="$HOME/code/ForgeSteward-vX.Y.Z"
python3 "$SRC/scripts/opencode.py" list
python3 "$SRC/scripts/opencode.py" status --all --user
python3 "$SRC/scripts/opencode.py" update prepare-work --user
python3 "$SRC/scripts/opencode.py" uninstall prepare-work --user
```

The installer accepts either a plugin short name or the full skill name, and `--all`. `install` refuses to replace a copy of a different version; `update` replaces only skills that are already installed, so skills that are new in a release need `install`. The upgrade steps above therefore uninstall and reinstall everything. `uninstall --all` removes only directories with this installer's receipt, even if their source no longer exists in the clone, and leaves unrelated skills and possibly empty `skills` directories.

The installer uses the local clone and never downloads anything itself. An explicit `update` follows the selected clone, including an intentional downgrade. Do not run `git pull` on a tag clone; clone the next release into a new directory instead. Use a separate clean clone if your source has local work.

Each installed skill contains `.forge-steward-install.json`, recording its plugin version, source commit (when Git is available), source dirty state, and content hashes. Repeating an identical install makes no changes. A changed source/version requires `update`; even when the version string is unchanged, content changes are detected.

If a target was copied manually, its receipt is damaged, or its files have been edited, installation/update/uninstall stops with the affected path. There is no `--force` overwrite. Back up or move the complete conflicting directory outside OpenCode's skill search paths, inspect and preserve your edits, then install again. Existing `.agents/skills` or `.claude/skills` copies are not adopted or removed; use `opencode debug skill` to check for duplicate names or unexpected locations. Symlink sources, symlink install paths, and linked content are not managed by this installer.

Selected targets are checked and staged before changing installed skills. Ordinary copy/rename failures roll back the batch. A lock prevents overlapping installer processes; avoid editing installed files while an operation runs. Forced termination or power loss can leave `.forge-steward.lock` and `.forge-steward-txn-*` beside the `skills` directory. Confirm the installer has stopped, preserve the entire transaction directory, and inspect its `old-<skill>` backups before restoring missing installations or moving conflicting copies aside. Once recovery is complete, move the transaction outside the config directory and remove the stale lock before retrying. No crash-durable or hostile-concurrent-writer guarantee is made.

If OpenCode does not discover the skills, confirm the printed target and run `status`, then `opencode debug skill` from the target project. Check OpenCode's skill permissions, custom configuration, and any duplicate manual installs. The installer never changes agent permissions or configuration files. The same script supports macOS, Linux and Windows; CI runs it on all three, and actual OpenCode discovery is tested with `1.18.30` on macOS locally and Linux in CI.

Development checks: `python3 -m unittest discover -s tests -v`. Set `FORGESTEWARD_OPENCODE` to an OpenCode executable to include actual discovery and removal checks in isolated temporary configuration directories; otherwise that test is explicitly skipped. See the [installer design and verification notes](docs/opencode-installer.md).

## Uninstall and verify

Each agent section above has **Uninstall** commands. Uninstall in the same agent environment and scope used for installation. Stop active skill-driven work first, then start a fresh session after removal: an existing conversation can still contain previously loaded instructions. Disabling a plugin is not uninstalling it. Do not delete an entire agent configuration or cache directory to remove ForgeSteward skills. Also remove `find-work@forge-steward` if an old release left it installed; the OpenCode and DeepSeek Harness `uninstall --all` already covers retired managed names.

### Installer uninstall report

For OpenCode and DeepSeek Harness, the uninstall report is deliberately bounded:

- It checks only immediate entries in the printed target, not every project, user directory, ancestor, compatibility path, or custom search path. `--all` reports `forge-steward-*` entries and the four historical names `check-workflow`, `find-work`, `review-and-merge`, `fix-feedback`. Named uninstall checks only the selected names and their known historical counterparts; intentionally retained plugins do not make that operation fail.
- Managed, unchanged installations are removed with resources and receipts. Modified or corrupt selected installations still block the entire planned batch. Missing-receipt/manual copies are not automatically adopted or deleted; `--all` can remove valid managed installations while reporting such leftovers. Historical names are only **candidates**, because another author's skill can have the same name.
- Exit `0` means no matching candidates remain **within that limited scan**. Exit `1` means the operation or scan failed. Exit `2` means removal finished but matching candidates remain (argument-parser usage errors also use `2`; distinguish them by the message). A failed uninstall also reports residues when the target can still be inspected. Empty skill/config containers are allowed; no crash-recovery guarantee is added.

Inspect each reported path, preserve user edits, and move only confirmed copies outside all skill search paths or delete them with explicit ownership confirmation. Do not reinstall a removed skill just to clear a warning. Re-run uninstall to verify its limited report, then `opencode debug skill` to verify actual discovery. `status --all` checks current release names, not every legacy or retired name.

OpenCode also discovers project/user `.agents/skills` and `.claude/skills` copies. Check those separately, along with ancestor and custom paths and any old unprefixed installations; the installer does not remove them. A scope being clean does not prove the skill is unavailable elsewhere. See [OpenCode discovery paths](https://opencode.ai/docs/skills/).

### ZCode imported skills

In **Settings → Skills**, inspect the actual paths of remaining `forge-steward-*` and legacy skills. Imported copies or symlinks are independent of plugin installations: preserve edits, confirm ownership, and move only the redundant copy/link outside discovery paths. Do not follow a symlink and delete another agent's source. Check project/user `.zcode/skills`, `.agents/skills`, configured roots and remote environments as applicable; verify in a new task that removed skills are absent. See [ZCode cleanup and recovery](docs/zcode.md#uninstalling-and-keeping-only-the-target-version).

### What removal does not undo

Uninstall removes availability, not work already performed. Changes made by `check-workflow` to project rules or agent entry documents, code commits, issues, PRs, comments, and conversation history remain project/user assets. Reverting those requires a separate reviewed change; do not delete `AGENTS.md` or `CLAUDE.md` wholesale. Independently configured credentials, integrations and automation are not revoked by skill removal either. A downloaded ForgeSteward source clone is separate from installed copies; retain it if you develop the project, or remove it only after checking for local work and completing uninstall verification.

## The name

**Forge** literally means a workshop where metal is shaped, or the act of creating something through deliberate effort. In software development, a forge is also a platform where source code is hosted and collaboratively developed, such as GitHub, GitLab, or Gitea. Here it represents both the repository platform and the process of shaping an issue into dependable code.

**Steward** means a trusted caretaker: someone responsible for looking after a system, applying its rules, and keeping work moving without claiming unchecked ownership. Here it reflects a careful repository maintainer that inspects project state, protects code quality, and keeps consequential actions subject to explicit policy and human control.

Together, **ForgeSteward** means a trusted steward for the software forge: an agent-assisted toolkit that helps maintainers move repository work forward while respecting review gates, project policy, and human judgment.

## Agent instructions

Repository-wide agent guidance has a single source of truth in [`AGENTS.md`](AGENTS.md). Codex, OpenCode, ZCode and Claude Code v2.1.277+ load it directly. Open this repository root as the ZCode workspace: ZCode does not recursively load nested `AGENTS.md` or expand `@import` / `@include`. Platform adapters must not duplicate shared guidance.

Project-maintained documentation, Issue and change-request titles, bodies, and comments are written in clear English. Skills default to everyday English while honoring explicit user and target-repository language requirements.

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
