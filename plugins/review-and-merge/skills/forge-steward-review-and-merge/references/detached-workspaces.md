## Disposable detached stage workspaces

Before considering any detached workspace for reclamation, read this file in full. Identity alone is insufficient. This exception applies only to a disposable workspace explicitly named by this run's ownership record, with `disposable: true`, `status: finished`, `branch: null`, `detached: true`, and an exact full recorded/current head match. Legacy, failed, paused, unknown-owned, or ambiguous resources remain untouched, including under the conventional directory. Never infer ownership from a path.

### Prepare and refresh the checks

Keep ownership writes with the orchestrator. Cleanup saves its separate `disposal.json` beside `workspaces.json` in the run's shared Git-metadata directory. Save complete handoff/evidence there before disposal; inspect ignored files and move any needed evidence or build output there too. Clean Git status does not prove ignored files dispensable. Preserve original ownership, handoffs, and evidence after reclamation.

Use one JSON-list entry per candidate, with these fields:

| Field | Required meaning |
| --- | --- |
| `workspace`, `task`, `head`, `owner_updated_at` | Exact absolute workspace, owning task, full lowercase current head, and ownership entry's update time; mismatches retain |
| `checked_at` | UTC ISO timestamp of the final checks |
| `inactive: true` | Caller freshly confirmed no stage, run, conversation, or tool still uses it; also pass every current/active workspace to inventory |
| `requests_clear: true` | Caller refreshed associated requests and confirmed none is open or using this workspace/head |
| `evidence_complete: true`, `handoff`, `evidence` | Confirmation of complete saved records, absolute nonempty handoff file, and nonempty list of absolute readable evidence files in this run directory, outside the workspace even after resolving symlinks |
| `ignored_paths` | Sorted exact list of ignored relative file paths from `git ls-files --others --ignored --exclude-standard -z`; caller inspected all and confirmed every remaining ignored file dispensable; use `[]` when none |
| `lifecycle` | `{ "kind": "git" }` only after confirming an ordinary Git workspace; for host-managed resources use `{ "kind": "host", "artifact": "<host identity>", "archive_supported": true }` after checking the host's supported API |
| `recovery` | One of the two durable proofs below |

Recovery is either:

- `{ "kind": "mainline", "ref": "refs/remotes/<remote>/<mainline>", "tip": "<full current tip>" }`: caller refreshed and confirmed this repository's durable remote mainline. Pass that exact ref with `--mainline`; inventory checks the recorded tip still matches and the detached head is reachable from it.
- `{ "kind": "request", "url": "<request page>", "state": "merged or closed", "head": "<full detached head>", "restorable": true }`: caller verified the request's recorded final head matches and the host can restore it. Squash/rebase history is permitted. An open request, local branch, reflog, or detached HEAD alone is insufficient recovery.

Never invent confirmations to obtain eligibility. Missing/failed host queries or unknown conversation use mean retain. Platform adapters perform host queries and lifecycle calls; core inventory only reports these explicitly supplied facts. A timestamp is an audit detail, not proof of freshness. Immediately before action, refresh ownership, identity, current/active use, requests, ignored-file review, recovery, and lifecycle support; replace the candidate's checks and rerun inventory. Changed facts require retention and a recorded reason.

### Inventory, action, and recovery

Run `scripts/worktree_inventory.py --repo <repository> --ownership <run>/workspaces.json --disposal <run>/disposal.json`, with confirmed `--mainline` when used, repeated `--current` and `--active` paths, and existing branch/request inputs. It remains read-only: each result includes ignored paths, checks, recovery, `reclamation_method`, retention reasons, and counts of inventoried/eligible/retained resources. `removal_allowed` permits only the reported method after the final fresh checks; it is not an automatic deletion command. Other ordinary safety exclusions still apply: dirty, untracked, locked, current, active, missing, unreadable, mismatched, or open-request resources remain untouched.

For an ordinary Git workspace, use `git worktree remove <path>` without force, then read back worktree registration and path state. For a host-managed workspace, use only its supported archive/lifecycle API and artifact identity, preserving host metadata; never substitute raw Git removal or filesystem deletion. Verify archive status and metadata by reading back. Unsupported/denied APIs retain it. An ambiguous action result requires readback before retry; never claim success without confirmation. Stop further detached reclamations after a command failure or user stop, and record completed and remaining resources.

Record one outcome per resource in `cleanup.md`: path, task, deletion-time head, method/host identity, saved records, checks, recovery commit/ref or request page, and confirmed removed/archived, retained, failed, or unqueried result. Report retained counts and reasons, without claiming unmeasured disk savings. Recovery recreates an ordinary worktree from the saved durable commit or restores through the verified host/request route; do not rely on a discarded reflog. Rollback restores blanket detached retention while preserving these additive records. Older readers may retain or reject the new facts; never rewrite evidence to bypass them.
