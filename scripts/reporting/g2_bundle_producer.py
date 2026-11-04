"""Create-only producer boundary for freezing a task-authored G2 bundle.

The caller supplies the already authored report and exact pre-slot Evidence
readback. This module does not author market analysis or infer a G2 from Docs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Protocol

from scripts.persist_report_slot_evidence import validate_stored_slot_evidence
from .context import aware
from .issuance_pipeline import IssuanceBlocked, _validate_scenario_review


def _canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _slot_at(report_date: str, report_time: str):
    if report_time != "08:00":
        raise IssuanceBlocked("G2_PRODUCER_SLOT_NOT_SUPPORTED")
    try:
        parsed = datetime.strptime(report_date, "%Y-%m-%d").date()
        if parsed.weekday() >= 5:
            raise IssuanceBlocked("G2_PRODUCER_WEEKDAY_REQUIRED")
        return aware(f"{report_date}T08:00:00+09:00")
    except (TypeError, ValueError) as exc:
        raise IssuanceBlocked("G2_PRODUCER_SLOT_INVALID") from exc


def build_frozen_g2_bundle(*, report: dict, full_text: str,
                           evidence_object: dict, evidence_object_name: str,
                           evidence_generation: int, frozen_at: str,
                           scenario_review: dict, now: datetime | None = None,
                           expected_project_id: str,
                           expected_evidence_bucket: str) -> dict:
    """Build a G2 bundle only from a complete exact Evidence readback and task output."""
    if not isinstance(report, dict) or not isinstance(full_text, str) or not full_text:
        raise IssuanceBlocked("G2_PRODUCER_REPORT_INPUT_MISSING")
    if (not expected_project_id or not expected_evidence_bucket or
            "test" in expected_project_id.lower() or "test" in expected_evidence_bucket.lower()):
        raise IssuanceBlocked("PRODUCTION_EVIDENCE_TARGET_NOT_CONFIGURED")
    report_date, report_time = report.get("date"), report.get("time")
    slot_at = _slot_at(report_date, report_time)
    report_id = f"{report_date}_08-00"
    revision = report.get("revision")
    if (report.get("report_id") != report_id or type(revision) is not int or revision <= 0):
        raise IssuanceBlocked("G2_PRODUCER_REPORT_IDENTITY_INVALID")
    if not evidence_object_name or type(evidence_generation) is not int or evidence_generation <= 0:
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_REFERENCE_INVALID")
    if not isinstance(evidence_object, dict):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_ENVELOPE_MISSING")
    if (evidence_object.get("environment") != "PRODUCTION" or
            evidence_object.get("project_id") != expected_project_id or
            evidence_object.get("bucket") != expected_evidence_bucket or
            evidence_object.get("object") != evidence_object_name or
            evidence_object.get("generation") != evidence_generation or
            evidence_object.get("generation_readback") != evidence_generation):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_TARGET_MISMATCH")
    encoded_evidence = evidence_object.get("bytes")
    if not isinstance(encoded_evidence, str):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_BYTES_MISSING")
    evidence_bytes = encoded_evidence.encode("utf-8")
    if _sha256(evidence_bytes) != evidence_object.get("object_sha256"):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_HASH_MISMATCH")
    try:
        evidence = validate_stored_slot_evidence(evidence_bytes, report_date, report_time)
        evidence_created_at = aware(evidence_object.get("created_at", ""))
        freeze_instant = aware(frozen_at)
        current = now or datetime.now(freeze_instant.tzinfo)
        if current.tzinfo is None:
            raise ValueError("naive current time")
        current = aware(current.isoformat())
    except (ValueError, KeyError, TypeError) as exc:
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_OR_TIME_INVALID") from exc
    if evidence.get("reportId") != report_id or evidence.get("revision") != revision:
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_IDENTITY_MISMATCH")
    if (not evidence.get("evidenceId") or
            not (evidence.get("snapshot") or {}).get("snapshot_id")):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_SNAPSHOT_MISSING")
    if evidence_created_at > slot_at or evidence_created_at > freeze_instant:
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_CREATED_TOO_LATE")
    if evidence_object.get("evidence_id") != evidence.get("evidenceId"):
        raise IssuanceBlocked("G2_PRODUCER_EVIDENCE_IDENTITY_MISMATCH")
    if freeze_instant > slot_at or freeze_instant > current:
        raise IssuanceBlocked("G2_PRODUCER_FREEZE_TIME_INVALID")
    if current >= slot_at:
        raise IssuanceBlocked("G2_PRODUCER_AFTER_SLOT_CUTOFF")

    body_hash = _sha256(full_text.encode("utf-8"))
    frozen_report = deepcopy(report)
    if frozen_report.get("fullText") not in (None, full_text):
        raise IssuanceBlocked("G2_PRODUCER_BODY_INPUT_CONFLICT")
    if frozen_report.get("bodyHash") not in (None, body_hash):
        raise IssuanceBlocked("G2_PRODUCER_BODY_HASH_INPUT_CONFLICT")
    frozen_report.update({
        "report_id": report_id, "revision": revision, "fullText": full_text,
        "bodyHash": body_hash, "snapshot_id": evidence["snapshot"]["snapshot_id"],
        "snapshot": evidence["snapshot"], "context": evidence["context"],
    })
    try:
        from scripts.report_source_contract import validate_saved_body
        validate_saved_body(frozen_report)
    except (ValueError, KeyError, TypeError) as exc:
        raise IssuanceBlocked("G2_PRODUCER_BODY_NOT_IMPORTER_ELIGIBLE") from exc

    review = deepcopy(scenario_review) if isinstance(scenario_review, dict) else scenario_review
    if not isinstance(review, dict):
        raise IssuanceBlocked("G2_PRODUCER_HUMAN_REVIEW_REQUIRED")
    if review.get("report_id") not in (None, report_id):
        raise IssuanceBlocked("SCENARIO_REVIEW_IDENTITY_MISMATCH")
    if review.get("body_hash") not in (None, body_hash):
        raise IssuanceBlocked("SCENARIO_REVIEW_IDENTITY_MISMATCH")
    if review.get("reviewed_at"):
        try:
            reviewed_at = aware(review["reviewed_at"])
        except (ValueError, TypeError) as exc:
            raise IssuanceBlocked("G2_PRODUCER_REVIEW_TIME_INVALID") from exc
        if reviewed_at > freeze_instant:
            raise IssuanceBlocked("G2_PRODUCER_REVIEW_AFTER_FREEZE")
    review["report_id"] = report_id
    review["body_hash"] = body_hash
    _validate_scenario_review(review, frozen_report, body_hash)

    return {
        "schemaVersion": 1,
        "g2": {
            "report_id": report_id, "revision": revision,
            "body_hash": body_hash, "evidence_id": evidence["evidenceId"],
            "snapshot_id": evidence["snapshot"]["snapshot_id"],
            "frozen_at": freeze_instant.isoformat(),
            "report": frozen_report, "scenario_review": review,
        },
        "evidence_ref": {
            "object": evidence_object_name, "generation": evidence_generation,
        },
    }


@dataclass(frozen=True)
class G2BundleWriteReceipt:
    object_name: str
    generation: int
    sha256: str
    status: str


class G2BundleStore(Protocol):
    def create_only(self, *, report_id: str, revision: int, bundle: dict) -> G2BundleWriteReceipt: ...


class GcsCreateOnlyG2BundleStore:
    """Persist one immutable G2 object. Existing identical bytes are retry-safe."""

    def __init__(self, *, project_id: str, bucket_name: str,
                 prefix: str = "g2-bundles/", client=None):
        if (not project_id or not bucket_name or "test" in project_id.lower() or
                "test" in bucket_name.lower()):
            raise ValueError("PRODUCTION_G2_TARGET_REQUIRED")
        if client is None:
            from google.cloud import storage
            client = storage.Client(project=project_id)
        self.project_id = project_id
        self.bucket_name = bucket_name
        self._bucket = client.bucket(bucket_name)
        self._prefix = prefix.strip("/") + "/"

    def create_only(self, *, report_id: str, revision: int,
                    bundle: dict) -> G2BundleWriteReceipt:
        if (not isinstance(report_id, str) or not report_id or
                type(revision) is not int or revision <= 0):
            raise IssuanceBlocked("G2_BUNDLE_TARGET_IDENTITY_INVALID")
        g2 = bundle.get("g2") if isinstance(bundle, dict) else None
        report = (g2 or {}).get("report") if isinstance(g2, dict) else None
        if (not isinstance(report, dict) or g2.get("report_id") != report_id or
                report.get("report_id") != report_id or g2.get("revision") != revision or
                report.get("revision") != revision):
            raise IssuanceBlocked("G2_BUNDLE_TARGET_IDENTITY_MISMATCH")
        object_name = f"{self._prefix}{report_id}-r{revision}.json"
        payload = _canonical_bytes(bundle)
        digest = _sha256(payload)
        blob = self._bucket.blob(object_name)
        created = True
        try:
            blob.upload_from_string(payload, content_type="application/json",
                                    if_generation_match=0)
        except Exception as create_error:
            created = False
            try:
                blob.reload()
                generation = int(blob.generation)
                existing = blob.download_as_bytes(if_generation_match=generation)
            except Exception as read_error:
                raise IssuanceBlocked(
                    "G2_BUNDLE_CREATE_OR_READBACK_FAILED", stage="G2_BUNDLE_WRITE",
                    retryable=True) from read_error
            if existing != payload:
                raise IssuanceBlocked("G2_BUNDLE_EXISTING_CONFLICT",
                                      stage="G2_BUNDLE_WRITE") from create_error
        try:
            blob.reload()
            generation = int(blob.generation)
            readback = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise IssuanceBlocked(
                "G2_BUNDLE_READBACK_FAILED", stage="G2_BUNDLE_READBACK",
                retryable=True) from exc
        if readback != payload:
            raise IssuanceBlocked("G2_BUNDLE_READBACK_MISMATCH",
                                  stage="G2_BUNDLE_READBACK")
        return G2BundleWriteReceipt(object_name, generation, digest,
                                    "CREATED" if created else "IDEMPOTENT_RETRY")


class TrustedG2BundleProducer:
    """Freeze task-authored text and hand off one immutable Evidence-bound G2."""

    def __init__(self, store: G2BundleStore, *, expected_project_id: str,
                 expected_evidence_bucket: str):
        self.store = store
        self.expected_project_id = expected_project_id
        self.expected_evidence_bucket = expected_evidence_bucket

    def freeze_and_store(self, *, report: dict, full_text: str,
                         evidence_object: dict, evidence_object_name: str,
                         evidence_generation: int, frozen_at: str,
                         scenario_review: dict,
                         now: datetime | None = None) -> tuple[dict, G2BundleWriteReceipt]:
        bundle = build_frozen_g2_bundle(
            report=report, full_text=full_text, evidence_object=evidence_object,
            evidence_object_name=evidence_object_name,
            evidence_generation=evidence_generation, frozen_at=frozen_at,
            scenario_review=scenario_review, now=now,
            expected_project_id=self.expected_project_id,
            expected_evidence_bucket=self.expected_evidence_bucket)
        receipt = self.store.create_only(
            report_id=bundle["g2"]["report_id"],
            revision=bundle["g2"]["revision"], bundle=bundle)
        return bundle, receipt
