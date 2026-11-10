# Foundation implementation — 2026-10-04

PRIMARY OBJECTIVE: Resolve SC-01–03 in the five formal Drive v1.8 documents, then implement immutable ReportContext → MarketDataSnapshot → ReportObject → G0–G8 validation foundations and the explicitly authorized P0 regression fixes.

ACTIVE PROFILE: dashboard + data-tool. Base commit: 600a533. Branch: codex/report-foundation-a-b-d-c.

ACCEPTANCE: Explicit dates, immutable retry identity, unknown-cron rejection, weekend new-report rejection; frozen report-bound snapshots; typed numeric markets and legacy read adapter; connected gates with PNG/manifest refusal, full-text Drive verification, rollback/projection/DOM checks; required A/B/D/C fixtures and existing regression checks; five formal Drive readbacks; unchanged production artifact hashes.

CONSTRAINTS: Preserve acquisition, readiness, history, source registry and legacy reads. No push/deploy or production JSON/report Docs/PNG/Receipt mutation. Formal specification updates are expressly authorized. 2026-10-02_21-00 remains UNRESOLVED / UNVERIFIED / NEEDS_REVIEW.

OUT OF SCOPE: E–H Publisher/Projection/Portal/Scheduler reorganization; production persist writer behavior change; canonical identity reconciliation.

FORBIDDEN SUBSTITUTE: Unit checks or new gate API do not prove that the existing live publishing pipelines enforce these gates. Report remaining deployment bypass separately.

OPEN OUTCOMES: None within the authorized A/B/D/C foundation task. Deferred: live Publisher/Projection/Portal/Scheduler enforcement, unresolved 2026-10-02_21-00 identity, existing unsafe canonical writer, historical structure/PNG gaps. These are not silently withdrawn.

NEXT ACTION: Foundation accepted at 0e14412. Phase E dry-run authorized below; prior deferred production outcomes remain open.

## Live Drive-to-Pages publication recovery — 2026-10-16 (ADD)
PRIMARY OBJECTIVE: Promote only complete, contemporaneous, source-bound scheduled Google Docs reports into GitHub canonical history and the public Pages portal, with verifiable end-to-end readback.
ACCEPTANCE: A pre-draft immutable snapshot/context matches the slot; Docs body/revision/hash readback matches; importer issues a v2 receipt; canonical/index/latest/dashboard pass consistency gates; Pages deploy and public full-text readback match; original schedule and report text remain untouched.
CONSTRAINTS: No gate relaxation, no inferred historical snapshot, no report completion or modification, no trigger/schedule change, preserve historical records and fail-closed archives.
OPEN OUTCOMES: PR hosted checks/merge; future scheduled report live import and Pages E2E; 08/12/16/21 repeated slot observations; formal Drive docs readback after amendment.
NEXT NECESSARY ACTION: Complete CI on the publication integration PR, then validate the next actual scheduled report through published-page readback. Until then status is PARTIAL.

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

## Market acquisition-to-evidence recovery — 2026-10-16 (ADD)

PRIMARY OBJECTIVE: For future 08:00/12:00/16:00/21:00 report slots, bind a verified market acquisition to immutable pre-draft evidence and confirm that evidence is present byte-for-byte on GitHub main before the report pipeline proceeds.

ACTIVE PROFILE: data-tool + generic-app. Base: 4efdc2db068db7cd1e1cc2e5a05ef09414dc2e6b.

ACCEPTANCE: Keep acquisition cutoff and evidence schema/hash guards fail-closed; connect the acquisition window and pre-slot recovery to the existing evidence writer; commit market data and evidence; read back evidence from origin/main; record JST/UTC timing, stage status and Actions URL; add targeted tests and hosted CI; submit Draft PR only.

CONSTRAINTS: Do not create evidence after the slot, rewrite historical evidence, overwrite same-ID evidence, relax publication/timeline gates, merge, or claim live recovery from local/hosted tests. Preserve user's dirty primary checkout.

OUT OF SCOPE: Report generation, Google Docs, receipts, projections, Pages and real scheduled-slot acceptance.

IMPLEMENTATION STATUS: Targeted local regression tests PASS. Branch codex/market-data-evidence-recovery-20261016; hosted checks and Draft PR remain open outcomes. No production Actions run, merge, or deployment has been performed from this branch.

OPEN OUTCOMES: Hosted CI on final PR head; reviewable Draft PR; live future-slot evidence and downstream report/Docs/receipt/Pages acceptance remain NOT_RUN. The scheduler/queue cause behind the observed multi-hour trigger delay is UNKNOWN.

