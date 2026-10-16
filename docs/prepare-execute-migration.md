# Preparation and execution Skill migration

## State at this migration

The target at the time of this migration was `0.2.3`, not yet released. It renamed `find-work` to `prepare-work` and packaged the former execution prompt as the independent `execute-work` Skill. Neither requires or automatically invokes the other. All three manifests of all five plugins matched the root `VERSION`. Version changes follow [AGENTS.md](../AGENTS.md#unified-version); this document still discloses the incompatible rename.

| Previous identifier | New identifier | Usage change |
| --- | --- | --- |
| `find-work@forge-steward` | `prepare-work@forge-steward` | Continue investigation, experiments, and plan refinement until implementation is possible or a real external blocker remains; do not implement production code |
| `forge-steward-find-work` | `forge-steward-prepare-work` | Persist the complete handoff on the original Issue; finish with one line of identifiers and no execution prompt |
| Manually copied long execution prompt | `execute-work@forge-steward` / `forge-steward-execute-work` | Accept an identifier list directly, implement and validate each item, and submit independent PRs/MRs without merging |

The other three plugins retain their names. No old-name alias is provided, avoiding simultaneous loading of two preparation workflows. Earlier prompt behavior remains part of earlier versions; historical Tags and Releases are not rewritten.

## Usage handoff

After an explicit prepare-work invocation, progress updates may describe investigation and external problems. The final response must be exactly one line such as `#123, #145, #167`, without manual line breaks. If nothing meets the requirements, return `[]`. For duplicate numbers across repositories, use platform-recognized qualified identifiers, or complete Issue URLs if necessary for unique resolution. Keep everything on one line. Record cross-repository implementation ownership on the original Issue instead of duplicating the task.

Append that list unchanged to an execute-work invocation. The implementer reads the Issues and actual repository rules, reuses valid audits, and checks relevant changes. If an item becomes genuinely blocked, retain evidence and continue other independent items. Do not stop after the first PR or stack work on unmerged code.

Read-only preparation does not publish Issue updates; omit items missing a required handoff and explain the gap during progress updates. Explicit local-only implementation does not publish a PR. Merely discussing a name or an implicit Skill match still requires interpreting authorization from the actual user request.

## Installation migration

These steps are for maintainers choosing the newer version; the source PR did not perform user installation or publication. For production use, wait for a confirmed published target Tag. To validate development source early, use a separate checkout at a specific reviewed commit rather than assuming `v0.2.3` already exists. At the time, root installation examples remained pinned to published `v0.2.1`; changing only plugin names could not obtain the new Skills.

Record the current source, installed subset, and scopes first, preserve local customizations, and stop active tasks using old Skills. In Codex/Claude, remove old `find-work@forge-steward` through the plugin manager, then follow the [version-switching guide](versioned-installation.md) to point the marketplace at the chosen newer snapshot. Install `prepare-work@forge-steward` and, if execution is needed, `execute-work@forge-steward`; synchronize other selected plugins to that snapshot. Replacing only a marketplace directory does not prove installed copies were upgraded.

For development validation, the marketplace may point to a separate local checkout. Use the Agent's supported local-path marketplace entry; do not edit caches or real user configuration to simulate installation validation. After installation, inspect actual package version, source, and the new-session selector, and update saved shortcuts to the new names. Codex uses `$forge-steward-prepare-work` and `$forge-steward-execute-work`; Claude uses `/prepare-work:forge-steward-prepare-work` and `/execute-work:forge-steward-execute-work`.

For OpenCode, use the chosen newer checkout with these commands. Replace `/path/to/ForgeSteward` with the actual path and run from the target project:

```bash
python3 /path/to/ForgeSteward/scripts/opencode.py uninstall find-work --project .
python3 /path/to/ForgeSteward/scripts/opencode.py install prepare-work execute-work --project .
python3 /path/to/ForgeSteward/scripts/opencode.py status prepare-work execute-work --project .
opencode debug skill
```

Check each result in order. For user installation use `--user`, retaining the original XDG/custom configuration choice. Update the other three existing plugins by name when needed. `update --all` neither installs missing new Skills nor renames old entries automatically. `install --all` installs only the current catalog and does not remove retired names, so it cannot replace uninstalling an old name.

The installer can remove an unchanged old Skill with a valid receipt without its original source. Customized, receipt-free, or manually copied old versions are preserved and reported. Back up, confirm ownership, and move them outside discovery paths before continuing; do not bypass protection. Check old copies in other Agent compatibility paths separately. A new name appearing does not prove the old workflow disappeared. To roll back, choose a historical snapshot and restore historical names; do not roll back Issues or code already produced by the Skills.

ZCode's development support reuses the Claude-compatible marketplace. If an old `find-work` was manually imported or installed, follow [ZCode maintenance](zcode.md) to remove that plugin, inspect imported copies, and switch marketplace snapshots. Then select `prepare-work` and optionally `execute-work`; do not copy Codex/Claude commands directly. In new tasks use `$` to select the actual Skill item; execution still requires an explicit list.

## Verification boundaries

Installer regressions at this migration covered installation of all five entries, safe removal of retired names, protection of old contents, and installation of new names. Format and marketplace validation do not prove actual model behavior. See [scenario acceptance checks](prepare-execute-scenarios.md) for limited rule walkthroughs; the PR records the checks and installation results actually run.
