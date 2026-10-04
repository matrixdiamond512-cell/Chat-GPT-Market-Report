# Decisions

- 2026-10-04: Isolated local clone based on latest origin/main 600a533. Upstream calendar/data changes predate this task. No production regeneration.
- Formal v1.8 documents are raw text/markdown and updated in place using Google Drive skill; same IDs and folder. Backups retain pre-change text. Historical v1.7 sequence remains historical, superseded by the explicit 2026-10-04 contract.
- Initial normalization permits only CRLF/LF and one trailing newline; blank-line collapse is deliberately excluded until a bounded rule can be justified. Punctuation and numbers remain significant.
- Foundation is a verifiable local transaction API/CLI with no external publisher side effects. Existing unsafe production writer and deployment bypass remain Phase E/F integration outcomes, not silently claimed fixed.
