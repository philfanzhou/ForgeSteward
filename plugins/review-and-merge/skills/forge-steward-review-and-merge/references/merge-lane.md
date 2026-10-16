## Merge lane

Use when the repository already has a platform merge queue, or when an approved, conflict-free Change Request cannot merge solely because policy requires an up-to-date branch. Merge these one at a time instead of syncing every remaining request after each merge. All other merge conditions still apply individually without relaxation.

When the caller supplies an approved list awaiting this lane, do not repeat reviews; follow this section in supplied order (prerequisites first, then original priority). Newly approved items during execution wait for the caller's next lane run.

### Existing platform merge queue

- Once all merge conditions except branch freshness hold, enqueue under repository process and wait; neither sync mainline yourself nor acquire `merge`. Do not enable a queue or auto-merge for the repository.
- After successful queue merging, follow [Post-merge work](post-merge.md). If rejected for conflicts, send to repair for mainline sync. For failed checks, apply [Review](review.md)'s CI rules, treating related failures as required changes.
- Use the CI wait limit for queue results; timeout means waiting externally. Follow [Read logs and wait for checks](ci.md).

### Without a queue: sync and merge individually

For concurrent invocation, acquire the caller's `merge` lock and release after the entire lane or on error. Standalone invocation needs no lock. For each item:

1. Fetch latest mainline and try a local merge into this head without pushing. Do not resolve conflicts; return them to repair as sync needed and continue. If source is unwritable, such as a fork, record author sync needed and continue.
2. Without conflicts, merge mainline into this source branch and push, or use the platform's update-branch feature. Never force-push or alter this request's own changes; a conflict-free mainline merge is not code modification. Sync only the current item. Mainline-only pushes do not count as review rounds.
3. Await required checks triggered by this push using [Read logs and wait for checks](ci.md), with [Review](review.md)'s wait/failure rules. Send related failures to repair as required changes and continue.
4. Confirm the new head differs from reviewed head only by mainline integration and matches the platform's automatic merge result. If mainline overlaps request files or both sides touch dependency lockfiles, migrations, registries, generated code, versions, changelogs, localized strings, or shared configuration, confirm step 3 covered affected checks and run missing ones. Do not merge on failed verification; record why.
5. If all other merge conditions still hold, merge, complete [Post-merge work](post-merge.md), then continue.

For each item report merged, sent to repair (conflict/related check failure), author sync needed, or waiting externally, plus check-wait and merge durations.
