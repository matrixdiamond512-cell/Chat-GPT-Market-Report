# Infographic Validator v1.0 — implementation report

Date: 2026-10-07 JST
Branch: `codex/report-foundation-a-b-d-c`
Mode: local/offline only. No commits, network calls, production artifact writes or external publication were performed.

## Implemented

- Immutable source lock over report ID, title and exact full-text SHA-256; spec also pins the validated snapshot ID.
- Reused existing G0/G1 market snapshot gates before spec/prompt construction. STALE or UNAVAILABLE data is WATCH and blocks image generation.
- Exact required-heading checks, six-market coverage, time-slot contamination checks and fixed time-specific timeline validation.
- Decimal numeric checks, required instrument/unit/as-of/source-section metadata, snapshot binding and price-derived direction checks.
- Hard rejection of decorative financial charts, gauges, unsupported visual elements and people in typed infographic specs.
- Prompt builder accepts only a passing structured spec and includes hard prohibitions and source-only number instructions.
- PNG structural validation (the existing PNG CRC/pixel decoder is reused); JPEG signature/end-marker checks; image hash is bound to the Vision review. Unsigned/caller-supplied claims remain WATCH. A configured provider HMAC can authenticate the review schema and exact report/body/source-Doc/Drive-image/image identities; the shared Python/Apps Script payload is regression-tested cross-runtime.
- Identity-bound structural check for Google Docs, Drive image, GitHub, receipt and Portal evidence. Bare PASS flags are rejected. Supplied evidence claims are not trusted external observations; live stages remain NOT_RUN.
- Completion gate requires PASS for market data, body, infographic, Docs, Drive image, GitHub, receipt and Portal. Dry-run has no external side effects.
- Existing Apps Script publication now requires `validateMarketReportBeforePublish_`, re-reads the same Google Docs file and compares normalized text plus SHA, loads the exact-slot review JSON, verifies provider HMAC and image/document identity, and completes these gates before any GitHub write. Missing trust configuration or any mismatch fails closed. The CI checks the order and exercises matching/tampered review and Docs fixtures. This applies to manual and scheduled publish calls.
- Per-report validation audit files; root `AGENTS.md` safety rules; complete request preserved in `INFOGRAPHIC_VALIDATOR_SOURCE_SPEC.md`.

## Validation stages

Market data (G0/G1) → report body → locked infographic spec/pre-generation → generated image/post-generation → Google Docs save/readback → Drive image save/readback → GitHub registration → receipt → Portal publish/readback → final completion gate.

The executable implementation stops at the externally connected boundary. The local CLI records live external stages as NOT_RUN because real adapters are not configured.

## Changed files

New: `AGENTS.md`; `docs/INFOGRAPHIC_VALIDATOR.md`; this report; `docs/project-control/INFOGRAPHIC_VALIDATOR_SOURCE_SPEC.md`; `scripts/market_report.py`; `scripts/reporting/infographic.py`; `scripts/test_apps_script_infographic_gate.js`; `tests/test_infographic_validation.py`; `tests/fixtures/vision_attestation_contract.json`; `validation/2026-10-02_08-00/{full_validation,report_validation,pre_validation,publication_validation}.json`.

Updated: `apps-script/MarketReportWebSync.gs`; `.github/workflows/apps-script-prepublish-validation.yml`; `docs/project-control/OBJECTIVE_CARD.md`, `EVIDENCE_LEDGER.md`, `DECISIONS.md`, `LESSONS.md`.

No Portal, report JSON, receipt, Drive, GitHub ref or deployment was changed. Apps Script source and its CI validation were updated locally; the deployed Apps Script project was not updated. No commits were made.

## Failure reasons

The stable reason catalog is in `docs/INFOGRAPHIC_VALIDATOR.md`. Core reasons include `MISSING_REQUIRED_REPORT_SECTION`, `SOURCE_CHANGED_AFTER_LOCK`, `TIME_SLOT_CONTAMINATION`, `INVALID_TIMELINE`, `NUMBER_NOT_FOUND_IN_SOURCE`, `NUMERIC_DRIFT`, `DIRECTION_MISMATCH`, `DECORATIVE_CHART_DETECTED`, `UNSUPPORTED_VISUAL_ELEMENT`, `VISION_ATTESTATION_INVALID`, `VISION_ATTESTATION_KEY_INVALID`, image/Vision-review failures, and Docs/Drive/GitHub/Receipt/Portal identity/readback failures.

