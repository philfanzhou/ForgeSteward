## Batch relationships and verification resources

Each selected Issue's handoff must include three audited, non-speculative items so implementers/callers can schedule work and verification:

1. **Expected changes:** files/directories, modules, external interfaces, and applicable migrations, generated files, and configuration.
2. **Relationships to other selections:** code dependency, overlapping changes, or independent, as below; include other identifiers and evidence. Write “none” for a single selection.
3. **Shared verification resources:** resources local checks use and available isolation methods from the inventory below. Write “none” if unused, or “the entire local suite must queue” if unclear.

### Classify relationships

- **Code dependency:** B's plan uses A's new/changed code, interfaces, data structures, or configuration. Prepare B against A's settled plan and specify the follow-up inspection after A merges: compare A's actual merged changes with B's plan and record any difference in B's original Issue. A must be selected too; if A is not selected, B is not selected. When the other readiness conditions hold, select both, list B after A, record that B waits for A's merge, and establish platform dependency links. B never starts from A's unmerged branch. Dependencies may only point to earlier batch items, without cycles. Every item in a chain counts against capacity.
- **Overlapping changes:** no code dependency, but expected files overlap or changes touch conflict-prone locations: dependency lockfiles, migrations/schema, route/plugin/command registries, generated code, versions, changelogs, localized strings, or shared configuration. Mark the earlier-listed item first and the later item waiting for its merge.
- **Independent:** neither condition holds; implementation may run concurrently.
- If uncertain, treat as overlapping. Do not narrow acceptance, split a single Issue, or exclude candidates to reduce overlap.

### Verification resource inventory

When first needed this run, read test configuration, container orchestration, startup scripts, and CI. Separate local commands requiring no shared resources from those using fixed ports, local databases/caches, containers, simulators/devices, browser profiles, fixed/global write locations, shared remote test environments, or accounts. Record existing isolation options such as configurable ports, database names, container project names, and temporary directories; do not change repository configuration for isolation. Save the inventory in a writable tracker or repository-designated location; when neither exists, keep it in the original Issue handoff or run record. Reuse it across continuous-run cycles, inspecting only changes.

### Output order

Within tier/priority ordering, place each prerequisite and earlier overlapping item before its dependents/followers; explain required reordering during progress. A standalone execute-work processes sequentially and marks items with unmerged prerequisites waiting under its rules, without stacking unmerged code.
