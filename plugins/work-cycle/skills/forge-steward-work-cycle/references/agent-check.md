## Other Agent installations and upgrades

Only the work-cycle orchestrator does this; the five stage skills and their subagents never check, ask, or install. At run start, inspect user-level ForgeSteward installations/versions for local Agents without changes and compare to GitHub's latest stable release. At report time list only actionable installations/upgrades or an older session package, and ask once. Install/upgrade only after explicit consent, affecting user scope only and never the maintained repository.

### Check at startup

1. After [Run records](run-record.md)'s `start`, use confirmed Python to run this package's:

   ```bash
   python3 <skill-directory>/scripts/agent_install.py check --json --output <run-directory>/agent-check.json
   ```

   Detection comes entirely from adjacent `agents.json`. The script is read-only: no shell for external commands, at most 20 seconds each. It first queries `gh release view`, then GitHub API without credentials on failure, accepting only stable `vX.Y.Z` releases. An unreadable Agent becomes “Unknown”; others continue. Exit `0` means check completed regardless of results; `2` means argument/environment error.
2. Do not delay the main flow: background the command when supported and continue; otherwise run directly. Wait at most 60 seconds from start, then stop waiting and treat as timed out.
3. Record `agent_check` in `handoff.json` under [Final report](report.md). For exit `0` with a written file use `{"file": "agent-check.json"}`. For exit `2`, timeout, interruption, unavailable Python, or sandbox blocking use `{"unavailable": "<reason>"}` with a short everyday-English reason such as “Timed out,” “Interrupted,” or “No usable Python.” Run once, without retries or blocking delivery.
4. `report` renders installation results from that file and [Final report](report.md)'s specification. Keep generated evidence unchanged; present it under that file's display-language rules without changing status meanings or guessing versions. Retain check results in the run directory if the user stops.
5. Inspect user scope only, not project installations, other machines, or remote environments. Unverified CLI-format changes yield “Unknown.” Codex data was verified with macOS CLI `0.157.1`: filter `plugin list` to the `forge-steward` marketplace, avoiding unrelated remote catalog fetches while reading `installed[].pluginId` and `version`. Keep 20-second command/60-second overall limits. Do not assume older CLI support. Unsupported options, failures, timeouts, or format changes mean “Unknown,” without retries, unfiltered fallback, or reading internal caches for missing results.

### Report section seven

Follow `agents` in [Final report](report.md). Latest must be a confirmed three-integer version; list only `ask_for` statuses (`Missing`, `Incomplete`, `Behind`), excluding current, unknown, development, or absent Agents. If latest is unknown, check not run/unavailable, file missing, or format unrecognized, omit the entire section while generating the first six and retaining check JSON.

Read this session's version only from the running work-cycle package's `scripts/VERSION` and compare to check-file `latest.version` as three integers. Never use repository version, install inventory, or a guessed Agent name. If older, place `session_old` first. With missing/invalid version, do not guess, but still list actionable Agents. Equal/newer packages get no session notice.

Append `other_scopes` for listed Agents also installed outside user scope. `{versions}` is deduplicated “vX, vY”; `{missing}` is “a, b.” For actionable Agents append one `ask` line with comma-separated `{names}`; for only an older-session notice use `ask_session`. Ask once even when both apply. With neither, omit the section.

### Ask at completion; install only after consent

1. Posting the report ends the run; do not wait for a reply. Continue only after later explicit consent, possibly for selected Agents. Do nothing on refusal, silence, or ambiguity; do not remember refusal as a future opt-out. Check/ask again next run. Silence is not consent.
2. An older-session notice does not identify an Agent installation and cannot construct `apply --agents`. If the user agrees only to session upgrading without naming the actual Agent, use check records to clarify which Agent. After consent, take approved `id` values from `agent-check.json` and use the report's target version:

   ```bash
   python3 <skill-directory>/scripts/agent_install.py apply --version <X.Y.Z> --agents <id,id>
   ```

   Pass only approved Agents/version. The script rechecks first. Changed latest release returns `3` without changes: rerun `check` and ask for the new version. An existing installer lock in the system temporary directory also returns `3`; tell the user without deleting it. Skip Agents already current or newer than target; never downgrade.
3. Process Agents independently, continuing after individual failures; determine success from a post-action recheck. Claude Code, Codex, and ZCode always use `agents.json` upgrade commands, installed or not: list marketplaces before changes; uninstall old user plugins while retaining data; remove `forge-steward` marketplace only if present; add target-version marketplace source and install each plugin. If marketplaces cannot be listed, change nothing for that Agent and report that marketplace existence could not be checked. Leave project/local installations untouched. Stop that Agent on a failed step. OpenCode/DeepSeek Harness use source matching the version tag commit: reuse a clean matching local copy, otherwise download tag source temporarily and verify its commit; mismatch prevents installation. Install missing skills, update old ones, uninstall retired ones. Do not overwrite modified, unrecorded, or linked copies. Remove temporary source afterward.
4. Exit `0`: all actions/cleanup complete. `1`: an Agent failed or cleanup incomplete, explained line by line. `2`: argument/environment errors before changes only, such as invalid arguments/unreadable data, with no changes. `3`: stopped before changes, including temporary-directory creation failure. Unexpected file errors after changes begin belong to the current Agent; recheck and continue others. Report temporary/lock-directory cleanup failures separately; remove locks manually only after confirming no installation runs. Keep every output line unchanged in evidence and faithfully render it in the requested/default user display language: what installed, target version, failures/reasons, and recovery (resolve cause, then consent again to rerun). If upgrading the running Agent, explain that this session retains its old version and a new session is required.
5. If networking/user-directory writes are blocked, report accurately and provide the same command for the user; do not switch installation methods.
