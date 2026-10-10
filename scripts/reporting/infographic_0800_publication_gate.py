"""Shared fail-closed checks for 08:00 publication entry points."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .infographic_0800_generation_contract import CONTRACT, canonical_sha256


def _full_text(report: dict[str, Any]) -> str:
    value = report.get("fullText") or report.get("full_text") or report.get("body_text")
    return value if isinstance(value, str) else ""


def validate_0800_publication_report(report: dict[str, Any]) -> dict[str, Any]:
    """Validate the PASS receipt before a new 08:00 report can be persisted/published."""
    errors: list[str] = []
    if not isinstance(report, dict) or report.get("time") != "08:00":
        return {"status": "NOT_APPLICABLE", "errors": []}
    report_id = str(report.get("date", "")) + "_08-00"
    body = _full_text(report)
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    receipt = report.get("infographicGenerationQa")
    if not isinstance(receipt, dict):
        errors.append("0800_GENERATION_QA_RECEIPT_MISSING")
        receipt = {}
    checks = {
        "contract_id": CONTRACT["contract_id"],
        "gate": "PRE_SAVE_AND_PRE_RENDER_08_00_GENERATION_QA",
        "status": "PASS",
        "report_id": report_id,
        "body_sha256": body_sha,
    }
    for key, expected in checks.items():
        if receipt.get(key) != expected:
            errors.append("0800_QA_RECEIPT_MISMATCH:" + key)
    if not body.strip():
        errors.append("0800_REPORT_BODY_MISSING")
    for key in ("structured_source_sha256", "numeric_registry_sha256", "snapshot_sha256", "qa_result_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(key, ""))):
            errors.append("0800_QA_HASH_MISSING_OR_INVALID:" + key)
    if int(receipt.get("fact_count") or 0) < 1 or int(receipt.get("numeric_count") or 0) < 1:
        errors.append("0800_QA_FACT_OR_NUMERIC_COUNT_MISSING")
    receipt_for_hash = dict(receipt)
    recorded_receipt_hash = receipt_for_hash.get("qa_result_sha256")
    receipt_for_hash["qa_result_sha256"] = ""
    if recorded_receipt_hash != canonical_sha256(receipt_for_hash):
        errors.append("0800_QA_RECEIPT_CHECKSUM_MISMATCH")
    gates = receipt.get("validation_gates") if isinstance(receipt.get("validation_gates"), dict) else {}
    for name in ("SOURCE_INTEGRITY", "NUMERIC_INTEGRITY", "SNAPSHOT_INTEGRITY", "CONTENT_COMPLETENESS"):
        if gates.get(name) != "PASS":
            errors.append("0800_QA_GATE_NOT_PASS:" + name)
    if receipt.get("snapshot_provenance") != "LIVE_CAPTURED":
        errors.append("0800_PRODUCTION_SOURCE_MUST_BE_LIVE_CAPTURED")
    if receipt.get("synthetic_fixture") is True or report.get("synthetic_fixture") is True:
        errors.append("0800_SYNTHETIC_FIXTURE_PRODUCTION_FORBIDDEN")
    return {"status": "PASS" if not errors else "BLOCKED", "report_id": report_id,
            "body_sha256": body_sha, "errors": errors}


def authorize_0800_action(report: dict[str, Any], action: str) -> dict[str, Any]:
    """Single policy decision used by the managed save/render/portal/JSON gateways."""
    allowed_actions = {"DOCS_SAVE", "PNG_GENERATION", "PORTAL_REFLECTION", "PRODUCTION_JSON_WRITE"}
    if action not in allowed_actions:
        return {"status": "BLOCKED", "action": action, "errors": ["UNKNOWN_0800_ACTION"]}
    result = validate_0800_publication_report(report)
    return {**result, "action": action, "allowed": result["status"] == "PASS"}


def report_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("reports", "items"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
        for key in ("latestReport", "report"):
            if isinstance(payload.get(key), dict):
                return [payload[key]]
        if payload.get("time"):
            return [payload]
    return []


def changed_0800_rows(before: Any, after: Any) -> list[dict[str, Any]]:
    def indexed(payload: Any) -> dict[tuple[str, str], dict[str, Any]]:
        return {(str(row.get("date", "")), str(row.get("time", ""))): row
                for row in report_rows(payload) if row.get("date") and row.get("time")}
    old = indexed(before)
    new = indexed(after)
    changed: list[dict[str, Any]] = []
    for key, row in new.items():
        if key[1] != "08:00":
            continue
        if key not in old or canonical_sha256(row) != canonical_sha256(old[key]):
            changed.append(row)
    return changed


def verify_changed_0800_reports(before: Any, after: Any) -> dict[str, Any]:
    reports = changed_0800_rows(before, after)
    validations = [validate_0800_publication_report(report) for report in reports]
    errors = [f"{result.get('report_id')}: {error}" for result in validations for error in result.get("errors", [])]
    return {"status": "PASS" if not errors else "BLOCKED", "changed_0800_count": len(reports),
            "report_ids": [str(row.get("date", "")) + "_08-00" for row in reports],
            "errors": errors, "validations": validations}


def assert_changed_0800_reports(before: Any, after: Any, *, operation: str) -> None:
    result = verify_changed_0800_reports(before, after)
    if result["status"] != "PASS":
        raise SystemExit(f"08:00 QA blocked {operation}: " + "; ".join(result["errors"]))
