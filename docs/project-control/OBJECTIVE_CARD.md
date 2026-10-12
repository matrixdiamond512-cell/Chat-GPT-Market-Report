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

## 2026-10-09 08:00 reconstructed infographic validation — ADD

PRIMARY OBJECTIVE: Validate whether the already fixed official 2026-10-09 08:00 report can produce a traceable infographic using an immutable `SOURCE_RECONSTRUCTED` snapshot without re-fetching the report, repeating the 28-row extraction, or inventing missing facts.

ACCEPTANCE: Reuse the locked source body/hash, structured facts, numeric registry and prior 28-row PASS; keep report time distinct from actual Docs timestamps; create a typed source-reconstructed snapshot; render with the fixed 08:00 reference layout; record independent source, numeric, snapshot, completeness, layout and 768px readability outcomes; retain DRAFT-only output if true source gaps remain.

CONSTRAINTS: 08:00 only. No 12:00, source re-fetch, market-data re-acquisition, report-body changes, Drive/API/GAS/workflow/Portal/production JSON changes, push or deploy. Never inspect or alter protected 2026-10-02_21-00 OLD/NEW identities.

IMPLEMENTATION STATUS: Local snapshot reconstruction and six ordered landscape DRAFT sheets generated. Source, numeric and snapshot integrity PASS; content completeness FAIL on source-absent data; layout similarity REVIEW_REQUIRED; automated 768px geometry/readability PASS. Full Python discovery 145/145 PASS. No production side effects observed.

OPEN OUTCOMES: Production readiness remains BLOCKED because the source body lacks the NY pre-open stage, TOPIX value, six markets' bullish/bearish conditions, news time/affected-market/price-response fields, and three explicit top conditions; the single-image reference zone/layout match is also unresolved. No missing content was synthesized.

NEXT NECESSARY ACTION: Stop at 08:00 DRAFT validation. Do not proceed to 12:00 until source/format decisions address the listed gaps and reference-layout review.

## 08:00 single-sheet fixed-layout correction — 2026-10-10 (CLARIFY)

CLARIFICATION: The prior six-sheet landscape output does not satisfy the approved 08:00 reference. Keep the accepted SOURCE_RECONSTRUCTED body, facts, numeric registry, snapshot, and 28-row QA unchanged; do not re-fetch/re-extract. Force one 1536×1024 DRAFT canvas with the reference's fixed 16-zone order and four row groups. Render source gaps inside their fixed zones. Content completeness and layout integrity are independent outcomes.

RESULT: Exactly one report PNG plus a separate side-by-side comparison artifact generated under `artifacts/0800_source_reconstructed_20261010_v9/`. Layout geometry/reference topology PASS; source/numeric/snapshot integrity PASS; content completeness FAIL and 768px readability FAIL; production readiness remains BLOCKED. Full unittest discovery 146/146 PASS after updating the legacy fixture assertion to the current fixed-source error code. No 12:00 work.

NEXT NECESSARY ACTION: Stop. Treat this as a DRAFT layout reproduction only; resolve genuine source gaps and 768px readability before claiming infographic readiness. Do not proceed to 12:00 or formal publication.

## 08:00 fixed single-sheet v1.1 contract — latest state

The v1.1 renderer contract is implemented: explicit `08:00_FIXED_SINGLE_SHEET` dispatch, generic auto-layout rejection, one-page/16-card geometry metadata, fixed page/row/render mode, synthetic-only complete fixture, and visible overflow warnings. The actual 2026-10-09 source remains unchanged and is rendered from the prior structured source.

LATEST DRAFT: `artifacts/0800_source_reconstructed_20261010_v11/`. Geometry contract PASS; source/numeric/snapshot integrity PASS; content completeness FAIL; 768px automated threshold PASS; actual fixed-zone overflow makes `LAYOUT_INTEGRITY=FAIL`; `PRODUCTION_READY=BLOCKED`. Full test discovery 150/150 PASS. No publication, production paths, or 12:00 work.

NEXT NECESSARY ACTION: Stop at the 08:00 DRAFT. The current one-sheet geometry is reproduced, but actual text density still overflows three panels. Do not treat the image as formal or move to 12:00 until the content/geometry trade-off is resolved.

## Fixture / production trust separation — 2026-10-07 (CORRECT)

