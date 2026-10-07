# Foundation implementation — 2026-10-04

PRIMARY OBJECTIVE: Resolve SC-01–03 in the five formal Drive v1.8 documents, then implement immutable ReportContext → MarketDataSnapshot → ReportObject → G0–G8 validation foundations and the explicitly authorized P0 regression fixes.

ACTIVE PROFILE: dashboard + data-tool. Base commit: 600a533. Branch: codex/report-foundation-a-b-d-c.

ACCEPTANCE: Explicit dates, immutable retry identity, unknown-cron rejection, weekend new-report rejection; frozen report-bound snapshots; typed numeric markets and legacy read adapter; connected gates with PNG/manifest refusal, full-text Drive verification, rollback/projection/DOM checks; required A/B/D/C fixtures and existing regression checks; five formal Drive readbacks; unchanged production artifact hashes.

CONSTRAINTS: Preserve acquisition, readiness, history, source registry and legacy reads. No push/deploy or production JSON/report Docs/PNG/Receipt mutation. Formal specification updates are expressly authorized. 2026-10-02_21-00 remains UNRESOLVED / UNVERIFIED / NEEDS_REVIEW.

OUT OF SCOPE: E–H Publisher/Projection/Portal/Scheduler reorganization; production persist writer behavior change; canonical identity reconciliation.

FORBIDDEN SUBSTITUTE: Unit checks or new gate API do not prove that the existing live publishing pipelines enforce these gates. Report remaining deployment bypass separately.

OPEN OUTCOMES: None within the authorized A/B/D/C foundation task. Deferred: live Publisher/Projection/Portal/Scheduler enforcement, unresolved 2026-10-02_21-00 identity, existing unsafe canonical writer, historical structure/PNG gaps. These are not silently withdrawn.

NEXT ACTION: Foundation accepted at 0e14412. Phase E dry-run authorized below; prior deferred production outcomes remain open.

## Phase E — 2026-10-06 (ADD)

PRIMARY OBJECTIVE: In an offline fixture, safely bind Docs, PNG, immutable Manifest, Git registration and post-verification Receipt to one transaction, resume durable checkpoints without duplicate effects, and reject identity drift.

ACTIVE PROFILE: data-tool + generic-app. Start commit c6d1236.

ACCEPTANCE: Required identity fields, same-fileId full-text readback and approved normalization, actual fixture PNG bytes, immutable prepublication Manifest, lost-Git-response reconciliation, all five crash fixtures, same-identity duplicate prevention, stale/changed identity rejection, protected-slot read-only proof, unchanged production evidence.

CONSTRAINTS: Offline design and fixture implementation only. No production connection, Drive writes (including formal docs), push, deployment, production JSON/PNG/Receipt changes. No Phase F–H implementation. Never certify either OLD/NEW ID for 2026-10-02_21-00.

COMPLETED OUTCOMES: E-01 durable identity/state; E-02 Docs/PNG/Manifest/Git/Receipt connections; E-03 crash/retry/error/duplicate fixtures; E-04 fixed-candidate sweep, regression and safety proof; E-05 architecture/schema/report. ACCEPTED within offline scope at tested c530715: 44 new tests, 138 total unique Python tests PASS; five CLI recovery scenarios PASS; protected824 mismatch0. Known legacy structure FAIL retained.

OPEN OUTCOMES: None in authorized Phase E offline scope. Prior protected identity, unsafe writer, live enforcement and legacy artifact risks remain deferred; real publication acceptance NOT_RUN.

OUT OF SCOPE: Real Drive/GitHub/Pages adapters, production publication, projection migration, body reformatting, scheduler/portal changes.

FORBIDDEN SUBSTITUTE: Simulated Git SHA/Pages/DOM evidence must never be presented as a real commit, deployment or verified production publication.

NEXT NECESSARY ACTION: Stop at accepted Phase E dry-run. Before Phase F, obtain explicit scope, projection mapping/rollback, unsafe writer treatment, durable real adapter reconciliation and nonproduction acceptance decisions. No production action is authorized.

## Infographic Validator v1.0 — 2026-10-07 (ADD)

PRIMARY OBJECTIVE: Make report-specific infographic artifacts pass deterministic source, timeline, numeric, design and post-generation review gates before any formal publication, and only report COMPLETE after identity-bound external readback evidence passes.

ACTIVE PROFILE: dashboard + data-tool + generic-app.

ACCEPTANCE: Source report SHA-256 lock; required report body/market checks; slot-isolated specification and fixed timeline checks; exact decimal subset, typed numeric provenance and derived direction validation; chart/gauge/person rejection; validated-JSON prompt; PNG/JPEG structural check plus identity-bound Vision review; Docs/Drive/GitHub/receipt/Portal evidence gate; final completion gate; CLI entry points; regression cases 01–12; existing Portal data unmodified.

