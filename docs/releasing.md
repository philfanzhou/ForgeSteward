# Release policy

## Versions and deliverables

ForgeSteward is distributed through Git repository snapshots and Agent marketplaces, not npm, PyPI, or NuGet registries. There is currently no automated pipeline for creating Tags, uploading packages, or creating Releases; existing CI runs tests on PRs and main pushes. This policy uses maintainer-authorized manual releases. Pushing an arbitrary branch is not publication.

| Identifier | Managed contents | Source of truth |
| --- | --- | --- |
| Repository Tag `vX.Y.Z` | Entire repository, including marketplace indexes, every plugin, installers, and docs | Annotated Tag on a reviewed main commit |
| Unified version `X.Y.Z` | Complete contents of every plugin package and this repository release | Root `VERSION`; all three `plugin.json` manifests per plugin must match |
| GitHub Release | Version mapping table, actual commit SHA, changes, verification, and limitations | Release page for the matching Tag |

The repository and all plugins share one version: when `VERSION` is `X.Y.Z`, all package versions are `X.Y.Z` and the release Tag must be `vX.Y.Z`; prerelease suffixes must also match exactly. This rule began in the `0.2.2` development baseline. `VERSION` determines the current unreleased target; historical release records remain unchanged. Repository installers are pinned with the repository Tag and have no separate package version. Independent installation does not mean independent versioning. Users may still install only one plugin; the project offers no resolver for arbitrary mixes of historical plugin versions.

## Version bump rules

