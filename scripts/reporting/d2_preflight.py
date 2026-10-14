"""D2 shadow API execution *preflight only*.

Pure, offline readiness analysis: no API SDK, network, credentials, cloud writes,
scheduler, production proof issuer or publishing permission. A local manifest
cannot attest actual approvals or account configurations. Therefore the
executable authorization outcome ALWAYS remains BLOCKED_EXTERNAL_ATTESTATION.
A simulation may establish contract validity but NEVER grant an API send.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re

REQUIRED_EVIDENCE = (
    "api_project", "least_privilege_key", "secret_manager",
    "cost_owner_approval", "api_run_approval",
    "private_store", "store_iam", "store_versioning", "store_encryption",
    "store_retention", "store_readback", "data_source_rights",
    "verified_source_bundle", "model_snapshot", "response_schema",
    "full_numeric_claim_check", "timeout_reconciliation",
    "no_publication_credentials",
)
MODEL_PATTERN = re.compile(r"^gpt-[A-Za-z0-9.]+(?:-[A-Za-z0-9.]+)*-\d{4}-\d{2}-\d{2}$")
EVIDENCE_PATTERN = re.compile(r"^[A-Za-z0-9_.:/-]{8,256}$")
COST_LIMIT = Decimal("1000000")


@dataclass(frozen=True)
class PreflightOutcome:
    phase: str
    contract: str
    blockers: tuple[str, ...]
    worst_case_usd: str | None
    api_send_allowed: bool = False
    publication_allowed: bool = False

    def to_dict(self):
        return asdict(self)


def _positive_int(value, name: str, errors: list[str]):
    if type(value) is not int or value <= 0:
        errors.append(name + "_NOT_POSITIVE_INTEGER")
        return 0
    return value


def _money(raw, name: str, errors: list[str]) -> Decimal | None:
    if not isinstance(raw, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?", raw):
        errors.append(name + "_NOT_APPROVED_DECIMAL_STRING")
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite() or value <= 0 or value > COST_LIMIT:
            errors.append(name + "_OUT_OF_BOUNDS")
            return None
        return value
    except InvalidOperation:
        errors.append(name + "_NOT_APPROVED_DECIMAL_STRING")
        return None


def evaluate_d2_manifest(manifest: dict | None = None) -> PreflightOutcome:
    """Evaluate schema/budget design. Real API execution is ALWAYS disallowed.

    Even a syntactically valid evidence reference is NOT proof of approval.
    External IAM/owner/actual receipt must be independently verified in D2.
    """
    if not isinstance(manifest, dict):
        return PreflightOutcome(
            "D2_PREP", "BLOCKED",
            ("MISSING_MANIFEST", "EXTERNAL_ATTESTATIONS_NOT_VERIFIED"), None,
        )
    errors: list[str] = []
    if manifest.get("schema_version") != "market-report-d2-preflight/v1":
        errors.append("SCHEMA_VERSION_MISMATCH")
    if manifest.get("lane") != "api-shadow" or manifest.get("run_mode") != "shadow":
        errors.append("SHADOW_LANE_REQUIRED")
    if manifest.get("eligibility") != "SHADOW_NOT_ELIGIBLE":
        errors.append("SHADOW_NOT_ELIGIBLE_REQUIRED")
    if manifest.get("dry_run_only") is not True or manifest.get("allow_publication") is not False:
        errors.append("PUBLICATION_BOUNDARY_REQUIRED")
    if manifest.get("external_tools") != [] or manifest.get("web_search_calls") != 0:
        errors.append("MODEL_TOOL_CALLS_FORBIDDEN_IN_D2")
    model = manifest.get("model_snapshot")
    if not isinstance(model, str) or not MODEL_PATTERN.fullmatch(model):
        errors.append("MODEL_SNAPSHOT_NOT_PINNED")
    else:
        try:
            date.fromisoformat(model[-10:])
        except ValueError:
            errors.append("MODEL_SNAPSHOT_NOT_PINNED")
    report_id = manifest.get("report_id")
    if not isinstance(report_id, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}_(08|12|16|21)-00", report_id):
        errors.append("REPORT_ID_OR_SLOT_INVALID")
    if isinstance(report_id, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}_(08|12|16|21)-00", report_id):
        try:
            if date.fromisoformat(report_id[:10]).weekday() > 4:
                errors.append("REPORT_ID_OR_SLOT_INVALID")
        except ValueError:
            errors.append("REPORT_ID_OR_SLOT_INVALID")
    if manifest.get("data_contract") != "immutable-context-snapshot/v1":
        errors.append("IMMUTABLE_INPUT_CONTRACT_MISSING")
    if manifest.get("response_contract") != "strict-json-schema/v1":
        errors.append("STRICT_OUTPUT_CONTRACT_MISSING")
    caps = manifest.get("caps") if isinstance(manifest.get("caps"), dict) else {}
    n_input = _positive_int(caps.get("max_input_tokens"), "MAX_INPUT", errors)
    n_output = _positive_int(caps.get("max_output_tokens"), "MAX_OUTPUT", errors)
    if caps.get("max_attempts") != 1 or type(caps.get("max_attempts")) is not int:
        errors.append("ONE_MANUAL_ATTEMPT_REQUIRED")
    if caps.get("max_runs") != 1 or type(caps.get("max_runs")) is not int:
        errors.append("ONE_MANUAL_RUN_REQUIRED")
    pricing = manifest.get("price_quote") if isinstance(manifest.get("price_quote"), dict) else {}
    if pricing.get("model") != model or pricing.get("unit") != "USD_PER_MILLION_TOKENS":
        errors.append("RATE_MODEL_OR_UNIT_MISMATCH")
    in_price = _money(pricing.get("input_per_million"), "INPUT_RATE", errors)
    out_price = _money(pricing.get("output_per_million"), "OUTPUT_RATE", errors)
    run_cap = _money(caps.get("max_run_usd"), "RUN_CAP", errors)
    monthly_cap = _money(caps.get("max_month_usd"), "MONTH_CAP", errors)
    estimate = None
    if in_price is not None and out_price is not None and n_input and n_output:
        estimate = (in_price * n_input + out_price * n_output) / Decimal(1_000_000)
        if run_cap is not None and estimate > run_cap:
            errors.append("RUN_BUDGET_EXCEEDED")
        if monthly_cap is not None and estimate > monthly_cap:
            errors.append("MONTHLY_BUDGET_EXCEEDED")
    if manifest.get("timeout_policy") != "UNKNOWN_STOP_NO_BLIND_RETRY":
        errors.append("UNKNOWN_PROVIDER_RESULT_POLICY_MISSING")
    store = manifest.get("store") if isinstance(manifest.get("store"), dict) else {}
    if store.get("access") != "private" or store.get("readback") != "byte_exact" or store.get("immutable_create") is not True:
        errors.append("PRIVATE_IMMUTABLE_STORE_CONTRACT_MISSING")
    retention = store.get("retention_days")
    if type(retention) is not int or not (1 <= retention <= 365):
        errors.append("STORE_RETENTION_NOT_APPROVED")
    refs = manifest.get("attestation_refs") if isinstance(manifest.get("attestation_refs"), dict) else {}
    for key in REQUIRED_EVIDENCE:
        value = refs.get(key)
        if not isinstance(value, str) or not EVIDENCE_PATTERN.fullmatch(value):
            errors.append("MISSING_ATTESTATION_REF:" + key)
    # Reject attempts to slip tokens or publication configurations into an
    # offline review manifest; separate secrets belong only in a secret manager.
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    for marker in ("sk-proj-", "sk-", "-----BEGIN PRIVATE KEY-----", "github_pat_", "ghp_"):
        if marker in serialized:
            errors.append("CREDENTIAL_MATERIAL_IN_MANIFEST")
            break
    if any(k in manifest for k in (
        "api_key", "openai_api_key", "github_token", "google_credentials",
        "publisher_token", "producer_private_key", "signature_secret",
    )):
        errors.append("CREDENTIAL_FIELD_IN_MANIFEST")
    # HARD STOP: References supplied in a file are never independently
    # authenticated IAM approval or proof of permission to incur API charges.
    errors.append("EXTERNAL_ATTESTATIONS_NOT_VERIFIED")
    return PreflightOutcome(
        phase="D2_PREP",
        contract="SPEC_CONTRACT_PASS" if len(errors) == 1 else "BLOCKED",
        blockers=tuple(errors),
        worst_case_usd=str(estimate) if estimate is not None else None,
        api_send_allowed=False,
        publication_allowed=False,
    )


if __name__ == "__main__":
    print(json.dumps(evaluate_d2_manifest().to_dict(), ensure_ascii=False, sort_keys=True))