NEXT NECESSARY ACTION: Finish code review and CI, create the Draft PR, then wait for an authorized future pre-slot run to verify production evidence readback. Keep the PR unmerged.


## Recovery PR validation — 2026-10-16 (CORRECT)

PR #156 was created OPEN / Draft on base 4efdc2db068db7cd1e1cc2e5a05ef09414dc2e6b, head d3105dd0ff44a86940e02db6fa1d51dd0828abe2. Hosted PR checks both passed on that exact head: Market report frozen-cutoff regression CI run 38885680439, including Python compile and offline cutoff/evidence suites; Delivery health regression CI run 38885680536, including all 16 targeted delivery/evidence tests. PR #156 remains OPEN / Draft and unmerged. Local evidence stays E1/E2; live acquisition, future-slot evidence, and report/Docs/receipt/Pages acceptance remain NOT_RUN.

NEXT NECESSARY ACTION: Keep PR #156 Draft and unmerged pending review. Verify live outcome only on a future scheduled slot after authorized merge.

## Final-head review correction — 2026-10-16 (ADD)

Code review found that the evidence writer reused a caller-supplied pre-write clock for its post-write cutoff guard. Fixed in commit 375c3e71741b5df3fe1e7271e1b6578d845a1e21 by re-reading the live clock after writing and deleting the new file if the slot cutoff has passed. Local targeted suite: 17/17 PASS. Hosted checks on that code head: frozen-cutoff run 38898453782 PASS and delivery health run 38898453962 PASS. PR #156 remains OPEN / Draft and unmerged. E1/E2 only; live scheduled recovery and downstream publication remain NOT_RUN; scheduler/queue cause remains UNKNOWN.

NEXT NECESSARY ACTION: Review PR #156 and, if authorized, merge before observing a future scheduled slot. Do not claim live recovery from these checks.

## PR #156 review follow-up — 2026-10-16 (ADD)

PRIMARY OBJECTIVE: Address every finding in review comment #6215245578 and leave PR #156 updated, validated on its final head, OPEN / Draft, and unmerged.

ACCEPTANCE: (1) freeze/readback failure keeps report readiness blocked while acquisition outcome remains independently auditable; (2) freeze each eligible verified/degraded acquisition before cutoff, reuse same-ID candidate bytes rather than rebuild, and never overwrite; (3) integrate current main and reconcile its workflows/contracts; (4) cover freeze, push, evidence/audit readback, cutoff crossings, audit state transitions, and other-actor cleanup with regression tests. Run targeted tests and both relevant hosted CI workflows on the exact final head.

CONSTRAINTS: Preserve publication gates and cutoff; no historical evidence reconstruction/backfill; no merge, deployment, or production publication. Report all NOT_RUN outcomes accurately.

IMPLEMENTATION STATUS: Latest fetched main `9b400545288f9c199bef86b3b9e33e830b1a9edc` merged locally without conflicts in `9173105d7`; compare was ahead 6 / behind 0 before this follow-up. Code and regression changes are being validated; final hosted CI is still open.

OPEN OUTCOMES: Commit/push the reviewed changes without force, confirm branch remains ahead 0 / behind 0 (or report exact counts), run final-head hosted CI, update PR description with results, verify OPEN / Draft / unmerged, and stop. Live scheduled acquisition and downstream Docs/GitHub publication remain NOT_RUN.

NEXT NECESSARY ACTION: Complete local tests and diff review, append the final evidence record, then commit/push and wait for final-head CI. Do not merge.

## Latest-main resynchronization — 2026-10-16 (CORRECT)

Fetched main advanced to `5797798a2ab41630c88856d2347d20b95a7ccee3` during validation. Merged without conflicts as `e3cdbff2e`; branch now compares 0 behind / 7 ahead. The new main commits changed only production data files; those files are in the merge ancestry and absent from `origin/main...HEAD` PR file diff. Re-run the final local suites after this merge, then push and verify hosted checks on the resulting PR head. Keep Draft; do not merge.

## Latest-main resynchronization 2 — 2026-10-16 (CORRECT)

GitHub main advanced again to `c3dae9fdaea7c05d8006006b6fb052a28e2535f4`; the 2 new commits update economic calendar and USDJPY production data only. Merged without conflicts as `c95ce5810`; branch compares 0 behind / 9 ahead locally. These main-owned data paths remain absent from the PR diff. Push this merge, rerun targeted tests on the final tree, and verify final-head hosted CI and Draft state. Do not merge.

