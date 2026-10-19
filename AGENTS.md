# AGENTS.md — Market report delivery documentation

For changes to the market report delivery system, read `docs/system/DOCUMENT_CONTROL.md` first.

- Do not create separately named dated/versioned requirements, specifications, or manuals. Keep stable GitHub paths and stable Google Docs IDs.
- For any change, record a change request ID, modification date, sources/PR, affected documents, verification status and unresolved items.
- Update affected requirements, specifications, body-authoring instructions and operations manuals together. A change to a market portal display or publishing pipeline is part of the same system when it affects report delivery.
- Preserve prior histories. Use Git history, Google Docs revision history, and the designated archive folder instead of naming a new "latest" file.
- Do not report `verified`, `published` or `complete` without independent evidence for the stated stage. Do not reconstruct pre-slot evidence retrospectively.
- Current configured report slots are weekdays 08:00/12:00/16:00/21:00 JST, none on weekends; recheck the actual config and task execution history before changing.
