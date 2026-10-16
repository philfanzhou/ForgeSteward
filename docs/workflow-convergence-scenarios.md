# Workflow convergence acceptance scenarios

This is a historical walkthrough from the `0.1.1` revision. “Current rules” in the table means the rules at that time. Current `prepare-work` and `execute-work` replaced `find-work` and its execution prompt. Use the [new scenario matrix](prepare-execute-scenarios.md) for current preparation/execution acceptance; S11's investigation-prompt exit no longer applies.

## Scope and method

That revision addressed mainline scheduling, cross-repository execution, review-state handoffs, and closure across repeated uses of three Skills. All three remained independently installable and moved from `0.1.0` to `0.1.1`, without a runtime, scheduler Skill, or cross-plugin file dependency. Each retained the handoff fields needed for independent use; shared-field changes required checking all three bodies.

The following is a manual walkthrough of limited inputs, deriving allowed actions, results, and stop conditions from the rules then current. It did not modify example repositories or constitute real multi-Agent/multi-round testing. Skill format validation proves only format validity, not Agent compliance. For unexpected real behavior, preserve input, Skill version, output, and state differences before revising the specific gap.

## Scenario matrix

| ID | Input and trigger | Required result and stop condition | Rule basis at the time and walkthrough result |
| --- | --- | --- | --- |
| S01 | Old mainline A is design-blocked, small independent B ready; a minimal experiment can decide A | Advance A's experiment first rather than selecting only B. If it resolves the blocker and other conditions hold, select A/B this round; discovery still does not implement | `find-work`'s mainline-blocker rule investigates then rechecks ready; matched |
| S02 | A awaits external access with a concrete request, responsible role, and unblock condition; unchanged next round, B independent | Do not repeat experiments or unactionable loops; hand off the external request, select B if appropriate, preserve A's remaining scope | `find-work` mainline investigation and zero-item paths provide external-wait exits; matched |
| S03 | `owner/library#71` is implemented in `owner/product`; another task belongs in library | Output full links, actual implementation repositories, main branches, and audits per item. Check open changes in both, open separate PRs, backlink original Issues without duplication | `find-work` baseline/output/execution template carry ownership; review/fix keep reading original tasks; matched |
| S04 | Limit 10, ten independent ready items; item 2 has an unresolved environment blocker, item 1's PR submitted | Preserve all ten, not three; record item 2 and continue 3–10. End only when each is submitted or concretely blocked; no merge or stacking unmerged code | Count rules/execution template preserve full batches and continuation; matched |
| S05 | Previous session recorded two reviews and accepted non-guarantees; head unchanged, no writable repository record location | Restore rounds/boundaries from handoff, never reset or reopen identical suggestions; output a complete updated handoff without automatically posting comments/creating trackers; mark missing facts unknown | All three handoff fields align and include output fallback; review/fix prohibit recounting; matched |
| S06 | PR has one clearly out-of-scope suggestion, no repository review budget, acceptance/platform conditions met | fix decides no code change needed; review does not block on the suggestion and delivers if merge is authorized | review/fix classify feedback and default to no implementation requirement without a budget; matched |
| S07 | Scope is disputed, or no code change is needed but a valid changes-requested approval remains | Record disagreement, decision owner, unblock condition/platform requirement; do not expand code, revoke approval, or falsely report mergeability; hand off and continue | review/fix separate required code, external decisions, and platform restrictions; matched |
| S08 | Complete starting audit; new main changes unrelated docs. Comparison case changes a relevant contract or lacks original evidence | Reuse the first audit; inspect relevant complete members/tests/contracts in the second. Revalidate actual implementation; old green checks are not new acceptance | `find-work` baseline item 4; review checks base/head and fix relevant changes; matched |
| S09 | Product PR merged but original library task remains open; direct parent has an unfinished child | Verify remote merge and original acceptance, close when authorized/permitted or hand off. Keep parent open, record remaining work, and stop upward traversal | review-and-merge post-merge closure verifies cross-repository state and only ascends after direct parent completion; matched |
| S10 | Cleanup cycle began with 5 tasks; 1 delivered, 2 newly discovered, 1 parent closed | Count 1 original task done and 4 remaining; count 2 new and 1 parent closure separately. Next round inherits the cycle; split tasks retain undelivered scope in the goal | All three preserve baseline/remainder and prohibit treating new work, splitting, migration, or parent closure as delivery; matched |
| S11 | No ready items: possible investigation, external waits only, or all tasks complete | Historically return, respectively, an investigation prompt with stop conditions, a concrete external handoff, or completion facts; no empty-ID implementation template or invented mainline | `find-work` no-ready rules covered all three exits; matched |
| S12 | Original acceptance omission found in a closed task; another finding concerns an accepted non-guarantee with no new evidence | Backlink original task/PR and omission as rework; do not reregister the accepted non-guarantee as a bug. Handle real serious risk by impact with recovery conditions | All three classify/report rework, independent defects, optional advice, and serious risk separately; matched |

## Verification record

- Each of the three Skills passed `skill-creator/scripts/quick_validate.py` format validation.
- All JSON manifests parsed; each plugin's three manifests agreed on names/versions; marketplace source and declared Skill paths existed. Shared handoff fields were manually compared across all three.
- `git diff --check` checked whitespace, and the 12 limited scenarios above were compared manually. No cross-Agent behavior evaluation or installation into the three Agents was performed to verify runtime compatibility.

## Main-branch protection

On 2026-09-13 an active GitHub ruleset was created and reread through the API:

- [Require pull requests on default branch](https://github.com/philfanzhou/ForgeSteward/rules/23147476) covers `main` and the default branch, requires Pull Requests, and prohibits force pushes and deletion.
- Bypass list is empty; the API returned `current_user_can_bypass: never`. Administrators were not listed as bypass actors.
- `GET /repos/philfanzhou/ForgeSteward/rules/branches/main` returned active `pull_request`, `non_fast_forward`, and `deletion` rules.
- No extra approval counts or nonexistent CI requirements were configured; that work required PR delivery only. No test commit was pushed to main, and that PR was not merged during the check.

Remote rules constrain main-branch updates; `AGENTS.md` governs local commit discipline. Local files are not server-side protection. Maintainers with rules-management access can still change configuration; this record does not promise resistance to future deliberate disabling.