## PR #156 final validation — 2026-10-16 (ADD)

Code head `fa958c370eec2420de21d762630c9c78cfaeacf3` passed both hosted workflows: frozen-cutoff run 38901726328 and delivery-health run 38901726374. Local compileall and 41 targeted tests passed; diff check passed. GitHub confirms PR #156 is OPEN, Draft, mergeable, unmerged, based on current main `c3dae9fdaea7c05d8006006b6fb052a28e2535f4`; compare ahead 10 / behind 0. PR description contains the four changes, evidence, and remaining NOT_RUN/UNKNOWN items.

To make these evidence-record changes rerun both required workflows on the exact final head, frozen-cutoff CI now includes project-control record paths. This trigger-only follow-up must be committed/pushed and both workflows must pass on its resulting head before final stop. Keep Draft; do not merge.

## PR #156 main drift recheck — 2026-10-16 (CORRECT)

GitHub main advanced from `c3dae9fdaea7c05d8006006b6fb052a28e2535f4` to `9615882cf018479bf3cb2eeeb6f6b73367ea764b` in two commits. Inspected the actual main range: only seven production data paths changed (Japan stock archive, close reference, Tokyo stock table, Nikkei metrics, stocks); no acquisition/evidence implementation, contract, workflow, or test files changed. Merged without conflicts as `733fd3821`; local compare 0 behind / 12 ahead. Re-run local tests and both hosted CIs against the synced head. If clean, make PR a merge candidate by marking ready for review; do not merge.

## PR #156 final main and outage recheck — 2026-10-16 (CORRECT)

Main advanced four commits from `9615882cf018479bf3cb2eeeb6f6b73367ea764b` to `d6420e2c3d53a16304bb8d301677e2db4c41da0c`. The actual range changes 15 production data files only (Japan stocks, Nikkei/US dollar-yen supply-demand and market references); no acquisition/evidence code, workflow, or tests changed. Merged without conflicts as `415c28c6d`; local compare 0 behind / 14 ahead before this record commit.

Verified on the synced tree: `data/market/latest.json` is `2026-10-16T20:16:17+09:00`, slot `21:00`, `verified`, with no required-field gaps; `data/report-evidence/2026-10-16_21-00-r1.json` and `reports/2026-10-16_21-00.json` are absent; `reports.json` latest is 2026-10-13 16:00. Do not reconstruct or publish the missed 21:00 slot. The recovery PR applies to future eligible acquisitions. Following local/final-head CI, the user has now directed PR #156 to be reviewed and merged; verify head/base once more, mark ready, and merge the exact approved head. Then observe future-slot production acceptance separately.


## MRF-0800-20261029 — 08:00 issuance integration (ADD)

PRIMARY OBJECTIVE: Safely connect one authentic weekday 08:00 report run from immutable pre-slot evidence through fixed G2 text and exact Google Docs readback into the existing canonical portal path, with no publication on any mismatch.

ACCEPTANCE: A latest-main-based independent Draft PR; same-run identity/revision/body hash/evidence generation/snapshot across stages; create-only duplicate protection; human source-bound scenario review; exact Docs ID/revision/fullText readback; existing portal/canonical/Pages readback; normal/abnormal tests; no gate weakening. External acceptance is separate from CI.

CONSTRAINTS: PR #97 untouched; no main merge, production deployment, Google Drive write, or other-time rollout. TEST_ONLY evidence cannot stand in for production evidence.

OUT OF SCOPE: Actual production rollout and live report publication in this task.

FORBIDDEN SUBSTITUTE: TEST_ONLY capture, fake adapter PASS, passing CI, or Docs save alone is not a restored published 08:00 report.

OPEN OUTCOMES: Trusted G2 source connection, production configuration/IAM, concrete existing-portal invocation, hosted CI on this branch, external Docs/importer/Pages E2E.


## MRF-0800-20261029 continuation

OPEN OUTCOME: Existing importer handoff is still missing. It consumes slot evidence from the main checkout, while the observed TEST_ONLY records are in GCS. A protected generation-pinned transfer and an approved invoke/readback path are required. The existing workflow dispatch writes main and Pages, so live portal verification is outside the current authorization.



## MRF-0800-20261029 staging continuation

