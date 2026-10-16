# Installing, upgrading, and rolling back fixed versions

For installation, upgrades, and uninstall of the current release, use the README's [supported Agents and installation](../README.md#supported-agents-and-installation), which contains commands for all five Agents. To choose another published version, see [upgrade and keep only the selected version](../README.md#upgrade-and-keep-only-the-selected-version); for removal checks, see [uninstall and verify](../README.md#uninstall-and-verify). This page adds pinning, scope, and rollback boundaries. Commands using `v0.2.1` illustrate a historical version, not the currently recommended installation. Upgrading the Agent application does not upgrade Skills pinned to a Tag.

## Choose a version first

Choose a published Tag from [GitHub Releases](https://github.com/philfanzhou/ForgeSteward/releases) and read its mapping table and migration notes. Examples below use `v0.2.1`; an example is not an available remote version until its Tag and Release are published.

The project requires a unified version: release Tag `vX.Y.Z` corresponds to package version `X.Y.Z` for every plugin, including those with unchanged functionality. The root `VERSION` records a source target, not publication; installation still requires a published Tag. This rule began in the `0.2.2` development baseline. Use `VERSION` for the current target and original mapping tables for historical versions; all four plugins in example `v0.2.1` were also `0.2.1`. In `find-work@forge-steward`, the portion after `@` is the marketplace name, not a replaceable package version. Both marketplaces load plugins from relative paths in one snapshot, so choosing a Tag pins the entire marketplace rather than resolving each plugin's historical versions independently. A single Skill can still be installed. Mixing plugins from different snapshots requires separately designed distribution sources, not cache edits.

A pinned Tag should not follow main automatically. Project policy prohibits moving Tags. For stronger reproducibility, record the full commit SHA in the Release body and compare it with the actual Git checkout. No `v0.1.x` Tags existed before the first release; former plugin version numbers do not establish that matching remote Tags exist.

## Codex

### First installation

Run in a terminal with a CLI supporting `plugin marketplace add --ref` (help checked in `0.154.0`):

```bash
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
codex plugin add find-work@forge-steward
codex plugin marketplace list
codex plugin list --json
```

To install other Skills, replace `find-work` with `check-workflow`, `review-and-merge`, or `fix-feedback` individually. Use `$forge-steward-find-work` in a new session. Marketplace refs support Git branches, Tags, and commits; a precise SHA can replace `v0.2.1`, using the Release's full SHA. Sources: [Codex marketplace configuration](https://learn.chatgpt.com/docs/config-file/config-reference) and local `codex plugin marketplace add --help`.

### Switching an existing marketplace

1. Stop sessions using these Skills and record installed plugins, the old ref, configuration layers, and user edits in caches. Follow administrator or project policies for controlled sources; do not bypass them.
2. Follow the [uninstall documentation](../README.md#uninstall-and-verify) to remove installed plugins from this marketplace. Remove only installed entries and leave same-named plugins from other marketplaces untouched.
3. Remove the old `forge-steward` marketplace configuration, then add the target ref. Do not assume adding the same name again replaces existing configuration.

```bash
# Complete the plugin removal and backups above first:
codex plugin marketplace remove forge-steward
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
codex plugin add find-work@forge-steward
```

4. Reinstall other needed plugins from the record. Use `marketplace list` to verify actual source/ref and `plugin list --json` to verify installation/version. Inspect corresponding cached manifests and Skill directories and verify invocation names in a new session. Appearing in an installable catalog does not mean a plugin is installed.

Upgrade and rollback use the same process with different published refs. Do not edit plugin version fields to force client updates. Different contents carrying the same package version are a release defect for the maintainer to correct first.

## Claude Code

### First installation

Run in a terminal (checked against Claude Code `2.1.269` help and official documentation):

```bash
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.1
claude plugin install find-work@forge-steward --scope user
claude plugin marketplace list
claude plugin list
```

Within Claude, `/plugin marketplace add philfanzhou/ForgeSteward@v0.2.1` and `/plugin install find-work@forge-steward` are also available. In a new session invoke `/find-work:forge-steward-find-work`. GitHub `@ref` supports branches/Tags; Git URLs use `#ref`. Marketplace refs and plugin-source SHA fields belong to different layers; the plugin-source JSON `sha` is not a marketplace-add argument. Source: [marketplace refs and version rules](https://code.claude.com/docs/en/plugin-marketplaces).

### Switching or rolling back

First record all marketplace plugins and installation scopes, the scopes declaring the marketplace, and affected projects. Back up user changes and follow uninstall instructions for `user` and each project's `project`/`local` installations. To retain persistent plugin data during upgrades, uninstall with `--keep-data` and separately back up important data. **Removing a marketplace also uninstalls its plugins; it is not a side-effect-free way to switch one Skill.** Marketplace declarations and plugin installation scopes are separate dimensions. In the checked CLI, omitting `--scope` from marketplace remove removes declarations from every scope.

The following applies only when both marketplace and plugins are installed solely in `user` scope, after plugin removal is complete:

```bash
claude plugin marketplace remove forge-steward --scope user
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.1 --scope user
claude plugin install find-work@forge-steward --scope user
```

For mixed scopes, handle each declaration from its original project directory, explicitly choosing `--scope project` or `--scope local` according to the record. Do not assume a user command from one project cleans other projects. Coordinate shared configuration changes; administrators handle administrator-controlled settings. Reinstall other recorded plugins in their original project scopes and check marketplace refs, installed versions, and new-session invocation. Refreshing a marketplace with an unchanged Tag keeps that ref rather than switching to main. Equal explicit package versions cause updates to be skipped, so successful refresh is not evidence of changed contents. Rechoosing the same Tag with identical version and contents needs no reinstall. On a new Release, update all selected plugins to its unified version.

For an exact commit rather than a Tag, clone a separate clean full repository, check out the Release SHA, and add the local marketplace with `claude plugin marketplace add /absolute/path/to/ForgeSteward`, handling the old same-named marketplace first. Keep the entire checkout, not just marketplace.json, because plugin paths are repository-relative. Do not modify the checkout while it is in use.

## OpenCode

### First installation from a fixed snapshot

Run in a macOS/Linux terminal. The destination must not exist; use a separate directory instead of overwriting an existing source workspace:

```bash
mkdir -p "$HOME/code"
git clone --branch v0.2.1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.1"
git -C "$HOME/code/ForgeSteward-v0.2.1" rev-parse HEAD
```

Confirm HEAD matches the Release SHA, then run from the project to maintain:

```bash
python3 "$HOME/code/ForgeSteward-v0.2.1/scripts/opencode.py" install find-work --project .
python3 "$HOME/code/ForgeSteward-v0.2.1/scripts/opencode.py" status find-work --project .
opencode debug skill
```

Use `--all` for all entries and `--user` for user scope. Retain the installation's `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` for user scope. On Windows select the same Git snapshot, then run `py -3 "C:\path\ForgeSteward-v0.2.1\scripts\opencode.py" install find-work --project .`, substituting the actual path.

### Switching an existing source checkout and installed copies

This example uses an existing `$HOME/code/ForgeSteward`. Check for local work first:

```bash
git -C "$HOME/code/ForgeSteward" status --short
git -C "$HOME/code/ForgeSteward" fetch origin --tags
```

Proceed only after confirming a clean workspace and no branch work to preserve; otherwise create a separate checkout. Replace `v0.2.1` with the selected published Tag or full SHA:

```bash
git -C "$HOME/code/ForgeSteward" checkout --detach v0.2.1
git -C "$HOME/code/ForgeSteward" rev-parse HEAD
# Run in the target project; select only installed Skills:
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" update find-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status find-work --project .
opencode debug skill
```

- Checkout changes source only. `update` explicitly replaces installed copies from that source and allows downgrades; use `install` for missing entries.
- `update --all` requires every Skill in the current checkout to be installed. Update by name for a subset. Separately uninstall removed or renamed Skills using their original names; update does not remove old entries absent from the new catalog.
- `.forge-steward-install.json` records plugin version, source commit at copying, and content digests. Identical contents and version leave the receipt unchanged, so its commit may not become the newly selected Tag SHA. Check digests and the current checkout instead of treating an older receipt commit as a content mismatch.
- User edits, corrupt receipts, or unclear ownership block overwriting. Back up and review differences manually; do not delete receipts or force overwrites to bypass protection. Inspect old names and other directories separately as described in uninstall documentation.
- Commits before the first release may not provide the same installer or invocation interface. Read that snapshot's documentation first; later scripts are not a contract for every historical version.

OpenCode still discovers Skills through its own search directories. `status` checks only the installer's selected scope; user, compatibility, ancestor, and duplicate paths may affect actual discovery. Source: [OpenCode Skill discovery](https://opencode.ai/docs/skills/).

## DeepSeek Harness

Filesystem installation support starts at `v0.2.15`. Use a separate clean checkout containing `scripts/deepseek.py`, pin it to a published Tag or fully reviewed commit, then explicitly update the installed subset. Old `v0.2.1` lacks that entry point. See [DeepSeek installation and maintenance](deepseek-installer.md#explicit-updates-pinned-source-and-rollback) for downgrades, receipts, conflict recovery, DSH_HOME/project Git roots, and uninstall boundaries. Client upgrades do not update Skills; inspect each scope and compatibility root separately.

## ZCode

Like Claude Code, ZCode pins marketplaces with a GitHub address plus version: run bundled CLI `node "$ZCODE_CLI" plugins marketplace add philfanzhou/ForgeSteward@vX.Y.Z`, then `plugins install <plugin>@forge-steward` for each plugin. This was verified on 2026-10-11 in an isolated environment with bundled CLI `0.16.9`: selecting an older Tag installed the older version. Full current commands are in the [README's ZCode section](../README.md#zcode).

To switch or roll back, record the installed subset and source, uninstall each using `plugins uninstall <plugin>@forge-steward --force --keep-data` (`--force` only skips confirmation), then run `plugins marketplace remove forge-steward` (marketplace removal alone does not uninstall plugins). Add the selected Tag and reinstall. Check versions with `plugins list --json` and sources in a new task. On failure, use the same process to restore the old Tag. Earlier local-checkout marketplace installations no longer depend on that directory once switched to GitHub this way. Desktop UI operations were not tested; see [ZCode fixed versions and rollback](zcode.md#fixed-versions-and-rollback).

Marketplace versions are derived from `VERSION` for update detection only; they do not select different source. `plugins update` follows the marketplace's version, including downgrades, but does not install newly added plugins. Both upgrade and rollback must handle manual imports, retired `find-work`, and other scopes; see [uninstalling and keeping only the target version](zcode.md#uninstalling-and-keeping-only-the-target-version).

## prepare-work and execute-work rename migration

From `v0.2.3`, old `find-work` is replaced by `prepare-work` and `execute-work`; see [migration notes](prepare-execute-migration.md). This page's pinned `v0.2.1` examples preserve historical names. For newer versions, update the installed subset using that version's name mapping; do not only replace the Tag and keep installing retired names.

## Upgrading from v0.2.0

When targeting `v0.2.1`, all four plugin packages move from `0.2.0` to `0.2.1`, mainly changing Codex plugin/Skill display metadata. Installation IDs, invocation names, default prompts, SKILL.md, and installer behavior remain unchanged. Old Tags do not receive fixes automatically; switch marketplace refs or source and explicitly update as above. Roll back the same way to retained `v0.2.0`, checking its [historical mapping table](releases/v0.2.0.md). Full changes are in the [v0.2.1 mapping table](releases/v0.2.1.md).

## Completion criteria

The source ref/SHA must match expectations, selected plugin versions must match the Release mapping table, actual installed contents must match the source, and a new session must show correct invocation names. Keep the old version and recovery record. On failure, report actual uninstall/install progress, not cache refresh or command exit as a completed switch. Switching Skills does not automatically undo project rules, code, Issues, PRs, Comments, or credentials already changed.

“Keep only the new version” first means no old copies remain among actual discovery sources. Check each environment, scope, and manual path; a selector showing one name does not prove there are no duplicates. Verify disk cleanup separately. Codex uninstall declares removal of the corresponding local cache; Claude Code has a background-cleanup grace period for old caches; OpenCode update replaces selected managed directories but leaves other scopes, retired names, and manual copies; ZCode handles plugin removal separately from imports, caches, and remote synchronization. Do not claim immediate zero leftovers across all of them.

For immediate disk cleanup, stop related sessions, list exact old paths, and confirm ForgeSteward ownership and references from every configuration/scope. Use the manager's uninstall command for managed installations. Move confirmed unreferenced caches or manual copies outside all discovery paths as backups, verify, then delete. Do not delete shared directories with broad wildcards. Treat source clones separately from installed copies: OpenCode and DeepSeek Harness copies do not depend on the original clone, nor do GitHub-source marketplaces depend on local directories. A checkout still used as a local marketplace source must remain until switched to GitHub. See the README's [checklist for keeping only the intended version](../README.md#verify-that-only-the-intended-version-remains).
