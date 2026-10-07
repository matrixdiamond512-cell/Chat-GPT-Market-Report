# Market Report Infographic Validator

## Purpose

This layer binds a report body, infographic specification, generated image and publication evidence to one report ID. A report ID is `YYYY-MM-DD_HH-MM`; each time slot is independent. Validation is fail-closed and reports machine-readable failure reasons.

## Stages

1. Market data and source report validation (the existing G0–G2 transaction gates validate the frozen context, snapshot and body).
2. Infographic source lock: exact UTF-8 body SHA-256, report ID and title.
3. Required body and six-market checks.
4. Pre-generation infographic checks: report identity, source hash, time-specific timeline, sections, market coverage, numeric subset/provenance, direction, time-slot contamination and disallowed elements.
5. Prompt construction from a passing JSON specification. It always prohibits decorative charts, gauges, invented price graphs and people.
6. Post-generation PNG/JPEG structure plus identity-bound Vision review. An unsigned/caller-supplied review remains `WATCH`. A provider attestation can become `PASS` only when its HMAC matches the configured trusted provider and it binds report/title/body SHA, source Docs ID, Drive image ID, image SHA, review ID/time and every required visual check.
7. Google Docs readback evidence must match title, report ID, exact source body/hash and the pinned file ID.
8. Drive image evidence must match the same pinned file ID, expected name, folder, MIME type and bytes/hash.
9. Git registration evidence must use `reports/<report_id>.json` and a full commit SHA.
10. Receipt evidence must reference the same report and commit and be `VERIFIED`.
11. Portal readback must match the report, latest ID, title, date, time and body hash.
12. `COMPLETE` is emitted only if all seven completion groups are `PASS`.

The currently available publication path remains offline-only. `market_report.py publish --dry-run` checks the schema/identity consistency of supplied evidence claims and performs no network or production writes. It leaves live Drive/GitHub/Portal stages `NOT_RUN` even if the supplied JSON says `PASS`; fixture-mode Phase E receipts are not production receipts. The command never publishes.

The local Trusted Vision Signer contract and its dry-run CLI are documented in [TRUSTED_VISION_SIGNER.md](TRUSTED_VISION_SIGNER.md). A fixture review is not a real Vision observation and cannot be trusted by a production provider identity.

The existing Apps Script `publishWebReportObject_` now requires strict body validation, same-file Google Docs text/hash readback, an exact-slot PNG, and a signed review file named `マーケットレポート_<date>_<HH-MM>.vision-review.json` before any GitHub write. The signed review must contain the fields represented by `tests/fixtures/vision_attestation_contract.json` (without `test_secret`, `payload`, or fixture values) and an HMAC-SHA256 `signature` over the canonical payload. Configure `MARKET_REPORT_VISION_HMAC_KEY` and `MARKET_REPORT_TRUSTED_VISION_PROVIDER` as Apps Script Script Properties; the review signer must use the same key and provider identity. The key must contain at least 32 UTF-8 bytes. The Python CLI reads those two values from environment variables. Missing configuration, image/document identity mismatch, incomplete checks or a bad signature blocks publication. No production secret values are stored in this repository, and no trusted provider is configured in this workspace.

## CLI

Run from the repository root with Python 3.12:

```text
python scripts/market_report.py validate-report --report reports/<report_id>.json
python scripts/market_report.py build-infographic-spec --report reports/<report_id>.json --output validation/<report_id>/infographic_spec.json
python scripts/market_report.py validate-infographic-spec --report reports/<report_id>.json --spec validation/<report_id>/infographic_spec.json
python scripts/market_report.py build-infographic-prompt --report reports/<report_id>.json --spec validation/<report_id>/infographic_spec.json
python scripts/market_report.py validate-image --report reports/<report_id>.json --spec validation/<report_id>/infographic_spec.json --image images/<name>.png --vision-review validation/<report_id>/vision_review.json
python scripts/market_report.py full-validation --report-id <report_id> --dry-run
python scripts/market_report.py publish --report reports/<report_id>.json --spec validation/<report_id>/infographic_spec.json --image images/<name>.png --vision-review validation/<report_id>/vision_review.json --evidence validation/<report_id>/publication_evidence.json --dry-run
```

