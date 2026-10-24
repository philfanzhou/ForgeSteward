# Final report

This file defines final report sections, order, and wording.

Before recording/reporting, read [report input fields](report-data.md) in full.

## Result vocabulary

`result` accepts only these seven values:

- Merged
- Awaiting your approval
- Waiting for CI
- Waiting for external approval
- Paused
- Closed without merge
- Not started

`Awaiting your approval`: checks passed, policy requires maintainer approval. `Waiting for external approval`: another person/system must approve. `Paused`: failed third-repair final review, real blocker, or unfinished work at stop; give reasons. `Not started`: no PR. User stop still requires a report with unfinished items `Paused`.

## Generation and fallback

1. Run `report` per [run records](run-record.md); it saves run-directory `report.md`. Paste output unchanged with at most one additional-notes paragraph.
2. Exit `1`: correct listed `handoff.json` fields and retry at most three times.
3. After failure, exit `2`, missing Python/script, use the template manually. Start `This report was written manually by the model because: ...`. Keep its format; use `summary`/events timings, else `No record`.

## Specification

Alias maps hold exact legacy inputs as Unicode escapes. Map in memory to current values before validation; reject unknown values, preserve records/free text. Handoff fields remain; `release_audit` is optional. Older readers may reject values or miscount events; rollback requires saved originals and a matching reader, never rewriting.

```json report-spec
{
  "title": "work-cycle report",
  "sections": ["Conclusion", "Needs your action", "PR results", "Run overview", "Time spent", "Errors and recovery", "Updates available"],
  "results": ["Merged", "Awaiting your approval", "Waiting for CI", "Waiting for external approval", "Paused", "Closed without merge", "Not started"],
  "merged": "Merged",
  "needs_you": ["Awaiting your approval", "Paused"],
  "issue_only": ["Paused", "Not started"],
  "release_audit_results": {"clean": "Clean", "findings": "Findings", "incomplete": "Incomplete", "not-run": "Not run"},
  "result_aliases": {
    "\u5df2\u5408\u5e76": "Merged",
    "\u7b49\u4f60\u5ba1\u6279": "Awaiting your approval",
    "\u7b49\u5f85 CI": "Waiting for CI",
    "\u7b49\u5f85\u5916\u90e8\u5ba1\u6279": "Waiting for external approval",
    "\u5df2\u6682\u505c": "Paused",
    "\u5df2\u5173\u95ed\u672a\u5408\u5e76": "Closed without merge",
    "\u672a\u5f00\u59cb": "Not started"
  },
  "stages": {"check-workflow": "Rule checks", "prepare": "Preparation", "implement": "Implementation", "review": "Review", "fix": "Repair", "merge": "Merge", "cleanup": "Cleanup"},
  "waits": {"ci": "Waiting for CI", "lock": "Waiting for local resources", "review": "Review wait", "external": "Waiting for external approval", "other": "Other waits"},
  "agents": {
    "absent": "Agent not installed",
    "current": "Current",
    "other_scopes": " (also installed outside user scope)",
    "ask_for": ["Missing", "Incomplete", "Behind"],
    "ask": "{names} can be installed or upgraded to v{latest}. Install or upgrade now?",
    "statuses": {
      "Missing": "{name}: Not installed (latest v{latest})",
      "Incomplete": "{name}: Missing {missing} (latest v{latest})",
      "Behind": "{name}: {versions}, behind latest v{latest}",
      "Current": "{name}: Already current at v{latest}",
      "Ahead of latest release": "{name}: {versions}, newer than the latest release; no action",
      "Unknown": "{name}: Unknown: {reason}"
    },
    "aliases": {
      "\u672a\u5b89\u88c5 Agent": "Agent not installed",
      "\u7f3a\u5c11": "Missing",
      "\u4e0d\u5b8c\u6574": "Incomplete",
      "\u843d\u540e": "Behind",
      "\u6700\u65b0": "Current",
      "\u9ad8\u4e8e\u6700\u65b0\u6b63\u5f0f\u7248": "Ahead of latest release",
      "\u65e0\u6cd5\u5224\u65ad": "Unknown"
    },
    "session_old": "This session uses older version v{session}; latest is v{latest}",
    "ask_session": "You can upgrade to v{latest}. Upgrade now?"
  },
  "timing": {"wall": "Total wall time {duration} (includes gaps and suspension)", "stages": "Accumulated completed stage time: {stages} (minutes; stages can overlap)", "active": "Active wall time {duration} (completed interval union)", "partial_active": "Active wall time incomplete; completed intervals cover {duration}", "suspension": "Suspension {duration} (accumulated; may overlap)", "wait_basis": "Matched waits are accumulated; {overlap}; included in stages", "overlap": "overlap is present", "no_overlap": "no overlap in recorded intervals", "ongoing": "Unfinished attempts: {attempts}", "diagnostics": "Timing incomplete: {diagnostics}"}
}
```

