# Capability reuse scenarios

Issue [#211](https://github.com/philfanzhou/ForgeSteward/issues/211) defines one optional run-scoped capability record. The installed contract is [Capability reuse](../plugins/work-cycle/skills/forge-steward-work-cycle/references/capabilities.md), loaded in full from [startup](../plugins/work-cycle/skills/forge-steward-work-cycle/references/startup.md), [stage lifecycle](../plugins/work-cycle/skills/forge-steward-work-cycle/references/subagent-lifecycle.md), and [run records](../plugins/work-cycle/skills/forge-steward-work-cycle/references/run-record.md). Adapters supply safe identities and available invocation methods. This change adds instructions and a reproducible walkthrough, without a production cache implementation or new platform integration.

Run the standard-library fixture:

```bash
python3 -m unittest discover -s tests -p 'test_capability_reuse_rules.py' -v
python3 tests/test_capability_reuse_rules.py --report
```

The [fixture](../tests/test_capability_reuse_rules.py) uses a fake adapter and fixed UTC observation time. It compares stages one minute apart and repeats the reuse walkthrough with the second stage two hours later, after the entry's one-hour deadline. Real adapters must choose and record their own justified freshness deadline and release conditions. No Agent, service, tool executable, real clock, credential, installation, or global configuration is called. The fixture's baseline repeats discovery at both stages; it does not reconstruct every historical caller.

## Reuse walkthrough and counts

A discovery probe tries a fake candidate invocation. An unsuccessful candidate increments the failed-invocation count. Cheap identity checks are counted separately and still happen once per stage under either policy. Current remote reads are separate from discovery; a working choice performs a fresh read at both stages. These counters measure fixture operations, not elapsed time.

| Adapter scenario | Discovery probes, baseline / reuse | Failed invocations, baseline / reuse | Cheap identity checks, baseline / reuse | Current reads, baseline / reuse |
| --- | ---: | ---: | ---: | ---: |
| macOS has no timeout command; existing bounded process method works | 4 / 2 | 2 / 1 | 2 / 2 | 2 / 2 |
| Unsupported pagination flag; explicit page method works | 4 / 2 | 2 / 1 | 2 / 2 | 2 / 2 |
| Unauthenticated route denied; existing authenticated API method works | 4 / 2 | 2 / 1 | 2 / 2 | 2 / 2 |
| Alert-source permission denied | 2 / 1 | 2 / 1 | 2 / 2 | 0 / 0 |
| Optional flag unsupported, with no working alternative | 2 / 1 | 2 / 1 | 2 / 2 | 0 / 0 |

Each reuse trace is `discover`, then `reuse`. The first stage records the safe choice or gap; the second checks the same complete identity and freshness, then uses that choice or preserves that gap. The timeout fixture selects the already available bounded process method; it installs nothing and does not alter the CI deadline. The pagination fixture does not retry the unsupported flag. The authenticated-method fixture's history contains one unauthenticated failure and one authenticated discovery; its second current read returns revision 2 using the authenticated method. No mutable revision is stored in the capability record.

The report's `expired_reuse` traces are `discover`, then `revalidate`, with the same reuse counts in every column above. Expiry blocks direct reuse. The second stage checks the current complete safe identity and release conditions, renews the matching observation in its own proposal, and preserves the working choice or uncovered gap without another discovery probe. For the unsupported optional flag, probes and failed invocations both remain 1, with two cheap identity checks and zero current reads. Boundary regressions also run exactly at the deadline, reject unknown/missing/duplicate identity, and change each identity component after expiry to permit one fresh bounded discovery. Only the orchestrator aggregates a renewed proposal; the original evidence remains unchanged.

## Acceptance and result-model walkthroughs

The following outcomes are checked by the executable fixture, with rule/link guards reported separately. The fixture is an implementation of this documented model for reproducibility, not an independent source of acceptance requirements.

| Input or transition | Concrete outcome and assertion |
| --- | --- |
| Same complete identity, valid freshness, cheap validation passes | All five count scenarios above reuse once; no known failed candidate is retried. Working methods still read current state. |
| Tool upgrade, runtime/host/repository change, safe configuration or authentication mechanism change | Each of the nine identity components is changed independently. Every affected capability discovers again; the prior record is unchanged. Unrelated entries remain reusable after aggregation. |
| Missing/old-run/unsupported-schema/malformed record, missing fields, duplicate matching entries, unknown identity | Fresh bounded discovery; unknown identity produces no reusable proposal. Existing evidence remains intact. |
| Expired observation/deadline | No direct stale reuse. A complete current cheap identity and release-condition match renews the observation without retrying known failed candidates; otherwise follow bounded discovery or unknown/uncovered handling. Only revalidated affected entries are replaced, keeping prior task evidence. The next unchanged stage reuses the refreshed choice. |
| Future, invalid, reversed or timezone-free observation/deadline | Unusable; no renewal from malformed evidence. Fresh bounded discovery remains subject to authorization. |
| Previous permission denial | Preserves `denied` and `uncovered:fixture-source`, makes zero current reads and does not turn denial into an empty successful scan. A changed safe permission indicator triggers rediscovery. Expiry still yields denial when the source remains unavailable. |
| Unsupported capability with no alternative | Preserves `unsupported` and uncovered scope without retrying the same flag. Arbitrary stored command text fails the adapter allowlist and is never invoked. |
| Current request/check/approval/protection evidence needed | Choice selects the read method only. The two working-stage reads return current revisions 1 and 2; no mutable business state is persisted. The fixture models a read, not actual hosting permissions or branch rules. |
| Sensitive probe output | Synthetic sensitive output is omitted before both proposed task evidence and shared-record serialization. Identity stores only the authentication mechanism name and safe configuration revision; no sensitive value or derived credential fingerprint is stored. |
| Concurrent stages and contradictory observations | Stages do not mutate the supplied shared record. Only the fixture orchestrator aggregates proposals; independent keys coexist. Conflicting same-key results remain ambiguous and require revalidation rather than last-writer-wins. |
| Explicit stop and compaction | Stop performs zero new identity checks, probes, or remote reads; saved evidence is retained. JSON-restored same-run state validates and reuses; a new run discovers afresh. No stop is described as cancellation of a running Agent. |
| Reused invocation fails | Invalidates the affected choice and does bounded discovery. It changes no CI deadline, recovery budget, required check, or permissions. |

Caller responsibilities remain explicit: provide current safe identity, report relevant changes, inspect only authorized services, supply a safe release-condition check, and honor the stage's existing failure/waiting conditions when required evidence is unavailable. An unknown safe fingerprint invalidates reuse; it does not authorize reading credentials. The fake adapter excludes raw output by construction rather than claiming to sanitize arbitrary real tool output.

## Compatibility and evidence limits

`capabilities.json` is optional Git run metadata. Older or missing records trigger discovery; there is no production migration. Only the orchestrator writes the shared file, and task observations stay in their own attempt evidence until validated. Rollback ignores the optional record while retaining evidence. The schema contains capability facts only; existing Issue/Change Request screening, scheduling, timing, wait recovery, workspace ownership and detached cleanup retain their own contracts.

Static tests check mandatory relative links, security/authorization boundaries, and LF/CRLF byte headroom. They do not prove that a real Agent loads rules, that a real adapter produces safe fingerprints, or that a service's permissions remain unchanged. Real hosting integration, arbitrary output sanitization and production performance are unmeasured. The fixture counts do not establish a runtime speedup, token-saving percentage, or successful real scan. No version, release, credential, configuration, Agent installation, reviewer-independence rule, required check or protected-branch rule changes are included.
