# DeepSeek Harness installation and maintenance

## Scope and sources

Since `v0.2.15`, `scripts/deepseek.py` supports DeepSeek Harness's native filesystem Skill discovery. It needs only the Python 3.9+ standard library, without an npm plugin, running Harness, or model key. All six Skills retain their original directories, bodies, references, and scripts. `--all` reads the current catalog, without fixing future counts. The Claude/Codex marketplaces are not native Harness marketplaces.

Shared lifecycle implementation lives in `scripts/skill_installer.py`. `scripts/opencode.py` preserves its existing commands, scopes, schema 1 receipts, output, and exit codes. The thin DeepSeek adapter handles paths and discovery guidance only, without changing Skill business rules. Installing one Skill does not require installing all of them; a complete `work-cycle` also requires five matching-version stage Skills and subagent support. The maintainer has verified that delegation behavior in a local `0.2.0-rc.2` run; its automated probe is not part of this repository's CI. Compatibility with other clients, models, and configurations is not guaranteed.

Sources: [official Skills documentation](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills), and the actual `FileSystemSkillProvider` and `resolveDshHome` in the local desktop/bundled `0.2.0-rc.2` packages on 2026-09-30. SHA-256 for `dsh-skill-filesystem/lib/index.js` is `244e92e032ef15e96cb60c9e2cfddf5d89e167eb171fcbfd83e9415b0455a0d7`; for `dsh-home-paths/lib/index.js` it is `97c1c10b299a4f2aec5f34bac5370cad3834391cd75c91a76b1e7b8a643584f5`. This evidence identifies the checked version, not all future clients.

## First installation and scope

Obtain a separate, trusted checkout first. This example follows current development source: check its commit, `VERSION`, and local changes before use. Development source is not a published Tag; to pin a release, select published `v0.2.15` or later. If source is already available, use its absolute path.

```bash
mkdir -p "$HOME/code"
git clone https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-deepseek"
git -C "$HOME/code/ForgeSteward-deepseek" rev-parse HEAD
git -C "$HOME/code/ForgeSteward-deepseek" status --short
# Run from the project to maintain:
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" list
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" install prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" status prepare-work --project .
```

The full name, such as `forge-steward-prepare-work`, is equivalent. To install everything, use `install --all --project .`. Each command must explicitly select exactly one of `--project PATH` or `--user`. Project PATH must exist: search upward for the nearest `.git` marker, a directory or worktree file, and write to that root's `.dsh/skills/<name>`. Without a Git marker, use PATH itself, matching the checked native provider. Quote paths containing spaces; a subdirectory does not automatically create another installation scope. Reject symlinks and Windows reparse points both before and after resolution so resolving a path cannot discard protection.

User installation uses `install prepare-work --user`, targeting `$DSH_HOME/skills`. Unset, empty, or whitespace-only values fall back to the OS home's `.dsh/skills`. Prefixes `~`, `~/`, and `~\` are supported. Resolve a nonempty relative value from the invocation cwd and preserve leading/trailing whitespace in nonempty values. Always print the absolute destination. Harness's explicit `dshHome` setting takes precedence over the environment; if client configuration overrides it, point the installer's `DSH_HOME` at the same path. The installer neither reads nor changes accounts, credentials, or configuration.

In Windows PowerShell, use an installed Python 3.9+ and the actual checkout:

```powershell
py -3 "$HOME\code\ForgeSteward-deepseek\scripts\deepseek.py" install --all --project .
```

Open a new session from the target project, verify full names and sources in the Skill list, load `forge-steward-prepare-work`, and check that supporting resources are readable. Installer `status` checks only the selected destination; it does not replace client discovery verification. The current provider ranks candidates from project `.dsh/skills`, project `.agents/skills`, custom roots, user `$DSH_HOME/skills`, user `.agents/skills`, and bundled roots, in that order. Higher-priority copies may shadow the same name. The provider does not recursively scan plugin marketplaces; adding only the ForgeSteward repository root does not establish installation.

## Explicit updates, pinned source, and rollback

```bash
# Run in the target project; select only installed entries:
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" update prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" status prepare-work --project .
```

