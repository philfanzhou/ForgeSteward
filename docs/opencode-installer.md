# OpenCode installation adapter

## Scope and choices

This adapter originally implemented Issue #1, when the repository had four plugins. `--all` reads `plugins/*/skills/*` from the current checkout rather than a fixed count; the current source has six plugins. This is a repository-level tool, not a separate Skill. Shared lifecycle code now lives in `scripts/skill_installer.py`; the OpenCode entry point preserves scope, schema 1 receipts, output, and exit codes. DeepSeek shares the core with a separate path adapter; see [DeepSeek installation and maintenance](deepseek-installer.md). See [prepare-work and execute-work](prepare-execute-migration.md) for the rename migration, which requires no installer algorithm change. `work-cycle` is independently installable, but a complete run also requires all five stage Skills at the same version and working subagent support.

The script uses the Python 3.9+ standard library, avoiding another package release, runtime dependencies, and three copies of core code. After obtaining the repository, users can install selected Skills or all Skills with one command. The initial Git clone is an explicit prerequisite; this is not a remote one-command service that needs no checkout.

Users must explicitly choose `--project PATH` or `--user`. Project installation targets `PATH/.opencode/skills`. User installation honors `OPENCODE_CONFIG_DIR`, otherwise using the XDG configuration path and the `~/.config/opencode` default. The resolved destination is printed; existing Agent configuration and permissions are preserved.

Sources: [OpenCode Skill discovery](https://opencode.ai/docs/skills/), [CLI debug commands](https://opencode.ai/docs/cli/), and [global configuration path source](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/global.ts). Real discovery is verified with pinned `opencode-ai@1.18.30`; the source's dev branch is not evidence for every released version.

## Installation and ownership

- `list` shows installable source entries. Select a plugin's short name or its full Skill name prefixed with `forge-steward-`. Directories and single-line frontmatter names and descriptions must pass repository format checks. This is not a general YAML or third-party Skill package parser.
- Install the whole Skill directory, including bundled references. `.forge-steward-install.json` records the tool identity, receipt format, Skill name, plugin version, source commit/dirty state, file digests, and empty directories.
- Reinstalling identical versions and contents leaves files and receipts unchanged. Version or content changes require an explicit `update`. Users may check out an older commit and update to roll back; a local installation is not an automatic version service.
- `status` reports missing installations, matching source, changed source, manual changes, or an invalid receipt. Conflicts return 1; reading status does not write directories.
- `uninstall` handles only directories with valid tool receipts and unchanged contents, without requiring the original Skill source to still exist. It removes the receipt too; repeating an unchanged uninstall succeeds. Empty configuration containers may remain.
- Receipts detect local ownership and accidental changes; they are not signatures or protection from malicious tampering. For reproducibility use a clean checkout at a fixed commit. When Git information is unavailable, record it as unknown and use digests to identify the copied contents.

## Conflicts and partial failures

Preflight checks all selected destinations. Any same-named unmanaged directory, missing/corrupt receipt, manual edit, or symlink stops the entire batch without overwriting. Recover from installation conflicts by backing up or moving the original directory, preserving differences manually, and reinstalling; there is no `--force` bypass. `uninstall --all` selects only prefixed directories with receipts, so receipt-free copies do not block removal of valid managed entries, but must be reported at the end rather than silently claiming cleanup. Uninstall leftovers only need confirmed ownership and removal or relocation, not reinstallation. Manual installations in other Agent paths remain untouched; check duplicate names in OpenCode's actual discovery list.

The installer holds an exclusive lock in the configuration directory and stages complete new copies outside `skills` so discovery cannot mistake staging files for Skills. Commit replaces directories with same-filesystem renames. Ordinary exceptions and KeyboardInterrupt trigger attempted rollback in reverse order. Failed rollback retains backup directories and reports their paths; later invocations refuse to overwrite unrecovered transactions.

A batch is not an atomic multi-directory snapshot for a running OpenCode session; restart the session after installation. Automatic recovery from power loss, SIGKILL, filesystem corruption, or hostile concurrent writes is not guaranteed. After an abnormal interruption, inspect `.forge-steward.lock` and `old-<skill>` copies in `.forge-steward-txn-*`. Preserve and restore the actual installation before moving transaction directories out and removing locks no process holds. Normal operations remove locks and staging files, not project files or other Skills.

## Uninstall leftover reports

After uninstall, inspect the printed destination read-only. Also try to report after preflight or ordinary transaction failures, with errors taking precedence and existing whole-batch protection and rollback unchanged. Reports do not depend on source directories or the catalog, so a Skill removed from newer source can still be uninstalled or reported.

- `--all` checks direct children named `forge-steward-*` and historical names `check-workflow`, `find-work`, `review-and-merge`, and `fix-feedback`. Historical names are compatibility hints, not a plugin-count limit or proof of ownership.
- Named selection checks only the selected name and known historical counterpart, without treating other deliberately retained plugins as uninstall failures.
- Report actual paths and states: a valid managed entry remains, unmanaged/missing receipt, invalid receipt, changed contents, historical-name candidate, or link. Do not follow links. Retain and report same-named files and empty directories too, without assuming ForgeSteward owns them.
- Exit codes: `0` means no candidate remains within the limited scan, `2` means candidates remain, and `1` means an operation or scan failed. Argument-parser usage errors also return `2`; distinguish them using the output. A scan failure cannot be reported as successful cleanup.
- Do not cross project, user, compatibility, ancestor, or custom discovery roots. Arbitrarily renamed or nested copies are not guaranteed to be found. Remind users to verify real discovery in a new session with `opencode debug skill`. Empty configuration containers are not leftover Skills and are not removed automatically.

Back up candidates and confirm ownership first. Move only confirmed copies outside all Skill discovery paths or delete copies no longer needed. There is no automatic purge of unmanaged contents. Uninstall does not undo project rules, code, Issues, PRs, Comments, or earlier work. The README provides unified uninstall instructions for three Agents, scope/cache boundaries, and verification requirements.

## Verification

`python3 -m unittest discover -s tests -v` covers individual/all selection, directory names/frontmatter, resource completeness, idempotence, version and same-version content changes, manual edits/file additions/removals/empty directories, unmanaged conflicts, corrupt receipts, path traversal and symlinks, user paths, uninstall after source removal, locking, staging failures, and rollback after a partial commit.

When `FORGESTEWARD_OPENCODE` names an OpenCode executable, the same suite invokes `opencode debug skill --pure` in temporary projects and isolated XDG configuration, checks every current name and full path actually discovered, and confirms an empty list after uninstall. It does not call a model or alter real user configuration. If the variable is unset and OpenCode is absent from PATH, this check is explicitly skipped.

GitHub Actions runs standard-library tests on macOS, Linux, and Windows, plus real discovery with pinned OpenCode `1.18.30` on Linux. On Windows use `py -3` or a configured Python 3.9+. Symlink tests report a skip if creation is not permitted; native Windows OpenCode runtime behavior has not been verified.

Leftover regressions additionally cover normal/repeated uninstall, missing receipts, manual and historical-name candidates, independence from source, named uninstall preserving other entries, batch protection/reporting for corrupt receipts, dangling links, user/project isolation, scan failures, and real CLI exit codes. The real OpenCode test also verifies that uninstall with a missing receipt returns a leftover state and the Skill remains discoverable; command completion must not be mistaken for removal. Tests use temporary directories and never delete real user installations.

The README places installation and invocation for three Agents before the project explanation, and documents source pinning, updates, uninstall, migration, scope, and recovery. The installer changes neither Claude/Codex distribution mechanisms nor Skill business workflows and authorization boundaries.