COMPLETED: isolated TEST_ONLY evidence-to-importer handoff code, strict Docs issuance-binding opt-in, and hosted regression workflows.
OPEN: Actual G2 capture/body hash, Docs create/readback using that exact body, matching Docs appProperties, human panel-12 review, external GCS staging invocation, isolated importer readback, and any approved production route. These were not supplied or executed; do not claim publication recovery.


### MRF-0800 bridge-test continuation (ADD, 2026-10-30 JST)
For the existing 08:00 issuance objective, added one composed offline contract test covering exact-generation TEST_ONLY staging, importer's slot-evidence receipt validation, Docs source revision, and strict Docs appProperties binding. A body-hash mismatch is held. Local: `test_importer_handoff.py` 12/12 and `test_issuance_pipeline.py` 12/12 PASS; py_compile and `git diff --check` PASS. Evidence E1/E2 only.

PR #188 source head before this addition was `0a37e8c35d8669110aa95560054e2ab275a56569`, based on `e70751bc4a202c84f4322df8748a08775d836458`; latest inspected main is `ec3e38b56397686c781e61de7efe97baeec48544`, 152 commits ahead. The 153 paths changed on main since PR base do not overlap PR #188's 16 changed paths, but latest-main reconciliation remains open before merge/readiness.

OPEN: push and exact-head hosted CI; inspect/reconcile main drift before PR readiness; real TEST_ONLY GCS staging invocation, authentic G2 body and human scenario review, Google Docs API save/readback, importer apply in isolated checkout, canonical persistence, Pages/public DOM, and future approved slot remain NOT_RUN. The 2026-10-30 08:00 Drive document is a display-only archive with missing pre-slot evidence; it was not used by this test. No production or schedule state changed.


## 08:00 importer staging prerequisite recheck — 2026-10-30 (ADD)

PRIMARY OBJECTIVE remains: verify one authorized weekday 08:00 issuance from exact pre-slot TEST_ONLY evidence through the isolated importer boundary, while preserving all identity, freshness, cutoff and readback gates. An offline bridge contract test is supporting evidence, not the final outcome.

ACTIVE PHASE: external TEST_ONLY staging readiness. PR #188 head `7a1b751923dc40c1cfae26e980f49bc10f7b82c9`, based on main `ec3e38b56397686c781e61de7efe97baeec48544`; PR #188 remains OPEN / Draft / unmerged.

COMPLETED: composed offline exact-generation staging → strict importer receipt/Docs-property binding test; local focused suites 12/12 + 12/12 PASS on the prior tested code; exact-head hosted issuance, frozen-cutoff and delivery-health CI PASS.

OPEN OUTCOMES: no local TEST_ONLY GCS auth/CLI or staged exact-generation object; no separate marked staging checkout; no confirmed Docs appProperties bound to the exact frozen G2 body/evidence/snapshot; strict importer runtime and apply; canonical/receipt, Pages/public DOM, and scheduled-slot acceptance. The read-only 2026-10-28 Doc is `閲覧用分析版` and lacks the required pre-issuance source linkage. These gaps remain BLOCKED/NOT_RUN; no historic evidence may be reconstructed.

NEXT NECESSARY ACTION: obtain an authorized TEST_ONLY identity and one exact-generation object, a matching issuance-bound Docs readback, and a separate marked staging checkout. Stage the exact generation and inspect strict-binding dry-run; run `--apply` only if all bindings pass. Otherwise stop and preserve the hold. No production workflow dispatch, Drive write, main change, or Pages deploy is authorized here.


## MRF-INGESTION-20261030-01 active objective (ADD, 2026-10-30 JST)
PRIMARY OBJECTIVE: Keep each scheduled report slot's evidence-backed delivery state observable from source ingestion through Docs readback, canonical receipt, Pages deployment, and public readback, without treating a saved archive or code test as completed publication.
ACTIVE PROFILE: generic-app + data-tool.
ACCEPTANCE CRITERIA:
- Import logs distinguish canonical ingestion, archive-only holding, Docs readback receipt, archive promotion, Pages deployment, and public DOM readback.
- Archive-only and unknown receipt/status pairs never emit a publication-success label.
- Focused offline tests and the relevant PR workflow run on the exact PR head.
- The original dirty checkout, existing PRs, main data, Drive files, receipts, schedule, Cloud settings, and Pages production state remain untouched.
CONSTRAINTS: Implement on a branch from GitHub main 52e99701f3bc71a77bdde31729e0f887f44a9135; do not merge, deploy, or write production Drive/Cloud state without a later explicit approval.
OUT OF SCOPE: Completing the full live four-slot transaction in this change; upstream generation, external scheduler provisioning, real Docs writer, actual PNG review/save, production publication, and runtime public-DOM acceptance remain independent outcomes.
STATUS: IN_PROGRESS; implementation branch codex/report-ingestion-stage-truth-20261030.
OPEN OUTCOMES: exact-head hosted CI, Draft PR creation/readback, formal Google Docs fixed-ID sync assessment, and four-slot production E2E. `test_report_contract.py` remains NOT_RUN because this Windows Python lacks IANA tzdata.
FORBIDDEN SUBSTITUTE: a successful import, local projection check, unit/CI result, or existing Drive file alone is not proof of formal publication or whole-system completion.
NEXT NECESSARY ACTION: inspect the final diff, commit/push this branch, submit a Draft PR, and record exact-head CI and remaining external outcomes.


