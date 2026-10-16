# ZCode support, installation maintenance, and verification

## Status and approach

ZCode support starts at `v0.2.3`. The current version contains six independent plugins, each with one canonical Skill body, without a `.zcode-plugin`, second marketplace, installer, or duplicate workflow. ZCode directly uses existing `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; all `source` entries still point to `./plugins/<plugin-name>` within one snapshot. Do not backport these changes into old Tags.

On 2026-10-11 the local ZCode desktop was `3.14.5`, with separately versioned bundled CLI `0.16.9` (the desktop was `3.14.3` during the 2026-09-27 discovery check, with the same CLI version). Updating the application and updating ForgeSteward Skills are separate operations; changing this repository's version does not update ZCode.

Marketplace sources use a GitHub address plus version, `philfanzhou/ForgeSteward@vX.Y.Z`, rather than depending on a local directory. Verified behavior covers bundled-CLI marketplace addition, installation, version switching, uninstall, marketplace removal, and Skill discovery/reading. Equivalent desktop UI operations and model behavior were not tested; these results do not guarantee every version.

## Installation and invocation

Use the [README's ZCode section](../README.md#zcode) for current installation, upgrade, and uninstall commands. They are maintained centrally in work-cycle's `scripts/agents.json`; tests keep README aligned with that file and `VERSION`. The following explains their evidence and boundaries.

1. The bundled CLI is inside the application package, by default `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs` on macOS. Run it with Node.js: `node "$ZCODE_CLI" plugins ...`. It shares `~/.zcode/cli/plugins` with the desktop UI, so CLI-installed plugins are visible there and take effect after restarting ZCode.
2. `plugins marketplace add philfanzhou/ForgeSteward@vX.Y.Z` adds the `forge-steward` marketplace with source `{"source":"github","repo":"philfanzhou/ForgeSteward","ref":"vX.Y.Z"}`. Without `@ref` it follows the remote default branch, not a pinned release, and does not obtain unmerged PR contents.
3. Run `plugins install <plugin>@forge-steward` individually for `check-workflow`, `prepare-work`, `execute-work`, `review-and-merge`, `fix-feedback`, and `work-cycle`. A complete work cycle requires all six at one version.
4. The desktop's Settings → Plugins → Add plugin marketplace (Discover → + in some clients) writes to the same plugin directory. Entering `philfanzhou/ForgeSteward@vX.Y.Z` should be equivalent, but the UI operation itself has not been tested.
5. Verify names in Skill settings and the new-task selector. Type `$` to select a Skill; the `/` menu also has a Skill group. If shown as `plugin-name:skill-name`, select the actual qualified item. Canonical identifiers still contain `forge-steward-`; support for Codex `agents/openai.yaml` display labels is not promised.

Selecting a Skill avoids pasting its complete prompt, but the operation still needs its required inputs and authorization. Preparation may use its default scope; execution requires an explicit Issue list. Explicitly selecting review-and-merge authorizes reviewing and directly merging eligible items without asking again for each. Explicit restrictions such as check-only or no-push take precedence; the selector does not bypass repository permissions. Users supply hosting-platform authentication through the CLI/connector, Git, and project test environments; installing a Skill does not grant these capabilities.

## Fixed versions and rollback

The source Tag determines the version: `@v0.2.21` installs `0.2.21`, and `@v0.2.20` installs `0.2.20`. `plugins marketplace update` refreshes the same Tag without following newer releases. Upgrade and rollback use the same process with different published Tags:

1. Choose a published Tag from remote Releases, verifying non-draft status and the version table. Do not treat an unpublished source target as a published Tag.
2. Record existing marketplace source, installed subset, and package versions. Preserve customizations and stop active tasks.
3. Run `plugins uninstall <plugin>@forge-steward --force --keep-data` individually. Noninteractive terminals reject uninstall without `--force`; it only skips confirmation. `--keep-data` retains plugin data directories. Errors for plugins never installed may be ignored. Also remove historical `find-work` leftovers.
4. Run `plugins marketplace remove forge-steward`. Marketplace removal alone does not uninstall plugins, so step 3 must come first.
5. Run `plugins marketplace add philfanzhou/ForgeSteward@<selected-tag>`, then install each plugin.
6. Check each `version` with `plugins list --json` and confirm Skill sources in a new task. If any step fails, use the same process to reinstall the recorded old Tag.

`plugins update <plugin>@forge-steward` replaces an installed plugin with the version currently selected by the marketplace, including downgrades. Newly added plugins still require `install`, so this document and README use uninstall → replace marketplace → reinstall. The marketplace remains named `forge-steward`; do not register multiple same-named sources or edit caches to simulate installation.

Earlier guidance used a local source directory as the marketplace. That source depends on the directory remaining available. If deleted, cached Skills may work temporarily, but later refresh/update fails. Switching to GitHub with the steps above removes the old directory dependency. To review an unpublished commit, a local checkout's **root** may still be added temporarily, not its `.claude-plugin` subdirectory. Keep it while in use. `owner/repo@<full-commit-SHA>` has not been verified.

Rollback does not undo code, Issues, PRs, Comments, or project constraints already produced by the Skills.

## Update detection and release constraints

ZCode uses a marketplace entry's `version` to detect available updates; the plugin's own `plugin.json` gives the installed package version. The shared marketplace therefore needs derived versions without becoming an independent source:

```bash
python3 scripts/sync_marketplace.py --write
python3 scripts/sync_marketplace.py --check
```

The script first validates a one-to-one match between marketplace entries and current plugin directories, same-snapshot relative sources, and matching names/unified versions across three manifests. It then synchronizes only marketplace `version`, without changing packages, fetching network data, or writing user configuration. Other fields and ordering are retained. Version mismatches, missing/duplicate entries, or external sources fail; marketplace edits cannot conceal package version problems. CI runs the check on three OSes. No ZCode fields are added to the Codex marketplace.

For sources without `@ref` that follow development, first refresh the marketplace in the client, then check and update the installed subset. Unpublished same-version changes may trigger no update notice; reinstall and verify contents instead of bumping every time for a notification. Releases still require unified versions, immutable old Tags, and the [release policy](releasing.md).

## Uninstalling and keeping only the target version

Disabling, uninstalling, removing a marketplace, and cleaning disk files are separate actions. Back up customizations and stop Skill tasks, uninstall the actual ForgeSteward subset, then remove the source if needed. See the [README's ZCode uninstall commands](../README.md#zcode): run `plugins uninstall <plugin>@forge-steward --force` individually, then `plugins marketplace remove forge-steward`. Without `--keep-data`, plugin data directories are deleted too. The desktop UI also offers uninstall in plugin details. New names do not automatically replace old names; check historical `find-work` as well.

Manual imports are independent of plugins: Copy does not track later source changes; Symlink depends on the source directory remaining. Do not use another Agent's version cache as a permanent symlink source, as upgrade cleanup may break it. Inspect user/workspace `.zcode/skills`, `.agents/skills`, other configured roots, and remote environments. A selector entry may shadow same-named copies; inspect actual paths, not just menu counts.

After confirming ownership and no remaining references, move redundant copies or links outside every discovery path for safekeeping. Do not follow a symlink and delete another Agent's source. Remove managed plugins through their manager first; handle only confirmed unreferenced ForgeSteward cache paths. GitHub sources do not depend on local directories. For a local source, first switch to GitHub using [fixed versions and rollback](#fixed-versions-and-rollback), then delete its directory. Do not delete all of `.zcode`, shared plugins/cache, or other Agent configuration. The runtime goal is absence from new tasks after uninstall; immediate zero disk leftovers is not guaranteed here. Verify SSH/WSL synchronized copies separately on their hosts.

## Project rule adaptation

ZCode natively reads global `~/.zcode/AGENTS.md` and the current Workspace's `AGENTS.md`; it neither merges multiple directory levels automatically nor expands `@import` / `@include`. `CLAUDE.md` is not a persistent loading entry point. In `0.2.5` and `0.2.6`, check-workflow wrote a standard workflow block into the Workspace-root `AGENTS.md`. From `v0.2.7`, workflow policy lives only in Skill bodies. check-workflow removes those blocks and project rules that duplicate the Skills, writes nothing to `AGENTS.md`, and never writes global rules. See bundled [Skill-owned rules and removal](../plugins/check-workflow/skills/forge-steward-check-workflow/references/skill-owned-rules.md).

## Verification records and reruns

On 2026-09-27, discovery of all six Skills, complete body loading, and length boundaries were rechecked with desktop `3.14.3` / bundled CLI `0.16.9`; see [cross-Agent compatibility records](skill-compatibility.md). The former static-test limit of 100 × 1024 body bytes was replaced with shared budget checks because the verified implementation actually limits the complete file to 100,000 bytes.

| Verification level | Result / boundary |
| --- | --- |
| Local version and package inspection | Desktop 3.14.3, bundled CLI 0.16.9; actual CLI verification remains authoritative for marketplace-manifest reading; installation was not covered by this inspection |
| Repository contract | `tests/test_zcode_packaging.py` checks derived marketplace versions, flat Skills, metadata length, body size, relative references, and synchronization rejection paths; it is not a general ZCode schema validator |
| Actual CLI discovery | Bundled CLI 0.16.9 loaded six relocated plugins in a temporary workspace; inspect confirmed each readable and untruncated; disabling temporary plugin configuration removed discovery from that path |
| CLI marketplace lifecycle | On 2026-10-11, bundled CLI 0.16.9 in isolated temporary HOME added `philfanzhou/ForgeSteward@v0.2.21`; all six installed at `0.2.21` and matched the Tag file by file. Switching to `@v0.2.20` installed `0.2.20`. Verified required `--force` for uninstall, marketplace removal leaving plugins installed, and `plugins update` following marketplace versions including downgrades. Local `~/.zcode/cli/plugins` and `config.json` were unchanged before/after |
| Desktop marketplace lifecycle | GUI marketplace addition, install, update, rollback, and uninstall were not tested. UI and CLI share a plugin directory, but UI operations remain unverified |
| Model behavior | No model calls or real business Issue/PR writes; no claim that selecting a Skill reliably completes work or that merge behavior passed |

Run static/regression tests with `python3 -m unittest discover -s tests -v`. Optional real CLI checks require an installed official application and Node.js, without a model key or changes to HOME/user configuration:

```bash
FORGESTEWARD_ZCODE_CLI=/opt/ZCode/resources/glm/zcode.cjs \
  python3 -m unittest discover -s tests -p test_zcode_packaging.py -v
```

With the variable unset, real runtime tests explicitly skip. CI does not download or silently install ZCode and normally proves only static contracts. Tests may read current discovery sources but assert only temporary-project Skills, do not output other Skill lists, and do not run model tasks. Later desktop verification should use an isolated workspace: add a reviewed marketplace → install six entries → check qualified names/complete references → switch a verified version → uninstall → confirm no duplicates in a new task. Separately test model acceptance for read-only/no-publication restrictions, execute's required list, and review merge requirements, without operating on real production PRs.

## Sources

- [ZCode installation](https://zcode.z.ai/cn/docs/install): public versions and supported platforms.
- [ZCode Plugin](https://zcode.z.ai/cn/docs/plugin): compatible manifests, custom marketplaces, update detection, enable/disable, and uninstall.
- [ZCode Skill](https://zcode.z.ai/en/docs/skill): format limits, invocation, import, and synchronization.
- [ZCode Agent](https://zcode.z.ai/cn/docs/agents): AGENTS instruction sources and loading boundaries.

When official docs and client versions differ, use verified-version behavior and record the difference. No unofficial same-named ZCode project was used as a specification source here.
