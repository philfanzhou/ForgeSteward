## Rule retention and recovery

Read this file in full before starting a run, dispatching a stage, or recovering changed/missing plugin paths. Follow [Complete bounded rule loading](rule-loading.md) for complete reads and current-context coverage. These rules add run-scoped retention, never an installation, plugin refresh, version bump, or automatic compatibility decision.

### Find usable Python

Try `python3 --version`, `py -3 --version`, then `python --version`; use the first working Python 3.9+ command, avoiding Windows stubs that only open the store. Substitute it for `python3` throughout these rules. Check before `start`. If none works, record it in the handoff, continue delivery, and use [Final report](report.md)'s manual fallback.

### Resolve and retain the complete set

Resolve the actual installed work-cycle package and all five stage packages before any stage writes. Check the host/installation contract permits a retention copy. Use only these authorized package roots, never a parent cache directory or unrelated user files. The bundled helper includes complete package-local resources, empty directories, stage VERSION markers, work-cycle scripts/VERSION, scripts/agents.json, all helpers and their relative resources (including references/report.md). Python bytecode caches are regenerable and excluded. Missing required resources, nonregular files, escaped links and symlinks fail closed. Other independently installed Skills acquire no dependency on work-cycle.

After `run_record.py start`, use the resolved work-cycle helper. Repeat `--package name=<actual-skill-directory>` for **each** name: `work-cycle`, `check-workflow`, `prepare-work`, `execute-work`, `review-and-merge`, `fix-feedback`:

```bash
python3 <resolved-work-cycle>/scripts/rule_snapshot.py resolve --expected <value> --package <name=directory> ...
python3 <resolved-work-cycle>/scripts/rule_snapshot.py create --repo <target-repository> --run <run-id> --expected <value> --package <name=directory> ...
```

The ellipsis means the other five repeated package arguments, not a literal argument. Save `resolve` JSON in run-directory `rules-source.json` before copying, including when copying is unsupported. The original canonical path, unified version, rule hash, every resource path/hash/size, and package/set identities identify the resolved set. The create result must have the same set identity; otherwise stop and inspect the source change. Versions alone cannot establish identity: two roots/content sets at the same version stay distinct.

Only the orchestrator creates retention at `<run-dir>/rules/`, in the target's Git common metadata. Creation checks all six sources, verifies each copied tree, then publishes the manifest and tree together. An existing rules directory is never overwritten. `.rules.lock` serializes creation; on interruption preserve evidence and inspect the named guard/staging paths. Remove a leftover guard or incomplete `.rules-*` directory only after confirming its writer stopped; never use incomplete staging for dispatch. Creation failure leaves existing run state untouched. The caller must keep published copies immutable; hashes detect changes but are not a defense against a writer replacing both code and its trust evidence.

Pin the returned set identity and `<run-dir>/rules/manifest.json` in the shared handoff and every task dispatch; keep `rules-source.json` as the independent identity anchor. Use **all** stage/rule/helper paths from the returned retained package map for the rest of this run, including locks, events and wait-end. Do not mix source and retained paths. Before each dispatch, before resuming affected writes, and after an external wait, validate from the retained helper:

```bash
python3 <retained-work-cycle>/scripts/rule_snapshot.py validate --manifest <run-dir>/rules/manifest.json --identity <pinned-identity> --expected <value>
python3 <retained-work-cycle>/scripts/preflight_versions.py --expected <value> --skill-dir <retained-stage-directory> --rules-manifest <run-dir>/rules/manifest.json --rules-identity <pinned-identity>
```

Stages run the second command before their first write. It validates the entire retained set and requires a retained stage path, while its default marker-only interface and exit codes remain unchanged. Validation never needs the original cache: removal between dispatch and wait-end can continue using the verified retained helpers. A hash, path, marker or dependency gap stops affected writes, naming the gap; a readable partial tree is not sufficient. Helpers cannot self-authenticate against hostile replacement; use the pinned evidence and trusted helper before executing changed code.

### Explicit transition when retention cannot be used

If retention is forbidden, unavailable, missing or damaged, record the exact reason and stop affected writes. Keep original run/task/attempt identities, review rounds, heads, completed remote writes, append-only evidence, and original CI/lock/external wait start times and deadlines. Do not retry an ambiguous external write or restart a wait budget. Never repair recovery by installing/updating plugins or rewriting saved identities.

Resolve **all six** actual installed packages afresh with `resolve`, checking a single expected unified version and complete resources; mixed, missing or unknown packages cannot continue. Save the new manifest separately, compare old/new paths, versions and hashes, and record an explicit transition in the handoff with affected tasks, compatibility decision and evidence. Re-resolve and compare the complete set before each affected continuation when immutable retention is unavailable. Run marker preflight against each new stage, reload changed current-stage rules in full with new coverage/context evidence, and give every resumed stage the same new package map and helper paths. Preserve old manifests. Only a documented compatible complete set permits continuation of the same run/attempt and deadlines. Uncertain compatibility returns a recoverable handoff naming old/new identities, exact missing paths, affected action and the validation/rule reload needed; no silent partial switch is permitted. This is a caller-reviewed recovery path, not automatic compatibility across arbitrary rule changes.

### Retention lifetime

Keep rules, original identities and transitions with the run's evidence until ordinary run-directory pruning removes that script-created run. `run_record.py` retains the latest 20 such directories; existing pruning removes the whole rules subtree together. Do not delete source caches, add marketplace entries, change global configuration, or retain package copies outside approved run metadata. Older run readers may ignore the additive rules files; rollback needs a matching verified reader/package or a recoverable handoff, never rewritten events or evidence. Unreadable retention storage cannot guarantee continued execution.
