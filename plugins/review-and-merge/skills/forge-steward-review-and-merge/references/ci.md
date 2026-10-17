## Read logs and wait for checks

This file governs only reading results and waiting for checks, and it defines the single CI wait limit. The stage rules still determine the one retry for unrelated failures and the external-wait status after a timeout.

### Wait limit

Use one limit for all required checks of the current Change Request:

- Recent runs are the last 10 successful completed runs of that required check on the default mainline that finished within 90 days.
- Use twice the median completed duration of the recent runs. If no run qualifies, use 30 minutes.
- Cap the limit for each required check at 60 minutes, then use the largest capped limit across all required checks.
- A rerun shares the original limit and does not start a new one. One long historical run cannot raise the limit past the cap.

### Find the failure

1. Identify the failed check and step. Read that step's log, working backward from the error. For example on GitHub, use `gh run view <run-id> --log-failed`, then extract the nearby error context.
2. If insufficient, expand backward in sections or read relevant other steps. “Read the end first” is not a limit: inspect any position needed, but never load the entire log at once.
3. For local test output, also start with failures; prefer existing repository/framework options that show failures only.
4. In Change Requests/Issues, quote only the few error lines and run link, never full logs, secrets, or tokens.

### Wait for completion

1. Prefer platform commands that return when checks finish, such as GitHub's `gh pr checks <number> --watch --interval 60` or `gh run watch <run-id> --exit-status --interval 60`. Non-terminal refreshes repeatedly print the whole table, so discard that output and inspect only the exit status. Once finished, query once for final results.
2. If a call exceeds the execution tool's duration limit, run it in the background or resume in segments, still reading only exit status per segment. Count all segments toward the original total wait limit.
3. If no checks exist yet, use the existing “not starting” rule: check again no sooner than 1 minute later and mark waiting for external checks after the limit.
4. Without a wait-until-finished command, query at intervals of at least 1 minute, fetching only counts of running/failed checks rather than the full table. Read the full final result once after completion.
