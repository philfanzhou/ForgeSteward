# Orchestration Skill acceptance scenarios

This document covers `work-cycle` in `0.2.16`, with later revisions identified below. These are limited rule walkthroughs; unit tests verify cache decisions. They are not presented as real cross-Agent end-to-end repository runs.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Default cycle count | Explicit invocation without a number | Run at most 10 nonempty preparation cycles, dispatching stage subagents; merge eligible Change Requests directly |
| Explicit limit and early end | Limit `5`; third prepare-work returns `[]` | Stop after 2 completed cycles; no empty execution task or work merely to reach 5; report existing pending items |
| Open PRs at startup | Two preexisting PRs, one mergeable and one needing repair | After startup checks, review the entire open queue, merge eligible work, dispatch required repair/review, then begin preparation cycle 1 |
| No ready Issue but open PRs | Preexisting open PRs, then prepare-work returns `[]` | Still complete startup reviews, eligible merges, and branch cleanup; `[]` only stops new cycles |
| No open PRs | Startup queue empty | Skip empty review tasks and begin preparation |
| Required subagents | Create/wait API confirmed absent, access definitively denied, or stage Skill missing | Stop before stage writes and report the specific gap; orchestrator does not perform stage work |
| Low-quota warning | Warning appears but create/wait remain usable | Continue required dispatch without reducing cycles, inventing `[]`, or making quota probes |
| Release completed stage | Stage finished, complete results/remote evidence saved, runtime supports closing threads | Release that stage's thread and continue; never close active or other-session Agents |
| First creation failure | Thread limit returned; status confirms no task created | Release eligible completed threads, retry within limits, and resume original stage on success; one error does not end the run |
| No close API | Completed threads remain listed, no close API, next creation succeeds | Record limitation and continue; invent no tool, do not assume interruption frees capacity, and do not reuse old review Agents |
| Ambiguous creation | Transport error, but status shows original task running | Wait for original Agent; do not duplicate a stage that may already have written |
| Persistent ambiguity | Creation uncertain after two additional queries | Save last confirmed state/recovery conditions and end without duplicate creation or claiming completion |
| Ordinary waiting | Wait timeout/no new message while Agent runs normally | Keep waiting for original Agent; not startup failure or recovery-budget consumption |
| Wait call fails | Actual transport failure, known Agent ID | Inspect original task, retry its wait/result read, never recreate stage |
| Recovery exhausted | Initial operation and at most two operation retries fail | Third round checks final status only; if still unable to continue, report errors, recovery results, unfinished stages, and unblock conditions; renaming cannot reset count |
| Independent work in a cycle | One Issue blocked, two independent items implementable | Execution continues with the other two; one paused item also does not stop independent review, repair, or merge |
| Final review after third repair | Third repair pushed, current head not finally reviewed, all requirements met | New reviewer audits commits and merges; three rounds alone do not exclude it |
| Failed final review | Same PR still has required in-scope problems, another is mergeable | Record failed head/reason, no fourth automatic repair; merge independent PR and do not rereview the failed unchanged head next cycle |
| External requirements pending | Code final review after third repair passed, CI unfinished | Record platform waiting rather than code failure; after conditions change, recheck merge requirements without another code final review |
| CI failure after repair | Repair deterministically breaks required CI | Same repair subagent fixes/pushes within that repair, without another exchange or waiting for review to discover it |
| Other PRs conflict after merge | First PR merges, others conflict or become stale under up-to-date-branch policy | Review records main-sync requirement; repair syncs original branch, reruns affected verification, and pushes without consuming an exchange; a new reviewer checks afterward |
| CI still running | Required review checks unfinished | Review other items first, then revisit. Merge if checks finish within the repository-history-based limit, or 30 minutes without history; timeout or delayed start becomes waiting for external checks |
| Implementation impossible | Execution confirms an Issue cannot be implemented | Record reason/unblock conditions on original Issue and remove stale ready marker; next preparation reuses conclusion while conditions stay unchanged |
| Subagent needs clarification | Stage requires a user question | Record question on original Issue/Change Request and in return, continue independent work, and return promptly without blocking all orchestration |
| Unchanged PR on rereview | Repair changed other PRs; this one's head, feedback, checks, and relevant main remain unchanged | New reviewer reuses conclusion and confirms only checks, approvals, conflicts, and protection; changed PRs get normal review |
| Second preparation cycle | Earlier cycle recorded alert checks, classification, blocker rechecks, times, and main baseline | Check only new/changed evidence; use full process if records or coverage are missing |
| Third-repair final audit | Repair recorded a per-commit audit covering its pushed head | Verify that record item by item and fully audit later commits, without repeating the entire audit |
| Review completed PRs early | Background subagents supported; execution handed off 2 PRs and is implementing item 3 | Dispatch review for handed-off items, excluding execution-owned items; execution stops pushing handed-off branches |
| Main changes during implementation | Review merges another PR while implementation is based on older main | Refetch remote main before push, resolve conflicts and rerun affected verification first; later conflicts go to repair |
| Cleanup alongside implementation | Review cleans after merge while another workspace implements | Delete this merged PR's branch/dedicated workspace and follow review cleanup rules for leftovers; preserve all other-stage active branches/workspaces listed at dispatch. Without that list, leftover cleanup is list-only; briefly retry Git lock conflicts |
| Early next-cycle preparation | Execution ended, a PR still cycles through repair/review | Dispatch next preparation concurrently; only orchestrator writes shared progress |
| No background support | Runtime cannot run/read background subagent progress | Run stages serially with unchanged scope/rules and disclose in final report |
| Two tasks need local database | Two implementation Agents verify; both Issues list a local database | First `db` lock holder runs; the other does independent checks, then waits for release; always release on success/failure |
| Isolatable resources | Existing config permits test database/container project names | Name them per task instead of queueing; do not change repository config for isolation |
| Unknown resources | External PR lacks resource records | Reviewer acquires all resources known to this run plus `local-suite` before local tests |
| Failure under concurrency | Test fails concurrently but passes alone while holding all relevant locks | Report resource collision, not code defect/repair round; orchestrator marks resource as queued thereafter |
| Subagent exits abnormally | Stopped Agent retains locks | Orchestrator confirms stop, then releases under same task ID; never release a running Agent's locks |
| Excessive lock wait | Cumulative wait exceeds 30 minutes | Return waiting-for-resource result instead of idle waiting |
| Lock script unavailable | Script cannot run or errors | Disable concurrency for this run and use serial stages |
| Three unrelated items | Preparation returns `#1, #2, #3`, no relationships, limit 3 | Three execution Agents each take one Issue in an independent external worktree; first handed-off PR enters review first |
| Code dependency | `#2` depends on `#1` | Start `#1`/`#3`; start `#2` only after `#1` merges, first checking actual merged changes within recorded recheck scope |
| Prerequisite paused | `#1` remains ineligible after three repairs | Keep `#2` waiting with reason, without affecting `#3` |
| Overlapping changes | `#3`/`#1` both change lockfile | Start `#3` after `#1` merges; if `#1` pauses or will not submit, start `#3` directly and send later conflicts to repair |
| Unexpected overlap | Implementing `#3` requires a file reserved for `#1` | Pause `#3`, preserve workspace/local commits, and report; orchestrator resumes only after `#1` merges |
| Same finding concurrently | Two subagents find the same existing defect | First `issue-registry` lock holder searches/registers; second searches under lock and adds only evidence to the existing Issue |
| Few CPU cores | 6 logical cores | Reduce concurrency limit to 2 |
| Next preparation cycle | Every current item started or waits for prerequisite | Dispatch next preparation with all assigned unfinished Issues excluded from reselection |
| Two concurrent reviews | A/B handed off, capacity available | One reviewer/workspace per PR; local checks queue on resource locks |
| One repair and one merge | A needs changes, B approved | Dispatch A repair and then a fresh reviewer; B independently takes `merge` lock and merges |
| Main changed with overlap | A merged during B review; both change lockfile | Rerun affected checks on B's temporary local merge with new main, then lock/confirm main unchanged/merge; failure becomes sync or repair requirement |
| Main changes before lock | B checked main M, but overlapping C merged before lock acquired | Release lock and recheck new main; do not run long checks inside lock |
| Up-to-date branches required | A merged, B/C both reviewed | Under this earlier concurrent-sync rule, dispatch B/C main sync together, run CI concurrently, then rereview/queue merges; later #87 below replaces repeated all-branch synchronization |
| Merge lock occupied | A merging when B requests lock | B waits until A finishes merge/cleanup and releases |
| Reviewer exits abnormally | Stopped reviewer holds `merge` | Confirm stopped, release, and redispatch that PR review from recorded state |
| First automatic cleanup | No target-repository Git-metadata record | Dispatch check-workflow once at startup, record in local Git metadata, outside cycle count |
| Same version, ordinary changes | Previous run completed at same version; ordinary commits/merges since | Skip automatic cleanup even after 7 days; PR state/file diffs do not trigger it |
| New-version cooldown | Version changed, last run 6 days ago or exactly 7 | Skip at 6 days; run at 168 hours; skips do not extend cooldown |
| Incomplete prior run | Previous automatic cleanup failed/uncertain | No automatic retry within 168 hours; afterward retry allowed even at same version; independent cycles continue |

