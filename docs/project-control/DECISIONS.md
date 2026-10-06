# Decisions

- 2026-10-04: Isolated local clone based on latest origin/main 600a533. Upstream calendar/data changes predate this task. No production regeneration.
- Formal v1.8 documents are raw text/markdown and updated in place using Google Drive skill; same IDs and folder. Backups retain pre-change text. Historical v1.7 sequence remains historical, superseded by the explicit 2026-10-04 contract.
- Initial normalization permits only CRLF/LF and one trailing newline; blank-line collapse is deliberately excluded until a bounded rule can be justified. Punctuation and numbers remain significant.
- Foundation is a verifiable local transaction API/CLI with no external publisher side effects. Existing unsafe production writer and deployment bypass remain Phase E/F integration outcomes, not silently claimed fixed.

- Sweep repairs: fixed direct/module window imports, required same-SHA Actions before Pages authorization, title/date and numeric display consistency, supported schema version, retained failed full-text normalization diffs, same-revision identical retry proof, and moved G0/G1 before producer invocation. Final code candidate af61a0a passed acceptance.
- Diagnostic preparation helper REMOVE after baseline/diffs; regression runner KEEP. Temporary browser overrides/tabs/server cleaned up. Existing legacy structure and 08 QA FAIL retained as unresolved outcomes.
