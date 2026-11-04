"""Fail-closed contracts for an external pre-slot trigger and G2-to-Docs handoff.

This module is deliberately side-effect free: it does not acquire market data,
write Google Docs, dispatch GitHub Actions, or publish artifacts. A directly
scheduled runtime must call these checks before invoking separately configured
adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
TRIGGER_SCHEMA = "market-report-pre-slot-trigger/v1"
MAX_TRIGGER_DELAY_SECONDS = 60
ALLOWED_WRITER_STAGES = {
    "G2_FROZEN", "DOCS_CREATE", "DOCS_UPDATE", "DOCS_READBACK", "DOCS_VERIFY",
}
DIAGNOSTIC_SCHEMA = "docs-body-mismatch/v1"
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """An input failed a fail-closed recovery contract."""


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field}_MISSING")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{field}_INVALID") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field}_NAIVE")
    return parsed.astimezone(JST)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sign_trigger_request(payload: Mapping[str, Any], secret: bytes) -> str:
    """Test/operator helper; production secret provisioning is external."""
    if len(secret) < 32:
        raise ContractError("TRIGGER_SECRET_TOO_SHORT")
    return hmac.new(secret, canonical_json_bytes(payload), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class VerifiedTrigger:
    attempt_id: str
    report_date: str
    report_slot: str
    scheduled_at: str
    triggered_at: str
    trigger_source: str
    execution_mode: str
    idempotency_key: str
    start_lag_seconds: int


def verify_pre_slot_trigger(
    payload: Mapping[str, Any],
    signature: str,
    secret: bytes,
    *,
    now: datetime | None = None,
    max_delay_seconds: int = MAX_TRIGGER_DELAY_SECONDS,
) -> VerifiedTrigger:
    """Verify a signed direct-run request and reject late, delayed, or wrong-slot work.

    A GitHub workflow_dispatch event is not an accepted proof of direct runner
    start. The external execution platform must POST/call this contract in its
    own runtime and retain its own invocation log.
    """
    if len(secret) < 32:
        raise ContractError("TRIGGER_SECRET_TOO_SHORT")
    if isinstance(max_delay_seconds, bool) or not isinstance(max_delay_seconds, int) or not 0 <= max_delay_seconds <= MAX_TRIGGER_DELAY_SECONDS:
        raise ContractError("TRIGGER_DELAY_POLICY_INVALID")
    if not isinstance(payload, Mapping):
        raise ContractError("TRIGGER_PAYLOAD_INVALID")
    expected_sig = hmac.new(secret, canonical_json_bytes(payload), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(expected_sig, signature.lower()):
        raise ContractError("TRIGGER_SIGNATURE_INVALID")

    required = ("schemaVersion", "attemptId", "reportDate", "reportSlot",
                "scheduledAt", "triggeredAt", "triggerSource", "executionMode")
    if any(not payload.get(key) for key in required):
        raise ContractError("TRIGGER_FIELDS_MISSING")
    if payload.get("schemaVersion") != TRIGGER_SCHEMA:
        raise ContractError("TRIGGER_SCHEMA_UNSUPPORTED")
    if payload.get("reportSlot") != "08:00":
        raise ContractError("TRIGGER_SLOT_OUT_OF_SCOPE")
    attempt_id = payload["attemptId"]
    source = payload["triggerSource"]
    mode = payload["executionMode"]
    report_date = payload["reportDate"]
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", attempt_id):
        raise ContractError("TRIGGER_ATTEMPT_ID_INVALID")
    if not isinstance(source, str) or source != "external_direct_runner":
        raise ContractError("TRIGGER_SOURCE_NOT_DIRECT")
    if mode not in {"TEST_ONLY", "LIVE"}:
        raise ContractError("TRIGGER_MODE_INVALID")
    try:
        date_value = datetime.strptime(report_date, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ContractError("TRIGGER_REPORT_DATE_INVALID") from exc
    if date_value.isoformat() != report_date or date_value.weekday() > 4:
        raise ContractError("TRIGGER_REPORT_DATE_NOT_SCHEDULED")

    scheduled = _instant(payload["scheduledAt"], "SCHEDULED_AT")
    triggered = _instant(payload["triggeredAt"], "TRIGGERED_AT")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ContractError("TRIGGER_CLOCK_NAIVE")
    current_jst = current.astimezone(JST)
    cutoff = datetime.combine(date_value, datetime.min.time(), JST).replace(hour=8)
    if scheduled.date() != date_value or triggered.date() != date_value:
        raise ContractError("TRIGGER_TIMESTAMP_DATE_MISMATCH")
    if scheduled >= cutoff or triggered >= cutoff or current_jst >= cutoff:
        raise ContractError("TRIGGER_AFTER_SLOT_CUTOFF")
    if triggered < scheduled:
        raise ContractError("TRIGGER_STARTED_BEFORE_SCHEDULED")
    lag = (triggered - scheduled).total_seconds()
    if lag > max_delay_seconds:
        raise ContractError("TRIGGER_START_DELAY_EXCEEDED")
    if (current_jst - triggered).total_seconds() < -5:
        raise ContractError("TRIGGERED_AT_IN_FUTURE")
    # Allow short clock skew, but do not accept a stale replay.
    if (current_jst - triggered).total_seconds() > max_delay_seconds:
        raise ContractError("TRIGGER_REQUEST_STALE")
    return VerifiedTrigger(
        attempt_id=attempt_id,
        report_date=report_date,
        report_slot="08:00",
        scheduled_at=scheduled.isoformat(),
        triggered_at=triggered.isoformat(),
        trigger_source=source,
        execution_mode=mode,
        idempotency_key=f"{report_date}_08-00:{attempt_id}",
        start_lag_seconds=int(lag),
    )



def claim_trigger_attempt(
    ledger_path: Path,
    trigger: VerifiedTrigger,
    *,
    repository_root: Path,
) -> bool:
    """Durably claim one external attempt; exact retries are safe no-ops.

    The ledger is operational state and must live in private, durable storage.
    It contains no HMAC key, body, or market data.
    """
    target = ledger_path.resolve()
    root = repository_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        pass
    else:
        raise ContractError("TRIGGER_LEDGER_MUST_BE_PRIVATE")
    record = {
        "schemaVersion": "pre-slot-attempt-ledger/v1",
        "idempotencyKey": trigger.idempotency_key,
        "attemptId": trigger.attempt_id,
        "reportDate": trigger.report_date,
        "reportSlot": trigger.report_slot,
        "scheduledAt": trigger.scheduled_at,
        "triggeredAt": trigger.triggered_at,
        "triggerSource": trigger.trigger_source,
        "executionMode": trigger.execution_mode,
    }
    encoded = canonical_json_bytes(record) + b"\\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ContractError("TRIGGER_LEDGER_READ_FAILED") from exc
        if hmac.compare_digest(existing, encoded):
            return False
        raise ContractError("TRIGGER_REPLAY_CONFLICT")
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return True

@dataclass(frozen=True)
class G2WriteInput:
    report_id: str
    revision: int
    report_date: str
    report_slot: str
    run_id: str
    full_text: str
    body_hash: str
    source: str
    frozen_at: str
    execution_mode: str


def freeze_g2_writer_input(
    *,
    report_id: str,
    revision: int,
    report_date: str,
    report_slot: str,
    run_id: str,
    full_text: str,
    body_hash: str | None = None,
    source: str = "producer_fixed_before_save",
    frozen_at: str,
    execution_mode: str = "TEST_ONLY",
) -> G2WriteInput:
    """Pin exact producer bytes for the writer; no normalization or re-generation."""
    if not all(isinstance(v, str) and v for v in
               (report_id, report_date, report_slot, run_id, full_text, source, frozen_at)):
        raise ContractError("G2_INPUT_FIELDS_MISSING")
    if report_slot != "08:00" or report_id != f"{report_date}_08-00":
        raise ContractError("G2_REPORT_IDENTITY_MISMATCH")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ContractError("G2_REVISION_INVALID")
    try:
        parsed_date = datetime.strptime(report_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ContractError("G2_REPORT_DATE_INVALID") from exc
    if parsed_date.isoformat() != report_date or parsed_date.weekday() > 4:
        raise ContractError("G2_REPORT_DATE_NOT_SCHEDULED")
    if source != "producer_fixed_before_save":
        raise ContractError("G2_SOURCE_NOT_PINNED_PRODUCER")
    if execution_mode not in {"TEST_ONLY", "LIVE"}:
        raise ContractError("G2_EXECUTION_MODE_INVALID")
    _instant(frozen_at, "G2_FROZEN_AT")
    computed = _sha256_text(full_text)
    if body_hash is not None and (not HEX_SHA256.fullmatch(body_hash) or not hmac.compare_digest(body_hash, computed)):
        raise ContractError("G2_BODY_HASH_MISMATCH")
    return G2WriteInput(
        report_id=report_id, revision=revision, report_date=report_date,
        report_slot=report_slot, run_id=run_id, full_text=full_text,
        body_hash=computed, source=source, frozen_at=frozen_at,
        execution_mode=execution_mode,
    )


@dataclass(frozen=True)
class DocsReadback:
    document_id: str
    document_revision_id: str
    full_text: str


@dataclass(frozen=True)
class DocsVerification:
    status: str
    reasons: tuple[str, ...]
    diagnostic: Mapping[str, Any]


def _first_difference(left: str, right: str) -> int | None:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return None if len(left) == len(right) else limit


@dataclass(frozen=True)
class DocsSaveEvidence:
    run_id: str
    report_id: str
    revision: int
    document_id: str
    document_revision_id: str
    body_hash: str
    saved_at: str


def verify_docs_readback(
    pinned: G2WriteInput,
    save_evidence: DocsSaveEvidence | None,
    readback: DocsReadback | None,
    *,
    required_sections: tuple[str, ...] = (),
    writer_stage: str = "DOCS_VERIFY",
    checked_at: str,
) -> DocsVerification:
    """Bind an independent Docs readback to the exact same-run save receipt."""
    if writer_stage not in ALLOWED_WRITER_STAGES:
        raise ContractError("WRITER_STAGE_INVALID")
    checked = _instant(checked_at, "CHECKED_AT")
    frozen = _instant(pinned.frozen_at, "G2_FROZEN_AT")
    reasons: list[str] = []
    missing: list[str] = []
    document_id = ""
    document_revision_id = ""
    read_text = ""

    if save_evidence is None:
        reasons.append("DOCS_SAVE_EVIDENCE_MISSING")
    else:
        document_id = save_evidence.document_id or ""
        document_revision_id = save_evidence.document_revision_id or ""
        if not all((document_id, document_revision_id)):
            reasons.append("DOCS_SAVE_EVIDENCE_IDENTITY_MISSING")
        if (save_evidence.run_id != pinned.run_id
                or save_evidence.report_id != pinned.report_id
                or save_evidence.revision != pinned.revision):
            reasons.append("DOCS_SAVE_EVIDENCE_RUN_IDENTITY_MISMATCH")
        if save_evidence.body_hash != pinned.body_hash:
            reasons.append("DOCS_SAVE_EVIDENCE_BODY_HASH_MISMATCH")
        try:
            saved = _instant(save_evidence.saved_at, "DOCS_SAVED_AT")
            if not frozen < saved:
                reasons.append("G2_NOT_FROZEN_BEFORE_DOCS_SAVE")
            if saved > checked:
                reasons.append("DOCS_READBACK_PRECEDES_SAVE")
        except ContractError:
            reasons.append("DOCS_SAVED_AT_INVALID")

    if readback is None:
        reasons.append("DOCS_READBACK_MISSING")
    else:
        read_text = readback.full_text
        if not readback.document_id:
            reasons.append("DOCS_DOCUMENT_ID_MISSING")
        if not readback.document_revision_id:
            reasons.append("DOCS_REVISION_ID_MISSING")
        if save_evidence is not None:
            if readback.document_id != save_evidence.document_id:
                reasons.append("DOCS_DOCUMENT_ID_DOES_NOT_MATCH_SAVE")
            if readback.document_revision_id != save_evidence.document_revision_id:
                reasons.append("DOCS_REVISION_DOES_NOT_MATCH_SAVE")
        if not isinstance(read_text, str):
            reasons.append("DOCS_FULL_TEXT_INVALID")
            read_text = ""
        else:
            if _sha256_text(read_text) != pinned.body_hash:
                reasons.append("DOCS_BODY_HASH_MISMATCH")
            if read_text != pinned.full_text:
                reasons.append("DOCS_BODY_TEXT_MISMATCH")
            missing = [section for section in required_sections if section not in read_text]
            if missing:
                reasons.append("DOCS_REQUIRED_SECTIONS_MISSING")

    diagnostic = {
        "schemaVersion": DIAGNOSTIC_SCHEMA,
        "verificationStatus": "PASS" if not reasons else "FAIL",
        "mode": pinned.execution_mode,
        "runId": pinned.run_id,
        "reportDate": pinned.report_date,
        "reportSlot": pinned.report_slot,
        "reportId": pinned.report_id,
        "revision": pinned.revision,
        "documentId": document_id,
        "documentRevisionId": document_revision_id,
        "sourceBodyHash": pinned.body_hash,
        "readbackBodyHash": _sha256_text(read_text) if readback is not None and isinstance(read_text, str) else None,
        "sourceCharCount": len(pinned.full_text),
        "readbackCharCount": len(read_text) if readback is not None else None,
        "firstDiffOffset": _first_difference(pinned.full_text, read_text) if readback is not None else None,
        "missingSections": missing,
        "writerStage": writer_stage,
        "reasonCodes": reasons,
        "checkedAt": checked_at,
    }
    return DocsVerification(status=diagnostic["verificationStatus"], reasons=tuple(reasons), diagnostic=diagnostic)


def save_frozen_g2_and_readback(
    pinned: G2WriteInput,
    writer: Any,
    *,
    required_sections: tuple[str, ...] = (),
    checked_at: str,
) -> tuple[DocsSaveEvidence, DocsReadback, DocsVerification]:
    """Only the frozen fullText is passed to the writer; receipt and readback are bound."""
    receipt = writer.save(
        full_text=pinned.full_text,
        body_hash=pinned.body_hash,
        run_id=pinned.run_id,
        report_id=pinned.report_id,
        revision=pinned.revision,
    )
    if not isinstance(receipt, DocsSaveEvidence):
        raise ContractError("DOCS_SAVE_RECEIPT_INVALID")
    readback = writer.readback(document_id=receipt.document_id)
    result = verify_docs_readback(
        pinned, receipt, readback, required_sections=required_sections, checked_at=checked_at
    )
    return receipt, readback, result


def write_private_diagnostic(
    path: Path,
    diagnostic: Mapping[str, Any],
    *,
    repository_root: Path,
    retention_days: int = 14,
) -> Path:
    """Create a redacted diagnostic outside the repository, without overwriting.

    Production storage must additionally enforce private IAM/ACL and an object
    lifecycle matching retention_days; a local file mode is not a cloud ACL.
    """
    target = path.resolve()
    root = repository_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        pass
    else:
        raise ContractError("DIAGNOSTIC_PATH_MUST_BE_PRIVATE")
    if retention_days != 14:
        raise ContractError("DIAGNOSTIC_RETENTION_MUST_BE_14_DAYS")
    allowed = {
        "schemaVersion", "verificationStatus", "mode", "runId", "reportDate",
        "reportSlot", "reportId", "revision", "documentId", "documentRevisionId",
        "sourceBodyHash", "readbackBodyHash", "sourceCharCount", "readbackCharCount",
        "firstDiffOffset", "missingSections", "writerStage", "reasonCodes", "checkedAt",
    }
    if set(diagnostic) - allowed:
        raise ContractError("DIAGNOSTIC_UNSAFE_FIELDS")
    serialized = dict(diagnostic)
    # Full bodies and arbitrary exception details must never enter this artifact.
    if any(key.lower() in {"fulltext", "body", "exception", "token", "secret"} for key in serialized):
        raise ContractError("DIAGNOSTIC_UNSAFE_FIELDS")
    checked = _instant(serialized.get("checkedAt"), "CHECKED_AT")
    serialized["expiresAt"] = (checked + timedelta(days=retention_days)).isoformat()
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(serialized) + b"\n"
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ContractError("DIAGNOSTIC_ALREADY_EXISTS") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return target

def purge_expired_private_diagnostics(
    directory: Path,
    *,
    repository_root: Path,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Delete expired redacted diagnostics from the TEST_ONLY/file-backed sink.

    Cloud object stores must also have a 14-day lifecycle policy and independently
    verify that policy; this function proves deletion only for this filesystem sink.
    """
    target = directory.resolve()
    root = repository_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        pass
    else:
        raise ContractError("DIAGNOSTIC_PATH_MUST_BE_PRIVATE")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ContractError("DIAGNOSTIC_PURGE_CLOCK_NAIVE")
    current = current.astimezone(JST)
    deleted: list[str] = []
    if not target.exists():
        return ()
    for path in sorted(target.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            expires = _instant(record.get("expiresAt"), "DIAGNOSTIC_EXPIRES_AT")
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise ContractError("DIAGNOSTIC_EXPIRY_RECORD_INVALID") from exc
        if expires <= current:
            path.unlink()
            deleted.append(path.name)
    return tuple(deleted)