Use `update --all` only when all entries are installed. Missing entries require install first; a conflict in any selected entry rejects the entire batch. The installer uses only the local checkout; it does not implicitly fetch, download, or run remote commands. For a fixed version, select a published Tag containing this adapter from [Releases](https://github.com/philfanzhou/ForgeSteward/releases), or record a reviewed full commit. Do not use early `v0.2.1`, which lacks the DeepSeek entry point. If the separate snapshot directory does not exist:

```bash
# Replace FULL_REVIEWED_COMMIT with the complete trusted SHA first:
git clone https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-deepseek-fixed"
git -C "$HOME/code/ForgeSteward-deepseek-fixed" checkout --detach FULL_REVIEWED_COMMIT
git -C "$HOME/code/ForgeSteward-deepseek-fixed" rev-parse HEAD
git -C "$HOME/code/ForgeSteward-deepseek-fixed" status --short
python3 "$HOME/code/ForgeSteward-deepseek-fixed/scripts/deepseek.py" update prepare-work --project .
```

Use the same checkout process for a published Tag and verify its non-draft Release and SHA. To roll back, select a saved older snapshot and explicitly update; downgrades and same-version content changes are supported. Do not git pull a detached checkout or overwrite source with local work. Receipts record version, source commit/dirty state, all file digests, and empty directories. Install/update with matching version and digests preserves bytes, mtimes, and receipts, so the receipt's commit need not change when equivalent source is checked out. Receipts are not signatures; callers remain responsible for source trust.

## Conflicts, transactions, and uninstall

Do not overwrite or adopt unmanaged same-named directories, user-added/removed/edited files or empty-directory changes, corrupt receipts, or links. There is no force option. Back up the complete directory and differences, move the confirmed conflicting copy outside every Skill search path, then install. Do not delete receipts to bypass protection. Different Agents, project/user scopes, and compatibility roots are independent; updating does not clean other roots.

Write commands hold `.forge-steward.lock` in the destination's parent. Validate and stage the full batch in that parent's `.forge-steward-txn-*`, then publish complete resources and schema 1 receipts with renames. Ordinary copy/rename failures and KeyboardInterrupt trigger reverse-order rollback and normal cleanup. If rollback fails, report the exact transaction path, retain `old-<skill>` backups, and reject the leftover transaction on the next call. A second process rejects an existing lock without deleting the first process's lock. After an interruption, confirm the process has stopped, preserve the entire transaction and restore the actual installation, then move out the transaction and remove the stale lock before retrying. SIGKILL, power loss, filesystem damage, malicious concurrent writes, and atomic multi-directory snapshots for running Agents are not guaranteed.

```bash
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall --all --project .
# Handle user scope separately, keeping the same DSH_HOME/cwd:
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall --all --user
```

Uninstall does not require the Skill to remain in the original source. It removes only selected, valid, unchanged managed directories and receipts, preserving other Skills and empty containers. `--all` may remove valid entries while reporting receipt-free/manual/historical-name candidates. Corrupt or modified selected managed entries still block the whole batch. Scan only direct children of the printed destination: all-selection reports `forge-steward-*` and four known historical names; named selection reports only selected names and their known historical counterparts. Candidates are not proof of ownership; do not follow links or delete unknown contents.

Exit `0` means no leftovers in the limited scan, `1` means an operation/scan failed, and `2` means candidates need manual review. Usage errors may also return 2, so read the output. Errors take precedence; do not report leftovers or a failed scan as successful cleanup. Other projects, user/agents/custom/bundled roots, and old sessions are unscanned; project uninstall does not prove user copies are gone. Recheck actual discovery and resource sources in a new session. Back up and handle only confirmed copies; do not delete whole configurations or caches. Uninstall does not undo project code, rules, Issues, PRs, or earlier work.

## Verification and support boundaries

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_skill_limits.py --check
python3 scripts/sync_marketplace.py --check
git diff --check
```

Shared lifecycle regressions run in three-OS CI. The DeepSeek suite reuses OpenCode's complete transaction/protection assertions and adds a path matrix, fixed-full-commit rollback, and real two-process locking. Real packages are not downloaded automatically. Explicitly give the test an unpacked Harness package directory containing `node_modules/@deepseek-ai/dsh-skill-filesystem/lib/index.js`, `dsh-home-paths`, and dependencies. Users must extract desktop ASAR packages separately first. A usable Node.js is required; the default is `node`, or the second variable may provide an absolute executable path.

```bash
FORGESTEWARD_DEEPSEEK=/absolute/path/to/dsh \
FORGESTEWARD_DEEPSEEK_NODE=/absolute/path/to/node \
python3 -m unittest discover -s tests -p test_deepseek_installer.py -v
```

Without `FORGESTEWARD_DEEPSEEK`, explicitly skip. If configured but packages/Node are missing or incompatible, fail. The probe imports only the explicit runtime and calls the real Provider with isolated project, user, agents, custom, and bundled roots, without exposing other user Skills or calling a model. Compare every full body, resourceBase, and resource digest; check `.git`-file subdirectories, the home matrix, and candidate ranking. After project CLI uninstall, the same provider must still find the user copy; after user uninstall, rediscovery must be empty.

The actual local macOS `0.2.0-rc.2` package passed these checks. Native Windows Harness, the desktop GUI, model behavior, and a complete work-cycle were not verified by this test. CI does not obtain Harness and explicitly skips real tests; real OpenCode discovery CI remains pinned to `1.18.30` on Linux. Passing length checks does not prove that a model always receives every rule in full; see [cross-Agent compatibility boundaries](skill-compatibility.md).
