## Complete bounded rule loading

Read this file in full before other work-cycle rule reads or stage dispatch. If its own output is truncated, continue only its missing sections through the end. These rules govern loading, not the stages' business decisions. Required rule text remains mandatory; neither a manifest, hash, receipt, nor summary replaces it. CI logs and test output retain their stages' selective-reading rules.

### Inventory and required order

Use the bundled read-only `scripts/rule_inventory.py` with the actual stage package directory. `inventory --package <directory>` inventories `SKILL.md` and Markdown under `references/`, with package-relative paths, SHA-256, raw UTF-8 bytes, line counts, and checked local link edges. It follows edge order and deduplicates cycles. It rejects escaping paths, symlinks, missing/unreadable files, invalid UTF-8 rules, and rule Markdown outside the checked locations. Report the exact path and affected action; stop that action until the gap is resolved. Inventory lists optional/other-stage references without making them required.

Read the actual entry first, then select its required files in the entry's stage order, adding each file's required references when its loading instructions apply. Links alone do not decide conditional requirements. Do not automatically dump the entire graph. Keep a manifest of selected required files, their identity/size, stage and dependency order, and bounded groups/ranges in the task evidence; pass its path in the compact dispatch handoff. Each subagent must still load its actual installed entry and applicable references in full. The orchestrator owns shared handoff updates; stages write only their own evidence.

### Plan and read one group

Establish the actual host/tool output allowance and units, reserving space for tool wrappers and other response contents. A token/line allowance is not a UTF-8 byte allowance; do not invent a conversion or raise client limits. When the allowance is unknown, use conservative one-file section reads and adapt after observed truncation. Even individually compliant files can overflow an aggregate response. Never batch independent groups into one tool result whose combined allowance is unknown or exceeded.

For a known byte allowance, use this data-only interface (paths below are task-owned evidence):

```bash
python3 <helper> plan --package <directory> --stage <stage> --required SKILL.md --required references/example.md --budget-bytes <allowance> --reserve-bytes <wrapper-reserve> > <manifest.json>
python3 <helper> read --manifest <manifest.json> --group 0
```

`--required` repeats in the actual entry's required order; `example.md` is a placeholder. Group indexes start at zero. Read exactly one group per response, then advance through all groups. The helper includes its own BEGIN/END frames in the UTF-8 allowance plus the caller's wrapper reserve. It preserves raw newline bytes, prefers complete lines, and splits overlong lines only between UTF-8 characters. Frames give file hash and half-open raw byte range `[start,end)`; the end offset is excluded. No single file, line, or character is silently dropped to fit. An allowance too small for the frame plus a character fails explicitly. Inventory/plan/receipt JSON can itself be large: save it as task data and inspect only needed fields or sections, without a whole-graph output dump.

### Observe, recover, and compact

After each read, check tool warnings, frame boundaries and text continuity. A warning, missing END frame, or incomplete text means the range cannot be marked fully observed. Record only text actually received, ending at a known UTF-8 byte boundary; if uncertain, leave that section unobserved. Recover only missing text through EOF. A possible boundary overlap for uncertain coverage is safer than inventing receipt. Do not reread an already observed whole graph merely because one group was truncated.

```bash
python3 <helper> receipt --manifest <manifest.json> --context <context-id> --observed references/example.md:0:420 > <receipt.json>
python3 <helper> plan --package <directory> --stage <stage> --required SKILL.md --required references/example.md --budget-bytes <allowance> --reserve-bytes <wrapper-reserve> --receipt <receipt.json> --context <context-id> > <missing.json>
```

Attest all actually observed ranges, including the entry, using repeated `--observed path:start:end`; use `--previous <receipt.json>` when extending a receipt. Use distinct output paths when reading a previous receipt so shell redirection cannot erase it. The receipt records package path/hash, per-file metadata, required stage/selection, current context identifier, merged observed ranges, completeness, and the next missing section. It is the caller's attestation, not automatic proof of model receipt. `read` never marks coverage. Save interrupted/cancelled reads as incomplete and retain the next missing section before resuming. Parallel readers use separate task/attempt manifests and receipts; no shared receipt writes or new locks are needed.

Before affected actions, verify selected rules are fully observed in the current context. The helper rechecks rule hashes before reads/receipts; changed package/rules invalidate coverage and require fresh inspection/planning. Hashes prove identity only. After compaction, recover the compact task handoff, preserve file identities, and change the context identifier: a prior disk receipt cannot prove that absent model context is present. Reload missing current-stage text, selecting all applicable required files whose text is absent, while keeping unrelated stages inventory-only. Reusing a receipt in a different context plans every selected range again. Keep complete traces outside the compact handoff.

Other Skills remain independently usable with their existing full-read navigation and conservative one-file section fallback. Their standalone installations acquire no dependency on this helper. This protocol adds no universal output limit and cannot prove arbitrary model compliance, permanent context retention, or a production speedup.