### PR #189 code-head CI evidence (ADD, 2026-10-30 JST)
PR #189 is OPEN / Draft / unmerged. Exact implementation head `71fce84ddfa814a3b0c66bbc0545d36e78bfec1a` passed hosted sync recovery run 40968791396, frozen-cutoff run 40968791427, and delivery-health run 40968791433. Evidence/docs were then updated, so final PR-head CI confirmation remains open. Hosted sync CI also passed `test_report_contract.py`, which local Windows Python could not import due missing IANA tzdata. Live scheduled delivery and downstream public readback remain NOT_RUN.


### MRF-INGESTION-20261030-01 matrix source-link correction (CORRECT, 2026-10-30 JST)
Corrected the four 10/29 report evidence links in HANDOFF from old main `52e99701f3bc71a77bdde31729e0f887f44a9135` (paths absent there) to current main `ec3e38b56397686c781e61de7efe97baeec48544`. Readback confirms all four are still `SOURCE_ARCHIVED` with `NOT_VERIFIED` infographics and no matching receipts. This is evidence-link repair only; live acceptance remains NOT_RUN.


## MRF-0800-IMPORTER-COMBO-20261030-01 — integrated importer validation (ADD, 2026-10-30 JST)

PR #188 now carries the compatible code and documentation from PR #189 for joint Draft validation. At head `d8394400dac2935f338d4d2ae9c068db689526eb`, exact-head issuance, synchronization recovery, frozen-cutoff and delivery-health hosted CI all PASS (runs 40989666087, 40989665981, 40989666048, 40989666122). Logs show importer handoff 12/12, issuance pipeline 12/12, and ingestion outcome 4/4, including the composed bridge and status-helper cases.

OPEN OUTCOMES remain: real TEST_ONLY GCS staging, exact issuance-bound Docs readback, isolated importer dry-run/apply, canonical receipt persistence, Pages/public DOM, and a future authorized slot. The standard GCS CLI/ADC, staged object and sibling staging checkout are still absent. The available 2026-10-28 Docs item is display-only and cannot satisfy issuance binding.

PR #188 and PR #189 both remain OPEN / Draft / unmerged. PR #189's code and affected formal documentation are now included in #188 for combined validation; do not merge both independently. Next necessary action: provision the permitted TEST_ONLY prerequisites, run the isolated staging gates, and settle the duplicate PR disposition before any merge.

## MRF-0800 staging boundary continuation (ADD, 2026-10-30 JST)

ACTIVE PHASE: hosted verification of the isolated TEST_ONLY staging boundary, then external prerequisite reconciliation. PR #188 code/test head `4125df20409bcb0337677ba12ec2e87590b2d8db`, based on main `ec3e38b56397686c781e61de7efe97baeec48544`; four hosted workflows PASS, including 12 issuance and 16 importer-handoff tests.

COMPLETED: closed root-ancestor overlap, substring-only TEST_ONLY identifier acceptance, non-test-only object path, and symlink-parent escape cases; requirements/specification/operations and evidence records updated together.

OPEN: independently authenticated exact-generation GCS read; authentic G2 body and human scenario review; matching Docs ID/revision/fullText/hash/appProperties readback; isolated staging and strict importer dry-run; apply only after all bindings pass. Canonical/receipt persistence, Pages/public DOM, and a future authorized slot remain NOT_RUN. PR #189 is still OPEN/Draft with duplicate code; no independent merge or production change.

## MR-DELIVERY-STABILIZE-20261104-01 — current continuation

