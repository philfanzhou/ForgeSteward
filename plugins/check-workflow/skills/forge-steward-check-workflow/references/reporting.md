# Reporting and change summary

Report in the language specified by the target project, otherwise everyday English: mode, automatic post-merge source-branch deletion setting and evidence or reason it is unknown, check commands/exit codes, Change Request link or zero-change conclusion, deletions, migrations, language operations, and translations separately, the About result, undecided items, skill gaps, unfinished work, and next steps. A disabled setting alone creates no file changes or empty Change Request.

If this run changed any project file, including local-only changes or interrupted commit/push/creation, include a change summary. Use actual `git status` and `git diff` (against mainline after committing), not planned changes; omit no file:

| File | Action | Change | Lines |
| --- | --- | --- | --- |

- **Action:** modified or deleted.
- **Change:** for migration, name source/target and moved sections, omitted exact duplicates/effective imports, preserved bytes/targets, conflicts and retained sources with reasons. Include minimum Claude version/support conditions and import rollback from [Claude entry migration](agent-entrypoints.md) in both report and cleanup Change Request. For language changes, name the destination and missing coverage, quote exact replaced originals with source lines, identify preserved conventions, and list unresolved mixed/external conflicts and recovery input. Do not call additions/replacements deletions or claim full English coverage with unresolved conflicts. Separately identify removed blocks, sections, clauses, or references by heading/first line, original line range, policy dimension, and owning skill. List multiple actions within a file individually.
- **Translation:** for each translated file, name it, quote the exact before/after text and source lines for every replaced passage, and list translated sections, unchanged technical content, unresolved text, permission failures, skipped content, and recovery inputs. A file is translated only when all its prose is English. Keep the same per-file results in the cleanup Change Request body; never claim full-English coverage while unresolved prose remains.
- **About:** report the exact before and after values, the read and write results, the observation time, and whether the read-back verified the change. Report an unchanged About with the reason, and any missing permission, unsupported platform, ambiguous write, retained old value, or recovery input. An About change is external metadata, not a project file; never create a branch, commit, or Change Request only for About, and never claim a successful write without the read-back.
- **Lines:** added/deleted counts for that file, such as `+0 / -32`.

After the table, state the changes' actual status: uncommitted, committed (branch and commit), pushed, or created/updated Change Request link. List candidates awaiting maintainer decisions as unchanged. Keep this summary consistent with the Change Request body.

When no project file changed, explicitly say “No project files were changed” and report the About result. In check-only and release-audit-only modes, separately list files that deletion, migration, translation or language work would change and why; clearly label them unchanged.

Claim only verified policy removals, entry migrations, language operations, and translations, and About writes verified by read-back. Distinguish planned, completed, and incomplete append/delete pairs after interruption; preserve completed authorized work and report recovery for incomplete pairs. Do not claim that the project contains no remaining workflow constraints or that Agent runtime behavior changed or hosting-platform enforcement was enabled.

## Report the release check separately

Separate release-check and deletion results. Use plain language such as “check” in the report. Under [Release pipeline audit](release-audit.md), list written contracts/baseline, query sources/times, scope/coverage, each dimension's conclusion and redacted evidence, findings, unknowns with reasons and recovery inputs, inapplicable checks, and unfinished work. One healthy conclusion must not conceal unknowns. Retain confirmed findings alongside unknown dimensions. On cancellation, state completed and remaining scope without treating cancellation as a pass.

Release findings appear only in this final report: do not create/update Issues, fix findings, or include them in the cleanup Change Request. Filing belongs to the user or a later independent prepare-work run. Create no empty branch, commit, or Change Request for findings. `release-audit-only` and other audit-only runs must also say “No project files were changed,” then list release conclusions and findings. The deletion table and delivery status describe actual project file changes only; keep cleanup deletions, migrations, translations, and language changes and their verification, plus the About result and verification, in the cleanup Change Request body.
