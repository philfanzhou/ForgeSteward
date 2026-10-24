# Resource scope investigation

The bounded experiment demonstrates that two repositories can each acquire a
capacity-1 `heavy` lock and then collide on one simulated exclusive identity.
Repository locks remain useful for worktrees of one repository. They cannot
promise a shared host or environment limit across unrelated repositories.
Keep the current runtime unchanged in this investigation; pursue an explicitly
configured shared coordinator only as separately authorized implementation work.

This report implements [Issue #215](https://github.com/philfanzhou/ForgeSteward/issues/215).
It does not establish the cause of a historical delay, characterize host
saturation, or promise that adding Agents improves production throughput.

## Reproduce and retain the evidence

Use Python 3.9 or newer and Git. Queue the measurement under the existing
work-cycle `heavy` resource, with this run's agreed capacity, before running it.
`REPORT_PARENT` below must name an existing directory owned by the caller. Choose
a new output name on every run; the tool refuses existing directories, files and
symlinks. It accepts no repository, service or lock-root input.

```bash
python3 -B scripts/measure_resource_scope.py \
  --output "$REPORT_PARENT/resource-scope-215" \
  --trials 3 --cpu-seconds 0.25 --memory-mib 4 --deadline-seconds 60
python3 -B -m unittest discover -s tests -p 'test_resource_scope_experiment.py' -v
```

The actual measured command on 2026-10-24 used the same flags and output
`/Users/phil/code/ForgeSteward/.git/forge-steward/runs/20261024T102544Z-eee3/implement-215/measurement-2`.
The run acquired `heavy` capacity 2 as owner
`20261024T102544Z-eee3/implement-215/1`, then released its own slot. This scheduling
lock protects the measurement, separately from the two disposable fixture locks.

The new output contains `results.json`, complete command arguments, stdout,
stderr, exits, PIDs, acquire responses and elapsed times, plus both initialized
repositories, worker configurations and synchronization files. Partial failures
also retain results and diagnostics. No fixture tree is automatically removed;
after checking completion and stopped children, a caller may delete only its own
output. The report reproduces every trial's measurements below, so its findings
do not depend on private workstation access. Full raw output remains in the
task's Git-metadata evidence directory named above.

Defaults are two workers, three trials, 0.25 CPU seconds and 4 MiB explicit
allocation per worker per condition. Hard upper bounds are two workers, five
trials, 0.5 CPU seconds, 16 MiB and a 120-second work deadline. The default work
deadline is 60 seconds. Individual child waits also have ten-second limits
(the bounded acquisition waits three seconds). Cleanup terminates and drains
each started child, escalating after two seconds, with a further two-second
drain limit. At most two acquired fixture locks receive a five-second release
attempt each. This finite cleanup grace can extend the work deadline. Failed
cleanup is an error with retained diagnostics, never a reported successful run.

Inherited `GIT_*` overrides are stripped from child environments. Git uses an
empty task-owned template and ignores system/global configuration. This prevents
an ambient Git directory override from redirecting fixture locks into another
repository. No shell command, network request, real port, daemon, account,
database, profile, credential or privileged probe is used.

## Conditions and causal observations

Every condition uses the same two bounded workloads and explicit capacity 1.
The tool invokes the existing source helper using argument arrays, including its
JSON acquire interface. Exit 0/acquired, exit 1/busy and exit 2/error stay
distinct; a helper error ends the experiment without a configuration retry.

| Condition | Fixture behavior | Observed outcome in all three trials |
| --- | --- | --- |
| Serial | Different repositories, one worker at a time, different marker files | Both acquire; no overlap and no collision |
| Isolated | Different repositories, paired workers, different marker files | Both acquire; two active workers and no collision |
| Shared identity | Different repositories, paired workers, one marker file | Both acquire; two active workers and exactly one expected collision |
| Same repository | Both owners use repository A and capacity 1 | Second wait-zero attempt is busy with the first owner preserved; bounded waiting acquisition succeeds after that owner's release; no collision |

Paired children first publish readiness and wait for the parent's start signal.
For the shared identity, worker 0 creates the marker exclusively and publishes
entry. Worker 1 waits for that entry, observes exclusive creation fail, and
publishes its attempt before worker 0 proceeds. Both publish workload completion
before either releases its marker. The collision is therefore observed while
the owner holds the marker, independent of a lucky launch order. The isolated
control uses the same paired completion barrier with two distinct markers.

In the same-repository condition, the busy response identifies the actual first
owner. The next acquisition command remains pending while that owner is held;
the parent then releases only that owner, observes successful acquisition and
runs the second workload. Recorded command/release timestamps establish this
ordering. The wait-zero response alone is not evidence of a positive queue wait.
Reported acquire elapsed time includes interpreter startup, helper work and
polling, rather than pretending to isolate time asleep in the queue.

## Measurement baseline and limits

Measured 2026-10-24, 11:40:20.993198–11:40:31.393352 UTC, on
macOS 27.0.1 arm64, Python 3.9.6, ten logical CPUs. Source baseline was
`61e47b96d3b53384a25fe2f35de5cb76554dd200`, target version 0.2.26; the new
experiment was uncommitted during measurement. Its SHA-256 was
`5d002ce00a68c50ce5465ef2dbfe960444f6f671bca9ddba5eedbcd5eddb3296`. The unchanged helper SHA-256 was
`49912886389dac32b7bd1a99ccdfa4b5b5f77d42268d7831cd8f929ddcfdbe26`.

Host load averages (1/5/15 minutes, runnable tasks) changed from
`[4.818359375, 5.94482421875, 5.14501953125]` to
`[5.1533203125, 5.97900390625, 5.16650390625]`. Background work was uncontrolled;
load averages cannot attribute pressure to this experiment. Host memory pressure
was unavailable: this implementation has no verified read-only macOS pressure
probe. Configured allocation and child peak RSS are memory-use indicators, not
complete host memory-pressure telemetry. The tool reads Linux memory PSI where
available and explicitly records unavailable reasons elsewhere. Windows child
RSS is unavailable because the standard-library POSIX `resource` module is not
available; no zero or pass is substituted for missing data. CI exercises behavior
on Windows and Linux, but this report's actual measurements are only macOS.

Durations use a process-local monotonic clock and CPU uses `process_time`.
Cross-process worker intervals use Unix epoch seconds because Python 3.9/macOS
does not provide the same monotonic clock origin to every process. These
intervals are subject to wall-clock adjustments; barriers provide the causal
overlap evidence. RSS is each child's lifetime peak, including Python runtime
and allocation: macOS native bytes stay bytes, Linux native KiB multiply by
1024, unverified platforms report a gap. Explicit allocation is exactly
4,194,304 bytes per worker. No thresholds require a faster parallel result.

Each row below gives workers 0/1 in that order. Times are seconds rounded to six
decimal places; raw JSON retains full precision. Total includes lock and child
startup, synchronization and release. `Active` is peak simultaneously active
workers; `Overlap` measures their identity-use intervals, including barriers.

| Trial | Condition | Total | Acquire elapsed 0/1 | Worker wall 0/1 | Worker CPU 0/1 | Peak RSS bytes 0/1 | Active | Overlap | Collisions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | serial | 0.728959 | 0.039454 / 0.039600 | 0.250227 / 0.250248 | 0.250007 / 0.250003 | 19398656 / 19365888 | 1 | 0.000000 | 0 |
| 1 | isolated | 0.449706 | 0.041464 / 0.040595 | 0.250541 / 0.250503 | 0.250007 / 0.250000 | 19398656 / 19431424 | 2 | 0.250693 | 0 |
| 1 | shared-identity | 0.481978 | 0.048083 / 0.045574 | 0.260424 / 0.257916 | 0.250001 / 0.250003 | 19349504 / 19398656 | 2 | 0.267121 | 1 |
| 1 | same-repository | 1.771272 | 0.042021 / 1.067484 | 0.250244 / 0.250572 | 0.250000 / 0.250002 | 19382272 / 19415040 | 1 | 0.000000 | 0 |
| 2 | serial | 0.735986 | 0.041966 / 0.040260 | 0.250671 / 0.250340 | 0.250002 / 0.250002 | 19398656 / 19415040 | 1 | 0.000000 | 0 |
| 2 | isolated | 0.448624 | 0.040665 / 0.041424 | 0.250814 / 0.250812 | 0.250000 / 0.250005 | 19382272 / 19333120 | 2 | 0.251152 | 0 |
| 2 | shared-identity | 0.453695 | 0.040434 / 0.039860 | 0.250743 / 0.250906 | 0.250002 / 0.250003 | 19333120 / 19415040 | 2 | 0.257386 | 1 |
| 2 | same-repository | 1.763070 | 0.040097 / 1.059773 | 0.250411 / 0.250424 | 0.250004 / 0.250002 | 19333120 / 19529728 | 1 | 0.000000 | 0 |
| 3 | serial | 0.769575 | 0.039662 / 0.041266 | 0.250367 / 0.250512 | 0.250000 / 0.250007 | 19431424 / 19333120 | 1 | 0.000000 | 0 |
| 3 | isolated | 0.463260 | 0.056680 / 0.041517 | 0.251013 / 0.250841 | 0.250006 / 0.250005 | 19496960 / 19349504 | 2 | 0.251350 | 0 |
| 3 | shared-identity | 0.455777 | 0.040574 / 0.039224 | 0.250362 / 0.250451 | 0.250004 / 0.250004 | 19365888 / 19333120 | 2 | 0.256965 | 1 |
| 3 | same-repository | 1.755999 | 0.039475 / 1.061398 | 0.250145 / 0.250193 | 0.250000 / 0.250004 | 19333120 / 19415040 | 1 | 0.000000 | 0 |

The three shared-identity collisions support a scope/identity limitation. The
serial and isolated results show that the collision depends on the shared
simulated identity. The same-repository results demonstrate that repository
queuing works within its actual boundary. These small loads neither establish
host saturation nor justify a CPU capacity value. CPU/wall differences and total
times include scheduling noise; no speedup percentage or production-throughput
conclusion follows. All 80 direct subprocesses were drained, final fixture
statuses had no holders, and cleanup reported no errors.

## Resource scope decision

Keeping repository locks unchanged preserves current independently installed
clients and owner recovery, with no configuration or permission change. It is
sufficient for resources isolated to one repository and cannot coordinate an
actually shared identity across repositories. A future shared coordinator would
make that boundary explicit for participating callers, at the cost of new
identity, configuration, access and compatibility obligations. The measurement
supports exploring that option for exclusive identities; it does not choose a
host CPU/memory limit.

| Resource | Appropriate future identity when shared | Decision for this investigation |
| --- | --- | --- |
| `run`, repository merge, repository Issue ownership/registry | Repository identity and, for checkout ownership, its existing checkout identity | Keep repository-local ownership unchanged |
| CPU/memory `heavy` capacity | Explicit host and coordinator identity, agreed capacity | Candidate host scope; capacity needs separate workload evidence |
| Simulator, Docker daemon, browser profile | Actual host/service endpoint and instance/profile identity | Coordinate only when the same underlying instance is shared |
| Fixed path or fixed port | Host plus canonical path, or host/network namespace plus port | Share only for the actual common identity; prefer task isolation |
| Exclusive remote test environment/account | Explicit environment/service/account identity across every participating host | Exclusive capacity 1; a local host lock cannot coordinate machines |
| Per-task temporary path, assigned port, isolated database/profile | Task-specific isolated identity | No additional shared coordination needed |

Resource names alone are insufficient: two `docker` names can mean separate
daemons, and different names can mean one daemon. Remote environments need a
coordinator visible across hosts; a file under one host's directory offers no
cross-machine guarantee. Remote service APIs and Agent-specific access methods
belong in adapters, while the scope/owner rules stay platform-neutral.

## Bounded future design, compatibility and authorization

This is a proposed separate implementation scope, not a shipped interface:

1. Define an explicit opt-in coordinator root and stable coordinator identity,
   including user/security boundary, host or remote environment, canonical
   resource identity and permissions. A shared directory must have documented
   ownership/access for the cooperating Agents; do not assume every client can
   access the same home directory, filesystem or account. Do not infer host
   identity from repository paths or silently create a global directory.
2. Keep repository/run/task/attempt in owner records together with coordinator
   and resource identity. Agree capacity explicitly before use, reject a
   mismatch, and retain exclusive remote capacity 1. Do not silently replace a
   saved capacity to satisfy a new caller. Require finite waits and observable
   errors. Existing polling is not FIFO and offers no starvation-freedom
   guarantee; bounded waiting and an explicit return to scheduling remain
   necessary. A fair queue would be additional scope requiring its own design.
3. Preserve conservative recovery. Age and a stopped acquire-helper PID do not
   prove the owning stage stopped. Confirm the exact stage/owner has ended
   before releasing; preserve active, ambiguous and unknown owners. Do not
   automatically reap slots, use leases as proof of death, or migrate/delete
   current active slots. Crash and inaccessible-host cases require recorded
   human or orchestration confirmation and a bounded waiting outcome.
4. Offer one platform-neutral owner/result contract with Agent/hosting adapters
   for actual access. Participation is cooperative, not hostile-user exclusion.
   Older repository-only clients remain compatible with their existing roots,
   but cannot be counted toward a new shared limit. Inventory actual client
   participation and drain/finish existing work before opting a resource into
   coordination. Do not claim a host-wide guarantee during mixed participation.
5. If the coordinator is unreadable, unwritable or inconsistent, emit an
   observable error identifying the resource and stop work using that shared
   identity. Do not silently fall back to independent repository locks and
   report shared protection. An explicitly authorized scheduler can instead
   serialize verified participating work or choose isolated fixtures, recording
   the limited guarantee. Remote access failure must not trigger local-only
   execution against the same remote environment.
6. Separately authorize configuration, permissions, participating installations,
   root/result schema, adapter changes and rollout before coding/enabling them.
   Implement identity/capacity validation, success/busy/error behavior, finite
   waits, cancellation, simultaneous callers, failed access and conservative
   recovery with disposable cross-repository fixtures. Test old-client
   coexistence and failed migration without touching active roots. A remote
   coordinator and distributed fairness would need separate design slices.

The current investigation changes none of these runtime capabilities, lock
schemas, installed clients, concurrency limits, user configuration, branch
protection or versions. Rollback reverts only the new experiment, tests and this
report. There is no persistent-user-data migration or sensitive data flow.

## Acceptance and scenario evidence

The Issue's original criteria and prepared result table remain authoritative.
This mapping identifies evidence rather than introducing a second protocol.

| Issue requirement/event | Concrete evidence and outcome |
| --- | --- |
| Reproducible risk with no-contention control | Three trials of all four conditions above; `test_all_conditions_metrics_owner_ordering_and_compatibility` asserts each collision/active-count/result and final empty statuses |
| Host capacity versus exclusive environments | Measured small CPU/allocation/RSS/load limits above; resource-scope decision distinguishes host capacity, local identities and cross-host exclusive environments |
| Migration, compatibility and authorization | Six-step future design above, unchanged helper bytes assertion, no production changes; new runtime work requires separate authorization |
| No guaranteed throughput gain or disruption | Explicit limits, no performance threshold; exclusive new output, fixed fixture roots and child cleanup; full measured output has no surviving fixture holders |
| Serial or isolated identities | Both successful and zero collisions; per-worker wall/CPU/RSS/allocation and acquire timing recorded |
| Same common directory busy/wait/release | Busy exit 1 preserves actual owner; pending acquisition starts before release and finishes successfully afterward; individual recorded timestamps and test assertions |
| Shared simulated identity | Both repository acquisitions exit 0; explicit entered/attempted/completed barriers and exclusive marker yield exactly one observed collision per trial |
| Missing/noisy telemetry | Unavailable reasons and background-load limits above; `test_unavailable_telemetry_and_rss_units` checks missing resource and normalization |
| Invalid bounds/output, helper/child failure/deadline | Tests reject NaN/infinite/excessive parent and worker bounds and existing directory/file/symlink, distinguish exit 2 without retry, reject malformed helper output, inject child failure and both work/subprocess deadlines; partial diagnostics retained |
| Cancellation or partial startup | Injected cancellation/start failure plus actual POSIX SIGTERM test; every started child drained and own fixture slots released; Windows skips only the POSIX signal-specific test |
| Foreign data/holders and ambient Git overrides | `test_inherited_git_overrides_cannot_redirect_fixture_locks` retains a foreign fixture holder byte-for-byte while contaminated environment variables cannot redirect child Git commands; all safety tests retain an outside sentinel |
| Shared coordinator recommendation | Supported boundary decision, scope table, recovery/fairness/compatibility/fallback design and separate runtime scope above; no capability enabled |

Local focused tests also cover cleanup after each error and compare production
helper bytes. Existing lock regression tests establish unchanged behavior;
repository wording, Markdown links, Skill budgets, marketplace consistency and
whitespace checks cover form. The full existing suite runs in required CI.
Those checks do not replace the measured scenario evidence or establish
arbitrary Agent compliance, universal fairness or production performance.
