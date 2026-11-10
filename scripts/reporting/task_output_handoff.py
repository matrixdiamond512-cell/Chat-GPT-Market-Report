"""Task-output boundary; no scheduler, credential discovery, or publication side effects.

An authenticated host must supply invocation identity separately from untrusted
JSON. This library does not authenticate ChatGPT tasks or attest a human review.
The resulting pinned manifest is consumed by scripts.run_0800_issuance, whose
ownership and protected-environment gates remain mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from .g2_bundle_producer import TrustedG2BundleProducer, _canonical_bytes
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
            not expected_task_id or not expected_principal or
            invocation.task_id != expected_task_id or
            invocation.principal != expected_principal or not invocation.run_id):
        raise IssuanceBlocked("BLOCKED_G2_TASK_HANDOFF")
    if not isinstance(request, dict) or request.get("schemaVersion") != 1:
        raise IssuanceBlocked("TASK_OUTPUT_SCHEMA_INVALID")
    report, text = request.get("report"), request.get("full_text")
    if not isinstance(report, dict) or not isinstance(text, str) or not text:
        raise IssuanceBlocked("TASK_OUTPUT_BODY_REQUIRED")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if request.get("body_sha256") != digest:
        raise IssuanceBlocked("TASK_OUTPUT_BODY_HASH_MISMATCH")
    ref = request.get("evidence_ref")
    if (not isinstance(ref, dict) or not isinstance(ref.get("object"), str) or
            not ref["object"] or type(ref.get("generation")) is not int or
            ref["generation"] <= 0 or not ref.get("evidence_id") or not ref.get("snapshot_id")):
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_REFERENCE_INVALID")
    # Never trust an Evidence envelope or creation timestamp in request JSON.
    envelope = evidence_reader(
        project_id=producer.expected_project_id,
        bucket_name=producer.expected_evidence_bucket,
        object_name=ref["object"], generation=ref["generation"])["evidence_object"]
    import json
    try:
        evidence = json.loads(envelope["bytes"])
        if (evidence.get("evidenceId") != ref["evidence_id"] or
                evidence.get("snapshot", {}).get("snapshot_id") != ref["snapshot_id"]):
            raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_IDENTITY_MISMATCH")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, IssuanceBlocked):
            raise
        raise IssuanceBlocked("TASK_OUTPUT_EVIDENCE_INVALID") from exc
    bundle, receipt = producer.freeze_and_store(
        report=report, full_text=text, evidence_object=envelope,
        evidence_object_name=ref["object"], evidence_generation=ref["generation"],
        frozen_at=request.get("frozen_at"), scenario_review=request.get("scenario_review"), now=now)
    if (not receipt.object_name or type(receipt.generation) is not int or receipt.generation <= 0 or
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
