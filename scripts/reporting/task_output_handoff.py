"""Task-output boundary; no scheduler, credential discovery, or publication side effects.

An authenticated host must supply invocation identity separately from untrusted
JSON. This library does not authenticate ChatGPT tasks or attest a human review.
The resulting pinned manifest is consumed by scripts.run_0800_issuance, whose
ownership and protected-environment gates remain mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from .context import aware
from .g2_bundle_producer import (TrustedG2BundleProducer, G2BundleWriteReceipt,
                                 _canonical_bytes, _slot_window)
from .issuance_pipeline import IssuanceBlocked


@dataclass(frozen=True)
class VerifiedTaskInvocation:
    """Host-verified claims, never constructed from task output by an HTTP handler."""
    task_id: str
    run_id: str
    principal: str


def freeze_task_output(request: dict, *, invocation: VerifiedTaskInvocation,
                       expected_task_id: str, expected_principal: str,
                       producer: TrustedG2BundleProducer, evidence_reader,
                       now=None) -> dict:
    """Validate task output, independently read pinned Evidence, then freeze G2.

    evidence_reader is an explicitly configured exact-generation reader. No
    cloud adapter is instantiated here. TEST_ONLY hosts inject isolated stores.
    Returned provenance is diagnostic; real GCS audit proof is still required.
    """
    if (not isinstance(invocation, VerifiedTaskInvocation) or
            any(not isinstance(value, str) or not value.strip() for value in
                (expected_task_id, expected_principal, invocation.task_id,
                 invocation.principal, invocation.run_id)) or
            invocation.task_id != expected_task_id or
            invocation.principal != expected_principal or not invocation.run_id):
        raise IssuanceBlocked("BLOCKED_G2_TASK_HANDOFF")
    if (not isinstance(request, dict) or type(request.get("schemaVersion")) is not int or
            request["schemaVersion"] != 1):
        raise IssuanceBlocked("TASK_OUTPUT_SCHEMA_INVALID")
    report, text = request.get("report"), request.get("full_text")
    if not isinstance(report, dict) or not isinstance(text, str) or not text:
        raise IssuanceBlocked("TASK_OUTPUT_BODY_REQUIRED")
    try:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise IssuanceBlocked("TASK_OUTPUT_BODY_ENCODING_INVALID") from exc
    if request.get("body_sha256") != digest:
        raise IssuanceBlocked("TASK_OUTPUT_BODY_HASH_MISMATCH")
    ref = request.get("evidence_ref")
    if (not isinstance(ref, dict) or not isinstance(ref.get("object"), str) or
            not ref["object"] or type(ref.get("generation")) is not int or
            ref["generation"] <= 0 or
            any(not isinstance(ref.get(key), str) or not ref[key].strip()
                for key in ("evidence_id", "snapshot_id"))):
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_REFERENCE_INVALID")
    # Reject impossible targets and expired requests before any external read.
    slot_start, slot_end = _slot_window(report.get("date"), report.get("time"))
    if (report.get("report_id") != f"{report.get('date')}_08-00" or
            type(report.get("revision")) is not int or report["revision"] <= 0):
        raise IssuanceBlocked("G2_PRODUCER_REPORT_IDENTITY_INVALID")
    try:
        frozen = aware(request.get("frozen_at"))
        current = now if now is not None else datetime.now(slot_start.tzinfo)
        current = aware(current.isoformat())
    except (ValueError, TypeError, AttributeError) as exc:
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_OR_TIME_INVALID") from exc
    if frozen < slot_start or frozen > slot_end:
        raise IssuanceBlocked("G2_PRODUCER_FREEZE_OUTSIDE_SLOT_WINDOW")
    if current > slot_end:
        raise IssuanceBlocked("G2_PRODUCER_AFTER_SLOT_WINDOW")
    if frozen > current:
        raise IssuanceBlocked("G2_PRODUCER_FREEZE_TIME_INVALID")
    # Never trust an Evidence envelope or creation timestamp in request JSON.
    try:
        readback = evidence_reader(
            project_id=producer.expected_project_id,
            bucket_name=producer.expected_evidence_bucket,
            object_name=ref["object"], generation=ref["generation"])
    except IssuanceBlocked:
        raise
    except Exception as exc:
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_READ_FAILED",
                              stage="TASK_EVIDENCE_READ", retryable=True) from exc
    try:
        if not isinstance(readback, dict):
            raise ValueError("readback is not an object")
        envelope = readback["evidence_object"]
        if not isinstance(envelope, dict) or not isinstance(envelope.get("bytes"), str):
            raise ValueError("missing evidence bytes")
        evidence = json.loads(envelope["bytes"])
        if not isinstance(evidence, dict) or not isinstance(evidence.get("snapshot"), dict):
            raise ValueError("invalid evidence shape")
    except (KeyError, TypeError, ValueError) as exc:
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_INVALID") from exc
    if (evidence.get("evidenceId") != ref["evidence_id"] or
            evidence["snapshot"].get("snapshot_id") != ref["snapshot_id"]):
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_IDENTITY_MISMATCH")
    bundle, receipt = producer.freeze_and_store(
        report=report, full_text=text, evidence_object=envelope,
        evidence_object_name=ref["object"], evidence_generation=ref["generation"],
        frozen_at=request.get("frozen_at"), scenario_review=request.get("scenario_review"), now=now)
    if (not isinstance(receipt, G2BundleWriteReceipt) or
            not receipt.object_name or type(receipt.generation) is not int or receipt.generation <= 0 or
            receipt.sha256 != hashlib.sha256(_canonical_bytes(bundle)).hexdigest() or
            receipt.status not in ("CREATED", "IDEMPOTENT_RETRY")):
        raise IssuanceBlocked("TASK_OUTPUT_G2_RECEIPT_INVALID")
    return {
        "status": "G2_FROZEN", "bundle": bundle,
        "g2_ref": {"object": receipt.object_name, "generation": receipt.generation,
                   "sha256": receipt.sha256},
        "report_id": bundle["g2"]["report_id"], "revision": bundle["g2"]["revision"],
        "evidence_ref": dict(ref),
        "invocation": {"task_id": invocation.task_id, "run_id": invocation.run_id,
                       "principal": invocation.principal},
        "publication_status": "NOT_RUN", "notification_status": "NOT_RUN",
    }
