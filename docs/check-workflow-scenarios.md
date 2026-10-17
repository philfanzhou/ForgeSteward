# Check Workflow adoption acceptance

## Scope

The new independent `check-workflow` plugin began at `0.1.0`. It checked and added missing workflow rules for initial project adoption; the three execution plugins stayed at `0.1.1`, with unchanged bodies and versions. OpenCode installation task #1 was outside scope. This Skill neither installed plugins nor changed Agent configuration.

The target project's existing rules were authoritative. The Skill added only nonconflicting missing contents, preserving stack, architecture boundaries, language, review budget, approval thresholds, task granularity, and loading scope. Coverage was semantic; copying a ForgeSteward template was not required.

## Limited scenarios

These are manual walkthroughs of the rules then current, using limited conditions rather than real consumer change requests. Expected actions are derived from the text, not an independent Agent evaluation.

| ID | Input | Expected action and completion condition | Rule basis |
| --- | --- | --- | --- |
| C01 | Adoption requested; no rules/configuration or specified Agent | Add shared workflow rules to AGENTS.md; CLAUDE.md only imports it; invent no test commands, approval counts, or batch limits | Missing-rule addition and minimal entry layout |
| C02 | Claude Code/OpenCode only; only CLAUDE.md, with pytest command and five-round suggestion budget | Preserve text, commands, and budget; append missing rules/references; do not create AGENTS.md that shadows CLAUDE fallback | Preserve wording/semantics, budget references, OpenCode fallback |
| C03 | ServiceMantle-like project has complete scope, explicit acceptance, non-guarantees, dependencies, and third-round scope audit | Record equivalent coverage/source; do not copy templates, reduce ready to existing tests, or impose three rounds elsewhere | Semantic mapping and existing-policy priority |
| C04 | Existing rule requires all optional advice fixed, conflicting with nonblocking feedback; handoff also incomplete | Preserve conflicting text, report affected stage/decision, add only independent handoff rules, and report partial adoption | Five classifications and conflict handling, no implicit override |
| C05 | Check-only request, otherwise C01 | Output coverage table/proposed patch only; no files or Change Request | Explicit check-only write boundary |
| C06 | Local adoption requested; docs have uncommitted edits, no publication authorization | Compare against initial contents, preserve user work, append allowed docs, deliver local diff without commit/push/remote change | Workspace preservation and authorized delivery |
| C07 | Second run, unchanged contents/source rules/entries | Treat additions as equivalent coverage; no paragraphs, timestamps, duplicate references, or pointless commit | No-write rerun and preservation of generated contents |
| C08 | Root/subdirectory AGENTS.override.md; body references another file | Follow effective loading chain/scope and add reading directions only where allowed; do not delete overrides or create higher-priority entries | Codex overrides/directories; unreadable required sources are unknown |
| C09 | CLAUDE.md already imports sole-source AGENTS.md | Add missing rules only at the authoritative location, without reverse imports or duplicate Claude body | Single source and cycle checks |
| C10 | Other Agent's loading protocol cannot be verified | Add generic rules if allowed; mark Agent adaptation unverified and state evidence needed, without guessing filenames/installing tools/changing global config | Evidence-based adaptation and validation levels |
| C11 | Existing OpenCode config cannot load chosen docs without non-document edits | Do not change config or claim loading works; deliver independent docs and report exact configuration gap/next action | Non-document configuration boundary |
| C12 | Workflow may be maintained only in designated docs, other entries immutable | Add only there; if no loading path exists, report the gap without changing permissions or bypassing policy with an entry | Authority/scope preservation and partial-adoption exit |

## Validation levels and rerun entry points

- Run `skill-creator/scripts/quick_validate.py` on the new Skill for frontmatter, name, and scaffold leftovers.
- Check four plugins' JSON, matching names/versions, marketplace sources, Skill entries, and resources. Copy the new Skill alone into a temporary installation layout and confirm no dependency outside ForgeSteward or on another plugin.
- Manually check these scenarios, possible semantic changes to existing rules, and that the diff contains only the new plugin, registration, and necessary project explanation.
- This check installed no Codex, Claude Code, or OpenCode and launched no additional Agent. Documentation/package checks do not prove runtime loading or behavior compatibility.