CONSTRAINTS: Do not alter production report JSON, PNGs, Docs, Drive, receipts, GitHub refs or public Portal as part of this implementation. Preserve the accepted Phase E offline Publisher. Validator source changes stay local; do not deploy or configure production secrets. Provider credentials are not configured. A required external result remains NOT_RUN until actually observed.

OUT OF SCOPE: Live Google Drive/Docs writes, GitHub writes, Actions, Pages or Portal deployment; automatic Vision-provider invocation; image generation service integration; automatic retries and dashboard UI.

FORBIDDEN SUBSTITUTE: Passing synthetic/furnished evidence, CLI syntax or local tests is not proof of live publication, Portal deployment or Vision model verification.

IMPLEMENTATION STATUS: Core validators/CLI and regression acceptance pass at E3 synthetic scenario scope. Existing Apps Script publishing now enforces strict body validation, same-file Docs text/hash readback and a signed HMAC Vision review bound to the exact report and Drive image before any GitHub write. The HMAC contract is cross-runtime tested with fixtures. No real Vision provider or secret is configured; the real sample run correctly stopped before image generation.

OPEN OUTCOMES: O-I1 real Vision provider and review provenance; O-I2 live Google Docs/Drive/GitHub/Pages/Portal adapters and external publication acceptance; O-I3 a source report with valid typed snapshot, all required sections, a post-generation image and full end-to-end evidence. The current 2026-10-02 08:00 sample is insufficient (required sections missing; typed snapshot/PNG absent).

NEXT NECESSARY ACTION: Configure an approved trusted Vision signer and HMAC key in a nonproduction Apps Script project, provide an exact-slot signed review JSON, then run a nonproduction end-to-end publication/readback. Until then, post-generation state cannot exceed WATCH and external stages remain NOT_RUN.

## Trusted Vision Signer v1.0 — 2026-10-07 (ADD)

PRIMARY OBJECTIVE: Provide a local signer boundary that turns a strict external Vision review into the existing identity-bound HMAC contract only when every required visual check is PASS.

ACCEPTANCE: Exact provider response schema; three-valued verdicts; fail-closed treatment of FAIL/UNCERTAIN; source, report, image, Docs and Drive identity binding; unchanged Python/Apps Script canonical HMAC contract; fixture-only provider identity; safe local CLI; no overwrite or protected production output; at least 25 regression cases; Python and Apps Script cross-runtime verification; documented nonproduction limitations.

CONSTRAINTS: No real provider credentials/API, production secrets, Apps Script deploy/configuration, production report/index/image/receipt edits, or publication. Fixture review is not actual Vision evidence. Preserve existing Validator strictness and the accepted offline Publisher.

OUT OF SCOPE: Real provider implementation, nonproduction provisioning, remote readbacks, image generation, deployment, publication, and production acceptance.

FORBIDDEN SUBSTITUTE: A fixture result, signed test JSON, or passing local test must never be represented as proof of actual visual inspection or production readiness.

OPEN OUTCOMES: Real approved provider adapter/provenance; nonproduction secret and Apps Script configuration; external Docs/Drive readbacks and end-to-end acceptance remain NOT_RUN.

IMPLEMENTATION STATUS: Local implementation complete. Full Python suite 102/102, Infographic tests 23/23, signer tests 27/27, Apps Script checks, GAS syntax 27 files, AST 148 files, dynamic Python/Apps Script HMAC and identity checks, and diff check PASS. Fixture provider only; no real Vision evidence.

NEXT NECESSARY ACTION: Await code review on Draft PR #75. Keep the PR unmerged until provider provenance and external nonproduction acceptance are separately completed. Do not merge as part of this task.

## Fixture / production trust separation — 2026-10-07 (CORRECT)

CORRECTION: The `fixture-test-only` identity must never be accepted as production trust, even when a sufficiently long key is configured. Apps Script trust configuration and production verifier reject it. Python signer defaults reject it; fixture signing requires explicit test-only authorization. The signed review schema and HMAC canonical payload remain unchanged.

ACCEPTANCE: Tests 28–35 cover default signer rejection, CLI rejection without `--test-only`, explicit test-only success with `production_write: false`, external path rejection when fixture identity is trusted, Apps Script config/verifier rejection, direct cross-runtime fixture HMAC verification, and unchanged non-fixture provider validation.

CONSTRAINTS: Keep PR #75 Draft and unmerged. No Apps Script production deployment, Script Properties update, production artifact change, production secret, or external Vision invocation.

IMPLEMENTATION STATUS: Fixture/production trust separation implemented. Local tests 106/106; signer 31/31; Apps Script fixture rejection, explicit test verifier, and non-fixture HMAC regression PASS. Hosted checks pending on the updated PR head.

NEXT NECESSARY ACTION: Push the correction to the existing branch, update PR #75 description, and confirm hosted validation while preserving Draft status.
