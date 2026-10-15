"""Verify immutable slot evidence and issue a read-back-bound Drive receipt."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from .context import ReportContext, aware
from .snapshot import MarketDataSnapshot, digest

JST = timedelta(hours=9)


def _canonical_hash(value: object) -> str:
    return digest(value)


def verify_slot_evidence(report: dict, path: Path, drive_file: dict, document_revision: str) -> dict:
    """Validate evidence created before the report slot and bind the exact Doc readback.

    This never repairs a body. Missing, stale, mismatched, or post-slot evidence
    raises ValueError so callers can retain the source as an ineligible archive.
    """
    if not path.is_file():
        raise ValueError("BLOCKED_SNAPSHOT_MISSING")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("schemaVersion") != 1 or evidence.get("evidenceStatus") != "READY_FOR_DRAFT":
        raise ValueError("BLOCKED_SNAPSHOT_INVALID_STATUS")
    expected_id = f"{report['date']}_{report['time'].replace(':', '-')}"
    if evidence.get("reportId") != expected_id or evidence.get("revision") != report.get("revision"):
        raise ValueError("BLOCKED_SNAPSHOT_REPORT_ID_MISMATCH")
    context = evidence.get("context")
    snapshot_data = evidence.get("snapshot")
    if not isinstance(context, dict) or not isinstance(snapshot_data, dict):
        raise ValueError("BLOCKED_SNAPSHOT_CONTEXT_OR_DATA_MISSING")
    if evidence.get("contextHash") != _canonical_hash(context):
        raise ValueError("BLOCKED_CONTEXT_HASH_MISMATCH")
    if evidence.get("snapshotHash") != _canonical_hash(snapshot_data):
        raise ValueError("BLOCKED_SNAPSHOT_HASH_MISMATCH")
    source_hash = (evidence.get("acquisitionSource") or {}).get("contentHash")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("BLOCKED_SNAPSHOT_SOURCE_HASH_MISSING")
    expected_evidence_id = hashlib.sha256(
        f"{evidence['contextHash']}:{evidence['snapshotHash']}:{source_hash}".encode("ascii")
    ).hexdigest()
    if evidence.get("evidenceId") != expected_evidence_id:
        raise ValueError("BLOCKED_EVIDENCE_ID_MISMATCH")
    if context.get("report_id") != expected_id or context.get("report_date") != report["date"] or context.get("report_time") != report["time"] or context.get("revision") != report.get("revision"):
        raise ValueError("BLOCKED_CONTEXT_REPORT_ID_MISMATCH")
    acquisition = evidence.get("acquisitionSource")
    if not isinstance(acquisition, dict) or acquisition.get("reportSlot") != report["time"]:
        raise ValueError("BLOCKED_SNAPSHOT_ACQUISITION_SLOT_MISMATCH")
    target = aware(f"{report['date']}T{report['time']}:00+09:00")
    cutoff = aware(context.get("data_cutoff", ""))
    if cutoff > target:
        raise ValueError("BLOCKED_CONTEXT_AFTER_REPORT_SLOT")
    snapshot = MarketDataSnapshot.restore(snapshot_data)
    snapshot.validate_context(ReportContext(**context))
    if snapshot.report_id != expected_id or snapshot.revision != report.get("revision"):
        raise ValueError("BLOCKED_SNAPSHOT_REPORT_ID_MISMATCH")
    if snapshot.captured_at != acquisition.get("generatedAt"):
        raise ValueError("BLOCKED_SNAPSHOT_CAPTURE_TIME_MISMATCH")
    if aware(snapshot.captured_at) > target:
        raise ValueError("BLOCKED_SNAPSHOT_CAPTURED_AFTER_REPORT_SLOT")
    generated_at = aware(acquisition.get("generatedAt", ""))
    if generated_at > cutoff or cutoff - generated_at > timedelta(minutes=15):
        raise ValueError("BLOCKED_SNAPSHOT_ACQUISITION_CUTOFF_INVALID")

    created_text = drive_file.get("createdTime")
    modified_text = drive_file.get("modifiedTime")
    if not created_text or not modified_text:
        raise ValueError("DRIVE_SAVED_QA_PENDING: Drive creation/modification timestamps are unavailable")
    created_at = aware(created_text)
    modified_at = aware(modified_text)
    if modified_at < created_at or modified_at > target + timedelta(minutes=40):
        raise ValueError("DRIVE_SAVED_QA_PENDING: document was modified outside the slot readback window")
    if not document_revision:
        raise ValueError("DRIVE_SAVED_QA_PENDING: Docs revision ID is unavailable")

    body_hash = report.get("bodyHash")
    if not isinstance(body_hash, str) or body_hash != hashlib.sha256(report["fullText"].encode("utf-8")).hexdigest():
        raise ValueError("DRIVE_SAVED_QA_PENDING: exact readback body hash mismatch")
    readback_at = datetime.now().astimezone().isoformat()
    return {
        "schemaVersion": 2,
        "date": report["date"],
        "time": report["time"],
        "title": report["title"],
        "status": "DOC_READBACK_PASS",
        "publisher": "google-drive-ingestion",
        "driveFileId": drive_file["id"],
        "driveUrl": report["sourceDocument"]["url"],
        "savedAt": modified_at.isoformat(),
        "reportId": expected_id,
        "revision": report["revision"],
        "documentRevisionId": document_revision,
        "bodyHash": body_hash,
        "readback": {"status": "PASS", "exactMatch": True, "bodyHash": body_hash, "readAt": readback_at, "characterCount": len(report["fullText"])},
        "evidenceId": evidence["evidenceId"],
        "snapshotId": snapshot.snapshot_id,
        "contextHash": evidence["contextHash"],
        "snapshotHash": evidence["snapshotHash"],
        "sourceDocument": {"createdAt": created_at.isoformat(), "modifiedAt": modified_at.isoformat()},
    }


def validate_receipt(receipt: dict, report: dict) -> None:
    """Require the importer-issued readback receipt to bind canonical report and evidence."""
    required = {
        "schemaVersion", "date", "time", "title", "status", "publisher", "driveFileId",
        "driveUrl", "savedAt", "reportId", "revision", "documentRevisionId", "bodyHash",
        "readback", "evidenceId", "snapshotId", "contextHash", "snapshotHash", "sourceDocument",
    }
    missing = sorted(k for k in required if receipt.get(k) in (None, ""))
    if missing:
        raise ValueError("receipt fields missing: " + ", ".join(missing))
    if receipt["schemaVersion"] != 2 or receipt["status"] != "DOC_READBACK_PASS" or receipt["publisher"] != "google-drive-ingestion":
        raise ValueError("receipt schema/status/publisher mismatch")
    for key in ("date", "time", "title"):
        if receipt[key] != report.get(key):
            raise ValueError(f"receipt {key} mismatch")
    expected_id = f"{report['date']}_{report['time'].replace(':', '-')}"
    if receipt["reportId"] != expected_id or receipt["revision"] != report.get("revision"):
        raise ValueError("receipt report identity/revision mismatch")
    if receipt["driveFileId"] != report.get("sourceDocument", {}).get("id"):
        raise ValueError("receipt Drive ID mismatch")
    if receipt["driveUrl"] != report.get("sourceDocument", {}).get("url"):
        raise ValueError("receipt Drive URL mismatch")
    if receipt["driveUrl"] != f"https://docs.google.com/document/d/{receipt['driveFileId']}/edit":
        raise ValueError("receipt Drive URL does not identify its file ID")
    try:
        saved_at = aware(receipt["savedAt"])
    except ValueError as exc:
        raise ValueError("receipt savedAt is not timezone-aware ISO8601") from exc
    if saved_at < aware(f"{report['date']}T{report['time']}:00+09:00"):
        raise ValueError("receipt save time precedes report slot")
    source_meta = receipt["sourceDocument"]
    if not isinstance(source_meta, dict) or not source_meta.get("createdAt") or not source_meta.get("modifiedAt"):
        raise ValueError("receipt Drive timestamps are missing")
    created_at = aware(source_meta["createdAt"])
    modified_at = aware(source_meta["modifiedAt"])
    slot_at = aware(f"{report['date']}T{report['time']}:00+09:00")
    if modified_at < created_at or modified_at > slot_at + timedelta(minutes=40) or saved_at != modified_at:
        raise ValueError("receipt Drive timestamps are inconsistent or outside the readback window")
    body_hash = hashlib.sha256(str(report.get("fullText", "")).encode("utf-8")).hexdigest()
    if receipt["bodyHash"] != body_hash or report.get("bodyHash") != body_hash:
        raise ValueError("receipt body hash mismatch")
    readback = receipt["readback"]
    if not isinstance(readback, dict) or readback.get("status") != "PASS" or readback.get("exactMatch") is not True or readback.get("bodyHash") != body_hash:
        raise ValueError("receipt exact readback missing")
    if readback.get("characterCount") != len(str(report.get("fullText", ""))):
        raise ValueError("receipt readback character count mismatch")
    evidence = report.get("publicationEvidence")
    if not isinstance(evidence, dict):
        raise ValueError("canonical publication evidence missing")
    for field in ("evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId"):
        if evidence.get(field) != receipt.get(field):
            raise ValueError(f"receipt {field} mismatch")
