## ForgeSteward Workflow Constraints

This block is maintained from a standard template by the ForgeSteward check-workflow skill. Every run replaces the whole block with the template, so do not edit inside it. Put project-specific constraints outside the block; where project rules outside the block differ from this block, the project rules take precedence.

Below, a Change Request is a change awaiting review and merge, such as a Pull Request or Merge Request; Review Feedback is a Comment, Discussion or Review Thread on a Change Request.

### Stages and authorization

- Work has four stages: preparation, implementation, review and merge, and repair. Each stage can run on its own; none requires running another stage first or starts the next stage automatically.
- Reading and analysis, editing issues, changing code, pushing, opening Change Requests and merging each need their own authorization. Mentioning or automatically loading a skill does not authorize external writes or merges.
- Do not bypass branch protection, required approvals or platform permissions.

### Preparation

- Preparation covers investigation, experiments, converging on a design and updating issues. It does not commit production code or open implementation Change Requests.
- An issue is ready only when all of the following hold:
  - The original issue, or evidence it links to, states the scope, exclusions, implementation plan, individually verifiable acceptance criteria, owning repository and dependencies;
  - The relevant code, tests and contracts have been audited against a recorded baseline;
  - No open Change Request covers the same scope, and the work does not depend on unmerged code.
- Labels, a clear description or past CI results do not prove readiness on their own; chat history does not replace a handoff written to the original issue.
- Security or robustness work states what is guaranteed and what is not.
- When the mainline has a blocker that can be advanced without outside input, advance it first. For a genuine external blocker, record the paths tried, the missing input, the responsible role and the unblocking condition; do not repeat the same investigation while conditions are unchanged.

### Implementation

- Implement an explicit issue list in its given order; do not discover or add tasks during implementation.
- Start each item on its own branch from the latest mainline at that time, without stacking other unmerged changes; open a separate Change Request for each item and link it to the original issue.
- The issue's exclusions are binding: no opportunistic refactoring and no absorbing unrelated problems.
- Map each acceptance criterion to an assertion or checkable evidence and its result; also verify applicable failure, cancellation, security and concurrency behavior. Passing CI does not replace item-by-item acceptance.
- When one item is blocked, record why and what would unblock it, then continue with the remaining independent items until the whole list has been handled.

### Review and merge

- Merge only when all of the following hold: every acceptance criterion in the original scope is met; required checks pass; no in-scope blocking feedback is unresolved; approvals, conflict status and branch protection satisfy repository policy; the head at merge time matches the reviewed head.
- Review Feedback falls into four categories:
  - In-scope required fixes: tied to a specific acceptance criterion or guarantee, with evidence and a completion condition;
  - Independent pre-existing defects: deduplicated and tracked separately; they do not block this change unless they break its acceptance;
  - Optional suggestions: when the repository sets no review budget, they need not be implemented in this change and do not block merging;
  - Platform gates: reported separately, not treated as code defects.
- For scope disputes, record the disagreement, the decision maker and the resolution condition; do not expand the implementation just to satisfy feedback.
- After merging, verify the original issue's acceptance before closing it; where parent and child items exist, check the remaining scope of each direct parent in turn.

### Repair

- Fix only in-scope required fixes, CI failures deterministically caused by the current branch, and confirmed acceptance gaps.
- Commit and push to the original Change Request branch, then hand it back for re-review. Repair never merges; pushed does not mean accepted.

### New findings

- Search open and closed records first to avoid duplicates.
- Link acceptance gaps in closed tasks back to the original issue and Change Request and record them as rework; track independent defects and optional improvements separately without expanding the current scope.
- Do not re-report an accepted non-guarantee as a defect without new evidence.

### Handoff and status

- Keep work recoverable across sessions: record issue and Change Request links, owning repository, baseline and head, acceptance evidence, Review Feedback categories and rounds, resolved feedback, accepted boundaries, blockers and next steps.
- Switching sessions or agents does not reset review rounds or reopen resolved feedback.
- Distinguish ready, submitted, accepted, merged and closed; neither ready nor submitted is grounds for closing the original issue.
- Clean up only temporary environments created by the current task that hold no unsaved work; keep branches of open Change Requests.