PRIMARY OBJECTIVE: Complete the authorized PR #188 code and test work for a fail-closed formal issuance path; keep production, Drive, main merge, and Pages operations outside this candidate run.
ACTIVE PROFILE: data-tool + generic-app + dashboard.
CURRENT MAIN: `27a7a1f6fb903901f345d71ec9c4cfce686f8b0f`.
PR #188: OPEN / Draft / unmerged at `f0a6517df07bc9a5a57a47ac02126b7ab933c421`, synchronized with latest main; PR diff is 25 paths. Exact-head hosted CI passed on that SHA.
OPEN OUTCOMES: (1) implement and test a concrete authenticated bridge from issuance to strict importer, canonical report + receipt commit, and Pages public-body readback; (2) enable production authorization/identities only through the existing review boundary; (3) prove a future real 08:00 transaction and later 12:00/16:00/21:00 rollout. Local Python tests were NOT_RUN because this Windows session has no accessible interpreter.
ROOT CAUSE: `run_issuance` accepts only the abstract `PortalPublisher` Protocol. No concrete implementation invokes the strict importer or proves canonical/receipt/Pages readback. TEST_ONLY staging is not a production handoff.
FORBIDDEN SUBSTITUTE: exact-head CI and fake adapters do not prove live Docs, canonical/receipt, Pages, or production acceptance.
NEXT NECESSARY ACTION: design the concrete bridge with exact-slot selection, pinned evidence identity, create-only behavior, durable readback, and a protected write/deploy boundary; add normal, failure, duplicate, and retry tests; then run hosted CI on the new head. Keep Draft until missing live acceptance and review are separately satisfied.

## MR-ISSUANCE-CONNECT-20261104-02 continuation

PRIMARY OBJECTIVE remains completion of PR #188's fail-closed formal issuance code and automated tests; production operation is excluded. Current main at start was `2df3113ac0934a92056c4546d35b210f390a393b`; code-test head `3f2a32324273032b51124fd96da7067ad251ea51` is on PR #188, still OPEN / Draft / unmerged. Exact-head hosted issuance, sync recovery, frozen-cutoff, delivery-health, dashboard-health and archive-recovery checks passed. Evidence ledger has run IDs and limits.

IMPLEMENTED: concrete adapter, exact-title importer entry point, create-only pinned evidence transfer, GitHub CAS canonical/receipt/index update with file readback, exact Pages-run and live JSON body/hash verification; 61 hosted unit/fixture tests across issuance pipeline, portal adapter and TEST_ONLY handoff.

NOT_RUN: local Python on Windows; live Docs write/readback; production main canonical/receipt write/readback; Pages deploy/public fetch; other slots and 12-slot/10-workday acceptance. No external write or merge occurred.

NEXT: settle required protected GitHub Actions environment and least-privilege identities; perform a separately authorized eligible 08:00 E2E after merge/review; reconcile all external stages; only then plan 12:00/16:00/21:00 generalization.

### MR-ISSUANCE-CONNECT final code-test correction

Latest exact code-test head: `e31f50db5c0c6f1316ea3c28eddd889d04a1fb13`. Composed chain test is now present and passed: Evidence/G2 validation → Docs fake writer/readback → exact-title strict importer and real receipt/evidence validation → fake atomic GitHub file/ref readback → Pages workflow stub and public report JSON text/hash comparison. Actions: issuance 16 + portal 30 + handoff 16 PASS; sync recovery, frozen-cutoff, delivery-health, dashboard-health, archive-recovery all PASS. This is E2 fixture evidence only; production/external stages remain NOT_RUN. Latest PR head will include this result-record update and must retain the same code tests as the preceding exact code head.

### MR-ISSUANCE-CONNECT latest exact-head run

Added an embedded different-reportId evidence regression. Exact code-test head `9c8ec84265891469f5ec473803a9e4bc6c15370f` passed issuance pipeline 16/16, composed portal/importer 30/30, TEST_ONLY handoff 16/16 and all five related regression workflows. External production stages remain NOT_RUN; no authorization boundary changed. The latest PR commit records this evidence and triggers a final documentation-head CI check.

### MR-ISSUANCE-CONNECT follow-up objective status