CORRECTION: The `fixture-test-only` identity must never be accepted as production trust, even when a sufficiently long key is configured. Apps Script trust configuration and production verifier reject it. Python signer defaults reject it; fixture signing requires explicit test-only authorization. The signed review schema and HMAC canonical payload remain unchanged.

ACCEPTANCE: Tests 28–35 cover default signer rejection, CLI rejection without `--test-only`, explicit test-only success with `production_write: false`, external path rejection when fixture identity is trusted, Apps Script config/verifier rejection, direct cross-runtime fixture HMAC verification, and unchanged non-fixture provider validation.

CONSTRAINTS: Keep PR #75 Draft and unmerged. No Apps Script production deployment, Script Properties update, production artifact change, production secret, or external Vision invocation.

IMPLEMENTATION STATUS: Fixture/production trust separation implemented. Local tests 106/106; signer 31/31; Apps Script fixture rejection, explicit test verifier, and non-fixture HMAC regression PASS. Apps Script Pre-Publish and All-Slot UI hosted checks PASS on PR #75.

SECRET HYGIENE: Contract fixture contains no HMAC secret/signature; tests generate ephemeral keys and signatures in process memory. No `test_secret` fixture field remains.

NEXT NECESSARY ACTION: Await review on PR #75. Keep it Draft and unmerged; real provider provenance and external nonproduction acceptance remain separate open outcomes.

## Trusted Vision Signer merge status — 2026-10-07 (CORRECT)

PR #75 was merged into main at `e1727ce9a4b9eae98505e1b5a4f6967c4fd8c16a`. Its merge-triggered GitHub Pages workflow executed the Deploy step, then the live DOM validation failed on the 2026-10-07 12:00 title mismatch (run `37623824126`). This observed deployment failure is the input to the Portal title-boundary and deploy-safety objective below. Apps Script production deployment, Script Properties, and Vision secrets were not configured.

## Portal deploy safety / title-body integrity — 2026-10-07 (ADD)

PRIMARY OBJECTIVE: Preserve exact canonical report titles and visible report bodies when legacy JSON has a malformed title/body boundary, prevent unrelated main pushes from publishing Pages, and stop invalid normalized artifacts before deploy.

ACTIVE PROFILE: dashboard + data-tool + generic-app.

ACCEPTANCE: Shared Apps Script title-boundary normalization for Docs conversion/hash/readback; renderer uses report.title and recovers malformed leading body text; malformed legacy fixture and embedded-title cases pass; Pages main-push paths are scoped while existing workflow_run sources remain; same strict local DOM gate runs after artifact normalization and before upload/deploy, with live post-deploy validation retained; all requested regressions pass.

CONSTRAINTS: No historical report JSON/index, market values, images, receipts, Drive documents, Script Properties, production secrets, Apps Script deploy, or Portal production deploy changes. Do not weaken title validation or infer/repair report content.

OUT OF SCOPE: Historical report data migration, atomic Pages rollback, production publication, Apps Script production configuration, real Vision provider and HMAC secret setup.

FORBIDDEN SUBSTITUTE: Passing unit tests or a completed Pages deploy is not proof of live Portal correctness; exact live title/DOM validation must pass after an authorized deployment.

IMPLEMENTATION STATUS: Implementation and local regressions pass on `codex/portal-deploy-safety-title-boundary`, based on main `e1727ce9a4b9eae98505e1b5a4f6967c4fd8c16a`. Python 106, Infographic 23, signer 31, Apps Script narrative/trust/readback, title-boundary parser, workflow path/order, AST 148, GAS syntax 27, renderer syntax, and diff checks PASS. Production report SHA-256 baseline and final for `reports/2026-10-07_12-00.json`: `03011e77b25c500e3df82effdcf1ea2c3c67fc5b605811a2a50ef94d637d377`. `reports.json` baseline and final: `f7058615cc5ffd8b150dcbbc31aa9fdb145b014477cac08987da0082c8275320f`. Windows local Chromium could not access the local HTTP server (`ERR_NETWORK_ACCESS_DENIED`); hosted local DOM validation is pending.

OPEN OUTCOMES: PR #76 remains OPEN/DRAFT at head 652118b6a315ba664caa573105c1553d89b56d58, based on main 3cb6171531ed19a6421a6bced3c3d1a1a20aeeec (ahead 9, behind 0). Rebase had no conflicts, latest main data retained, and production data paths are absent from PR diff. Apps Script Pre-Publish on final code head PASS. Hosted strict report check at 3ef4832 records 08:00 FAIL from MorningReportQA and 12:00 PASS; report/index contents are unchanged through final head. Hosted malformed fixture previously PASS on a70261e. A new final-head hosted renderer job has not appeared; keep its latest-head evidence outcome open. Preserve data and QA, keep Draft, do not merge/deploy.

