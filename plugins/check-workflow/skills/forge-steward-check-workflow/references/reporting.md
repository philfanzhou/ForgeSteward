# Reporting and change summary

Use clear, everyday Chinese for final user replies/reports and questions requiring a user decision, unless the user explicitly requests another language. Internal handoffs and run records may stay in English. Hosting-platform content follows the owning repository's language rules, otherwise English. Report: mode, automatic post-merge source-branch deletion setting and evidence or reason it is unknown, check commands/exit codes, Change Request link or zero-change conclusion, undecided items, skill gaps, unfinished work, and next steps. A disabled setting alone creates no file changes or empty Change Request.

If this run changed any project file, including local-only changes or interrupted commit/push/creation, include a change summary. Use actual `git status` and `git diff` (against mainline after committing), not planned changes; omit no file:

| File | Action | Change | Lines |
| --- | --- | --- | --- |

- **Action:** modified or deleted.
- **Change:** identify removed blocks, sections, clauses, or references by heading/first line, original line range, policy dimension, and owning skill. List multiple actions within a file individually.
- **Lines:** added/deleted counts for that file, such as `+0 / -32`.

After the table, state the changes' actual status: uncommitted, committed (branch and commit), pushed, or created/updated Change Request link. List candidates awaiting maintainer decisions as unchanged. Keep this summary consistent with the Change Request body.

When no project file changed, explicitly state that no project files were changed. Translate this conclusion for the user; keep English in hosting-platform content unless the owning repository requires another language. In check-only mode, separately list files that deletion would change and why; clearly label them unchanged.

Claim only that confirmed workflow policy text and legacy blocks were removed. Do not claim that the project contains no remaining workflow constraints or that Agent runtime behavior changed.

## Report the release check separately

Separate release-check and deletion results. Use plain language such as “check” in the report. Under [Release pipeline audit](release-audit.md), list written contracts/baseline, query sources/times, scope/coverage, each dimension's conclusion and redacted evidence, findings, unknowns with reasons and recovery inputs, inapplicable checks, and unfinished work. One healthy conclusion must not conceal unknowns. Retain confirmed findings alongside unknown dimensions. On cancellation, state completed and remaining scope without treating cancellation as a pass.

Release findings appear only in this final report: do not create/update Issues, fix findings, or include them in the cleanup Change Request. Filing belongs to the user or a later independent prepare-work run. Create no empty branch, commit, or Change Request for findings. Audit-only runs must also state that no project files were changed in the user's display language, then list release conclusions and findings. The deletion table and delivery status describe actual project file changes only; retain deletion-only content in the cleanup Change Request body.