## Regression and acceptance evidence

- Infographic regression tests TEST 01–12: PASS. Additional source lock, exact-heading, direction, typed market provenance, unsigned Vision WATCH, signed-attestation authentication and identity-bound publication evidence tests: PASS.
- Full Python `tests/` suite after signed-provider extension: 145/145 PASS, including the 23 infographic validator cases.
- Existing selected script regression modules: 16/16 PASS.
- Apps Script narrative and Portal UI foundation regression: PASS.
- Apps Script WebSync syntax and narrative tests: PASS. Cross-runtime Python/Apps Script fixture verifies the canonical HMAC payload/signature; Apps Script gate accepts matching identities, rejects a different Drive image, and rejects changed Docs text. Static checks confirm all gates precede GitHub writes. `git diff --check` passes with repository CRLF accounted for.
- Python AST parse: 149 script files PASS.
- Actual sample Full Validation on `tests/fixtures/2026-10-02_08-00.json`: expected INCOMPLETE/exit 1. Body FAIL due seven missing required sections; market-data FAIL because the legacy fixture has no immutable snapshot; infographic and all later stages NOT_RUN. Audit is under `validation/2026-10-02_08-00/`.
- Production-scope check: report JSON, dashboard/latest data, images, receipts and Portal sources remain unchanged. Apps Script and its CI workflow contain the reviewed local prepublish gate; no deployed project, remote repository or external service was changed. No remote-state comparison was run.

## Acceptance status

PASS: source lock; same-report slot binding; number rejection and 1-digit drift; derived direction; 12:00/16:00 timeline checks; typed chart/gauge/person rejection; fail-closed Docs/Portal/receipt gates; deterministic regression cases; no local production/Portal changes.

INCOMPLETE: no real trusted Vision provider or matching HMAC secret is configured; only fixture signing was tested. Apps Script independently verifies the shared signed review contract and same-file Docs readback but does not invoke the local Python runtime. Exact Drive image bytes were exercised with fixtures only. GitHub/receipt/Portal adapters; actual successful sample full workflow; external idempotency/recovery and live readback remain open. Thus no real image can exceed WATCH here, external stages remain NOT_RUN, and formal COMPLETE is not available in this offline implementation.

Evidence ceiling: E3 synthetic behavioral scenarios and local fixture behavior. No E5 live publication claim.

## Review split — 2026-10-07

The original review branch (`codex/report-foundation-a-b-d-c`) combined Validator, accepted Foundation, and Phase E work in one 78-file diff. A review-only branch was reconstructed from the locally available latest `origin/main` commit `606e3da11da85dde646a692d1659b8960e03f253` as `codex/infographic-validator-v1-review`.

The split retains the Validator implementation, Apps Script prepublish gate, its tests/attestation fixture/audit, the source specification and minimal project-control records. It also retains only the report context, frozen snapshot, report-heading parser, G0/G1 and transaction gate modules required by the Validator and its regression fixtures. `report-core-v3.js`, Phase E publisher/recovery files, report-building/structuring/persistence scripts, unrelated formal-document readbacks, and production report data are excluded.

Local evidence on the split candidate: Python suite 75/75 PASS, Infographic suite 23/23 PASS, Apps Script narrative and signed-gate tests PASS, Apps Script syntax PASS, shared HMAC fixture exercised by Python and Apps Script tests PASS, Python AST 145 scripts PASS, All-Slot Report UI workflow-equivalent checks PASS, and Apps Script Pre-Publish workflow-equivalent order checks PASS. After GitHub access returned, `origin/main` advanced to `606e3da11da85dde646a692d1659b8960e03f253`; the review branch was rebased onto it without conflicts. No live production services were contacted.