`build-infographic-spec` outputs a DRAFT. It does not infer untyped market numbers. The source's typed market rows are carried as cards with value, unit, as-of timestamp and source section. Finish and validate the panel list before building a prompt.

`--force` records `OVERRIDDEN` and can never change `INCOMPLETE` into formal `COMPLETE` or a publication PASS.

## Evidence formats and limitations

The Vision review file contains a `checks` object with booleans for `decorative_charts`, `gauges`, `invented_charts`, `people`, `title_correct`, `date_correct`, `time_correct`, `required_sections_present`, `timeline_correct`, `numbers_match`, `text_overflow`, `headings_match`, and `major_typos`. Missing evidence or checks are failures/NOT_RUN. The local trust settings are not configured, so caller-supplied reviews remain `WATCH`; the shared test fixture proves cross-runtime payload/signature compatibility only, not a real Vision observation.

Publication evidence must include full identity-bound readback fields. Bare `{ "status": "PASS" }` flags cannot pass the structural checker. The checker returns `STRUCTURE_PASS`, not publication PASS. There are no live Google Drive, Google Docs, GitHub, Actions, Pages or Portal adapters in this implementation. Actual live publication and public readback are `NOT_RUN`.

Number tokens are compared as exact decimal values (comma grouping is ignored); provenance fields are required for each typed numeric card. Direction checks derive from `previous` and `current` values. Automated visual review can still miss semantic errors; independent Vision evidence and human review remain required for real use.

## Machine failure reasons

`EMPTY_REPORT_BODY`, `INVALID_REPORT_IDENTITY`, `REPORT_ID_MISMATCH`, `SOURCE_LOCK_MISMATCH`, `SOURCE_CHANGED_AFTER_LOCK`, `MISSING_REQUIRED_REPORT_SECTION`, `MISSING_REPORT_TITLE`, `REPORT_TITLE_IDENTITY_MISMATCH`, `REPORT_TIME_MISMATCH`, `MARKET_DATA_SNAPSHOT_NOT_FOUND`, `MARKET_DATA_VALIDATION_FAILED`, `MARKET_DATA_NOT_PASS`, `SNAPSHOT_ID_MISMATCH`, `SOURCE_NOT_LOCKED`, `MISSING_REQUIRED_SECTION`, `INVALID_TIMELINE`, `TIME_SLOT_CONTAMINATION`, `NUMBER_PROVENANCE_MISSING`, `NUMBER_NOT_FOUND_IN_SOURCE`, `NUMERIC_DRIFT`, `DIRECTION_MISMATCH`, `DECORATIVE_CHART_DETECTED`, `UNSUPPORTED_VISUAL_ELEMENT`, `IMAGE_NOT_FOUND`, `UNSUPPORTED_IMAGE_FORMAT`, `INVALID_IMAGE_BYTES`, `VISION_REVIEW_NOT_PROVIDED`, `VISION_REVIEW_IDENTITY_MISMATCH`, `VISION_REVIEW_INCOMPLETE`, `VISION_PROVIDER_NOT_CONFIGURED`, `IMAGE_TITLE_MISMATCH`, `IMAGE_DATE_MISMATCH`, `IMAGE_TIME_MISMATCH`, `HEADING_BODY_MISMATCH`, `TEXT_OVERFLOW`, `MAJOR_TYPO_DETECTED`, `POST_GENERATION_IMAGE_NOT_PROVIDED`, `LIVE_READBACK_ADAPTERS_NOT_CONFIGURED`, `GOOGLE_DOC_READBACK_FAILED`, `DRIVE_IMAGE_READBACK_FAILED`, `GITHUB_REGISTRATION_FAILED`, `PUBLICATION_READBACK_EVIDENCE_NOT_PROVIDED`, `PUBLICATION_EVIDENCE_INVALID`, `PUBLICATION_RECEIPT_FAILED`, `PORTAL_READBACK_FAILED`.