The controlled 08:00 CLI entrypoint, GitHub create-only conflict/retry guards, rendered DOM identity/body validator, and read-only auth preflight are implemented in the current candidate. The production Pages verifier invokes public-mode DOM validation after the Pages JSON check; failures include the top-level completed stages. Local Node and diff checks PASS; Python and hosted CI are NOT_RUN. Fine-grained GitHub credential `contents:write` scope is UNKNOWN to read-only APIs and blocks preflight READY until administrator confirmation. Production Docs/main/receipt/Pages/public DOM and actual scheduled invocation remain NOT_RUN. Keep PR #188 Draft and unmerged pending exact-head CI.

### MR-ISSUANCE-ENTITY-20261105-02 status

New pinned-generation G2 consumer has been added to the existing 08:00 CLI. This does not generate a G2 bundle. Source review found only an Apps Script path that reads an existing Google Doc and publishes it; the ChatGPT task and installed trigger/history are not accessible here. Production remains blocked by BLOCKED_G2_PRODUCER_MISSING, and ownership config remains legacy for every slot. No merge, external write, Pages deployment, auth/environment change, or scheduled task change was performed. Exact-head hosted CI is pending and will be recorded after final main sync.

### MR-ISSUANCE-ENTITY-20261105-02

The CLI now supports exact-generation GCS G2 intake and verifies explicit report/revision/Evidence target fields. Apps Script still reads existing Docs and does not invoke the new G2 producer adapter. External ChatGPT task settings and adapter invocation are not inspectable. Producer identity remains unverified, the preflight fails closed with BLOCKED_G2_PRODUCER_MISSING, and ownership remains apps_script_legacy. Main `8a09c2e4838d044e04b9e162961ec2d042f8963c` was synchronized with zero path overlap. Exact tested code SHA `9fd7470606bbf2bdd9fbcc9fd1e9f250b63de736`: 110 Python tests and all 10 related Actions PASS. Latest PR head is a documentation-only descendant; the executable tree is unchanged. Production E2E remains NOT_RUN.

## MR-ISSUANCE-G2-PRODUCER-20261105-03 — implementation and connection status

Implemented in the PR: `scripts/reporting/g2_bundle_producer.py` exposes `TrustedG2BundleProducer.freeze_and_store()`. It accepts final task-authored text plus the exact pre-slot Evidence envelope, binds reportId/revision/body SHA/frozen_at/evidenceId/snapshotId and scenario review, writes one create-only GCS object, and reads back its exact generation/bytes. Identical retry reuses the same generation; conflict or uncertain readback blocks. The 08:00 CLI consumes the returned object/generation with explicit report and Evidence references.

This adapter is not yet invoked by the existing ChatGPT task, and its production GCP workload identity/bucket IAM is not configured or verified. No task callback or installed schedule was inspected. Therefore preflight remains `NOT_READY` and production status remains `BLOCKED_G2_PRODUCER_MISSING` until the task-to-adapter handoff and trusted writer identity are established. Do not infer G2 from an existing Docs file or change the task schedule.

On code SHA `9fd7470606bbf2bdd9fbcc9fd1e9f250b63de736`, six isolated Python suites passed 110 tests (17+39+16+17+7+14); all 10 related Actions passed. This is fixture/CI evidence only, not a live task, GCS, Docs, GitHub, or Pages result.

## MR-ISSUANCE-G2-PRODUCER-20261105-03 — synchronized code acceptance

Executable tree on synchronized code SHA `a4641d4fa1d55120e1e95af0548d06a886dafb17` passed 110 Python tests under Actions Python 3.12: pipeline 17, portal 39, importer handoff 16, preflight 17, pinned G2 handoff 7, producer 14; compile and CLI smoke also passed. All ten related Actions passed: [issuance 41907967951](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967951), [UI/DOM 41907968119](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968119), [sync recovery 41907967813](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967813), [Apps Script validation 41907967892](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967892), [frozen cutoff 41907968232](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968232), [delivery 41907968211](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968211), [dashboard health 41907967835](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967835), [eligibility 41907968113](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968113), [historical recovery 41907968451](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968451), and [saved-source QA 41907968393](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968393).

Main `ba8d09a1b1170b56b42c8f33c125a19f120fb0dd` was synchronized in merge commit `a4641d4fa1d55120e1e95af0548d06a886dafb17`. Main's only change since the previous sync was `data/usdjpy-volume.json`; it did not overlap the 44 PR paths and is absent from the PR diff. PR #188 remains OPEN/Draft/unmerged. Live G2 task invocation, workload identity/IAM, installed trigger inventory, authenticated preflight, Docs, canonical/receipt and Pages writes remain NOT_RUN or UNKNOWN. The adapter's automated pass does not remove BLOCKED_G2_PRODUCER_MISSING.

