# Decisions

- 2026-10-04: Isolated local clone based on latest origin/main 600a533. Upstream calendar/data changes predate this task. No production regeneration.
- Formal v1.8 documents are raw text/markdown and updated in place using Google Drive skill; same IDs and folder. Backups retain pre-change text. Historical v1.7 sequence remains historical, superseded by the explicit 2026-10-04 contract.
- Initial normalization permits only CRLF/LF and one trailing newline; blank-line collapse is deliberately excluded until a bounded rule can be justified. Punctuation and numbers remain significant.
- Foundation is a verifiable local transaction API/CLI with no external publisher side effects. Existing unsafe production writer and deployment bypass remain Phase E/F integration outcomes, not silently claimed fixed.

- Sweep repairs: fixed direct/module window imports, required same-SHA Actions before Pages authorization, title/date and numeric display consistency, supported schema version, retained failed full-text normalization diffs, same-revision identical retry proof, and moved G0/G1 before producer invocation. Final code candidate af61a0a passed acceptance.
- Diagnostic preparation helper REMOVE after baseline/diffs; regression runner KEEP. Temporary browser overrides/tabs/server cleaned up. Existing legacy structure and 08 QA FAIL retained as unresolved outcomes.

- 2026-10-06 final reporting recheck: G4 filename was inconsistent with formal v1.8. Corrected to マーケットレポート_<report_id>.png; revision remains explicit metadata rather than an invented filename suffix. Added exact-name and different-slot/invented-name rejection tests. Earlier completion statement overlooked this mismatch; final acceptance is rerun after the correction.

- 2026-10-06 Phase E ADD: User authorizes design + offline dry-run only. Reuse G0–G8 and isolate Publisher in additive files. No Drive skill/connector invoked because all production connections are prohibited, including formal spec writes.
- E-D01: Concrete SQLite FixtureStore models effects separately from journal checkpoints; action IDs and an exclusive SQLite runner lock make retries and restarts deterministic. Real adapter is not injectable. Trade-off: simulated SHA/Pages evidence proves E3 recovery behavior, not real service idempotency or publication. Reversal requires separately approved real adapter acceptance.
- E-D02: Same report_id+revision reserves one snapshot/body identity; lower revisions are conservatively rejected after any higher claim. Failed claims are not automatically reset. Actual distributed retry/retention and reviewed recovery policies remain future decisions.
- E-D03: Manifest created_at remains fixed on retry, body_hash uses exact raw text, and official PNG filename is reused without revision suffix. Reverification by pinned ID is allowed; successful saves are never repeated. Receipt is post-G7 only; default dry-run ends at GIT_REGISTERED.
- E-D04: Sandbox default OS temp path denied nested writes in the first test invocation. Use explicit writable evidence temp root for reproducibility, without broadening permissions or modifying production paths. Initial infrastructure failure is retained in acceptance notes.
