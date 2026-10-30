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
- E-D05 (fixed-candidate sweep): Missing saved effects must not be silently recreated from a claimed checkpoint. Validate checkpoint invariants first and preserve comparison failure evidence. Recovered UNKNOWN restores the completed state even when no new step is needed. Persist passed publication observations at PUBLISHED so Receipt restart does not depend on a new external observation; changing them requires review. Added corruption/restart/no-network fixtures; 44 Phase E tests PASS before final acceptance.
- E-D06: Acceptance reruns get fresh timestamped fixture namespaces and preserve earlier databases; never delete or reset a completed transaction merely to replay a crash test. Explicit scenario counts are acceptance assertions as well as unit assertions.
- 2026-10-07 I-D01: Reuse existing G0/G1 snapshot validation before report body/spec generation; any STALE/UNAVAILABLE series produces WATCH and blocks generation. Reason: the existing numeric source cannot be inferred from a display string. Reversal requires an explicit partial-data policy in the report specification.
- 2026-10-07 I-D02: Exact heading matches are required for report sections; body mentions do not satisfy a missing section. A spec is locked to body SHA-256, report ID, snapshot ID, timestamped market rows and source section.
- 2026-10-07 I-D03: Caller-supplied Vision JSON is not a trusted provider observation, so its best state is WATCH/VALIDATING. Caller-supplied publication readback JSON is structural-only; live stages remain NOT_RUN. Reversal requires authenticated providers/readback adapters and nonproduction acceptance.
- 2026-10-07 I-D04: Apps Script accepts Vision review evidence only as a 32-byte-minimum HMAC-SHA256 attestation bound to exact report/body/Docs/image identities and configured provider identity. Missing Script Properties block publication before any GitHub write. Shared canonical payload is fixture-tested across Python and Apps Script; fixture HMAC is not real Vision evidence.

- 2026-10-07 I-D05: Split the review branch from the latest locally fetched main and retain only Validator files plus direct G0/G1/report/snapshot dependencies and test fixtures. Exclude Portal renderer changes and Phase E / report-building / canonical persistence changes. Reason: keep the review scoped and avoid triggering unrelated legacy report validation workflows; production data and validators remain untouched. Reversal: add a dependency only if import/test evidence shows the Validator requires it.
- 2026-10-07 TVS-D01: Keep the Vision provider as a strict interface and leave the external adapter unconfigured. The fixture provider uses the immutable `fixture-test-only` identity, never inspects the image, and cannot satisfy a production provider identity. This permits local schema/HMAC regression without treating test verdicts as visual evidence.
- 2026-10-07 TVS-D02: Preserve the existing Python/Apps Script canonical HMAC payload exactly. The signer reuses the current field order and raw UTF-8 source body SHA; payload changes require a separately versioned contract and coordinated runtimes.
- 2026-10-07 TVS-D03: Any provider FAIL or UNCERTAIN verdict blocks signature creation. Do not serialize a partial or failed review as `VERIFIED`; uncertainty in numeric review remains non-signable.
- 2026-10-07 TVS-D04 (CORRECT): `fixture-test-only` is forbidden as a trusted production identity in Apps Script configuration, Apps Script production verification, Python signer defaults, and CLI default paths. Fixture signing requires explicit `allow_fixture_test_provider=True` in test code or CLI `--test-only` together with the fixture provider identity. The separate canonical HMAC helper remains usable by cross-runtime tests; no production auto-detection or test mode was added to Apps Script.

- 2026-10-07 PORTAL-D01: `report.title` is the canonical rendered title. Strip only an exact leading title from source text and preserve its remainder as body, including malformed no-newline legacy text. Reuse one Apps Script canonicalization helper for generated `fullText`, body hashing, and Docs readback. Reversal requires an explicit versioned title/body contract change.
- 2026-10-07 PORTAL-D02: GitHub Pages `push: main` uses path filters for Portal artifact/data and direct deployment-validator inputs; existing `workflow_run` publication sources remain unchanged. This prevents unrelated documentation/signer-only pushes from deploying Pages.
- 2026-10-07 PORTAL-D03: Run browser DOM validation on the normalized local artifact before upload/deploy and repeat the same strict checks against the public Portal after deployment. Keep exact title equality and fail closed. A successful Deploy step is not a successful Portal publication when live DOM validation fails.