## Template

The first six sections always appear in order; empty: `- None`. Section seven needs an installable/upgradable Agent or older session package. Omit the entire section when there is no action available; no placeholder.

```markdown
## work-cycle report

Conclusion: <merged PR count> PRs merged; <action count> items need your action. Completed <completed_cycles> cycles (limit <requested_cycles>); <stop_reason>.

### Needs your action
1. PR <PR link> <result>: <reason>; Next: <next>.
2. Issue #<issue> Paused: <reason>; Next: <next>.
3. <one needs_you item>.

### PR results
| PR | Linked Issues | Result | Details |
|---|---|---|---|
| <PR link> | #<issue>, #<issue> | <result> | <reason>; Next: <next> |
| None | #<issue> | <result> | <reason>; Next: <next> |

### Run overview
- Startup check: <startup_check>
- Release audit: <summary>; Result: <result>; Findings: <all findings>; Unknowns: <all unknowns>; Evidence: <path>
- Existing PRs: <count>, <note>
- Cycles: <completed_cycles> / <requested_cycles>; Stop reason: <stop_reason>
- Concurrency: Enabled, up to <agent_limit>; <note>
- Branch cleanup: <branch_cleanup>

### Time spent
- Total <duration>: Preparation 12, Implementation 48, Review 25 (minutes)
- Including Waiting for CI <duration>, Waiting for local resources <duration>, Review wait <duration>, Waiting for external approval <duration>, Other waits <duration>

### Errors and recovery
- <what>. Recovery: <recovery>

### Updates available
- <optional older-session notice, first>
- <installable/upgradable Agent>
- <ask once whether to install or upgrade>
```

Filling rules:

- Use Markdown for `<PR link>`: label `#<number>`, target `url`.
- Needs your action: PRs in `needs_you`, then `Paused` Issues, then extra `needs_you` items; preserve group order, number continuously, and use the total in the conclusion.
- PR results: PRs, then Issues without PRs (`None` PR column); empty Issue list: `None`.
- Omit empty `reason`/`next` including `Next:`; flatten line breaks, trim ending punctuation, escape table `|` as `\|`.
- Release audit: only when present; include summary, display name, every finding/unknown, and evidence. Omit empty `Findings:`/`Unknowns:` parts; preserve older handoffs.
- Disabled/serial concurrency: `Concurrency: Disabled; Reason: <serial_reason>`. Omit separators and suffixes for empty concurrency or existing-PR notes.
- Last section: follow section-seven rules in [installation checks](agent-check.md).
- Time spent: total is first-to-last event. Use `Y min` below one hour, else `X h Y min`; round to nearest minute. Show completed stages in specification order, then unknown names alphabetically. Missing waits are `0 min`; no events means `- No record`. Unambiguous legacy records retain the template line (omit its colon/suffix without stages). New/ambiguous records use `timing`: elapsed wall time, completed stage sums, active interval union (incomplete with open/ambiguous attempts), suspension, matched waits/overlap, unfinished attempts, and diagnostics. Waits remain in stage occupancy; never subtract overlapping waits twice or claim CPU time. Summary: seconds; never reconstruct ambiguous legacy events.