NEXT NECESSARY ACTION: Finish implementation, run all requested local/hosted checks, verify protected production files unchanged, then stop with a Draft PR. Do not merge or deploy.


## 08:00 fixed single-sheet Phase 2 — visual fidelity (ADD, 2026-10-10)

PRIMARY OBJECTIVE: Improve the 2026-10-09 08:00 DRAFT's visual fidelity to the fixed reference while preserving the 1536×1024 single-sheet geometry, 16 zone coordinates, four row groups, SOURCE_RECONSTRUCTED provenance, and source/numeric/snapshot identity.

IMPLEMENTED: Dedicated render modes for all 16 zones; structural visual-fidelity checks include hierarchy, numbering, tables, arrows, scenario colors and 5/12/13 overflow. Added an 08:00 report/source fact contract and extended validation for five attention points, judgement evidence, explicit material-market relations and cross-asset causality.

LATEST DRAFT: `artifacts/0800_visual_fidelity_phase2_20261010_r3/`. 16-zone/one-sheet geometry PASS; visual component fidelity PASS; SOURCE/NUMERIC/SNAPSHOT PASS; target text overflow count 0; content completeness FAIL; 768px automated font-floor PASS; visual review NOT_RUN; PRODUCTION_READY BLOCKED. The report body/source identity and numeric registry were reused without re-fetch or re-extraction.

CONSTRAINTS: No 12:00 processing, source/body modification, report/production JSON change, Drive/Apps Script/workflow/Portal write, push, or deploy. Keep the artifact DRAFT because required source facts are absent.

NEXT NECESSARY ACTION: Stop after reporting this 08:00 visual fidelity candidate. Do not move to 12:00 or production.


FINAL ARTIFACT UPDATE — 2026-10-10: The final post-code-change DRAFT and side-by-side comparison are in `artifacts/0800_visual_fidelity_phase2_20261010_final/`. PNG SHA-256 `2e6a18f62e066c4ed230e8ff71e3ee64d502bfa054c0898c1fc08fc758c06860`; comparison SHA-256 `d3be65e62f196a057b3b567733d0161b82e4dba23b1d3a614e89a1a2830c19f6`. Final Python unittest discovery: 154/154 PASS. `compileall` and `git diff --check` PASS (Git emitted only line-ending conversion warnings).

## 08:00 new-report generation contract — 2026-10-10 (ADD)

PRIMARY OBJECTIVE: Require each new 08:00 report body and structured source to contain all source-bound facts needed by the fixed 16-zone infographic before Docs save or infographic rendering; do not fill historical 2026-10-09 gaps.

IMPLEMENTED: Extended `config/infographic_0800_content_contract_v1.json` with explicit generation-QA fields and minimum counts; added a fail-closed pre-save/pre-render validator and CLI; expanded the synthetic complete fixture with stable fact IDs, ordered facts, exact body excerpts and numeric links; documented the required authoring flow in the formal v1.8 manual.

ACCEPTANCE: Missing fact/field, altered body hash, source excerpt mismatch, or numeric-registry drift blocks before the renderer is called. A complete synthetic fixture must pass source, numeric, snapshot, content, layout, and 768px gates. Synthetic and DRAFT inputs must remain production-ineligible.

RESULT: Focused 08:00 suites 22/22 PASS; full Python suite 161/161 PASS. Complete synthetic fixture: SOURCE_INTEGRITY, NUMERIC_INTEGRITY, SNAPSHOT_INTEGRITY, CONTENT_COMPLETENESS, LAYOUT_INTEGRITY, READABILITY_768 all PASS; PRODUCTION_READY BLOCKED because the fixture is synthetic/DRAFT. Previous 2026-10-09 DRAFT hashes unchanged. Renderer source was not changed.

CONSTRAINTS: Do not modify fixed renderer or 2026-10-09 historical body/artifacts; no 12:00, Drive/API/GAS/workflow/Portal/production data, push, or deploy.