- 2026-10-20 / HANDOFF-20261020-01: Add `README.md` and `HANDOFF.md` as **stable developer onboarding paths**, extend existing `AGENTS.md` and introduce a PR evidence checklist. This is development-process documentation only: no report schedule, publication code, market data, receipt, Google Docs canonical requirements/specification/operations, or portal output is changed. Preserve the `docs/system/DOCUMENT_CONTROL.md` precedence and fixed-ID formal document workflow. Refer to Issue #173 for actual second-PC acceptance, Issue #103 for production audit, and live PR/Actions state rather than copying old success claims. Reassess any future functional change separately with the affected-document matrix.


## MRF-0800-20261029 decisions

- D-0800-01: Retain GCS generation-pinned evidence and immutable create-only per-slot claim; identical retry may continue, any changed identity/hash is a conflict. Do not clear a claim automatically.
- D-0800-02: Google Docs writer saves only the frozen G2 fullText and exact readback is mandatory before portal work. Ambiguous or partial Docs creation stops for manual reconciliation.
- D-0800-03: Existing portal publication is behind an adapter boundary. Contract fixtures can test the boundary but cannot represent a live portal publish; rollout awaits a concrete, approved invocation/readback route.
- D-0800-04: No main/production/Drive/Pages change; PR #97 remains untouched.


- D-0800-05: Use the existing importer filename (`マーケットレポート_YYYY-MM-DD_08-00`) for the Drive object while preserving the report's separate in-body title; run the existing body validator before creating Docs.
- D-0800-06: Do not invoke the existing Docs publication workflow in the current task. It applies canonical writes to main and deploys Pages; first add and review an exact-generation GCS evidence handoff and an explicitly authorized environment boundary.



- D-0800-07 (2026-10-29): Permit importer execution only against a separately marked LOCAL_STAGING_ONLY checkout using exact-generation TEST_ONLY GCS evidence and strict Docs appProperties binding. Keep the production workflow's default root and flags unchanged; never use its workflow_dispatch as a staging mechanism because it writes main and dispatches Pages.


## MRF-0800-BRIDGE-20261030-01 — use a composition test at the importer boundary (ADD, 2026-10-30 JST)
The isolated handoff helper and the Docs issuance-binding helper had separate unit tests, while the actual importer's `publication_evidence` wrapper had no test proving the staged evidence and Docs properties meet in one call. Add one offline contract test to compose those existing seams. Preserve the `TEST_ONLY` environment marker and use fake GCS and Google-auth modules. A valid local receipt plus strict property match is component/integration evidence only; do not interpret it as Google Docs save, canonical receipt persistence, Portal publication, or production GCS evidence. No functional requirements/spec/operations text changes.


- MRF-INGESTION-20261030-01 (2026-10-30 JST): Replace the combined VERIFIED_REPORT_INGESTION_AND_PUBLICATION message with stage-specific status lines. Keep source archival available when publication evidence is absent; do not turn evidence failure into a claim of publication or erase the archive. Docs readback receipt remains separate from Pages deployment and live public readback. No gate or data behavior changes.


## MRF-0800-IMPORTER-COMBO-20261030-01 — integrate importer changes for joint validation (2026-10-30 JST)

Decision: Carry PR #189's ingestion status helper, test/workflow and affected requirements/specification/operations/project records onto the latest-main PR #188 branch so both importer behaviors are tested on one Draft head. Keep PR #188 based on current main and retain PR #189 as OPEN/Draft for now; do not merge either independently while duplicate code is present.

Reason: Both changes touch `scripts/sync_reports_from_drive.py`; per-PR CI alone did not prove they compose. The combined head ran both test suites and all four relevant workflows. Reversal: if the owner chooses separate review scopes, remove the incorporated PR #189 delta from #188 in follow-up commits, or designate one Draft as superseded before merging. No force-push, merge to main, deployment, or production write occurred.

## D-0800-08 (2026-10-30) — Fail-closed TEST_ONLY importer staging boundary

A separately marked staging checkout must be path-disjoint from the importer checkout in both directions. GCS project and bucket identifiers require a standalone `test` token, and the object name must start with `test-only/`; substring matches alone are not a TEST_ONLY identity. Resolve the evidence destination and prove it remains under the staging root before creating directories, then verify again afterward. This is a local staging guard only; it is not independent proof of external resource identity or publication.
