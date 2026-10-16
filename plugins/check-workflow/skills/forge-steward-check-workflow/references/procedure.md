## Run the release audit and deletion independently

At startup, read [Release pipeline audit](release-audit.md) in full. First perform the authorized read-only audit and save each dimension's result, then follow the deletion flow below. For an explicit release-audit-only request, proceed to [Reporting](reporting.md) after the audit. Complete all possible audit checks before any zero-change exit; no deletion candidates is not a reason to skip them. Missing audit permissions, query failures, unknowns, and findings do not block deletion delivery. A deletion-check error stops its writes only; continue checking readable release evidence. Report the two separately. Do not fix or file audit findings or include them in the cleanup Change Request body. On cancellation, stop further queries and deletion writes and report completed coverage and unfinished items.

## Procedure

1. Locate the repository root, mainline, and workspace state. Record existing changes and preserve user work. Read the hosting platform's automatic post-merge source-branch deletion setting; record value, source, and time. If unreadable, record the permission, capability, or query failure without guessing. The setting does not replace per-merge remote-branch checks; disabled or unknown settings do not block document checks. In default delivery mode, refresh remote mainline and find an open Change Request from `forge-steward/remove-skill-duplicates`. If repository naming rules differ, choose a compliant fixed branch name and reuse it in later runs. Report any legacy open `forge-steward/workflow-block` request as superseded by this change; do not close it automatically.
2. Check legacy blocks against the latest mainline, where `<skill>` is this skill's directory:

   ```bash
   python3 <skill>/scripts/remove_workflow_blocks.py --repo <repository-root> --check
   ```

   - Exit `0`: no legacy blocks.
   - Exit `1`: blocks need deletion; output lists files and reasons.
   - Exit `2`: unmatched/nested markers, unclosed code fences, non-UTF-8 or non-regular files, etc. Report the reason and stop writing; do not guess a repair.
3. On the same mainline, read all candidate locations and compare each clause against the reference's policy catalog. Record file, line range, heading/first line, policy dimension and owning skill, equivalent skill clause, and action (section, clause, document, or reference deletion). Classify as “confirmed deletion” or “maintainer decision needed.” Handle clauses lacking equivalent skill semantics under the reference rules, separately recording a “skill gap” and retaining the original text. If there are no candidates, record the locations checked.
4. If step 2 exits `0` and step 3 confirms no deletions, finish without changes, branch, commit, or Change Request. Report any open request from step 1 as no longer needed; do not close it automatically. Still report undecided items.
5. If changes are needed, continue on the step-1 open request's branch and integrate latest mainline using repository policy (merge when force-push is forbidden). Otherwise create that branch from latest mainline. Run the same command with `--write` to remove blocks, then delete confirmed clauses under the reference rules. Finally run `--check`; it must exit `0`.
6. Inspect the diff: allow deletions only. For clause deletions, preserve every character outside the deleted clause; do not rewrite, combine, or reformat retained text. Leave no links, contents entries, or reading instructions to removed documents/sections, heading-only empty sections, or broken numbered lists. If preventing these requires rewriting retained content, undo that deletion and mark it undecided. Revert and report other changes.
7. Without Python 3, manually follow the script's exact block rules: delete start through end marker and the one resulting extra blank line. Markers in code fences are not blocks. If block-only deletion cannot be guaranteed, report without submitting.

## Submit and hand off

1. In default delivery mode, stage only this task's changed/deleted files. Commit and push under repository conventions, then create/update the Change Request targeting mainline; do not duplicate PRs/MRs. Follow repository title, body-language, and template rules.
2. Its body records skill version, check command and exit code; each deletion's file, original line range, heading/first line, policy dimension, owning skill, and method; undecided candidates and reasons; and a separate list of skill gaps with original text, owning skill, and missing semantics. Explain that deleted workflow constraints apply only when ForgeSteward skills are invoked and that maintainers may withdraw any deletion during review.
3. If creation/push responses are ambiguous, query the remote branch and same-source Change Requests before retrying. When permissions, authentication, network, or repository requirements block progress, preserve local commits/diffs and identify the exact stopping point: uncommitted, committed but not pushed, or pushed without a PR/MR.
4. Read back the actual Change Request link, base/head, and status. Do not wait for merging, review it yourself, or merge.