OPEN OUTCOMES: The repository has no automatic Google Docs save integration for the new authoring CLI; future report creation must provide body plus structured facts/numeric registry to the documented pre-save QA. Live `LIVE_CAPTURED` report execution and trusted visual review remain NOT_RUN.

NEXT NECESSARY ACTION: Use this contract for new 08:00 generation only. Keep 2026-10-09 DRAFT content FAIL and stop before 12:00.

FINAL FIXTURE IDENTITY — The preserved synthetic acceptance fixture uses sentinel report ID `2099-01-01_08-00`, not the historical 2026-10-09 report. Its source hash is `83674443277a75cb1729951a4abee68c8bb4b7d7aebdb9c88c0ef43403bc96f6` and output DRAFT hash is `1aae831a80ca8e5f2c43f1e7f5e9ad926eadd611197195c2e900dfff4946ff48`. The historical-looking intermediate probe was removed. The test PNG banner is a pre-existing renderer label mismatch (`SOURCE_RECONSTRUCTED` vs metadata `SYNTHETIC_FIXTURE`); renderer modification remained out of scope.

## 08:00 mandatory QA gate — Phase 3 (ADD, 2026-10-10)

OBJECTIVE: Make strict 08:00 content QA mandatory before managed save/render/publish paths, record report-bound hashes, and separate technical readiness from production candidacy. Preserve the 2026-10-09 historical body and DRAFT; do not process 12:00.

IMPLEMENTED: Apps Script managed save/menu, pre-publish validation, web sync, historical/structured imports and auto-publish now require the QA receipt. CLI report writers and repository workflows/deploy check changed 08:00 reports. The fixed renderer labels provenance from the snapshot and verifies the source-bound pre-render attestation for LIVE_CAPTURED. QA evidence stores body/source/numeric/snapshot/image hashes and provenance. Synthetic and SOURCE_RECONSTRUCTED stay non-production; production candidacy requires LIVE_CAPTURED, real Docs source, all technical gates and trusted visual review.

RESULT: Python discovery 177/177 PASS; Apps Script Node fixture suite PASS; changed Apps Script source syntax PASS; 11 touched Python files compile PASS; `git diff --check` PASS. Nonproduction synthetic CLI smoke generated one preview with visible `SYNTHETIC_FIXTURE`, matching validation metadata, and production_candidate=false. Historical 2026-10-09 DRAFT hash remains `2e6a18f62e066c4ed230e8ff71e3ee64d502bfa054c0898c1fc08fc758c06860`.

LIMITS: PyYAML is unavailable, so local YAML parser validation is NOT_RUN. No hosted GitHub Actions run or deployed Apps Script execution was performed. The repo-managed paths are covered by local integration/static tests; direct unmanaged Google Docs editor writes are outside this code gate. No actual Drive/API/Portal production write, push, deploy, or commit occurred.

NEXT NECESSARY ACTION: Deploy/execute the Apps Script integration and run hosted CI/nonproduction end-to-end before claiming external enforcement. Keep the historical DRAFT blocked and stop before 12:00.

## 08:00 QA forced connection Phase 4 — Nonproduction acceptance (PARTIAL, 2026-10-10)

SHA RECONCILIATION: The final Phase 2 PNG at `artifacts/0800_visual_fidelity_phase2_20261010_final/2026-10-09_08-00.SOURCE_RECONSTRUCTED.DRAFT.png` and the matching R3 copy both hash to `2e6a18f62e066c4ed230e8ff71e3ee64d502bfa054c0898c1fc08fc758c06860`. The competing `2e6a18f62f196c4...` value was a transcription error; no evidence of file change. Other earlier iteration directories contain different expected image hashes.

LOCAL ACCEPTANCE: Current Python discovery 177/177 PASS; Apps Script local fixture suite PASS; `git diff --check` PASS. No production report paths are modified. No Apps Script deployment, nonproduction Drive write, hosted Actions run, push, or production deploy occurred.

BLOCKERS: No nonproduction Apps Script project ID/config or `clasp` CLI is available. GitHub CLI authentication is invalid and the GitHub API connection failed. Local repo lacks PyYAML, so standalone YAML parser validation is NOT_RUN. Do not infer runtime enforcement from local tests. Phase 4 remains PARTIAL.

NEXT ACTION: Provide/identify the exact nonproduction Apps Script project and make its nonproduction deployment path available. Restore GitHub CLI authentication/network for the repository, then run the hosted checks on a nonproduction branch. Do not connect production credentials or deploy production.
