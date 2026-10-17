# English working environment

Read this file in full before planning or applying the working-environment rule, including check-only. Apply it after policy deletion and [Claude entry migration](agent-entrypoints.md), and after [Collaboration language](collaboration-language.md), whose fixed section it replaces. Follow [Procedure](procedure.md) for authorization, branch reuse, verification and submission. Missing or unreadable rules stop affected actions; read truncated rules through the end and reload missing rules after compaction.

## Fixed section

This is the one authoritative section. Copy its heading and prose verbatim for an addition or replacement, using the destination's newline convention:

```markdown
## English working environment

Write in English: project-maintained documentation (README and docs), Issue and Change Request titles and bodies, Comments, Discussions, Review Threads, and future commit messages, unless a maintainer explicitly requests another language. Preserve historical Issues, Change Requests, and comments. Do not translate code, commands, paths, identifiers, logs, technical data, or quoted external text. Preserve other project conventions.
```

## Apply the rule

1. Choose the safe existing root instruction entry selected by [Collaboration language](collaboration-language.md). Do not create an entry; report an unsafe, missing or unreadable destination with the reason and recovery input. Preserve BOM, newlines and all content outside the permitted rule edits.
2. Apply each applicable outcome:
   - Fixed collaboration section present: replace its heading and prose with the fixed section, leaving no duplicate section or empty heading.
   - Complete equivalent English coverage of every listed surface: write nothing.
   - No English rule: append the fixed section once.
   - Partial English coverage, or a separable conflicting non-English documentation or collaboration rule: replace only the conflicting portion, preserve the rest, and use the fixed section once for the missing coverage.
   - Mixed rule that cannot be separated cleanly: retain it unchanged and report the conflict with the maintainer decision needed.
   - Conflicting rule outside the chosen root entry: retain and report it; do not add a competing root rule.
3. Record the exact original heading and text, source lines and replacement for every change. Never add a second section, rewrite existing English prose, or change content outside the fixed section and replaced conflicting portion. Preserve unrelated conventions, including stack, architecture boundaries, title and branch formats, and code-comment languages.

## Documentation translation

Translate the project's README and project-maintained documentation into English in the same cleanup branch and Change Request, after policy deletion, [Claude entry migration](agent-entrypoints.md), [Collaboration language](collaboration-language.md), and the working-environment rule above. The default delivery flow authorizes this operation; check-only, review-only, and audit-only runs write no translated file, and local-only stops at the verified local diff.

Translate only the project's own prose. Preserve code blocks, inline code, commands, paths, link destinations, identifiers, logs, technical data, code comments, and quoted external text in their original form. Do not translate historical Issues, Change Requests, comments, releases, release notes, or other people's content. Do not restructure, reorder, summarize, or rewrite already-English prose; an unrelated rewrite is outside the diff gate.

For a large or ambiguous document, translate only complete sections whose result you can verify, retain the remaining bytes unchanged, and report the exact boundary and recovery input. Never truncate a document or present a partial translation as complete. A file with no non-English prose stays byte-unchanged and is reported as unchanged. If a file cannot be read or written, retain its original content and report the permission failure and recovery input. If translation fails, stop that document, keep its original content, and report the failure. If a retained rule requires specific documentation to stay non-English, leave those files unchanged and report them as unresolved.

After translating, verify every relative link and heading fragment in each changed file. When translation changes a heading used as a link target, update only that link's fragment and verify it resolves. On a link regression, stop translating the affected document, restore its original content, and report the regression. Report each file, its translated sections, every replaced passage, and unchanged content under [Reporting](reporting.md).

## Limits and reporting

About is the only repository setting this flow may change; do not change other settings. Do not rewrite historical Issues, Change Requests, comments, releases, release notes, or other people's content. Translating existing documentation and changing About are separate operations with their own procedures and reporting; [Documentation translation](#documentation-translation) defines the translation flow, and this rule update records the requirement and the root-entry rule.

Check-only, review-only and audit-only write no project files; local-only stops at the local diff and publishes nothing. A completed rerun writes nothing and adds no duplicate section. Report the section added or replaced, exact replaced originals and source lines, preserved conventions, and unresolved conflicts. Do not claim complete English coverage while conflicts remain.
