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


# Market data completeness recovery — 2026-10-11

PRIMARY OBJECTIVE: Make every market data item required by the report explicitly acquired, validated, date-aligned, and persisted, or automatically reported as missing, while preserving existing behavior and Google Sheets structure.

ACTIVE PROFILE: data-tool. Run ID: market-data-completeness-20261011.

ACCEPTANCE: Remove the fixed Nikkei futures contract month; expand acquisition to the report contract; detect an incomplete or stale report input; repair close-row persistence and safe fill-only history recovery; handle delayed Actions and bounded timeouts; compare source coverage, acquisition completeness, and save/readback evidence against diagnosis run market-data-diagnosis-20261011.

CONSTRAINTS: Preserve existing sheet tabs/headers/cell values and successful flows. Never present stale, different-session, or unverified data as current. Do not expose credentials. External save/readback requires the configured Google service account secret.

OUT OF SCOPE: Merge/deploy, credential creation, GitHub Actions platform internals, and asserting full report completeness from common-market-only success.

IMPLEMENTED: Dynamic quarterly futures contract selection, five major equity indices, stale-aware final refresh, timeout/retry bounds, 28-item readiness validation, differentiated acquisition/authentication status, confirmed date-matched JP10Y reuse, and fill-only close history repair.

EVIDENCE: 30 Python tests PASS; 8 scripts compile. Existing source configuration maps 16/28 report items after the change (14/28 before). The retained JP10Y record 3.001% for 2026-10-09 passes the new adapter and validation. An official FRED DGS10 daily CSV adapter now maps US10Y into the existing close field. Existing observed common snapshot remains 10/10 verified. FRED live fetch, Google Sheets save/readback, and new-source scheduled acquisition have not been executed.

OPEN OUTCOMES: O1 full 28-item source coverage and runtime completeness remain open (12 items have no common acquisition path). O2 confirm the five new index sources and FRED DGS10 in a scheduled run remains open. O3 Google Sheets write/readback/history fill remain open until GOOGLE_SERVICE_ACCOUNT_JSON is configured. O4 exact close-row historical repairs beyond retained same-date confirmed sources remain open.

NEXT ACTION: Configure the authorized service-account secret, run the scheduled acquisition and close sync, confirm readback and fill-only results, then add and validate source paths for the remaining 13 contract items without relaxing date/session checks.


## 2026-10-11 continuation status
Connected the 25-day and 200-day Nikkei deviation routes in the existing market source catalog, registered their 25/200-bar Yahoo calculation windows, added a 120-hour weekend tolerance, and wired verified same-date results into the 08:00 report builder. Existing fill-only mappings to the current deviation columns remain in place. The catalog's original entries were preserved.

OPEN OUTCOMES: 18/28 report-item source/config routes are connected (64.3%). CME yen/USD, Nikkei valuation (PER/PBR/EPS), and five Prime indicators remain open. The isolated adapter run returned 0/18 verified because this execution environment could not resolve source hostnames (DNS name-resolution failure); this is an environment/network limitation, not evidence of a source outage. An independent TradingView cross-check returned 16 current quote/bar responses for a separate market sample, of which the OSE daily bar was dated 2026-10-08 while the shared close target was 2026-10-09; these observations do not count as adapter-runtime passes. Whole-contract Sheets save/readback remains NOT_RUN (0/28). Historical fill remains 5/13 (38.5%); eight Prime turnover/volume gaps remain. GitHub Actions runtime and service-account save/readback remain unverified. Nikkei/JPX source authorization and publication scope are unconfirmed.

NEXT NECESSARY ACTION: Use an authorized source for the ten remaining report items; verify contractual rights for Nikkei index derived values and JPX Prime metrics before enabling publication. Then run the configured source adapters and Sheets save/readback through GitHub Actions, repair only blank historic cells, and keep PR #94 OPEN/DRAFT until all acceptance checks pass.