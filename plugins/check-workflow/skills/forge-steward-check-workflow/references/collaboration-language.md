# Configure English collaboration defaults

Read this file in full before planning or applying language changes, including check-only. Run **after** policy deletion and [Claude entry migration](agent-entrypoints.md), inspecting the actual resulting locations, including moved rules. This is a project convention for ordinary Agent work, not a copy of Skill workflow policy or a hosting-platform setting. Follow [Procedure](procedure.md) for authorization, branch reuse and submission. Missing/unreadable rules stop affected actions; read truncated rules through the end and reload missing rules after compaction.

## Inspect and choose the destination

Semantically read the [candidate locations](skill-owned-rules.md#candidate-locations) for meaningful language rules covering Issue and Change Request titles/bodies, Comments, Discussions, and Review Feedback replies. Record exact originals, source lines and coverage per surface. Fenced/inline examples and quoted code, logs or external text are data, not operative rules; do not translate them. Keyword matches cannot decide equivalence. A maintainer's explicit alternative-language request remains an override, not a conflicting default.

Choose existing root `AGENTS.md`, otherwise existing root `CLAUDE.md`, otherwise `.claude/CLAUDE.md` only when it supplies the root instruction entry. Require the chosen entry to be tracked, regular, readable, writable UTF-8 with safe parsing. Select only the exact-case tracked path; a differently cased file is not the entry. Do not follow symlinks to write, substitute a lower-priority entry for an unsafe preferred one, create an entry, or recreate one removed by cleanup. Report untracked, nonregular, unreadable/undecodable, unsafe-link or ambiguous entries with the reason and input needed to recover. Preserve BOM/newlines and all content outside permitted language edits. No user/global settings changes or nested-entry writes are authorized.

## Fixed section and decision table

This is the one authoritative section; copy its heading and prose verbatim for an addition or replacement (use the destination's newline convention):

```markdown
## Hosting-platform collaboration language

Write Issue and Change Request titles and bodies, Comments, Discussions, and Review Feedback replies in English unless a maintainer explicitly requests another language. Quoted code, logs, and external source text may retain their original language.
```

| Existing rule after migration | Action | Evidence/report |
| --- | --- | --- |
| No collaboration-language rule; safe existing destination | Append the fixed section | Addition, destination and missing coverage |
| Complete equivalent English coverage across checked candidates; no conflicting root rule | No addition | Existing sources and complete coverage |
| Partial English coverage, no conflict | Preserve it; append the fixed section once to supply missing coverage | Covered/missing surfaces; never duplicate a complete rule |
| Root separately requires another collaboration language | Remove/replace only that portion; put the fixed section at the destination | Exact original text/source lines and replacement |
| Root mixed rule is cleanly separable | Change only collaboration portion; add the fixed section once | Exact change; unchanged documentation/code-comment/commit conventions |
| Root mixed rule cannot be separated cleanly | Retain it unchanged | Concrete maintainer decision; coverage remains unresolved |
| Conflicting rule outside the chosen root entry | Retain/report; do not add a competing root rule solely to override it | Source, conflict and maintainer decision |
| No safe writable existing destination | No language write there | Reason and recovery input; no new entry |
| Check-only, local-only, cancelled or blocked delivery | Respect actual boundary | Proposed operation, completed diff and exact delivery state separately |

When complete equivalent coverage already exists, remove only a separable conflicting root portion and reuse that coverage; never append a duplicate or rewrite existing English prose.

Full English coverage includes all listed surfaces, the explicit maintainer override and quoted-text exception. A narrower English rule is partial, not complete. Partial coverage triggers only one fixed-section addition, not custom fragments or rewriting existing English prose. If a heading or existing section prevents a safe addition without duplicate sections or unrelated rewriting, retain/report it for decision. A later successful run recognizes complete coverage and writes nothing.

A dedicated section containing only the conflicting collaboration rule may be replaced as a whole by the fixed section; quote its original heading and text. Leave no empty heading. A heading with other retained content stays intact.

For a separable mixed sentence such as `Docs and Issues are written in Chinese`, retain `Docs are written in Chinese` and supply the fixed section for collaboration. This exception permits only the connective/subject adjustment needed to preserve the original non-collaboration obligation; record the exact before/after. If grammar or meaning cannot be preserved unambiguously, leave it unchanged. Preserve documentation, code-comment and commit-message languages, title formats, other conventions, and quoted text. Do not translate prior Issues/Change Requests or repair templates/contributor docs. Rules moved by migration are now assessed at their new destination; migration itself still preserves bytes.

An unresolved mixed/external conflict does not erase safe independent work, including policy deletions, migration, or a separate root collaboration replacement. Record remaining coverage honestly; do not claim a root addition resolves an external conflict. Earlier explicit maintainer retention decisions still apply under [Cases to retain](skill-owned-rules.md#cases-to-retain).

## Verify and report

Compare original/result bytes and each planned operation: only the fixed section, separable collaboration-language portion and minimal grammatical adjustment above may change. Record unchanged conventions, quoted exceptions, source lines, existing coverage and unresolved decisions. Any unrelated addition/rewrite fails the diff gate. Report language additions/replacements separately from policy deletions and migration, quoting replaced originals in both final report and cleanup Change Request. State this configures a default; it does not guarantee client/model compliance or platform enforcement.

Language-only work uses the same fixed cleanup branch/PR as policy deletion; it keeps the no-change gate open. Check-only reports planned additions/replacements without changing any bytes/mtime or creating branch/commit/PR. Local-only stops at the permitted local diff. Cancellation/failure preserves completed authorized changes and records unfinished operations/recovery; do not claim success for them. On completed reruns, inspect actual coverage and conflicts: no duplicate section, timestamp, empty commit, branch or PR. Release reconciliation remains read-only, separate and final-report-only under [Reporting](reporting.md).