## MR-ISSUANCE-TIME-CONTRACT-20261105-01｜継続状態

- 08:00時刻契約を修正：pre-slot Evidenceを維持し、G2生成・レビュー・freezeは08:00〜08:40に整合。CI確認待ち。
- Latest main c82235d39bbe03c3ce8833a061cb1daface84a32を4つのデータ/履歴JSON込みで同期。PR履歴・既存ファイルは保持。
- 未完了：ChatGPTタスク出力との実接続、信頼ID/作成主体の証明、Apps Script deployed version/triggers/history読取、承認付き本番08:00 E2E。
- Ownerはapps_script_legacyのまま。PR #188未マージ。

### G2 provenance and owner blockers

- G2 producer identity preflight now requires a matching Cloud Storage create audit record for exact object/generation and independently read-back body hash; environment self-report cannot authorize PASS.
- Admin work not performed: verify/enable Data Access audit logs and logging reader permission, establish protected GitHub OIDC→GCP service identity, confirm task output handoff, inspect deployed Apps Script triggers/history, and approve future one-slot E2E.


## MR-G2-TASK-HANDOFF-20261111-01 — 2026-11-11 JST

Source: user integration instructions and PR #188; prior head `b8ba8817f78294d9314f4fe20413b4b5b3dc4cbd`.
Affected canonical paths: requirements.md, specification.md, operations.md, DOCUMENT_CONTROL.md; project-control objective, decisions, lessons and evidence ledger. Google Docs fixed IDs remain unchanged; their current revisions and runtime access were not available, so synchronization/readback is NOT_RUN. Body-authoring changes are specified below for the fixed body-authoring manual, pending authorized access.

- Scope: task-output intake boundary plus an isolated chain; no production release. `task_output_handoff.freeze_task_output` reuses `TrustedG2BundleProducer.freeze_and_store`. Caller authentication must occur in an authorized host, outside task JSON. `VerifiedTaskInvocation` is a typed host contract, not an authentication implementation or a GCS provenance attestation.
- Body-authoring handoff contract: schemaVersion=1, report (date/time/report_id/revision), full_text with terminal newline, body_sha256, evidence_ref (object/generation/evidence_id/snapshot_id), frozen_at and scenario_review. Preserve full text and review quote offsets exactly. No Docs-derived substitute, inferred review, historical Evidence reconstruction or deadline extension is allowed.
- Independently configured evidence_reader reads the pinned generation; request-supplied Evidence bytes are ignored. The existing producer validates its exact bytes/hash/time/report/revision and persists G2 create-only. Return g2_ref object/generation/SHA-256, report/revision, Evidence reference and diagnostic invocation identity. Publication and notification remain NOT_RUN.
- Actual task-to-host authentication, callback/output access, installed Apps Script deployment/triggers and Google Docs permissions are UNKNOWN. The official scheduled-task documentation describes schedules/chat context and supported app events, but does not establish this account's task-to-GCS interface: https://learn.chatgpt.com/docs/automations . Therefore live task handoff is BLOCKED_G2_TASK_HANDOFF. No undocumented API or invented task webhook is used.
- Evidence must precede 08:00; review/freeze must remain within 08:00–08:40. The existing issuance CLI continues to enforce ownership and protected production gates. All four configured slots remain apps_script_legacy; weekday 08:00/12:00/16:00/21:00 and no weekend slots are unchanged.
- Isolation: task input -> exact Evidence -> immutable G2 -> fake Docs -> fake canonical/Receipt/Pages -> exact HTMLParser text; UI CI additionally feeds this generated canonical into the real report renderer and Playwright public-mode DOM validator. External stores/adapters remain simulated; this is not TEST ONLY live-service or production proof.
- Local verification: Python 3.13, ten targeted suites (task handoff, pipeline, portal, importer handoff, preflight, G2 handoff/producer, Evidence and WIF read/create-only), 168 tests, 167 PASS / 1 SKIP. Hosted final-head CI and browser DOM remain pending at this record's creation; older head successes are not reused.
- Read-only Environment API: report-publication exists and has a required reviewer, but prevent_self_review=false. Custom branch policy is enabled; exact branch inventory and admin bypass remain unverified. Protected preflight is not ready. Production WIF/IAM/GCS audit principal/Docs write scopes/GitHub write scopes are UNKNOWN; authenticated preflight and production E2E NOT_RUN. No configuration was changed.
