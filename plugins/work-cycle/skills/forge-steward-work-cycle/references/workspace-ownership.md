## Workspace ownership records

The orchestrator keeps `workspaces.json` in this run's Git-metadata directory, with one entry per dispatched workspace. It is a JSON list, not a tracked project file, and does not change the `handoff.json` schema. Never infer ownership from a path or branch name. Only the orchestrator writes it.

Each entry requires nonempty `task`, absolute `workspace` path, owning `stage`, `status` (`active`, `finished`, `failed`, or `paused`), and UTC `updated_at` strings, plus `branch`:

- Attached: the real branch string; optional `detached: false` and full `head` object ID. Existing branch-only records remain readable.
- Detached: `branch: null`, `detached: true`, and `head`, a full 40- or 64-digit hexadecimal Git object ID. Record the actual checked-out commit, never a fabricated branch or an abbreviated ID.

Before dispatch, replace the entry for that exact absolute workspace with its current identity and status `active`. After confirmed completion, reread its identity and set `finished`, `failed`, or `paused`; a stage may have detached or changed its head. Preserve other entries. Stop or interruption leaves evidence for recovery, not permission to guess completion. Pass the record and the current active-workspace list to cleanup.

The inventory normalizes empty/whitespace branches to null and hexadecimal heads to lowercase in memory only. Legacy empty/null branches without both `detached: true` and a full head remain readable but unverified, with a retention reason. A missing branch field, malformed head/flag, missing required ownership field, unknown status, relative path, or duplicate canonical workspace is a record error. Identity disagreements or a recorded branch/head that differs from Git retain the worktree, including under the conventional directory. Unrecorded external workspaces remain unowned.

Recognizing a matching detached identity does not authorize removal: detached HEAD remains a retention condition. Current, caller-active, owner-active, locked, dirty, untracked, missing, unreadable, and open-request protections still apply. Recheck live identity and all cleanup conditions before any separately authorized removal; inventory is read-only and never deletes or prunes.

Keep original records for recovery. Old readers may reject null branches: use a reader supporting this format, or retain the worktree. Do not rewrite legacy evidence or invent missing heads to satisfy an older reader.
