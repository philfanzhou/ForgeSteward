# Final report

This file alone defines final-report sections, order and English source wording; other rules define field contents.

Before recording results or generating reports, read [all report input fields](report-data.md) in full. Vocabulary and output format remain here.

## Result vocabulary

`result` accepts only these seven values:

- Merged
- Awaiting your approval
- Waiting for CI
- Waiting for external approval
- Paused
- Closed without merge
- Not started

 `Awaiting your approval`: checks passed; repository policy requires maintainer approval. `Waiting for external approval`: another person/system must approve. `Paused`: failed final review after repair three, a real blocker, or unfinished work when stopped; explain why. `Not started`: Issue has no PR. On user stop, still report; mark unfinished items `Paused` with reasons.

## Generation and fallback

1. Run `report` in [run records](run-record.md). Saved run-directory `report.md` is authoritative English evidence; never rewrite it or machine-translate saved records or legacy/user free text on disk.
2. Present a complete Chinese rendering to the user by default. An explicit user language request overrides this default: for English, present the generated output unchanged; for other languages, render it faithfully. Translate headings, outcome labels, all reasons/actions, timing labels, errors/recovery and any upgrade question. Preserve section order, every result/count/reason/action, optional-section conditions, Issue/PR identities, URLs, version strings, commands and technical identifiers. Do not append the raw English report to a translated final reply. Append at most one display-language notes paragraph.
3. Exit `1` means invalid data. Correct the fields listed in `handoff.json` and retry, at most three times.
4. If it still fails, exits `2`, Python is unavailable, or the script cannot run, write the template below manually in the requested/default display language, including the failure explanation meaning `This report was written manually by the model because: ...`; keep the remaining format and rendering guarantees above. Use `summary` timings or derive them from events; if neither exists, render `No record`.

## Specification

The script reads sections, outcomes, and display names here. This sole specification and its English template are source evidence for rendering, not a second final English block. `result_aliases` and `agents.aliases` contain exact legacy input values as Unicode escapes for compatibility data, not output prose. Map aliases in memory before validation; reject unknown values and targets outside current vocabulary. Never rewrite inputs or translate free text. Schema, fields and CLI stay unchanged. On rollback, old readers may reject English values: retain original records; use old copies or the new reader, never reverse-write user data.

```json report-spec
{
  "title": "work-cycle report",
  "sections": ["Conclusion", "Needs your action", "PR results", "Run overview", "Time spent", "Errors and recovery", "Updates available"],
  "results": ["Merged", "Awaiting your approval", "Waiting for CI", "Waiting for external approval", "Paused", "Closed without merge", "Not started"],
  "merged": "Merged",
  "needs_you": ["Awaiting your approval", "Paused"],
  "issue_only": ["Paused", "Not started"],
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
  "waits": {"ci": "Waiting for CI", "lock": "Waiting for local resources"},
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
  }
}
```

## Template

The first six sections always appear in order; write `- None` for empty sections. Add section seven only for a confirmed installable/upgradable Agent or a session package behind the latest release. Omit the entire section when there is no action available; do not add a placeholder.

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
- Existing PRs: <count>, <note>
- Cycles: <completed_cycles> / <requested_cycles>; Stop reason: <stop_reason>
- Concurrency: Enabled, up to <agent_limit>; <note>
- Branch cleanup: <branch_cleanup>

### Time spent
- Total <duration>: Preparation 12, Implementation 48, Review 25 (minutes)
- Including Waiting for CI <duration>, Waiting for local resources <duration>

### Errors and recovery
- <what>. Recovery: <recovery>

### Updates available
- <optional older-session notice, first>
- <installable/upgradable Agent>
- <ask once whether to install or upgrade>
```

Filling rules:

- Use Markdown for `<PR link>`: label `#<number>`, target `url`.
- Needs your action: first PRs with results in `needs_you`, then `Paused` Issues, then extra `needs_you` items. Keep data order within each group and number continuously; their total is the conclusion's count.
- PR results: PRs first, then Issues without PRs (`None` in PR column). An empty Issue list is `None`.
- Omit empty `reason`/`next` parts, including `Next:`. Flatten line breaks to spaces, strip extra ending punctuation, and escape table `|` as `\|`.
- Concurrency disabled or returned to serial: `Concurrency: Disabled; Reason: <serial_reason>`. Omit the separator and suffix for empty notes, likewise for the existing-PR note.
- Last section: follow section-seven rules in [installation checks](agent-check.md).
- Time spent: total is the interval between first and last event; below one hour use `Y min`, otherwise `X h Y min`. Show only stages with completed records, in specification order, then unknown stage names alphabetically as-is. With no stages, omit the colon and suffix. Round minutes to the nearest integer. Missing CI/local-resource waits are `0 min`; with no events, the whole section is `- No record`.
