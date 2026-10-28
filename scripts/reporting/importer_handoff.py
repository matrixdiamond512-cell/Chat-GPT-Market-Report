"""TEST_ONLY GCS evidence handoff for a local, isolated importer checkout.

This module never writes to GitHub, Google Drive, or Pages. It copies one
verified GCS generation into the path consumed by the existing importer, but
only below an explicitly marked LOCAL_STAGING_ONLY checkout.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re

from scripts.persist_report_slot_evidence import validate_stored_slot_evidence


class ImporterHandoffBlocked(ValueError):
    """The local staging handoff did not meet its exact-generation contract."""


def validate_staging_root(staging_root: Path, *, importer_root: Path) -> Path:
    root = Path(staging_root).expanduser().resolve()
    current = Path(importer_root).expanduser().resolve()
    if root == current or current in root.parents:
        raise ImporterHandoffBlocked("STAGING_ROOT_MUST_BE_ISOLATED")
    if not root.is_dir():
        raise ImporterHandoffBlocked("STAGING_ROOT_NOT_FOUND")
    marker_path = root / ".market-report-staging.json"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImporterHandoffBlocked("STAGING_MARKER_MISSING_OR_INVALID") from exc
    if marker.get("schemaVersion") != 1 or marker.get("mode") != "LOCAL_STAGING_ONLY" or marker.get("environment") != "TEST_ONLY":
        raise ImporterHandoffBlocked("STAGING_MARKER_NOT_TEST_ONLY")
    return root


def validate_docs_issuance_binding(app_properties: dict, report: dict, receipt: dict) -> None:
    """Require Docs appProperties to bind the readback body to this exact evidence."""
    expected = {
        "report_id": report.get("report_id"),
        "revision": str(report.get("revision")),
        "body_hash": report.get("bodyHash"),
        "evidence_id": receipt.get("evidenceId"),
        "snapshot_id": receipt.get("snapshotId"),
    }
    if not isinstance(app_properties, dict):
        raise ImporterHandoffBlocked("DOCS_ISSUANCE_BINDING_MISSING")
    for key, value in expected.items():
        if not value or app_properties.get(key) != value:
            raise ImporterHandoffBlocked("DOCS_ISSUANCE_BINDING_MISMATCH:" + key)


def stage_test_only_evidence(
    *,
    staging_root: Path,
    importer_root: Path,
    project_id: str,
    bucket_name: str,
    object_name: str,
    generation: int,
    object_sha256: str,
    report_date: str,
    revision: int,
    expected_snapshot_id: str,
    client=None,
) -> dict:
    """Read one pinned TEST_ONLY GCS generation and create-only stage exact bytes."""
    root = validate_staging_root(staging_root, importer_root=importer_root)
    if not project_id or "test" not in project_id.lower() or not bucket_name or "test" not in bucket_name.lower():
        raise ImporterHandoffBlocked("TEST_ONLY_GCS_TARGET_REQUIRED")
    try:
        parsed_date = date.fromisoformat(report_date)
    except (TypeError, ValueError) as exc:
        raise ImporterHandoffBlocked("REPORT_DATE_INVALID") from exc
    if parsed_date.isoformat() != report_date or type(revision) is not int or revision <= 0:
        raise ImporterHandoffBlocked("REPORT_IDENTITY_INVALID")
    expected_report_id = f"{report_date}_08-00"
    if not isinstance(expected_snapshot_id, str) or not expected_snapshot_id:
        raise ImporterHandoffBlocked("EXPECTED_SNAPSHOT_ID_REQUIRED")
    if type(generation) is not int or generation <= 0:
        raise ImporterHandoffBlocked("GCS_GENERATION_REQUIRED")
    if not re.fullmatch(r"[0-9a-f]{64}", str(object_sha256 or "")):
        raise ImporterHandoffBlocked("GCS_OBJECT_SHA256_REQUIRED")

    if client is None:
        from google.cloud import storage
        client = storage.Client(project=project_id)
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    try:
        payload = blob.download_as_bytes(if_generation_match=generation)
        blob.reload()
    except Exception as exc:
        raise ImporterHandoffBlocked("PINNED_GCS_GENERATION_READ_FAILED") from exc
    if int(blob.generation) != generation:
        raise ImporterHandoffBlocked("PINNED_GCS_GENERATION_MISMATCH")
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != object_sha256:
        raise ImporterHandoffBlocked("GCS_OBJECT_HASH_MISMATCH")
    try:
        frozen = validate_stored_slot_evidence(payload, report_date, "08:00")
    except (ValueError, KeyError, TypeError) as exc:
        raise ImporterHandoffBlocked("STORED_SLOT_EVIDENCE_INVALID") from exc
    snapshot_id = (frozen.get("snapshot") or {}).get("snapshot_id")
    if frozen.get("reportId") != expected_report_id or frozen.get("revision") != revision:
        raise ImporterHandoffBlocked("STORED_SLOT_IDENTITY_MISMATCH")
    if snapshot_id != expected_snapshot_id:
        raise ImporterHandoffBlocked("STORED_SLOT_SNAPSHOT_MISMATCH")
    marker = json.loads((root / ".market-report-staging.json").read_text(encoding="utf-8"))
    marker_report_id = marker.get("report_id")
    marker_revision = marker.get("revision")
    if marker_report_id != expected_report_id or marker_revision != revision:
        raise ImporterHandoffBlocked("STAGING_MARKER_IDENTITY_MISMATCH")

    relative = Path("data") / "report-evidence" / f"{report_date}_08-00-r{revision}.json"
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.resolve() not in (root, *root.parents) and root not in destination.parent.resolve().parents:
        raise ImporterHandoffBlocked("STAGING_EVIDENCE_PATH_ESCAPES_ROOT")
    try:
        with destination.open("xb") as handle:
            handle.write(payload)
    except FileExistsError:
        try:
            existing = destination.read_bytes()
        except OSError as exc:
            raise ImporterHandoffBlocked("STAGING_EXISTING_EVIDENCE_READ_FAILED") from exc
        if existing != payload:
            raise ImporterHandoffBlocked("STAGING_EVIDENCE_CONFLICT")
    except OSError as exc:
        raise ImporterHandoffBlocked("STAGING_EVIDENCE_CREATE_FAILED") from exc

    readback = destination.read_bytes()
    if readback != payload or hashlib.sha256(readback).hexdigest() != actual_hash:
        raise ImporterHandoffBlocked("STAGING_EVIDENCE_READBACK_MISMATCH")
    return {
        "status": "LOCAL_STAGE_READBACK_PASS",
        "environment": "TEST_ONLY",
        "report_id": expected_report_id,
        "revision": revision,
        "snapshot_id": snapshot_id,
        "generation": generation,
        "object_sha256": actual_hash,
        "path": str(relative).replace("\\", "/"),
    }