- Repository releases use `vX.Y.Z`; candidates may use `vX.Y.Z-rc.N`, marked prerelease on GitHub. The `0.x` series remains an early interface, not a 1.0 stability promise. The first numbered release was `v0.2.0`; do not invent earlier Tags.
- Users decide versions; Agents must not bump them independently. Follow [AGENTS.md's unified version rules](../AGENTS.md#unified-version). A requested bump without a target increments only the last component; other components or prerelease channels require explicit user choice. Change size does not justify changing another component. Document migration for incompatible changes rather than implying compatibility from a patch number.
- Choose one version for the entire release and update `VERSION` and all plugin manifests together, even if a plugin's functionality is unchanged or only the root README/installer changed. Development commits may keep an unreleased target; no per-commit bump is required. Agents change versions only on explicit user request, following [AGENTS.md](../AGENTS.md#unified-version).
- Keep each plugin's `plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/plugin.json` names and versions synchronized. Shared Claude/ZCode marketplace `plugins[].version` is derived metadata for ZCode update detection, not a separate version source. After synchronizing manifests, run `python3 scripts/sync_marketplace.py --write`, then `--check` before release. Codex marketplace format stays unchanged. References remain relative paths within the same snapshot; index versions do not independently switch plugin source.
- A published plugin version must never identify different package contents. Later repository Releases do not reuse old plugin versions, even for unchanged functionality. Claude's explicit version in particular affects cache updates; do not move Tags or change only marketplace metadata to bypass caching. See [Claude version rules](https://code.claude.com/docs/en/plugin-marketplaces#version-resolution-and-release-channels).
- Never move, overwrite, or delete and recreate published Tags; release a new version for fixes. Annotated Tags are not cryptographic signatures by default. Configure signing separately if needed; this policy does not substitute for server-side Tag protection.

## Release steps and requirements

1. Obtain the maintainer's version choice and authorization. Prepare changes on a working branch and add `docs/releases/<tag>.md` with the mapping table, changes, migration, and verification boundaries. In the same PR update versions in the README opening, installation table, and each Agent's installation/upgrade/uninstall commands to the new `VERSION`. For added/renamed plugins or changed Agent commands, update work-cycle's bundled `scripts/agents.json` first, then synchronize README. `tests/test_agent_catalog.py` checks README against `VERSION`, plugin directories, and `agents.json`, identifying missing plugins or mismatched versions. After merge, immediately Tag and publish using the steps below. README says Releases are authoritative and the new version may briefly be unavailable before the Tag is published. Since `VERSION` changes only for releases, README should not point at an unpublished version long term. Do not rewrite historical tables when current plugins are bumped.
2. Check `VERSION`, every plugin's three manifests, shared-marketplace derived versions, and complete resources. Every package version must match `VERSION`. Run `python3 scripts/sync_marketplace.py --check`. Manually confirm the target Tag is exactly `v` plus `VERSION` and every plugin in the new Release mapping table has that version. Compare the previous release record to confirm a new version. CI metadata tests check source consistency, not the remote Tag and Release mapping.
3. Submit and review the PR. Run `python3 scripts/check_skill_limits.py --check`, `python3 -m unittest discover -s tests -v`, `git diff --check`, relative-document link checks, and version-table checks; run available Agent validation. All three OS installer checks and pinned OpenCode discovery checks must pass. For changed Agent packages, add affected-Agent installation verification and explicitly disclose the absence of model-behavior testing.
4. Merge through repository protection without direct main pushes or bypassing checks. Record the reviewed head, actual main merge commit, and CI links. Wait for all four checks on that main commit to pass; verify again if the merged source differs.
5. Query read-only to confirm the target Tag/Release does not exist. If it exists, verify its target instead of overwriting it. Create an annotated Tag only on the exact verified commit from the previous step and push that single Tag, never bulk `--tags`. Use a resolved explicit SHA in release commands; do not guess again after main moves.
6. Reread the remote Tag after pushing. Its annotated object and target commit have different SHAs: dereference to the commit and compare with the review record. Use `gh release create <tag> --verify-tag` to associate the existing Tag, rather than letting the platform silently create one from latest main.
7. Use only the Tag name as the Release title, such as `v0.2.18`, with no project name or extra text. Write the Release body in English, including the exact commit SHA, mapping table, installation links, CI, compatibility, and migration. Current releases contain Git snapshots and GitHub's automatic source archives; do not claim standalone build packages or end-to-end certification across all Agents.
8. Verify remote Tag and Release tagName/draft/prerelease state and links, and leave the handoff on the PR. Clean only this task's merged branches/temporary directories with no unique work; do not touch user installations.

`<tag>` above is a parameter placeholder, not directly executable shell text. Fill in verified values before running commands.

## State, failure, and rollback

- Version documents in the repository are release inputs, not proof of publication. Confirm completion using both the remote Tag and matching non-draft GitHub Release. The Release body records the full commit SHA; documents in that same commit do not include their own SHA, avoiding circular dependence.
- If Tag push succeeds but Release creation fails, retain the Tag, verify its target, and retry the same Release without retagging. Query first after an uncertain result to avoid duplicate creation.
- If released contents are faulty, disclose known problems, recommend rollback, and open a fix PR followed by a new version. Do not delete existing versions to hide problems. Corrections to release notes must be marked as errata and cannot change the Tag's source identity.
- See [fixed-version installation](versioned-installation.md) for user rollback. Rolling back a Skill does not undo code, project rules, or hosting-platform actions it already produced.

## Current release input

The current source target is `0.2.24`; see its [mapping table and notes](releases/v0.2.24.md). Publication is determined by the matching remote Tag and non-draft Release. Change versions only on explicit user request; see [unified version rules](../AGENTS.md#unified-version).

## Release records
- [v0.2.23 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.23); [mapping table and notes](releases/v0.2.23.md)
- [v0.2.22 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.22); [mapping table and notes](releases/v0.2.22.md)
- [v0.2.21 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.21); [mapping table and notes](releases/v0.2.21.md)
- [v0.2.20 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.20); [mapping table and notes](releases/v0.2.20.md)
- [v0.2.19 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.19); [mapping table and notes](releases/v0.2.19.md)
- [v0.2.18 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.18); [mapping table and notes](releases/v0.2.18.md)
- [v0.2.17 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.17); [mapping table and notes](releases/v0.2.17.md)
- [v0.2.16 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.16); [mapping table and notes](releases/v0.2.16.md)
- [v0.2.15 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.15); [mapping table and notes](releases/v0.2.15.md)
- [v0.2.14 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.14); [mapping table and notes](releases/v0.2.14.md)
- [v0.2.13 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.13); [mapping table and notes](releases/v0.2.13.md)
- [v0.2.12 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.12); [mapping table and notes](releases/v0.2.12.md)
- [v0.2.11 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.11); [mapping table and notes](releases/v0.2.11.md)
- [v0.2.10 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.10); [mapping table and notes](releases/v0.2.10.md)
- [v0.2.9 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.9); [mapping table and notes](releases/v0.2.9.md)
- [v0.2.8 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.8); [mapping table and notes](releases/v0.2.8.md)
- [v0.2.7 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.7); [mapping table and notes](releases/v0.2.7.md)
- [v0.2.6 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.6); [mapping table and notes](releases/v0.2.6.md)
- [v0.2.5 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.5); [mapping table and notes](releases/v0.2.5.md)
- [v0.2.4 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.4); [mapping table and notes](releases/v0.2.4.md)
- [v0.2.3 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.3); its [original preparation document](releases/v0.2.3.md) preserves the state and historical mapping table at that time; the Release is authoritative for actual publication.
- [v0.2.1 mapping table and notes](releases/v0.2.1.md)
- [v0.2.0 mapping table and notes](releases/v0.2.0.md)
