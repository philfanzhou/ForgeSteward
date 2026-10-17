# Report input fields

During the run, save results in `handoff.json` in the run directory (the short handoff in [run records](run-record.md); retain other existing fields, which the report does not read). Before writing, verify actual remote state. The script checks format and vocabulary, not agreement with the remote.

| Field | Content |
| --- | --- |
| `requested_cycles`, `completed_cycles` | Requested maximum (positive integer), completed cycles (integer) |
| `stop_reason` | One plain-English sentence explaining why the run stopped |
| `startup_check` | Whether check-workflow ran or was skipped, and the cached version and time |
| `release_audit` | Optional release-audit result: `result` (`clean`, `findings`, `incomplete`, `not-run`); one-sentence `summary`; `evidence` (the check-workflow `result.md` path); optional `findings` and `unknowns` lists. Use redacted text only, and record it from the stage's `result.md` under [Startup](startup.md). Older handoffs without it stay valid |
| `startup_queue` | Existing PRs: `count` and handling `note` (may be empty) |
| `concurrency` | `enabled`; when enabled, `agent_limit`; otherwise or after falling back to serial, `serial_reason`; optional `note` for CI queueing with several PRs, whose added delay is not time saved |
| `branch_cleanup` | Cleanup results, including retained branches and workspaces |
| `change_requests` | Each PR: `url`, `number`, `issues` (Issue list), `result`, `reason`, `next` |
| `issues_without_change_request` | Each Issue without a PR: `issue`, `result` (only `Paused` or `Not started`), `reason`, `next` |
| `exceptions` | Each actual error in `what`; state checks, recovery actions and results, last confirmed remote state, unfinished stages, and recovery conditions in `recovery` |
| `needs_you` | Optional additional actions for the user, one sentence per item |
| `agent_check` | Optional [Agent installation check](agent-check.md): `file` is its result filename in the run directory; if unavailable, only an `unavailable` reason; omit the last section if absent |

All fields except the optional `needs_you`, `release_audit`, and `agent_check` are required; lists may be empty. `reason` and `next` may be empty strings, but `Awaiting your approval` and `Paused` require a reason. Use integer Issue numbers or cross-repository text such as `owner/repo#5`.
