"""Executable TEST_ONLY/direct-runner orchestration for pre-slot evidence.

The TEST_ONLY path exercises the real trigger verifier and existing immutable
slot-evidence builder, then reads the exact bytes back from a private local sink.
No Google Docs, GitHub main, Drive, or publication side effect occurs here.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Protocol

from scripts.persist_report_slot_evidence import (
    build_slot_evidence,
    canonical_bytes,
    require_before_slot,
    validate_stored_slot_evidence,
)
from scripts.reporting.slot_recovery_contract import (
    ContractError,
    VerifiedTrigger,
    claim_trigger_attempt,
    verify_pre_slot_trigger,
)

class EvidenceStore(Protocol):
    def put_if_absent(self, evidence_id: str, encoded: bytes) -> None: ...
    def read(self, evidence_id: str) -> bytes: ...


class PrivateFileEvidenceStore:
    """Create-only filesystem sink for isolated TEST_ONLY use."""
    def __init__(self, directory: Path, *, repository_root: Path):
        self.directory = directory.resolve()
        self.repository_root = repository_root.resolve()
        try:
            self.directory.relative_to(self.repository_root)
        except ValueError:
            pass
        else:
            raise ContractError("EVIDENCE_STORE_MUST_BE_PRIVATE")

    def _path(self, evidence_id: str) -> Path:
        if len(evidence_id) != 64 or any(ch not in "0123456789abcdef" for ch in evidence_id):
            raise ContractError("EVIDENCE_ID_INVALID")
        return self.directory / f"{evidence_id}.json"

    def put_if_absent(self, evidence_id: str, encoded: bytes) -> None:
        path = self._path(evidence_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as exc:
            if path.read_bytes() != encoded:
                raise ContractError("EVIDENCE_IMMUTABLE_CONFLICT") from exc

    def read(self, evidence_id: str) -> bytes:
        return self._path(evidence_id).read_bytes()


def execute_test_only_capture(
    *,
    payload: dict,
    signature: str,
    secret: bytes,
    acquisition: Callable[[VerifiedTrigger], bytes],
    store: EvidenceStore,
    attempt_ledger: Path,
    repository_root: Path,
    now: datetime,
) -> dict:
    """Signature -> acquisition bytes -> immutable snapshot -> exact readback."""
    trigger = verify_pre_slot_trigger(payload, signature, secret, now=now)
    if trigger.execution_mode != "TEST_ONLY":
        raise ContractError("TEST_CAPTURE_REQUIRES_TEST_ONLY")
    claimed = claim_trigger_attempt(attempt_ledger, trigger, repository_root=repository_root)
    if not claimed:
        raise ContractError("TEST_ATTEMPT_ALREADY_CLAIMED")
    require_before_slot(trigger.report_date, trigger.report_slot, now=now)
    raw = acquisition(trigger)
    if not isinstance(raw, bytes) or not raw:
        raise ContractError("ACQUISITION_BYTES_MISSING")
    try:
        market = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("ACQUISITION_JSON_INVALID") from exc
    if not isinstance(market, dict):
        raise ContractError("ACQUISITION_JSON_NOT_OBJECT")
    evidence = build_slot_evidence(trigger.report_date, trigger.report_slot, market, raw)
    encoded = canonical_bytes(evidence)
    store.put_if_absent(evidence["evidenceId"], encoded)
    readback = store.read(evidence["evidenceId"])
    if not hashlib.sha256(readback).digest() == hashlib.sha256(encoded).digest() or readback != encoded:
        raise ContractError("EVIDENCE_READBACK_MISMATCH")
    validated = validate_stored_slot_evidence(readback, trigger.report_date, trigger.report_slot)
    require_before_slot(trigger.report_date, trigger.report_slot, now=now)
    return {
        "status": "PASS_TEST_ONLY",
        "executionMode": "TEST_ONLY",
        "attemptId": trigger.attempt_id,
        "reportId": validated["reportId"],
        "revision": validated["revision"],
        "evidenceId": validated["evidenceId"],
        "snapshotHash": validated["snapshotHash"],
        "contextHash": validated["contextHash"],
        "sourceHash": validated["acquisitionSource"]["contentHash"],
        "capturedAt": validated["snapshot"]["captured_at"],
        "readbackSha256": hashlib.sha256(readback).hexdigest(),
        "readback": "PASS_EXACT_BYTES",
        "mainReadback": "NOT_RUN_TEST_ONLY_PRIVATE_STORE",
    }

def run_existing_live_pipeline(
    *,
    trigger: VerifiedTrigger,
    now: datetime,
    audit_path: Path,
    enable_main_evidence_write: bool = False,
) -> dict:
    """Opt-in adapter to the existing acquisition->freeze->main-readback path.

    This calls scripts.run_market_data_window.perform_attempt, whose existing
    implementation writes the acquisition audit/evidence to GitHub main. The
    default is therefore BLOCKED; never call this from offline tests or TEST_ONLY.
    """
    if trigger.execution_mode != "LIVE":
        raise ContractError("LIVE_PIPELINE_REQUIRES_LIVE_TRIGGER")
    if not enable_main_evidence_write:
        raise ContractError("LIVE_MAIN_EVIDENCE_WRITE_NOT_ENABLED")
    require_before_slot(trigger.report_date, trigger.report_slot, now=now)
    from datetime import date
    from scripts.run_market_data_window import perform_attempt

    scheduled_at = datetime.fromisoformat(trigger.scheduled_at)
    late_minutes = max(0.0, (now - scheduled_at).total_seconds() / 60.0)
    record = perform_attempt(
        trigger.report_slot,
        date.fromisoformat(trigger.report_date),
        scheduled_at.strftime("%H:%M"),
        trigger.trigger_source,
        audit_path,
        "full",
        late_minutes,
        freeze_evidence=True,
    )
    if (record.get("evidenceStatus") != "VERIFIED_ON_MAIN"
            or record.get("evidenceReadback") != "PASS"):
        raise ContractError("LIVE_MAIN_EVIDENCE_READBACK_FAILED")
    return {
        "status": "PASS_LIVE_EXISTING_PIPELINE",
        "executionMode": "LIVE",
        "reportDate": trigger.report_date,
        "reportSlot": trigger.report_slot,
        "evidenceStatus": record["evidenceStatus"],
        "mainReadback": record["evidenceReadback"],
        "workflowRunId": record.get("workflowRunId"),
    }

def execute_verified_live_trigger(
    *,
    payload: dict,
    signature: str,
    secret: bytes,
    now: datetime,
    attempt_ledger: Path,
    repository_root: Path,
    audit_path: Path,
    enable_main_evidence_write: bool = False,
) -> dict:
    """Verify, claim, call the existing acquisition/freeze/main-readback pipeline."""
    trigger = verify_pre_slot_trigger(payload, signature, secret, now=now)
    if trigger.execution_mode != "LIVE":
        raise ContractError("LIVE_PIPELINE_REQUIRES_LIVE_TRIGGER")
    if not enable_main_evidence_write:
        raise ContractError("LIVE_MAIN_EVIDENCE_WRITE_NOT_ENABLED")
    if not claim_trigger_attempt(attempt_ledger, trigger, repository_root=repository_root):
        return {
            "status": "NOOP_EXACT_RETRY",
            "executionMode": "LIVE",
            "attemptId": trigger.attempt_id,
            "reportId": f"{trigger.report_date}_08-00",
        }
    return run_existing_live_pipeline(
        trigger=trigger, now=now, audit_path=audit_path,
        enable_main_evidence_write=enable_main_evidence_write,
    )
