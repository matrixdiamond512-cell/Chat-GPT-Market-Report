# Control records and evidence boundaries

Formal specification is the five v1.8 files in the designated Drive folder. Root docs are their updated local mirrors. `spec-backups/` is the pre-change audit copy, not a competing specification. `spec-readbacks/` is the connector's complete text after the 2026-10-04 writes, with one connector-added trailing newline.

Acceptance evidence lives outside the repository under `review/market-report-foundation-20261004/evidence/` in the containing workspace. No generated fixture evidence is a production Manifest/Receipt or actual publication success. `SOURCE_SPEC.md` preserves the complete implementation request; prior audit artifacts are retained under `review/market-report-audit-20261004/`.

Diagnostic preparation script: REMOVE after generating initial baseline and document diffs; retaining a rerunnable baseline-overwriting helper would weaken the evidence. Regression runner: KEEP, read-only except explicitly named evidence and TemporaryDirectory fixture files. Legacy unsafe writer: unchanged, risk demonstrated only in a temporary fixture.
