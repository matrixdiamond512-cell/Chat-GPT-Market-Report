# Trusted Vision Signer v1.0

## Scope

The signer creates a local `market-report-vision-review/v1` JSON artifact for one report body, infographic specification, image, source Google Docs ID, and Drive image ID. It does not publish, upload, deploy Apps Script, or write to production data. Output paths inside repository `reports/`, `data/`, `images/`, and `publication-receipts/`, and the root `reports.json`, are rejected.

## Review provider contract

`scripts/reporting/vision_provider.py` defines a provider interface and a strict response contract. The response must contain exactly the thirteen required check names, each with `PASS`, `FAIL`, or `UNCERTAIN`. Unknown, missing, extra, or malformed values fail closed. `build_vision_prompt` supplies the source text, report identity, validated panels, and timeline as read-only evidence. Providers must not guess unreadable text or numbers; uncertainty is not a pass.

The fixture provider is deterministic and does not inspect the image. Its identity is fixed to `fixture-test-only`; it exists for contract and cross-runtime tests. Never configure that identity or its key in a production Apps Script project. `ExternalVisionProvider` is an integration seam and deliberately returns `VISION_PROVIDER_NOT_CONFIGURED` until an approved provider adapter is implemented.

## Signing rules

The signer validates the report and infographic spec using the existing validator, verifies image structure and SHA-256, snapshots image bytes for review, and checks that the source report and image remain unchanged during review. It binds the raw UTF-8 report body hash, report ID/title, source document ID, Drive image ID, image hash, provider ID, checks, review ID, and UTC timestamp.

Only thirteen `PASS` verdicts produce the existing boolean checks and an HMAC signature. Any `FAIL` blocks with `VISION_REVIEW_FAILED`; any `UNCERTAIN` blocks with `VISION_REVIEW_UNCERTAIN`. In particular, uncertain or failed numeric review cannot be signed. The HMAC payload and field order reuse `vision_attestation_payload` and the existing Apps Script verifier contract. That contract is not modified.

`MARKET_REPORT_VISION_HMAC_KEY` and `MARKET_REPORT_TRUSTED_VISION_PROVIDER` must be supplied through the process environment. The key must contain at least 32 UTF-8 bytes. The signer never includes the key in review JSON, stdout, or safe error messages. Do not put a real key in shell history, CI logs, fixtures, or source control. Tests create ephemeral keys in process memory.

## Local CLI

```text
python scripts/sign_market_report_vision_review.py \
  --report validation/<report_id>/report.json \
  --spec validation/<report_id>/infographic_spec.json \
  --image validation/<report_id>/infographic.png \
  --source-document-id <source-doc-id> \
  --drive-image-file-id <drive-image-id> \
  --output validation/<report_id>/マーケットレポート_<report_id>.vision-review.json \
  --provider fixture --dry-run
```

`--dry-run` is required. It means the signer may create only a local review file; it does not call publication code. The fixture provider can sign only when the configured trusted provider is `fixture-test-only`, so its output will be rejected by any real provider identity. The external provider option currently returns `NOT_RUN`/`VISION_PROVIDER_NOT_CONFIGURED`.

Output creation is exclusive: an existing path is never overwritten. The filename must be `マーケットレポート_<report_id>.vision-review.json`. The command emits a compact summary with hashes and `production_write: false`; secrets are excluded.

## Status and limits

Fixture signing and Apps Script verification prove schema, canonical payload, HMAC, and identity binding at local E1/E2/E3 test scope. They do not prove that a Vision model inspected the image. A real external provider, its provenance controls, nonproduction secret provisioning, Google Docs/Drive readbacks, Apps Script deployment, and end-to-end publication remain `NOT_RUN`. No production configuration or data was changed for this implementation.
