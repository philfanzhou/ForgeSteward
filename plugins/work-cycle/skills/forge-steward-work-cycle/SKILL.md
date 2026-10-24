---
name: forge-steward-work-cycle
description: Review the existing open change requests, then run a bounded number of complete ForgeSteward work cycles with mandatory stage subagents through issue preparation, implementation, repair, and eligible merges. An optional positive integer sets the maximum cycles; the default is ten. Use only for an explicitly requested end-to-end run.
---

# Work Cycle

## Load the rules

Before other rule reads, read [Complete bounded rule loading](references/rule-loading.md) in full, in sections if needed. Then read [Startup and infrequent checks](references/startup.md), [Subagent lifecycle and recovery](references/subagent-lifecycle.md), [Cycles, handoffs, and stopping](references/cycles.md), [Move completed items forward](references/concurrency.md), [Concurrent local verification](references/verification.md), [Run records and timing](references/run-record.md), [Other Agent installations and upgrades](references/agent-check.md), and [Final report](references/report.md) in full. These are required rules; resolve paths from this `SKILL.md`. Follow the loading reference for complete reads, truncation, missing files, and compaction recovery.

Each stage subagent must read its actual installed skill's `SKILL.md` and all references required by that entry in full. This orchestrator does not duplicate or replace the five skills' business rules.

## Input and authorization

Explicit invocation runs preparation, implementation, review, necessary repairs, and eligible merges. The sole optional input is a positive integer limiting work cycles; default to **10** when omitted. Do not ask for another mode or repeated stage confirmations. For an invalid count, request a positive integer instead of guessing. Mentioning the skill, implicit matching, or asking about usage does not authorize execution or merging.

Invocation authorizes the Issue updates, implementation branches, commits, pushes, Change Requests, Review Feedback, and eligible merges needed for this full run. Still obey actual platform permissions, required checks/approvals, branch protection, and owning-repository conventions. Never bypass conditions or describe a commit, CI wait, or repair push as merged. Stop when the user explicitly stops; add no invocation parameters or default human-confirmation steps.

## Subagents are required

The orchestrator only prechecks, decides on infrequent checks, dispatches, waits, verifies handoffs, and summarizes. Every actual `check-workflow`, `prepare-work`, `execute-work`, `review-and-merge`, or `fix-feedback` invocation **must** create a stage subagent that loads and executes that skill. The orchestrator may not do the work itself or have a subagent advise while it acts. Every later review also requires a new review subagent. Await stage results, save a concise traceable handoff, then start dependent stages. When runtime support permits, follow [Move completed items forward](references/concurrency.md): a Change Request belongs to only one stage at a time; stages use separate workspaces; only the orchestrator writes shared progress. Otherwise run stages sequentially.

Before starting, confirm the runtime can create and wait for subagents and that all five stage skills are readable and share this plugin's unified version. Record confirmed capability/skill gaps and stop; never silently fall back to a single agent. Low-quota or near-limit warnings are not missing capabilities. For actual call failures, inspect status and attempt bounded recovery under [Lifecycle and recovery](references/subagent-lifecycle.md); do not stop after one failure. Agent-specific subagent APIs belong in adapters; this skill mandates no platform command. Subagents inherit only this invocation's scope and repository authorization and enforce their own skill's full requirements.

## Overall order

1. Use [Startup and infrequent checks](references/startup.md) to decide whether the target needs one `check-workflow` subagent. Ordinary commits, candidate-file changes, and Change Request creation/merging do not trigger it. It does not count as a cycle. After starting the run record, perform one read-only [Agent installation check](references/agent-check.md), without waiting for it before continuing.
2. At startup, freeze and handle existing open Change Requests through review, necessary repair, and re-review subagents under [Cycles, handoffs, and stopping](references/cycles.md). This does not count as a cycle or depend on prepare-work returning Issues. Skip if none are open.
3. Run at most the requested cycles. Each dispatches preparation, execution, review, required in-scope repairs, and necessary re-review in order. See [Cycles, handoffs, and stopping](references/cycles.md) for detailed handoffs, third-round final review, and stopping.
4. After all stages end, dispatch a cleanup-only `review-and-merge` subagent under [Cycles](references/cycles.md); record a `cleanup` event, set `branch_cleanup` from its audit, and report an explicit-stop skip.
5. Stop starting cycles immediately when prepare-work returns `[]`, even below the limit. A paused Issue/Change Request does not block independent items in that cycle or later work. Check actual remote state and generate/post the [Final report](references/report.md); never infer delivery from cycle counts. If the report asks about other Agent installations/upgrades, act only after explicit user consent under [Installation checks and upgrades](references/agent-check.md). Use clear, everyday English for progress, questions, reports, subagent handoffs, and Issue/Change Request bodies and comments, unless the user or owning repository explicitly specifies another language. Do not copy internal jargon into these outputs; explain any necessary term on first use. Prefer plain terms such as “build output” when referring to artifacts. Restate subagent results in everyday language instead of copying them verbatim.