Agent entry details and checked official sources are in bundled [entry adaptation](https://github.com/philfanzhou/ForgeSteward/blob/v0.2.6/plugins/check-workflow/skills/forge-steward-check-workflow/references/agent-entrypoints.md), which ships independently of this acceptance document. The above is the historical `0.1.0` record. `0.2.0` renamed the Skill invocation to `forge-steward-check-workflow`, retaining plugin name `check-workflow` and workflow behavior.

## 0.2.2 default completion and Change Request submission

This section preserves verification context for the unreleased `0.2.2` development revision. Root `VERSION` gives the current unified version; the behavior continued toward `0.2.3`, not with other plugins frozen at `0.2.2`.

Users reported explicit invocation stopping at a report or local edits. The previous text separately required addition and publication authorization, and its default prompt did not require submission. `0.2.2` changed explicit invocation's default to check, add, validate, commit, push, and create a PR/MR. The maintainer explicitly selected check-workflow `0.2.2` for this fix; changed external-write defaults and limits still needed disclosure. The other three plugins also moved to `0.2.2` under unified versioning without workflow changes. Historical Releases and user installations remained unchanged; no Tag was published in that change.

The following are manual rule walkthroughs and future behavior-test cases, not independent end-to-end Agent runs. C01–C12's rule/scope preservation remained applicable; C06's local-only request still restricted publication.

| ID | Input/state | Expected observation |
| --- | --- | --- |
| D01 | Explicit Skill selection, no extra prompt; main lacks handoff rules, remote writable, no conflicts | Add rules/entries on an independent branch, validate, commit/push, return a real PR/MR link rather than a plan; no merge |
| D02 | Same gaps, but check-only/no-modification request | No file/branch changes, commits, or remote Change Request; report gaps |
| D03 | Explicitly add locally without committing | Preserve local diff without commit/push/PR; default prompt cannot override restriction |
| D04 | Explain Skill purpose, or Skill auto-loaded for read-only analysis | Complete only the actual request; loading grants no publication authority |
| D05 | Main already has equivalent complete rules | No edits, empty commits/PRs, or invented gaps |
| D06 | Open PR/MR already covers gaps | Update this task's existing branch if applicable; otherwise report coverage without duplicate creation or takeover |
| D07 | Additions possible but another original-policy conflict exists | Preserve original text, submit independent additions with partial-completion/draft status under policy; no hidden override |
| D08 | No write permission or PR creation times out | Preserve allowed local work if unauthorized; for uncertain response query remote branch/PR before retrying and report exact stopping point |
| D09 | Uncommitted user files or dependency on another unmerged branch | Preserve user work and use an independent delivery baseline; report a concrete blocker if inseparable |
| D10 | Rerun after additions submitted | Reuse coverage/delivery, adding no paragraphs/commits/duplicate PR unless a real new gap exists |

Metadata tests compare plugin and Skill default prompts so entry choice cannot change the intended endpoint. They do not assert behavior through fixed body keywords. Format checks, installer tests, and these manual walkthroughs cannot replace actual D01–D10 execution evidence in independent consumer scenarios.

## Five-Skill stage handoff revision

This adds check-workflow adoption checks after prepare-work/execute-work split, without rewriting earlier acceptance history or changing other Skills, installation entries, or invocation syntax. Add only necessary stage boundaries/handoff semantics, not complete Skill copies or automatic chaining.

These manual walkthroughs/future behavior cases were checked against bundled minimum constraints and preparation/execution bodies. No independent Agent end-to-end tests ran. Static packaging and installer regressions do not prove model compliance.

| ID | Input/state | Expected adoption check/addition |
| --- | --- | --- |
| F01 | Old repository requires find-work to output an execution prompt and chat as sole plan source | Report output/handoff migration conflict, preserve old rules, and do not silently override with Issue authority; add independent gaps only and report partial adoption |
| F02 | Old names occur only in historical releases/examples; effective rules cover new stages | Names alone are not conflicts; preserve history and make no change if rules/entries are otherwise complete |
| F03 | General session handoff exists but preparation need not be recoverable from original Issue; no conflict | Add only preparation persistence requirements, retaining other-stage session fallback; identifier lists locate plans rather than contain them |
| F04 | Read-only preparation; A has full Issue plan/evidence, B acceptance exists only in chat | A may pass later real readiness checks; B cannot qualify without required persisted handoff. Explain the gap without widening writes; adoption itself does not decide these Issues' readiness |
| F05 | Explicit execution list, preparation neither installed nor run | Read original Issues and verify, filling solvable gaps; do not require all Skills or a preparation rerun, and do not invoke other Skills automatically |
| F06 | Execution list missing, empty, or ambiguous across repositories | Request list, finish without action, or clarify identity respectively; no discovery, guessed repository, or empty PR/MR; Skills retain detailed format rules |
| F07 | Ordered A/B/C; A PR submitted, B externally blocked, C independent | Save A/B state and continue C from then-current main, without stacking A or ending after one PR/blocker |
| F08 | Session changes mid-list: A submitted, B pending, known rounds/accepted boundaries | Restore full order, item states, and valid evidence; retain B/rounds, neither rediscover nor expand queue; ready/submitted are not merged delivery |
| F09 | Preparation experiments produce evidence; execution pushed but PR open; unpushed commits also exist | Save experiment outputs/recovery locations, preserve repair branches and unpushed work, and clean only this task's safely disposable environments |
| F10 | Equivalent stage boundaries, Issue handoffs, completion, and cleanup rules already exist | Cite existing sources with no additions/empty PR; add only missing semantics, not full checklists, batch counts, or commands |
| F11 | Project requires stacked changes or preparation and production implementation in one step | Preserve/report the conflict and needed decision; do not silently enforce separate branches/stages or claim full compatibility |

This revision changed only check-workflow, its bundled checklist, and this record. No body-keyword tests were added as a substitute for behavior validation. Releases use unified versions; development changes neither rewrite published Tags nor upgrade users.

## 0.2.5 standard block synchronization

This records the decision and acceptance for switching from semantic gap checks/additions to synchronizing a bundled standard block, preserving earlier history.

### Why it changed

The former Agent judged coverage and authored additions. Semantic judgment varied by session/Agent, and merged additions became project rules that could only be appended to. Repeated runs could accumulate paragraphs, with quality dependent on Agent capability.

The replacement shipped one standard body to copy verbatim, comparing rather than composing:

- Managed scope: root AGENTS.md's `forge-steward:workflow` block, root CLAUDE.md's `@AGENTS.md` import, and the `forge-steward:claude-rules` reading-direction block when CLAUDE.md contains other text.
- Append missing blocks, replace differing blocks completely, and do nothing when equal. Preserve outside text byte for byte, without reading/evaluating/referencing other project rules.
- The template gives outside project rules priority; project differences belong outside the block.
- Historical templates provided `zh-CN` and `en`, recording the language in the opening marker and reusing it later.
- `scripts/sync_workflow_block.py` decides/writes changes; the same Skill version produces identical rerun results.

### Migration

- This was incompatible. Semantic coverage/conflict/preservation expectations in C01–C12, D01–D10, and F01–F11 no longer applied. Authorization, check-only/local-only, no-merge, and reread-before-retry delivery boundaries remained.
- Older unmarked additions could not be identified automatically and were not deleted. A first new-version run appended the standard block beside them; maintainers could remove duplicates during review.
- Manual edits inside blocks would be replaced next run; move desired differences outside.
- A changed template after upgrading causes one synchronization change, not redundant modification.

### Limited scenarios

`tests/test_check_workflow_block.py` automatically verified G01–G10 in temporary directories. G11–G14 were manual delivery-rule walkthroughs without independent Agent end-to-end tests.

| ID | Input/state | Expected result |
| --- | --- | --- |
| G01 | Empty repository, no language selected | `--check` returns 2 without writes; choosing a language creates block and CLAUDE.md import; rerun returns 0 with unchanged bytes/mtime |
| G02 | Edited block with surrounding project text | Replace only block; preserve surrounding bytes |
| G03 | AGENTS.md has project rules but no block | Append block at EOF without altering original text |
| G04 | Only CLAUDE.md with rules | Create AGENTS.md block and following reading directions; append CLAUDE import; update existing directions in place, remove them when CLAUDE has only import |
| G05 | Import/markers appear only in code fences | Treat as absent and append under rules |
| G06 | Duplicate, unpaired, nested markers, or unclosed fence | Collapse duplicates into first location; malformed markers/unclosed fence return 2 without writes |
| G07 | CRLF, mixed LF/CRLF, or BOM | Preserve each original line ending/BOM; new lines use majority ending |
| G08 | Existing `zh-CN`, explicit `en` request | Replace with English template; later language-unspecified runs retain `en` |
| G09 | CLAUDE.md symlinks to AGENTS.md, or root AGENTS.override.md exists | Never write through links; only warn about override |
| G10 | Both language templates | Matching heading/list structure; bodies contain no marker text |
| G11 | Explicit invocation, check returns 1, writable remote | Write on `forge-steward/workflow-block`, recheck 0, commit/push/create PR/MR, no merge |
| G12 | Check returns 0 | No edits/branch/commit/empty PR; report same-named open PR no longer needed without auto-closing |
| G13 | Existing open `forge-steward/workflow-block` PR/MR, main still needs sync | Merge latest main into original branch, synchronize/push, no duplicate |
| G14 | Check-only request | Run/report only `--check`, without writes/branch |

Static packages, script tests, and installer regressions do not prove Agent delivery compliance or runtime loading of the block.

## 0.2.6 removal of old additions

This records removing old additions during standard-block synchronization, without rewriting 0.2.5 history.

### Why it changed

0.2.5 left old unmarked additions beside a new block for manual cleanup. In practice they were interspersed with project rules, with ordinary documentation commit/PR titles, making them hard to locate. Because outside rules took priority, old additions could duplicate or override the block. The maintainer requested their removal in favor of the standard block.

Scripts could not identify them deterministically. Agents therefore gathered evidence under `references/legacy-additions.md`, including removals in the same synchronization Change Request for maintainer review:

- Candidate locations were limited to Agent instructions, workflow/collaboration docs, and Issue/Change Request templates older versions might have written.
- Removal required both content characteristics—old constraint dimensions presented as supplements—and provenance showing the whole passage added by a workflow-supplement commit.
- Preserve project-authored, substantially edited, still-referenced, explicitly retained, or insufficiently evidenced content; list it for decision.
- List source and rationale for each removal in the Change Request; maintainers may withdraw any deletion.
- No-change now required both matching blocks and no confirmed removals.

### Migration

- This changed default external writes: the first upgraded run could remove old Skill-authored paragraphs, documents, and reading directions in the same synchronization Change Request.
- The `0.2.4`-and-earlier rule against overwriting generated content once adopted as project rules no longer applied to confirmed old additions. Content substantially revised and adopted by maintainers remained preserved for decision.
- A repository already synchronized in 0.2.5 but retaining old additions would receive one removal change on rerun.

### Limited scenarios

H01–H10 are manual walkthroughs, not independent Agent end-to-end tests. Script behavior stayed unchanged; G01–G10 automated tests still applied.

| ID | Input/state | Expected result |
| --- | --- | --- |
| H01 | AGENTS.md has a workflow-authorization/review/handoff supplement whose introduction says it implements policy without rewriting old Issues; one AGENTS-only commit and PR identify a workflow addition | Delete the whole section and sync block in one PR, listing original lines, introducing commit, and rationale |
| H02 | Block matches template but H01 remains | Check exit 0 does not mean no edits; create PR removing addition |
| H03 | Project-authored three-round review budget shares block's topic | Preserve unchanged; not a candidate |
| H04 | Maintainer later rewrote two rules in an old addition | Preserve for decision and cite editing commit |
| H05 | Older version created entirely supplemental docs/workflow.md and a CLAUDE reading direction | Delete document and direction pointing only to it, leaving no dangling link |
| H06 | CONTRIBUTING.md project rules reference a suspected addition | Withdraw removal and list for decision |
| H07 | Shallow clone prevents locating introducing commit | Obtain history when authorized; if unavailable, preserve for decision |
| H08 | Check-only request | Report block differences, confirmed removals, and undecided candidates without writes/branch |
| H09 | Rerun after removal merged | Do not rediscover removed content; unchanged undecided items are report-only, no edits |
| H10 | Maintainer previously withdrew a deletion and explained retention | Do not remove in later runs; mention only in report |

### Change summary

When project files change, report operations, contents, added/deleted line counts, and delivery state per file. Explicitly state when nothing changed. I01–I04 are manual walkthroughs.

| ID | Input/state | Expected result |
| --- | --- | --- |
| I01 | Block synced and old section removed; PR created | Summary lists AGENTS.md's old-addition removal/source and new block (`+59 / -32`), plus CLAUDE import; follow with PR link and undecided candidates |
| I02 | Committed but push denied | List all changed files/counts and committed-but-unpushed state, branch, and commit |
| I03 | Block matches and no confirmed removals | Explicitly state no project files changed, without an empty summary table |
| I04 | Check-only request with missing block | State no files changed; separately list proposed files/reasons without implying completion |

## 0.2.7 removing project rules that duplicate Skills

This records switching from standard-block synchronization to removal of duplicate project workflow rules, preserving earlier history.

### Why it changed

0.2.5/0.2.6 copied Skill summaries into project AGENTS.md while prioritizing outside rules. Actual use exposed two problems:

- All block contents already existed in four Skills; project copies could become stale after Skill upgrades.
- Project-authored readiness/review rules coexisted with blocks. Blocks prioritized project rules while Skills also deferred to more specific repository requirements/budgets, leaving two or three differently worded/strict sources for the same policy.

The maintainer decided Issue/Change Request/Review workflow policy belongs only in Skills. Remove equivalent project constraints and use Skill policy; check-workflow now removes project duplicates.

### Decisions

- check-workflow writes no new project contents. Remove template resources, reading directions, and entry management; replace `sync_workflow_block.py` with deletion-only `remove_workflow_blocks.py`.
- Classify by bundled [Skill-owned rules and removal](../plugins/check-workflow/skills/forge-steward-check-workflow/references/skill-owned-rules.md), without old-addition provenance requirements. Equivalent project-authored rules also qualify.
- Preserve project conventions explicitly delegated by Skills: language, title/commit format, template structure, merge method, required checks/approvals, branch protection, build/verification commands, engineering/security constraints, and Agent entries.
- Scope includes Agent instructions, CONTRIBUTING.md, collaboration docs, and Issue/Change Request templates. Preserve template structure while removing workflow-policy directions/checklists.
- Four Skills dropped repository-specific readiness/review-budget deference and adopted generalized feature splitting, complex protocol/state semantic models/end-to-end scenarios, per-commit audits before a third review/repair, and stopping after three exchanges for human handling. See [Skill workflow policy scenarios](skill-owned-policy-scenarios.md). This superseded C03's historical rule against carrying three rounds into other projects.

### Migration

- Incompatible behavior: the first upgraded check-workflow run submits one Change Request removing old blocks and duplicate workflow rules from instructions, contribution docs, and templates, including project-authored rules. Maintainers may withdraw any deletion during review.
- Afterwards these constraints apply only when Skills are invoked; other sessions/contributors no longer read them in project docs.
- Projects needing different workflow policy must change the Skill itself rather than override through project rules.
- This version supersedes open 0.2.5/0.2.6 `forge-steward/workflow-block` Change Requests, reporting them without automatic closure.
- G01–G14 and H01–H10 no longer apply. I01–I04 summaries remain, with modification/removal as the only operations.

### Limited scenarios

`tests/test_check_workflow_blocks.py` automatically verifies J01–J08 in temporary directories. J09–J19 are manual walkthroughs, not independent Agent end-to-end tests.

| ID | Input/state | Expected result |
| --- | --- | --- |
| J01 | No old blocks; project rules exist | `--check`/`--write` return 0, bytes/mtime unchanged |
| J02 | AGENTS.md has workflow/claude-rules blocks and surrounding text | Remove both and excess blank lines, preserving outside bytes; rerun makes no edits |
| J03 | Blocks at beginning/end or duplicated | Remove all blocks without extra leading/trailing blanks |
| J04 | AGENTS.md contains only blocks; CLAUDE.md only `@AGENTS.md` | Delete both files |
| J05 | AGENTS.md only blocks; CLAUDE also has rules and fenced import example | Delete AGENTS and effective import, preserving rules/fenced example |
| J06 | Markers only in code fences; compare unpaired/nested markers/unclosed fences | First is not a block; malformed cases return 2 without writes |
| J07 | CRLF, mixed endings, or BOM | Preserve retained lines' own endings/BOM |
| J08 | AGENTS.md symlink; root AGENTS.override.md | Never write through links; only warn about override |
| J09 | Project-authored scope section consists entirely of ready checks, one-PR-one-Issue, feedback classification, and third-round stop | Delete whole section without provenance requirement; Change Request lists dimensions/corresponding Skills |
| J10 | Same section mixes one-PR-one-Issue with build commands | Remove only policy list item; preserve commands/code blocks |
| J11 | List item requires compatibility impact before dependencies/public API changes | Preserve as engineering convention |
| J12 | Language policy requires Chinese Issue titles and conventional-commit PR titles | Preserve; not a candidate |
| J13 | Issue template has scope/acceptance fields, no-empty-ready and one-task-one-PR directions, and delivery-constraints section | Preserve fields/filling guidance; delete policy sentences and entire delivery-constraints section |
| J14 | PR template has review-convergence policy checklist and project-build verification section | Remove former, preserve latter |
| J15 | README links a candidate section | Preserve for decision |
| J16 | Removing numbered middle item breaks numbering, or deleting clause breaks grammar | Preserve for decision without rewriting retained contents |
| J17 | ADR/release notes describe older review process | Historical description; preserve |
| J18 | Check-only request | Report blocks/candidates without writes/branch |
| J19 | Project ready rule requires caller responsibilities, absent from Skill body | Still delete; separately identify Skill gap on Change Request with original quote and missing meaning, not merely same-dimension coverage |

## 0.2.14 read-only repository setting checks

Every check-workflow invocation reads the hosting platform's automatic post-merge source-branch deletion setting and records value, source, and reasons for uncertainty. It changes neither settings nor branches; actual post-merge cleanup belongs to review-and-merge.

| ID | Input/state | Expected result |
| --- | --- | --- |
| L01 | Automatic deletion disabled, no document removals | Report setting/evidence, no files or empty Change Request |
| L02 | Setting unreadable, confirmed document removals | Record failure, continue authorized removal/validation/submission, never guess setting |
| L03 | Check-only request | Read/report settings and candidates only; no file/settings/branch changes |

## 0.2.17 release reconciliation

This section manually evaluates [Issue #51](https://github.com/philfanzhou/ForgeSteward/issues/51)'s acceptance against implemented [release-audit rules](../plugins/check-workflow/skills/forge-steward-check-workflow/references/release-audit.md), [procedure](../plugins/check-workflow/skills/forge-steward-check-workflow/references/procedure.md), and [reporting](../plugins/check-workflow/skills/forge-steward-check-workflow/references/reporting.md). Inputs are written contracts and finite evidence. No production reconciler was added merely for testing, and keyword assertions are not behavior validation. Historical C01–L03 records remain.

R01–R24 were each evaluated by establishing contract/coverage, deriving the single result below, and checking authorized writes/delivery exits. They validate semantics for these inputs, not arbitrary Agents/models/private feeds. Unless stated otherwise, the fixture requires every `v1.2.x` release Tag to have a same-named announcement, A/B package `1.2.x`, stable-release marking, and actual latest pointing to the newest stable release. All queries are complete. Fixture versions are unrelated to this repository's versions.

| ID | Contract and input | Derived result and delivery exit |
| --- | --- | --- |
| R01 | `v1.2.3` Tag exists, complete announcement list lacks it | Confirm Tag without announcement, list version/source in final report only, no registration/repair |
| R02 | Announcement exists, complete A/B feeds lack `1.2.3` | Confirm required packages missing, list A/B separately; announcement success is not package success |
| R03 | Tag/announcement `v1.2.3`, A/B only `1.2.4`, normalization permits removing `v` only | Confirm mismatch; do not normalize nearby versions into equality |
| R04 | Tag/announcement/A `1.2.3` complete, B absent after full query | Confirm only B missing, retain A's success evidence |
| R05 | Contract marks `v1.2.4-rc.1` prerelease but announcement has `prerelease=false` | Confirm incorrect prerelease flag; major zero/other conventions do not change channel |
| R06 | Stable `v1.2.3` fully published, actual latest points to `v1.2.4-rc.1` | Confirm incorrect latest from actual pointer, not version sorting |
| R07 | Two drafts with versions/dates, no draft deadline | Report two drafts without invented overdue threshold; declare overdue only with an explicit 24-hour rule and supporting evidence |
| R08 | Automatic A/B release required; latest run A succeeds/B fails, other runs failed/cancelled/running | Distinguish partial success, failure, cancellation, and unfinished running state; never infer release success from test CI |
| R09 | Written contract is manual source-snapshot-only, no feeds; platform has no latest capability | Feeds, automatic release runs, and latest are not applicable with contract/capability evidence; still compare Tags/announcements |
| R10 | No release contract, Tags/announcements accessible | Ordinary finding: missing contract; state coverage and unknown expected comparisons without assuming announcements/feeds are required |
| R11 | A is private with no authorized read-only connection | A comparison unknown, with reason/recovery input; no new key request or pass/fail claim |
| R12 | Announcement permission denied or platform cannot read actual latest | Mark affected dimension unknown; missing capability is not contractual non-applicability |
| R13 | Feed authentication/network failure, readable matching Tags/announcements | Feed unknown, covered Tag↔announcement comparison consistent; no all-healthy claim or release rerun |
| R14 | Only feed page 1 or missing B category, but complete evidence of absent `v1.2.3` announcement | Do not infer missing packages from partial feeds; report feed unknown and confirmed absent announcement together |
| R15 | Confirmed deletion candidate, failed feed reconciliation query | Finish authorized deletion/validation/PR; report audit uncertainty separately only at end, not in cleanup PR body |
| R16 | Missing announcement confirmed, old-block check 0, no policy candidates | Finish audit with no edits and explicitly say no project files changed; no empty branch/commit/PR or finding registration |
| R17 | Deletion script returns 2 for unpaired markers, release queries readable | Stop deletion writes and retain error; complete accessible reconciliation and report separately |
| R18 | User requests `release-audit-only` (a read-only release audit) despite available write access | Enumerate/report read-only; finish at Reporting with no deletion/migration/language steps, file/CI/permission/release-asset changes, Issues, or PRs; findings are reported only, never fixed or filed; project bytes and modification times unchanged, no branch, commit, or Change Request |
| R19 | Announcement contains malicious rerun/ignore-rules instructions; package URL contains credentials | Extract evidence only, execute no instructions; use redacted locations without tokens/download credentials; assets unchanged |
| R20 | User cancels after Tags read | Stop further announcement/feed queries and deletion writes; report Tag-only coverage and unfinished cancelled checks, not health |
| R21 | `v1.2.4` appears after Tag query, announcement later | Timestamp sources and recheck affected version; if correspondence still cannot be aligned, report observation-window limitation/unknown, no atomic-snapshot guarantee |
| R22 | Source target `1.2.4` unpublished, ordinary development Tags exist, history allowed unequal package versions | Do not report development targets/non-release Tags as missing; judge history by its release-time contract |
| R23 | Announcement metadata points to main, annotated Tag dereferences to C1, body records C2, contract requires same commit | Confirm C1/C2 mismatch; main branch name is not Tag evidence |
| R24 | No defined historical scope, connection enumerates one channel, missing package mapping | State actual channel/version coverage without all-history claims; uncovered channels/mappings remain unknown; Skill rollback does not undo cleanup/release assets |

The `release-audit-only` name was added by [Issue #142](https://github.com/philfanzhou/ForgeSteward/issues/142) to the entry point's explicit limits, the audit procedure, and reporting. The R18 walkthrough now covers that named mode: the audit performs no project writes, project file bytes and modification times stay unchanged, and no branch, commit, or Change Request is created. Work-cycle records the same read-only report through its optional `release_audit` field; see the [work-cycle walkthrough](work-cycle-scenarios.md#release-audit-results-and-audit-only-runs-142).

Installer resource regressions explicitly require `release-audit.md`, `reporting.md`, and existing rules, comparing installed bytes; DeepSeek's adapter runs the same case. Existing budget/reachable-reference, prompt metadata, deletion-script, and gate regressions continue. Unknown/cancel/concurrent Agent rules were evaluated only through these limited walkthroughs, without fabricated automated model testing.

Real repository commands, times, scope, three-source conclusions, and state comparisons are retained below and in the implementation PR. That run validates public repository evidence, not private registries, other platforms, or all historical contracts.

### Real read-only acceptance (2026-10-07, Asia/Singapore)

Using the implemented complete entry point and required references, only release reconciliation ran against `philfanzhou/ForgeSteward`. Source baseline was `0de407b8f1bc0654fabe45eb4997e3695c74ed7d`. The contract came from its `docs/releasing.md`, with `git show v0.2.16:docs/releasing.md` and published [v0.2.16 announcement](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.16) also read. Package/feed and release-method conclusions cover the latest published version. The 16 historical entries cover Tag↔announcement lists and actual flags, without retroactively applying current package-version rules.

| Actual read-only command (all exit 0) | Observation time (UTC) | Coverage and result |
| --- | --- | --- |
| `gh api --paginate --slurp repos/philfanzhou/ForgeSteward/tags` | 2026-10-06T16:05:18.719853Z | Complete pagination, 16 release Tags |
| `gh api --paginate --slurp repos/philfanzhou/ForgeSteward/releases` | 2026-10-06T16:05:20.006727Z | Complete pagination, 16 non-draft announcements, matching names; 0 drafts, all prerelease flags false |
| `gh api repos/philfanzhou/ForgeSteward/releases/latest` | 2026-10-06T16:05:21.404506Z | Actual latest `v0.2.16` |
| `gh api repos/philfanzhou/ForgeSteward/actions/workflows` | 2026-10-06T16:05:22.436418Z | Only test workflow; config confirms PR/main triggers, not release execution |
| `git ls-remote --tags origin` | 2026-10-06T16:05:24.080233Z | 16 annotated objects dereference to commits matching Tag API; v0.2.16 commit `0adce4a2412a36aa15fd119f7cc56a73d7689eba` matches announcement's release commit |
| `git status --porcelain=v1` before/after | 2026-10-06T16:05:17.676989Z to 16:05:24.081759Z | Outputs byte-identical, retaining earlier implementation edits only; audit changed no project files |

Three-source conclusion: Tags and announcements match within that list scope. Package feeds are inapplicable under the written Git-snapshot/marketplace, non-registry contract. Latest v0.2.16's stable flag matches its contract; other historical flags are observations only, without restoring every old contract. Automated release runs are inapplicable under manual publication.

Findings/unknowns: actual latest is v0.2.16, but no written latest policy exists, so pointer correctness is unknown pending written expectations; highest version alone cannot establish a pass. No confirmed Tag/announcement mismatch was found. The approximately 6.4-second observation window showed no cross-source version-set changes, without guaranteeing an atomic snapshot, permanent health, or complete historical package semantics. No private feed or model evaluation was used. This read-only audit **changed no project files**, created/edited no Issues, cleanup PRs, release assets, or release runs. Findings appeared only in the report.

Raw responses, sources/times, and state comparisons remain in that local evidence directory; commands and public announcement are reproducible, with itemized acceptance retained in the implementation PR. Recording verification does not authorize a latest-policy fix or new release.

## Root Claude entry consolidation (#125)

This source revision introduces a narrow exception to the historical 0.2.7 deletion-only decision above. It moves retained project instructions into an existing root `AGENTS.md`; it adds no copy of Skill workflow policy. Project conventions remain useful outside Skill invocation and do not acquire the duplicated-policy staleness problem. Existing policy deletion runs first. Collaboration-language rules are preserved, including conflicts; [#126](https://github.com/philfanzhou/ForgeSteward/issues/126) separately owns English defaults. No version, release, installation, setting, or this repository's own instruction entry changed.

The required, independently bundled [migration rules](../plugins/check-workflow/skills/forge-steward-check-workflow/references/agent-entrypoints.md) define root `CLAUDE.md` before `.claude/CLAUDE.md`, exact source headings, byte-preserving retained paragraphs, import/reference resolution, append verification before source deletion, interruption recovery, and no-write reruns. The legacy remover remains a block-removal CLI: exit 0 is not a complete migration decision. Existing malformed-block errors still stop cleanup writes. No production migration helper or separate protocol was added.

### Compatibility evidence and limits

On 2026-10-16, the official [Claude memory documentation](https://code.claude.com/docs/en/memory#agents-md) confirmed direct AGENTS.md loading from v2.1.277, enabled built-in support and instruction-mode/session conditions, including the first session after some upgrades. Root and ancestor `CLAUDE.md`, `.claude/CLAUDE.md`, or `CLAUDE.local.md` can prevent default fallback. Source removal therefore does not guarantee loading. Restoring root `CLAUDE.md` containing `@AGENTS.md` supports older or restricted sessions; maintainers choose that rollback. This Skill changes no user/global settings and scans no personal files.

The same source's [import rules](https://code.claude.com/docs/en/memory#import-additional-files) establish source-relative resolution and literal code examples. Retaining a path string is insufficient when moving it changes its target, especially from `.claude/`. Direct AGENTS.md loading also differs for instruction hooks, additional directories and external-import approval. Preserved imports can still require previous approval. These are documentation-based compatibility conclusions, not independent client/model execution or a guarantee for arbitrary sessions. Other Agents' import interpretation is not made equivalent by consolidation; see [existing loading verification boundaries](skill-compatibility.md).

### Finite repository walkthroughs

M01–M26 were walked through against the final rules using individual temporary Git repositories. Each input was written as explicit bytes, tracked, and inspected; the reviewer selected each action from the rule, then performed that fixed action and asserted retained bytes, original destination prefix, source deletion, or unchanged bytes/mtime. For appends, assertions ran before unlinking. Completed-state inspection performed no subsequent write. M23 additionally executed the unchanged block remover. Raw input repositories, selected actions/reasons and diffs are retained with the implementation run evidence; the PR records its location. The fixture driver only performs predetermined case actions: it does not implement a general migration or test Agent judgment. No independent Agent/model, consumer cleanup PR, or remote publication ran for these scenarios.

| ID | Finite input | Observed selected result |
| --- | --- | --- |
| M01 | Only tracked CLAUDE.md, no root AGENTS.md | No migration; no target created; bytes/mtime unchanged |
| M02 | Root AGENTS.md, no tracked Claude source | No change or empty delivery |
| M03 | Root CLAUDE.md has blank lines and `@./AGENTS.md` | Delete source only; target untouched |
| M04 | `.claude/CLAUDE.md` has `@../AGENTS.md` | Delete root-resolving import-only source |
| M05 | Root CLAUDE.md symlinks exactly to root AGENTS.md | Unlink source only, preserve target bytes |
| M06 | Root import plus own Build section | Omit standalone import; append exact section under fixed root-source heading, then delete source |
| M07 | Exact existing paragraph plus own paragraph | Omit only duplicate bytes; append remaining paragraph |
| M08 | Root says Python, source says Ruby | Move Ruby text unchanged; report both exact conventions for maintainer decision |
| M09 | Both root sources have own text | Append root then `.claude` payload under their distinct fixed headings; delete verified sources |
| M10 | Fenced and inline `@AGENTS.md` examples | Preserve both as literal payload; do not treat as effective root imports |
| M11 | Root source imports existing `@docs/rules.md` | Preserve import and its target identity |
| M12 | `.claude` source imports `@rules.md` | Retain/report: destination would change the import target |
| M13 | `.claude` source imports bare `@AGENTS.md`, with `.claude/AGENTS.md` present | Retain/report: not a root import and would change target |
| M14 | Destination BOM/CRLF; source BOM and mixed newlines | Preserve destination prefix and complete source BOM/newline payload; no normalization |
| M15 | Non-UTF-8 source | Retain/report undecodable source, no writes |
| M16 | Source symlink points to another file | Preserve link and both file targets; report unsupported move |
| M17 | Unclosed source fence | Retain/report ambiguous parsing |
| M18 | Effective root import embedded in prose | Retain/report: omission would require rewriting retained prose |
| M19 | README has a live link to source | Retain/report rather than break link or rewrite referrer |
| M20 | Nested pair and tracked CLAUDE.local.md | Report unchanged scope/loading blockers; no fallback promise |
| M21 | Safe own-content input, check-only | Plan only; all files/mtime unchanged, no branch/commit/PR |
| M22 | Safe own-content input, local-only | Coherent local append/delete diff; no commit/push/PR |
| M23 | Root AGENTS.md consists solely of legacy block; source imports it | Actual remover deletes both; do not recreate AGENTS.md for migration |
| M24 | Verified payload already appended, source not yet deleted | Omit exact duplicate and delete source only; no second heading/content |
| M25 | Source paragraph entirely duplicated in target | Delete source only; no empty heading |
| M26 | Source paragraph differs only in case | Keep and append; semantic/case normalization is not exact deduplication |

The decision review also checked nonregular/unreadable paths, broken/cyclic symlinks, unresolved imports/links, and source-specific heading collisions: all retain/report without partial migration. Untracked local instructions are outside modification scope. For interrupted unverified appends, preserve the source and recovery bytes and report the pair incomplete; M24 applies only after byte verification. A completed run has no remaining migrated source, so repeated inspection adds no heading or content and starts no branch/commit/PR. Byte/mtime checks here cover fixed inspections rather than arbitrary Agent reruns.

The diff gate was reviewed with four finite changes: policy deletion (allowed), exact retained append plus source deletion (allowed), rewritten retained prose (rejected), and an unrelated added project rule (rejected). A heading without retained content or source deletion before verified append is also rejected. Migration-only input M06 follows the same cleanup-branch/PR route as policy deletion; safe migration keeps the no-change gate open even when the legacy script returns 0. Check-only never enters that delivery route; local-only stops at the local diff. Cancellation stops further writes and accurately separates completed and incomplete pairs. These are instruction/delivery walkthrough outcomes, not an executed hosting-platform integration test.

Packaging regression explicitly requires the new migration reference in installed check-workflow resources; existing byte-for-byte resource comparisons also cover it for filesystem adapters. Skill budgets, prompt equality, marketplace checks and the complete suite are required implementation checks. Runtime-dependent skips remain skips; neither static success nor these walkthroughs proves all clients load instructions correctly. Release reconciliation retains its read-only scope and separate final-report-only findings.


## English collaboration defaults (#126)

The current source extends the historical 0.2.7 deletion-only decision with a second narrow exception: configure one fixed English collaboration default in an existing root instruction entry. This is a shared project convention useful outside ForgeSteward invocation, rather than another copy of changing Skill workflow policy. It complements #125's entry consolidation; policy deletion runs first, migration second, language inspection third. Historical release decisions above remain history. VERSION stays 0.2.24; no release or installation change is included.

The independently bundled [language rules](../plugins/check-workflow/skills/forge-steward-check-workflow/references/collaboration-language.md) are authoritative for the fixed heading/prose, semantic coverage table, safe destination precedence, separable edits, unresolved conflicts and verification. The default covers Issue and Change Request titles/bodies, Comments, Discussions and Review Feedback replies. It honors explicit maintainer requests and quoted code/log/external-text exceptions. Complete equivalent coverage can reside in checked candidate files. Partial English coverage supplies only the surfaces it actually covers; it triggers one fixed section for the remaining coverage, never another complete duplicate. No keyword classifier or model-compliance guarantee is introduced.

### Finite source walkthroughs and outcomes

E01–E30 used individual temporary Git repositories, explicit input bytes and predetermined operations selected by reading the decision table. Original file digests/mtime, selected operations/reasons, resulting digests/mtime and tracked diffs are retained with implementation evidence. Appends assert the original byte prefix and exact fixed section; replacements assert exact old/new bytes; retained cases assert no byte/mtime changes. Reinspection of every completed state writes nothing. These are finite instruction walkthroughs, not a general language processor, independent Agent/model execution or a consumer hosting integration test.

| ID | Finite input | Observed selected result |
| --- | --- | --- |
| E01 | Root AGENTS.md with only a Python convention | Append the exact fixed section; preserve prefix |
| E02 | Complete equivalent root English rule | No addition or duplicate |
| E03 | Complete English rule only in CONTRIBUTING.md | Existing candidate coverage recognized; root unchanged |
| E04 | English Issue-title rule only | Preserve it; append fixed section once for missing coverage |
| E05 | Separate root Chinese collaboration sentence | Remove only that sentence; supply fixed section; record exact original/source |
| E06 | `Docs and Issues are written in Chinese` | Retain `Docs are written in Chinese`; fixed English section covers collaboration |
| E07 | Separate Chinese documentation, Spanish code-comment, French commit-message and Chinese collaboration rules | Replace collaboration only; other convention bytes remain |
| E08 | Documentation and Issues must use identical language chosen together for each release | Retain inseparable shared obligation; report maintainer decision and unresolved coverage |
| E09 | Chinese collaboration rule only in CONTRIBUTING.md | Retain external rule; no competing root addition |
| E10 | Independent Chinese root rule plus external Chinese rule | Replace root portion safely; report external conflict unresolved |
| E11 | Only root CLAUDE.md | Add to existing CLAUDE.md; no AGENTS.md creation |
| E12 | Only .claude/CLAUDE.md supplies root entry | Add there; no other entry created |
| E13 | README only, no instruction entry | Report missing entry/recovery; no file creation |
| E14 | AGENTS.md symlink to another file | Preserve link and target; report unsafe destination |
| E15 | Non-UTF-8 root entry | Retain/report undecodable entry |
| E16 | Untracked root entry | No write authorization through it |
| E17 | Directory named AGENTS.md | Retain/report nonregular entry |
| E18 | Inline/fenced examples and explicitly quoted external Chinese instruction | Preserve example bytes; add actual rule separately |
| E19 | Fixed rule with explicit override and quoted-text exception | Complete coverage; no write; explicit alternative request is supported |
| E20 | CLAUDE import plus Build and Chinese collaboration text | Verify byte-preserving migration first; delete source; replace moved collaboration at its new root location, retain Build text |
| E21 | Safe replacement input, check-only | Report proposed replacement; all bytes/mtime unchanged |
| E22 | Missing rule, local-only | Verified local addition only; no delivery command |
| E23 | Missing rule, delivery blocked after local addition | Preserve completed uncommitted diff; report exact stopping point |
| E24 | Completed fixed-section state inspected again | No duplicate section, timestamp, branch, commit or PR |
| E25 | Fixed heading with unrelated decision instruction | Retain/report heading collision rather than duplicate or rewrite |
| E26 | Unsafe preferred AGENTS.md plus regular CLAUDE.md | No lower-priority write; both unchanged |
| E27 | All collaboration surfaces use English but no override/quoted exception | Partial equivalence; one fixed section supplies missing guarantees |
| E28 | Partial external English plus conflicting external Chinese rule | Keep conflict visible; no root override added |
| E29 | Existing destination BOM and CRLF | Preserve original prefix; fixed prose uses destination newlines |
| E30 | Complete English rule plus a separate root Chinese rule | Remove only conflict; reuse existing English coverage without a duplicate |

Additional decision review covered unreadable/unwritable entries, ambiguous parsing, root-only dedicated language sections and explicit earlier maintainer retention: unsafe operations remain unchanged; a dedicated collaboration-only section can be replaced as a unit without leaving empty headings, while unrelated section content remains. An explicit maintainer alternative-language request is honored by the fixed default and does not change repository configuration. Cancellation stops further writes; verified completed operations remain recoverable and unfinished operations are reported without claiming completion.

The final diff gate admits policy deletions, #125's exact migration operations, and this fixed section/separable language exception. It rejects unrelated new project rules, translating documentation, changing commit-message language, editing external conflicts, arbitrary paraphrases of the fixed rule and creating a missing entry. A language-only input keeps the no-change gate open and follows the same fixed cleanup branch, verification, commit, push and actual PR/MR creation path as policy deletion. Check-only bypasses that write/publication path; a completed rerun starts no empty delivery. The cleanup PR must quote replaced text/source lines and unresolved decisions separately from deletions/migrations. These route and PR-body outcomes were reviewed against the instructions; no consumer repository PR was fabricated for a rule walkthrough.

The new reference is explicitly included in installer resource expectations and existing byte-for-byte packaging comparisons. Required checks are Skill budgets (including simulated CRLF), the complete suite, marketplace consistency and whitespace. Existing metadata/prompt equality, resource, wording and link checks apply; no implementation-mirroring keyword test was added. Environment-dependent skips are reported as skips. Release reconciliation remains read-only with findings only in the separate final report. Combined parent #124 acceptance is supported by #125's M01–M26 migration record plus E01–E30, especially E20; neither static checks nor these finite cases certify arbitrary Agent/model behavior.

## Standalone comparison and packaged stage versions (#174)

[Issue #174](https://github.com/philfanzhou/ForgeSteward/issues/174) makes the policy catalog the authoritative comparison source for a standalone install and adds one packaged stage-version preflight to work-cycle. These are finite rule walkthroughs, not independent Agent/model runs or a consumer installation test.

| ID | Input/state | Expected action and completion condition | Rule basis |
| --- | --- | --- | --- |
| N01 | Standalone check-workflow install; the owning skill's text is not installed; a candidate clause's equivalence depends on missing semantics | Compare the clause against the bundled policy catalog; record an explicit “skill gap” with the original text and missing semantics; retain the clause; do not report it as equivalent or clean | Procedure step 3; skill-owned rules |
| N02 | The owning skill is installed and its entry links additional rule files | Compare each clause with that full text and also inspect the rule files linked from its entry before deciding deletion | Procedure step 3 |
| N03 | Orchestrator 0.2.25; one stage package carries 0.2.24 and another has no `VERSION` marker | Preflight exits 1 and prints each exact missing or mismatched path with expected 0.2.25 and the actual value; the stage stops before its first write and changes no project file | Startup preflight; `scripts/preflight_versions.py` |
| N04 | All five stage packages carry markers equal to the orchestrator's bundled version | Preflight exits 0; the stage proceeds and the check writes no project file | Startup preflight |

The comparison still has one authoritative source: the bundled catalog. A missing owning skill produces an explicit skill gap, not a clean result, and no bundled snapshot of other skills' clauses is added. The preflight reads only packaged markers, is read-only and idempotent, and adds no client configuration or version change.