The orchestration Skill accepts only one optional positive integer, with no extra merge-permission or subagent toggle. Explicit invocation requests complete delivery, while repository checks, approvals, protection, and actual permissions still apply per item. Each stage Skill governs its own frozen scope and Issue granularity.

Migration: previously the first prepare-work `[]` skipped review, and preexisting open Change Requests appeared only in the final report. Since `0.2.14`, process that open queue first, then at most the requested number of Issue cycles. Startup review may merge and clean existing branches. Do not explicitly invoke a complete work cycle for read-only analysis.

`0.2.16` changed subagent failure termination: quota warnings no longer justify stopping; actual failures require state checks and bounded recovery. Independent stages, fresh review Agents, and sequential dependent writes in one repository remain. Recovery walkthroughs do not constitute end-to-end certification of runtime thread release.

[#59](https://github.com/philfanzhou/ForgeSteward/issues/59) removes rework and stalls in handoffs: repair watches its own post-push CI; repair handles conflicts/stale branches without consuming exchanges; CI wait limits derive from repository history; impossible implementation conclusions go back to the original Issue for preparation reuse; dispatched subagents do not stop waiting for user answers. Merge conditions, review standards, and the three-round limit stay unchanged.

[#60](https://github.com/philfanzhou/ForgeSteward/issues/60) removes duplicate checks on unchanged objects: reuse prior review/repair classification; reuse earlier-cycle global preparation checks within a run; final review reuses repair's commit audit; do not rerun locally checks already passed by CI on the same head; read auto-delete settings once per invocation. Orchestrator stores only conclusions/evidence locations and verifies only objects involved in the finished stage. Standards and decisions remain unchanged.

[#61](https://github.com/philfanzhou/ForgeSteward/issues/61) lets completed work advance early: with background subagents, each handed-off PR can enter review while later implementation or next-cycle preparation runs. One PR has one stage owner at a time; stages use independent workspaces; execution branches from latest remote main and synchronizes before push; cleanup preserves other stages' workspaces; only orchestrator writes shared progress. This initial revision kept execution/preparation mutually serial. Without background support, use serial stages.

[#67](https://github.com/philfanzhou/ForgeSteward/issues/67) adds concurrent local verification: `scripts/resource_lock.py` stores locks in the repository's common Git directory shared by all worktrees. Isolate by task first, queue unisolatable resources, and separately limit heavy work. Rerun concurrent failures alone to distinguish collisions from defects; disable concurrency if locks cannot work. Verification standards remain unchanged.

[#68](https://github.com/philfanzhou/ForgeSteward/issues/68) makes implementation concurrent per Issue: default total maximum 3 subagents, reduced for fewer cores. Orchestrator schedules using recorded batch relationships. Worktrees live outside the repository; use separate clones for submodules. Search/deduplicate under `issue-registry` before creating Issues.

[#69](https://github.com/philfanzhou/ForgeSteward/issues/69) makes review/repair concurrent per PR: each independently follows review → repair → rereview. `merge` lock permits one merge at a time, with overlapping changes rechecked on new main and main reconfirmed under lock before merge/cleanup. This revision dispatched simultaneous synchronization when current branches were required; #87 below refines it. Review standards, merge conditions, and three-repair limit remain unchanged.

## Language and commit conventions (#83)

The original #83 revision used everyday Chinese as the default while prioritizing target-repository language rules. The English migration changes that default to everyday English; explicit user/repository requirements still take precedence.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| English commit messages required | Target contribution rules require English commits and Chinese PR bodies | Explicitly provide English merge title/body, including squash merges, instead of reusing the Chinese PR body |
| English Issue/PR bodies required | Contribution rules require English Issue/PR bodies | Write bodies/comments in the required English; user reports, progress, and questions default to everyday English unless explicitly requested otherwise |
| No language policy | No applicable convention | Use everyday English for Issue/PR bodies/comments and platform defaults for merge commits |

## Leftover branch cleanup once per run (#84)

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Concurrent merges | Three PRs each merged by a reviewer | Each cleans only its PR branch/workspace under merge lock; no repository-wide scan or leftover cleanup in the lock |
| Repeated serial reviews | Review dispatched 6 times in a run | None performs leftover cleanup |
| Run completion | All stages finished, one PR paused | Dispatch one cleanup-only subagent, explicitly retaining paused PR branches/workspaces; one leftover pass for the whole run |
| Standalone review-and-merge | User directly invokes review Skill | Unchanged: one leftover pass after processing its list |

## Run records and timing (#85)

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Start | Startup checks finished | `start` creates `runs/<run-id>/` in common Git metadata and retains only the latest 20 script-created runs, leaving other old-version files untouched |
| Dispatch/completion | Execution Agent starts then returns | Record `started` before dispatch and `finished` after confirmed completion; place evidence in `task-dir` directory, not `/tmp` |
| CI wait | Subagent waits 8 minutes after push | Record `wait-start`/`wait-end` with type `ci`; include time in summary |
| Recovery | Orchestrator context compacted | Read run-directory `handoff.json` first to restore progress |
| Final report | Run ends | Include wall time, aggregate stage durations, and total CI/lock waits |
| Script unavailable | Recording command errors | Explain in session handoff and continue delivery |

## Retry unrelated CI failures once (#86)

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Unrelated flaky test | Docs-only PR, required concurrent test fails then passes rerun | Rerun failed job once, accept pass and continue merge; record both run links on PR, then deduplicate/register test Issue under lock |
| Rerun fails | Same input, rerun also fails | Record external waiting, no more reruns; continue independent work |
| Related failure | Test covers changed code | Repair or classify as required; do not rerun to dismiss it |
| Unclear relationship | Cannot determine whether failed test depends on changed code | Treat as related, without rerun-to-dismiss |
| Known flaky test recurs | Another PR sees the same flaky failure | Rerun once; under lock find existing Issue and append this run's links only |

## Merge lane and repository merge queue (#87)

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Up-to-date policy, 4 approved PRs | After first merge, 3 become stale without conflicts | One merge-lane subagent holds `merge` and processes each: sync only next PR, wait checks, verify changes come only from main, merge. Do not resync all after each merge or create a new Agent each lap |
| Conflict in lane | Second PR trial merge conflicts | Do not resolve in lane; send to repair and continue third. Repaired PR gets reviewed before another lane pass |
| Checks fail in lane | Required checks fail after sync | Retry unrelated failure once; related failure goes to repair, lane continues |
| Fork source | Lane cannot push source branch | Record author-sync requirement and continue |
| Repository merge queue enabled | Approved branch is stale | Enqueue and wait, without own sync or `merge` lock. Conflict rejection goes to repair; failed checks follow CI rules |
| No repository queue | Same state | Do not enable queue or auto-merge; synchronize/merge one at a time |
| Standalone review-and-merge | Three approved frozen PRs are stale under policy | After review, process sequentially through merge lane |

## Fixed final report format (#95)

Sections, result vocabulary, and display-name mappings are defined only in work-cycle's `references/report.md`. `run_record.py report` reads that specification and renders `handoff.json` plus events. The table is a rule walkthrough; `tests/test_run_report.py` compares fixed examples byte for byte.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Normal finish | Complete handoff, all results in seven-value vocabulary | Print six required sections, add seventh only for available updates, save run `report.md`, return `0`; orchestrator pastes unchanged with at most one additional-notes paragraph |
| Repeat render | Identical data | Byte-identical output/report, without reading current time |
| Invalid result | PR result `Ready to merge`, or a required field missing | Return `1`, list exact field errors such as `change_requests[2].result`, and do not write report; orchestrator corrects/retries at most 3 times |
| Retries exhausted | Still `1` after three corrections | Use report template manually, starting `This report was written manually by the model because: ...` |
| Script cannot run | No Python 3.9+, Windows Store placeholder only, sandbox denial, or exit `2` | At startup try `python3`, `py -3`, then `python`; record absence in handoff. At end use annotated manual template and continue delivery |
| User stops | PRs still reviewing and Issues not started | Still report; unfinished items become `Paused` with reasons, actionable ones appear under Needs your action |
| Empty run | No PRs or exceptions | Still render first six sections with `- None` where empty; seventh depends on upgrades |
| No events | Recording became unavailable, events.jsonl empty | Time spent section says `- No record` |
| Zero time | All events at same instant | Report `Total 0 min`, CI/resource waits `0 min` |
| Optional upgrade section | No `agent_check`, due to old records or skipped check | Omit seventh section and render six normally; saved checks use filtering below |
| Old free-form record | handoff.json predates required structured fields | Return `1` with missing fields and use manual fallback; migration is not required |

## Other-Agent installation checks (#97)

At startup work-cycle runs bundled `scripts/agent_install.py check` once, read-only, to compare local Agents' user-scope ForgeSteward versions with the latest GitHub stable release. Save `agent-check.json` in the run directory. The optional final section appears only for actionable upgrades. Detection comes solely from adjacent `agents.json`. Raw states remain in the check JSON; the report lists only upgrade candidates. End-of-run consent/install behavior follows below. These are rule walkthroughs; `tests/test_agent_install.py` checks states using temporary HOME/PATH fake commands and injected release data without network.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Agent absent | No command, application, or config directory | State `Agent not installed`; omit from report |
| No plugins installed | Only Harness lacks ForgeSteward; latest v0.2.21 | State `Missing`; report `DeepSeek Harness: Not installed (latest v0.2.21)` |
| Partial installation | Codex has two plugins, both latest | State `Incomplete`; report `Codex: Missing a, b (latest vN)` |
| Older version | ZCode all 0.2.20, latest 0.2.21 | State `Behind`; report `ZCode: v0.2.20, behind latest v0.2.21` |
| All current | Every installed Agent complete/current, same session package | No seventh section or question; retain check JSON |
| Newer than stable | OpenCode development 0.2.22 | State `Ahead of latest release`; omit from report |
| Other installation scopes | Claude also has project-level same-named plugins | Judge user scope only; append other-scope note only if this Agent is listed as upgradeable |
| Timeout/unrecognized output | `claude plugin list --json` exceeds 20 seconds or returns unexpected JSON | State `Unknown` with reason; omit that Agent but retain others, still exit `0` |
| Manual copy | OpenCode/Harness has forge-steward-* without receipts | State `Unknown` with manual-copy reason |
| Missing ZCode runtime | Only ~/.zcode, no node or zcode.cjs | State `Unknown`, identify missing component; no additional internal installation-record fallback path |
| Latest unavailable | gh unavailable and API fails, or latest is prerelease/non-vX.Y.Z Tag | Preserve raw states, omit section seven/question |
| Check unavailable | No Python, exit `2`, more than 60 seconds, or interruption | Record unavailable reason in handoff, omit section seven, continue delivery |
| Read-only | Compare all temporary-HOME files before/after | Paths/bytes unchanged; write check only to run directory |
| Slow first Codex catalog query (#114) | macOS CLI 0.157.1; unfiltered fake command delays on cold remote cache but not warm | Catalog uses only `codex plugin list --marketplace forge-steward --json`, skipping remote path on first/later calls with same target names/versions as old filtered result; preserve 20-second command/60-second overall limits |
| Codex target states | Strict argument checks, target Current/Behind/Missing/Incomplete, same names in other marketplaces | Preserve four classifications; ignore other marketplaces; JSON schema/other Agents unchanged |
| Codex failure/old CLI | Timeout, nonzero, invalid JSON, nonarray installed, changed pluginId/version fields | Codex `Unknown`, other Agents continue, overall check `0`; one query only, no unfiltered/internal-cache fallback; absent CLI/config still `Agent not installed` |
| Codex read-only/timeout termination | Isolated HOME config/files, output run directory; timeout fake spawns child | HOME paths/bytes unchanged, only check result written; terminate command and child on timeout, no extra query |
| Older session package (#113) | Bundled scripts/VERSION 0.2.9, confirmed latest 0.2.10, all Agents current or empty | First upgrade line states session v0.2.9 vs latest v0.2.10; ask once. Compare integer components and do not infer Agent ID from notice |
| Old session and upgradeable Agents | Older session plus multiple Missing/Incomplete/Behind Agents | Session notice first, only eligible Agents without duplicates, one combined question |
| Same/newer session | Session 0.2.10/0.2.11, latest 0.2.10 | No old-session notice; seventh section only for eligible Agents |
| Invalid session version | Missing/invalid package VERSION, eligible Agent exists | Do not guess session version; still list eligible Agent |
| Unreadable check file | Missing file, invalid JSON, unrecognized fields | Omit seventh section, preserve six; do not rewrite check or hide handoff validation errors |
| Repeat render | Same handoff/events/check/package version | Byte-identical output, unchanged check file; fixed fixtures control package version to avoid actual version contaminating injected data |

Real Codex queries were checked on macOS `0.157.1` on 2026-10-13: old query 0.949 seconds, first/repeated scoped queries 0.070/0.047 seconds, with matching six target plugin names/versions. Fixed source [run_plugin_list and fetch_remote_marketplaces](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/cli/src/plugin_cmd.rs) skips remote fetch for a specified nonglobal marketplace. Fake-command regressions verify that argument path and failures, not Windows/Linux real CLI behavior or fully cold OS-cache timings. No internal-cache reader is added; installation/update steps remain unchanged.

## Ask at completion, install or upgrade after consent (#98)

Show the final optional section only when the latest stable release is known and there are Missing/Incomplete/Behind Agents or an older session-package notice. With eligible Agents, end with their names/target version and one `Install or upgrade now?` question. With only a session notice, ask once about upgrading; do not derive `apply --agents` from the notice, and obtain explicit consent for actual Agents. After consent, orchestrator runs `scripts/agent_install.py apply --version X.Y.Z --agents <id,...>` and reports actual script results. Only work-cycle orchestrator does this; stage Agents neither check nor ask/install. The following are walkthroughs tested with temporary HOME/directories, stateful fake PATH commands, local temporary Git repositories, and injected releases, without network or real Agent configuration.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Only Harness missing, consent given | Offer Harness v0.2.21, user agrees | Resolve Tag commit; if no usable local copy, download Tag temporarily and verify commit. Individually install six Skills using `scripts/deepseek.py install forge-steward-<plugin> --user` into DSH_HOME/skills or ~/.dsh/skills with receipts/version 0.2.21. Recheck Current, remove temporary source/lock, report installed version and activation in each Agent's next new session |
| Decline/no answer | Same offer, no consent | Do not run apply or change files; do not persist refusal, check/ask again on a later run |
| Only Codex behind | Codex 0.2.20, others current, user agrees to all | Skip current Claude/Harness; Codex first reads `marketplace list --json`, then runs each `codex plugin remove`, `marketplace remove`, `marketplace add philfanzhou/ForgeSteward --ref v0.2.21`, and each `codex plugin add`. Others receive only list calls and remain unchanged |
| Partial consent | Codex/Harness offered, only Codex accepted | Pass only `--agents codex`; leave Harness untouched |
| No plugins/marketplace | Claude exists without ForgeSteward | Use upgrade sequence, skip absent removals after listing marketplace, run `marketplace add ...@v0.2.21 --scope user`, then each `plugin install --scope user`, report installed version |
| Empty old marketplace remains | Claude/Codex has no plugins but marketplace v0.2.20 remains; direct new-source add fails in verified behavior | List/confirm, run `marketplace remove forge-steward`, add v0.2.21 and install individually; recheck Current, exit `0` |
| Plugins remain, marketplace absent | Codex plugins 0.2.20 but source deleted | List first, uninstall plugins, skip nonexistent marketplace removal, add v0.2.21/install; recheck Current, exit `0` |
| Marketplace query fails | `claude plugin marketplace list --json` returns nonzero, exceeds 20 seconds, or is unrecognized | No mutation commands for this Agent; report cannot determine existence and reason, recheck unchanged state. Other consented Agents continue; exit `1` |
| Retired plugin remains | Codex has find-work | Remove during upgrade without reinstall; OpenCode/Harness use installer uninstall for receipted retired Skills |
| Other scopes | Claude also has project plugins | Modify user scope only and state other-scope installations were untouched |
| Usable local source | Claude marketplace clone `~/.claude/plugins/marketplaces/forge-steward` has HEAD equal to Tag commit and is clean | Use its installer without download; never remove it afterward |
| Unusable local source | Dirty files or wrong HEAD | Leave it alone; download/verify Tag instead |
| Download commit mismatch | Downloaded `git rev-parse HEAD` differs from API-resolved commit | Do not install that Agent, report both commits, remove temporary source, exit `1` |
| Edited managed copy | Older Harness `forge-steward-prepare-work` has receipt but changed contents | Installer rejects update with byte-identical directory; other Skills still install; report path/reason, recheck Behind, exit `1` |
| Receipt-free copy | Manual OpenCode `forge-steward-review-and-merge` | Check Unknown, apply skips Agent with reason, directory unchanged |
| Higher installed version | Codex 0.2.22, target 0.2.21 | Skip as newer than target, no downgrade/mutation commands |
| Step failure | ZCode uninstall succeeds, marketplace add fails offline; Codex also behind | Stop ZCode before install, recheck Missing, report failed command/reason and renewed-consent recovery; continue Codex, exit `1` |
| User interruption | apply interrupted halfway | Completed Agents keep updates; active Agent may be removed but not reinstalled. Later check shows Missing/Incomplete and renewed consent can complete it; remove lock/temporary source on exit |
| Unexpected file error | Codex file error before second mutation, e.g. temporary-file permission; Claude also behind | Stop Codex steps, report command/file error/reason/path even if recheck is installed, and use recheck state. Continue Claude; exit `1`, not `2` |
| Cleanup failure | Harness installed, temporary/lock directory deletion denied | Report successful install separately from retained path/reason/recovery. Temporary source may be removed manually; confirm no installer running before removing lock. Record top-level JSON cleanup details; exit `1` |
| Cannot create temp directory | Lock acquired/recheck passed, temp work directory unavailable | Exit `3`, report no changes and cause, no mutation commands |
| Invalid arguments | Missing version/agents, malformed X.Y.Z, unknown Agent, unreadable data file | Exit `2` only before mutation; no changes. Later file errors never return `2` |
| Latest changed | Consent v0.2.21, latest now v0.2.22 | Exit `3` without changes; orchestrator rechecks and asks for new version |
| Another installer active | forge-steward-agent-install.lock exists in system temp | Exit `3`, explain active installation, never delete its lock |
| Current Agent upgraded | Running in Claude, consent includes Claude | Upgrade normally; explain current session remains old and next session uses new version |
| Sandbox rejection | Network/user-directory writes prohibited | Explain accurately and give the same command for the user to run, without another installation route |

Not guaranteed: automatic rollback after a failed step (report actual state/recovery); exit codes/output for program defects beyond file errors, Ctrl+C, or stdout failure; identical behavior in unverified Agent CLI versions. apply reads only GitHub release/Tag contents, requires vX.Y.Z Tags, and runs argument arrays without a shell. It does not read/save/output tokens, and GitHub API requests contain no credentials.

## Logs, CI waiting, and subagent returns (#99)

Log/wait instructions live in execute-work, fix-feedback, and review-and-merge's own `references/ci.md`, byte-identical under `tests/test_shared_ci_rules.py`. Existing wait limits, external-wait timeout classification, and one retry for unrelated failures remain unchanged. Return format is in work-cycle `references/agents.md`, under Return format. The table is a rule walkthrough.

| Scenario | Input and state | Expected behavior |
| --- | --- | --- |
| Long log, middle-step failure | Thousands of CI lines, step 3 fails | Read only failed-step log, e.g. `gh run view <run-id> --log-failed`, working backward from error; repair/classify, post a few error lines/run link, not entire log |
| Earlier root cause | Failed step says missing dependency caused during install | Expand backward in chunks or read previous step; not restricted to the tail |
| Truncated rule vs log | Both repair.md and CI log reads truncate | Reread rule to EOF per entry requirements; read only needed log portions under ci.md |
| GitHub CI wait | Checks running after push | Run `gh pr checks <number> --watch --interval 60`, discard output, inspect exit status (0 passed, 1 failures, 8 pending), then read final result once; respect existing total limit |
| Tool wait shorter than CI | Checks need 25 minutes, tool maximum 10 | Run in background or resume bounded segments, examining exit status only; overall limit unchanged, exceeded means external waiting |
| No checks yet | Command immediately says no checks reported | Treat as not started; poll at least one minute apart until limit, then external waiting |
| Platform has no blocking watcher | Status query only | Query summary counts at least one minute apart, read full result once finished |
| Local failures | Two unit tests fail | Read failures first, using failure-only framework output if available |
| Normal subagent completion | Implementation #12 hands off PR | Return Handed off, PR link, one reason sentence, one next-step sentence, and task evidence result.md; orchestrator records schedule without reading full result.md |
| Missing/conflicting return | Return says PR submitted but remote cannot find it | Read result.md and verify remote; remote state wins |
| Excessive process return | Hundreds of narrative lines returned | Save only fixed fields, not process in handoff |
| No return after failure | Create/wait errors | Use existing agents.md recovery rules |
| User stops | PR still in review | Generate report; unfinished work Paused |
| Concurrent evidence | Three subagents run | Task IDs distinguish evidence directories; result.md files cannot overwrite each other |
| Sensitive logs | Failure log includes token | Quote only relevant error lines, without copying token into PR/Issue/return |

| Stage | Result | Link | Reason / next step | Orchestrator records |
| --- | --- | --- | --- | --- |
| check-workflow | `clean` or `pr-open` | Cleanup PR if any | One sentence each | check_workflow record and startup_check |
| prepare-work | One-line Issue list or `[]` | None | Per selected item one sentence for relationships/queued resources; one reason for `[]` | Schedule; stop_reason for `[]` |
| execute-work per Issue | Handed off, Not started, or Paused | PR or Issue | One sentence each | Schedule; final change_requests or issues_without_change_request |
| review-and-merge per PR | One of seven report results, or Awaiting repair for edits/main sync | PR | One sentence each | Schedule and change_requests |
| fix-feedback per PR | Handed off after push, Waiting for CI, or Paused | PR | One sentence each | Schedule |
| Leftover cleanup | Retained branches/workspaces | None | None | branch_cleanup |

Static checks do not prove model compliance or any specific token reduction. These instructions do not specify commands for CI systems outside the hosting platform.

## English migration and record compatibility (#118)

Current source rules, newly generated statuses, reports, errors, prompts, and manually prepared handoffs use clear English. Earlier releases used Chinese defaults; translating historical notes does not change that fact. No schema, field name, CLI command, persisted-record path, event model, or version number changes as part of this migration.

The single report specification in `references/report.md` defines current vocabularies and exact aliases for known legacy Chinese result and Agent-state values. On reading structured `handoff.json` or `agent-check.json`, readers map only those known fields in an in-memory copy before validation, counting, and upgrade filtering. Equivalent old, new, or mixed values produce the same merged/actionable counts and upgrade candidates. Unknown values remain invalid. Invalid Agent-check data retains the existing behavior of omitting the optional upgrade section, while invalid handoff data still fails validation. Old free-form records missing required fields still use the existing manual fallback.

Reading does not rewrite original input files or translate user-provided free text such as reasons, next actions, Agent names, or external command errors. New handoff prose must use the required language. Keep original records for recovery. Old readers may reject new English enum values; when rolling source back, use saved old records or continue generating reports with the new reader. Do not automatically reverse-translate or overwrite user records. The migration neither upgrades installed plugins nor grants installation or release authorization.
