#!/usr/bin/env python3
"""Persist immutable, pre-draft evidence for one real report slot.

This artifact only establishes the frozen acquisition and report context. It is
not a publication receipt and never makes a report eligible for publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if __package__:
    from .reporting.context import ReportContext, aware
    from .reporting.snapshot import MarketDataSnapshot, digest
    from .run_market_data_window import snapshot_is_current
else:
    from reporting.context import ReportContext, aware
    from reporting.snapshot import MarketDataSnapshot, digest
    from run_market_data_window import snapshot_is_current

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
SLOT_WINDOW_MINUTES = 15


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def require_slot_window(report_date: str, report_time: str, *, now: datetime | None = None, window_minutes: int = SLOT_WINDOW_MINUTES) -> datetime:
    """Require execution inside the target slot's real pre-cutoff window.

    A scheduled event is never assigned to a different date because the runner
    started late. Manual dispatch uses the same window.
    """
    if report_time not in {"08:00", "12:00", "16:00", "21:00"}:
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:unsupported report slot")
    target = aware(f"{report_date}T{report_time}:00+09:00")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:naive execution clock")
    current = current.astimezone(JST)
    start = target - timedelta(minutes=window_minutes)
    if current < start:
        previous_target = target - timedelta(days=1)
        if previous_target.weekday() < 5 and previous_target <= current:
            # If the previous business day's same-slot cutoff is closer than
            # today's future cutoff, this is a delayed prior-slot event that
            # crossed midnight, not an early run for today's slot.
            if current - previous_target < target - current:
                raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")
        if target.weekday() >= 5:
            raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:non-weekday report date")
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:early or date-mismatched execution")
    if target.weekday() >= 5:
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:non-weekday report date")
    if current >= target:
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")
    return current


def require_evidence_slot_guard(report_date: str, report_time: str, *, now: datetime | None = None) -> datetime:
    """Use the new narrow live window for 08:00; preserve cutoff-only legacy gates for other slots."""
    if report_time == "08:00":
        return require_slot_window(report_date, report_time, now=now)
    current = now if now is not None else datetime.now(timezone.utc)
    require_before_slot(report_date, report_time, now=current)
    return current.astimezone(JST)


def require_gcs_evidence_slot(report_time: str) -> None:
    if report_time != "08:00":
        raise ValueError("BLOCKED_GCS_EVIDENCE_08_ONLY")


def build_slot_evidence(report_date: str, report_time: str, market_payload: dict, raw_market_bytes: bytes, *, max_age_minutes: int = 15, evidence_created_at: datetime | None = None) -> dict:
    day = date.fromisoformat(report_date)
    if max_age_minutes < 0:
        raise ValueError("max_age_minutes must be nonnegative")
    if market_payload.get("reportSlot") != report_time or market_payload.get("reportDate", report_date) != report_date:
        raise ValueError("INPUT_SLOT_MISMATCH")
    if market_payload.get("overallStatus") not in {"verified", "degraded"}:
        raise ValueError("ACQUISITION_FAILED")
    if not snapshot_is_current(market_payload, report_time, day):
        raise ValueError("INPUT_STALE: acquisition is not verified for the requested report date/slot/cutoff")

    cutoff = aware(f"{report_date}T{report_time}:00+09:00")
    generated_at = aware(market_payload["generatedAt"])
    age_seconds = (cutoff - generated_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_minutes * 60:
        raise ValueError("INPUT_STALE: acquisition is outside the allowed pre-draft cutoff window")
    if evidence_created_at is not None:
        if evidence_created_at.tzinfo is None or evidence_created_at.utcoffset() is None:
            raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:naive evidence creation time")
        evidence_created_at = evidence_created_at.astimezone(JST)
        require_evidence_slot_guard(report_date, report_time, now=evidence_created_at)
        if generated_at > evidence_created_at:
            raise ValueError("INPUT_STALE: acquisition timestamp is after evidence creation")
    context = ReportContext.create(report_date, report_time, generated_at.isoformat(), revision=1, mode="new")
    snapshot = MarketDataSnapshot.from_acquisition(context, market_payload)
    context_data = context.to_dict()
    snapshot_data = snapshot.to_dict()
    source_hash = hashlib.sha256(raw_market_bytes).hexdigest()
    context_hash = digest(context_data)
    snapshot_hash = digest(snapshot_data)
    evidence_id = hashlib.sha256(f"{context_hash}:{snapshot_hash}:{source_hash}".encode("ascii")).hexdigest()
    return {
        "schemaVersion": 1,
        "evidenceStatus": "READY_FOR_DRAFT",
        "evidenceId": evidence_id,
        "evidenceCreatedAt": evidence_created_at.isoformat() if evidence_created_at is not None else None,
        "reportId": context.report_id,
        "revision": context.revision,
        "context": context_data,
        "contextHash": context_hash,
        "snapshot": snapshot_data,
        "snapshotHash": snapshot_hash,
        "acquisitionSource": {
            "path": "data/market/latest.json",
            "contentHash": source_hash,
            "generatedAt": market_payload["generatedAt"],
            "reportSlot": report_time,
            "overallStatus": market_payload.get("overallStatus"),
        },
    }


def validate_stored_slot_evidence(encoded: bytes, report_date: str, report_time: str, *, max_age_minutes: int = 15) -> dict:
    """Validate an existing immutable artifact without rebuilding it from latest data."""
    try:
        evidence = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("BLOCKED_STORED_EVIDENCE_INVALID_JSON") from exc
    if not isinstance(evidence, dict) or evidence.get("schemaVersion") != 1 or evidence.get("evidenceStatus") != "READY_FOR_DRAFT":
        raise ValueError("BLOCKED_STORED_EVIDENCE_INVALID_STATUS")
    expected_report_id = f"{report_date}_{report_time.replace(':', '-')}"
    if evidence.get("reportId") != expected_report_id or evidence.get("revision") != 1:
        raise ValueError("BLOCKED_STORED_EVIDENCE_REPORT_ID_MISMATCH")
    context_data = evidence.get("context")
    snapshot_data = evidence.get("snapshot")
    acquisition = evidence.get("acquisitionSource")
    if not isinstance(context_data, dict) or not isinstance(snapshot_data, dict) or not isinstance(acquisition, dict):
        raise ValueError("BLOCKED_STORED_EVIDENCE_FIELDS_MISSING")
    if evidence.get("contextHash") != digest(context_data):
        raise ValueError("BLOCKED_STORED_EVIDENCE_CONTEXT_HASH_MISMATCH")
    if evidence.get("snapshotHash") != digest(snapshot_data):
        raise ValueError("BLOCKED_STORED_EVIDENCE_SNAPSHOT_HASH_MISMATCH")
    source_hash = acquisition.get("contentHash")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("BLOCKED_STORED_EVIDENCE_SOURCE_HASH_MISSING")
    try:
        int(source_hash, 16)
    except ValueError as exc:
        raise ValueError("BLOCKED_STORED_EVIDENCE_SOURCE_HASH_INVALID") from exc
    expected_evidence_id = hashlib.sha256(
        f"{evidence['contextHash']}:{evidence['snapshotHash']}:{source_hash}".encode("ascii")
    ).hexdigest()
    if evidence.get("evidenceId") != expected_evidence_id:
        raise ValueError("BLOCKED_STORED_EVIDENCE_ID_MISMATCH")
    created_at_raw = evidence.get("evidenceCreatedAt")
    target_for_creation = aware(f"{report_date}T{report_time}:00+09:00")
    if report_time == "08:00":
        if not isinstance(created_at_raw, str):
            raise ValueError("BLOCKED_STORED_EVIDENCE_CREATION_TIME_MISSING")
        created_at = aware(created_at_raw)
        if created_at < target_for_creation - timedelta(minutes=max_age_minutes) or created_at >= target_for_creation:
            raise ValueError("BLOCKED_STORED_EVIDENCE_CREATION_TIME_OUTSIDE_WINDOW")
    elif isinstance(created_at_raw, str) and aware(created_at_raw) >= target_for_creation:
        raise ValueError("BLOCKED_STORED_EVIDENCE_CREATION_TIME_OUTSIDE_CUTOFF")
    context = ReportContext(**context_data)
    snapshot = MarketDataSnapshot.restore(snapshot_data)
    snapshot.validate_context(context)
    if context.report_id != expected_report_id or context.report_date != report_date or context.report_time != report_time:
        raise ValueError("BLOCKED_STORED_EVIDENCE_CONTEXT_IDENTITY_MISMATCH")
    if snapshot.report_id != expected_report_id or snapshot.revision != 1:
        raise ValueError("BLOCKED_STORED_EVIDENCE_SNAPSHOT_IDENTITY_MISMATCH")
    if acquisition.get("reportSlot") != report_time or acquisition.get("generatedAt") != snapshot.captured_at:
        raise ValueError("BLOCKED_STORED_EVIDENCE_ACQUISITION_MISMATCH")
    cutoff = aware(context.data_cutoff)
    generated_at = aware(snapshot.captured_at)
    target = aware(f"{report_date}T{report_time}:00+09:00")
    age_seconds = (target - generated_at).total_seconds()
    if cutoff > target or generated_at > cutoff or age_seconds < 0 or age_seconds > max_age_minutes * 60:
        raise ValueError("BLOCKED_STORED_EVIDENCE_CUTOFF_INVALID")
    return evidence


def require_before_slot(report_date: str, report_time: str, *, now: datetime | None = None) -> None:
    """Legacy cutoff-only check for downstream publication guards."""
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("BLOCKED_LIVE_EVIDENCE_NAIVE_CLOCK")
    target = aware(f"{report_date}T{report_time}:00+09:00")
    if current.astimezone(JST) >= target:
        raise ValueError("BLOCKED_LIVE_EVIDENCE_AFTER_SLOT")


def unlink_if_same_file(path: Path, opened_stat: os.stat_result) -> bool:
    """Remove only the file created by this writer, never a replacement at its path."""
    try:
        current_stat = path.stat()
    except FileNotFoundError:
        return True
    if not os.path.samestat(opened_stat, current_stat):
        return False
    path.unlink()
    return True


def persist_slot_evidence(report_date: str, report_time: str, market_data_path: Path, output_dir: Path, *, max_age_minutes: int = 15, require_live_before_slot: bool = False, now: datetime | None = None) -> tuple[Path, bool]:
    evidence_created_at = now if now is not None else datetime.now(timezone.utc)
    if evidence_created_at.tzinfo is None or evidence_created_at.utcoffset() is None:
        raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:naive execution clock")
    if require_live_before_slot:
        require_evidence_slot_guard(report_date, report_time, now=evidence_created_at)
    raw = market_data_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("market acquisition must be a JSON object")
    evidence = build_slot_evidence(report_date, report_time, payload, raw, max_age_minutes=max_age_minutes, evidence_created_at=evidence_created_at)
    out_path = output_dir / f"{evidence['reportId']}-r{evidence['revision']}.json"
    encoded = canonical_bytes(evidence)
    if out_path.exists():
        if out_path.read_bytes() == encoded:
            return out_path, False
        raise FileExistsError(f"immutable report evidence already exists with different content: {out_path}")
    if require_live_before_slot:
        require_evidence_slot_guard(report_date, report_time, now=now)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    created_stat: os.stat_result
    try:
        # Exclusive creation prevents two independent workflows from silently
        # replacing one another's evidence between the existence check and write.
        with out_path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            created_stat = os.fstat(handle.fileno())
    except FileExistsError:
        existing = out_path.read_bytes()
        if existing == encoded:
            return out_path, False
        raise FileExistsError(f"immutable report evidence already exists with different content: {out_path}")
    if require_live_before_slot:
        try:
            # Re-read the clock after the write; `now` may be a caller-supplied
            # snapshot from before serialization and file I/O.
            require_evidence_slot_guard(report_date, report_time)
        except ValueError:
            unlink_if_same_file(out_path, created_stat)
            raise
    # Read back and verify both exact bytes and calculated identity before success.
    readback = out_path.read_bytes()
    if readback != encoded:
        unlink_if_same_file(out_path, created_stat)
        raise OSError("report evidence readback differs from persisted bytes")
    restored = json.loads(readback.decode("utf-8"))
    if restored.get("evidenceId") != evidence["evidenceId"] or digest(restored["snapshot"]) != evidence["snapshotHash"] or digest(restored["context"]) != evidence["contextHash"]:
        unlink_if_same_file(out_path, created_stat)
        raise OSError("report evidence identity readback failed")
    return out_path, True



def gcs_storage_client():
    """Use ADC established by GitHub OIDC/WIF; service-account JSON keys are not accepted here."""
    try:
        import google.auth
        from google.cloud import storage
        credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        project = os.environ.get("REPORT_EVIDENCE_PROJECT_ID") or detected_project
        if not project:
            raise RuntimeError("EVIDENCE_WRITE_FAILED: REPORT_EVIDENCE_PROJECT_ID is required for ADC")
        return storage.Client(project=project, credentials=credentials)
    except Exception as exc:
        if isinstance(exc, RuntimeError) and str(exc).startswith("EVIDENCE_WRITE_FAILED:"):
            raise
        raise RuntimeError("EVIDENCE_WRITE_FAILED: WIF/ADC credentials are unavailable") from exc


def gcs_evidence_object_name(prefix: str, report_id: str, revision: int) -> str:
    safe_prefix = prefix.strip("/")
    leaf = f"{report_id}-r{revision}.json"
    return f"{safe_prefix}/{leaf}" if safe_prefix else leaf


def _gcs_time(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("EVIDENCE_WRITE_FAILED: GCS returned a naive creation timestamp")
        return value.astimezone(JST)
    if isinstance(value, str):
        try:
            timestamp = aware(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("EVIDENCE_WRITE_FAILED: GCS creation timestamp is invalid") from exc
        return timestamp.astimezone(JST)
    raise ValueError("EVIDENCE_WRITE_FAILED: GCS creation timestamp is missing")


def _validate_gcs_evidence_bytes(encoded: bytes, report_date: str, report_time: str, gcs_created_at: datetime, *, max_age_minutes: int = SLOT_WINDOW_MINUTES) -> dict:
    evidence = validate_stored_slot_evidence(encoded, report_date, report_time, max_age_minutes=max_age_minutes)
    target = aware(f"{report_date}T{report_time}:00+09:00")
    lower = target - timedelta(minutes=max_age_minutes)
    created = gcs_created_at.astimezone(JST)
    body_created = aware(evidence["evidenceCreatedAt"]).astimezone(JST)
    if not lower <= created < target:
        raise ValueError("EVIDENCE_WRITE_FAILED: GCS object was created outside the pre-slot window")
    if not lower <= body_created < target or body_created > created:
        raise ValueError("EVIDENCE_WRITE_FAILED: Evidence creation time does not precede GCS object creation")
    return evidence


def _validate_gcs_object_metadata(metadata, payload: bytes) -> None:
    try:
        evidence = json.loads(payload.decode("utf-8"))
        acquisition = evidence["acquisitionSource"]
        expected = {
            "reportid": evidence["reportId"],
            "revision": str(evidence["revision"]),
            "evidenceid": evidence["evidenceId"],
            "snapshotid": evidence["snapshot"]["snapshot_id"],
            "contentsha256": hashlib.sha256(payload).hexdigest(),
            "sourcedatahash": acquisition["contentHash"],
            "evidencecreatedat": evidence["evidenceCreatedAt"],
        }
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("EVIDENCE_WRITE_FAILED: GCS object metadata cannot be bound to Evidence") from exc
    if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("EVIDENCE_WRITE_FAILED: GCS object metadata identity/hash mismatch")


def _download_gcs_generation(bucket, object_name: str, generation: int) -> tuple[bytes, datetime]:
    if type(generation) is not int or generation <= 0:
        raise ValueError("EVIDENCE_WRITE_FAILED: GCS generation is missing or invalid")
    try:
        pinned = bucket.blob(object_name, generation=generation)
        payload = pinned.download_as_bytes(if_generation_match=generation)
        pinned.reload()
    except Exception as exc:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: pinned GCS readback failed") from exc
    if int(pinned.generation) != generation:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS generation changed during readback")
    _validate_gcs_object_metadata(getattr(pinned, "metadata", None), payload)
    return payload, _gcs_time(getattr(pinned, "time_created", None))


def read_gcs_slot_evidence(bucket_name: str, object_name: str, report_date: str, report_time: str, *, client=None) -> tuple[bytes, dict] | None:
    """Read one deterministic 08:00 object name and immediately pin its generation."""
    require_gcs_evidence_slot(report_time)
    client = client or gcs_storage_client()
    bucket = client.bucket(bucket_name)
    current = bucket.blob(object_name)
    try:
        current.reload()
    except Exception as exc:
        if type(exc).__name__ == "NotFound" or getattr(exc, "code", lambda: None)() == 404:
            return None
        raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS object lookup failed") from exc
    try:
        generation = int(current.generation)
        payload, created_at = _download_gcs_generation(bucket, object_name, generation)
        evidence = _validate_gcs_evidence_bytes(payload, report_date, report_time, created_at)
    except Exception:
        raise
    reference = {
        "schemaVersion": 1,
        "canonicalStore": "gcs",
        "reportId": evidence["reportId"],
        "revision": evidence["revision"],
        "evidenceId": evidence["evidenceId"],
        "snapshotId": evidence["snapshot"]["snapshot_id"],
        "bucket": bucket_name,
        "object": object_name,
        "generation": generation,
        "contentSha256": hashlib.sha256(payload).hexdigest(),
        "sourceDataSha256": evidence["acquisitionSource"]["contentHash"],
        "evidenceCreatedAt": evidence["evidenceCreatedAt"],
        "gcsCreatedAt": created_at.isoformat(),
    }
    return payload, reference


def persist_gcs_slot_evidence(encoded: bytes, bucket_name: str, object_name: str, report_date: str, report_time: str, *, client=None, now: datetime | None = None, max_age_minutes: int = SLOT_WINDOW_MINUTES) -> dict:
    """Create the canonical 08:00 Evidence object with create-only and pinned readback."""
    require_gcs_evidence_slot(report_time)
    if not bucket_name:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: REPORT_EVIDENCE_BUCKET is not configured")
    require_slot_window(report_date, report_time, now=now)
    evidence = validate_stored_slot_evidence(encoded, report_date, report_time, max_age_minutes=max_age_minutes)
    client = client or gcs_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    metadata = {
        "reportid": evidence["reportId"],
        "revision": str(evidence["revision"]),
        "evidenceid": evidence["evidenceId"],
        "snapshotid": evidence["snapshot"]["snapshot_id"],
        "contentsha256": hashlib.sha256(encoded).hexdigest(),
        "sourcedatahash": evidence["acquisitionSource"]["contentHash"],
        "evidencecreatedat": evidence["evidenceCreatedAt"],
    }
    blob.metadata = metadata
    # Recheck immediately before the externally visible create-only request.
    # Production calls use the live clock (now=None).
    require_slot_window(report_date, report_time, now=now)
    try:
        blob.upload_from_string(encoded, content_type="application/json", if_generation_match=0)
    except Exception as write_error:
        # A create-only collision is a safe retry only if exact bytes and identity
        # read back from the same deterministic object. All other errors fail closed.
        try:
            existing = read_gcs_slot_evidence(bucket_name, object_name, report_date, report_time, client=client)
        except Exception as read_error:
            raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS create/read reconciliation failed") from read_error
        if existing is None:
            raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS create-only upload failed") from write_error
        existing_bytes, reference = existing
        if existing_bytes != encoded:
            raise FileExistsError("BLOCKED_GCS_EVIDENCE_CONFLICT: existing object has different content")
        return reference

    try:
        restored = read_gcs_slot_evidence(bucket_name, object_name, report_date, report_time, client=client)
    except Exception as exc:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: uploaded GCS object readback validation failed") from exc
    if restored is None:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: uploaded GCS object cannot be read back")
    readback, reference = restored
    if readback != encoded or reference["contentSha256"] != hashlib.sha256(encoded).hexdigest():
        raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS content hash or byte readback mismatch")
    return reference


def gcs_reference_path(evidence_path: Path) -> Path:
    return evidence_path.with_name(f"{evidence_path.stem}.gcs-reference.json")


def write_create_only_file(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise FileExistsError(f"BLOCKED_GCS_EVIDENCE_CONFLICT: mirror differs at {path}")
    if path.read_bytes() != encoded:
        raise OSError("EVIDENCE_WRITE_FAILED: local GitHub mirror readback mismatch")


def write_gcs_reference_mirror(evidence_path: Path, evidence_bytes: bytes, reference: dict) -> Path:
    """Write an immutable pointer to the exact canonical object generation."""
    evidence = json.loads(evidence_bytes.decode("utf-8"))
    if any(reference.get(key) != value for key, value in (
        ("reportId", evidence.get("reportId")),
        ("revision", evidence.get("revision")),
        ("evidenceId", evidence.get("evidenceId")),
        ("snapshotId", evidence.get("snapshot", {}).get("snapshot_id")),
        ("contentSha256", hashlib.sha256(evidence_bytes).hexdigest()),
        ("sourceDataSha256", evidence.get("acquisitionSource", {}).get("contentHash")),
        ("evidenceCreatedAt", evidence.get("evidenceCreatedAt")),
    )):
        raise ValueError("EVIDENCE_WRITE_FAILED: GCS reference identity mismatch")
    reference_path = gcs_reference_path(evidence_path)
    write_create_only_file(reference_path, canonical_bytes(reference))
    return reference_path


def verify_gcs_reference_mirror(evidence_bytes: bytes, reference_bytes: bytes, bucket_name: str, *, client=None) -> dict:
    """Verify the GitHub mirror against an exact GCS object generation."""
    try:
        reference = json.loads(reference_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("BLOCKED_GCS_REFERENCE_INVALID") from exc
    if not isinstance(reference, dict) or reference.get("canonicalStore") != "gcs" or reference.get("schemaVersion") != 1:
        raise ValueError("BLOCKED_GCS_REFERENCE_INVALID")
    if reference.get("bucket") != bucket_name:
        raise ValueError("BLOCKED_GCS_REFERENCE_BUCKET_MISMATCH")
    evidence = json.loads(evidence_bytes.decode("utf-8"))
    require_gcs_evidence_slot(evidence.get("context", {}).get("report_time"))
    if hashlib.sha256(evidence_bytes).hexdigest() != reference.get("contentSha256"):
        raise ValueError("BLOCKED_GCS_REFERENCE_HASH_MISMATCH")
    for key, expected in (
        ("reportId", evidence.get("reportId")),
        ("revision", evidence.get("revision")),
        ("evidenceId", evidence.get("evidenceId")),
        ("snapshotId", evidence.get("snapshot", {}).get("snapshot_id")),
        ("sourceDataSha256", evidence.get("acquisitionSource", {}).get("contentHash")),
        ("evidenceCreatedAt", evidence.get("evidenceCreatedAt")),
    ):
        if reference.get(key) != expected:
            raise ValueError("BLOCKED_GCS_REFERENCE_IDENTITY_MISMATCH")
    client = client or gcs_storage_client()
    try:
        pinned_bytes, gcs_created_at = _download_gcs_generation(
            client.bucket(bucket_name), str(reference.get("object") or ""), reference.get("generation")
        )
    except Exception as exc:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: GCS reference readback failed") from exc
    if pinned_bytes != evidence_bytes or hashlib.sha256(pinned_bytes).hexdigest() != reference.get("contentSha256"):
        raise ValueError("BLOCKED_GCS_REFERENCE_READBACK_MISMATCH")
    checked = _validate_gcs_evidence_bytes(
        pinned_bytes, evidence["context"]["report_date"], evidence["context"]["report_time"], gcs_created_at
    )
    if reference.get("gcsCreatedAt") != gcs_created_at.isoformat():
        raise ValueError("BLOCKED_GCS_REFERENCE_CREATION_TIME_MISMATCH")
    return checked


def reconcile_gcs_slot_evidence(report_date: str, report_time: str, output_dir: Path, bucket_name: str, prefix: str, *, client=None, now: datetime | None = None) -> bool:
    """Reconcile only the current 08:00 slot, restoring a GCS-first partial success safely."""
    require_gcs_evidence_slot(report_time)
    require_slot_window(report_date, report_time, now=now)
    if not bucket_name:
        raise RuntimeError("EVIDENCE_WRITE_FAILED: REPORT_EVIDENCE_BUCKET is not configured")
    expected_path = output_dir / f"{report_date}_{report_time.replace(':', '-')}-r1.json"
    reference_path = gcs_reference_path(expected_path)
    object_name = gcs_evidence_object_name(prefix, f"{report_date}_{report_time.replace(':', '-')}", 1)
    local_bytes = expected_path.read_bytes() if expected_path.exists() else None
    if local_bytes is not None:
        validate_stored_slot_evidence(local_bytes, report_date, report_time)
        if reference_path.exists():
            verify_gcs_reference_mirror(local_bytes, reference_path.read_bytes(), bucket_name, client=client)
            return True
    existing = read_gcs_slot_evidence(bucket_name, object_name, report_date, report_time, client=client)
    if existing is None:
        if local_bytes is None:
            return False
        # Recover only a current-slot local artifact whose embedded freeze time
        # is itself in the live window. Never rebuild it from later market data.
        reference = persist_gcs_slot_evidence(
            local_bytes, bucket_name, object_name, report_date, report_time, client=client, now=now
        )
        write_gcs_reference_mirror(expected_path, local_bytes, reference)
        return True
    evidence_bytes, reference = existing
    if local_bytes is not None and local_bytes != evidence_bytes:
        raise FileExistsError("BLOCKED_GCS_EVIDENCE_CONFLICT: local mirror differs from canonical GCS bytes")
    write_create_only_file(expected_path, evidence_bytes)
    write_gcs_reference_mirror(expected_path, evidence_bytes, reference)
    return True


def create_gcs_evidence_and_mirror(evidence_path: Path, bucket_name: str, prefix: str, report_date: str, report_time: str, *, client=None, now: datetime | None = None) -> dict:
    evidence_bytes = evidence_path.read_bytes()
    evidence = validate_stored_slot_evidence(evidence_bytes, report_date, report_time)
    object_name = gcs_evidence_object_name(prefix, evidence["reportId"], evidence["revision"])
    reference = persist_gcs_slot_evidence(
        evidence_bytes, bucket_name, object_name, report_date, report_time, client=client, now=now
    )
    write_gcs_reference_mirror(evidence_path, evidence_bytes, reference)
    return reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="explicit report date YYYY-MM-DD; never inferred from runner time")
    parser.add_argument("--slot", required=True, choices=("08:00", "12:00", "16:00", "21:00"))
    parser.add_argument("--market-data", default="data/market/latest.json")
    parser.add_argument("--output-dir", default="data/report-evidence")
    parser.add_argument("--max-age-minutes", type=int, default=15)
    parser.add_argument("--require-live-before-slot", action="store_true", help="require the actual 15-minute pre-slot execution window")
    parser.add_argument("--gcs-bucket", default=os.environ.get("REPORT_EVIDENCE_BUCKET", ""))
    parser.add_argument("--gcs-prefix", default="pre-draft-evidence")
    parser.add_argument("--persist-gcs", action="store_true", help="create the canonical GCS object create-only and read back its exact generation")
    parser.add_argument("--reconcile-gcs", action="store_true", help="read back an existing exact-slot GCS object and restore its GitHub audit mirror")
    args = parser.parse_args()
    if args.persist_gcs and args.reconcile_gcs:
        parser.error("--persist-gcs and --reconcile-gcs are mutually exclusive")
    if args.reconcile_gcs:
        output_dir = Path(args.output_dir)
        expected = output_dir / f"{args.date}_{args.slot.replace(':', '-')}-r1.json"
        had_mirror = expected.exists() and gcs_reference_path(expected).exists()
        restored = reconcile_gcs_slot_evidence(
            args.date, args.slot, output_dir, args.gcs_bucket, args.gcs_prefix
        )
        ready_value = "true" if restored else "false"
        restored_value = "true" if restored and not had_mirror else "false"
        status = "VERIFIED" if had_mirror and restored else ("RESTORED" if restored else "ABSENT")
        print(f"GCS_RECONCILE={status}")
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as output:
                output.write("ready=" + ready_value + chr(10) + "restored=" + restored_value + chr(10))
        return
    path, created = persist_slot_evidence(
        args.date, args.slot, Path(args.market_data), Path(args.output_dir),
        max_age_minutes=args.max_age_minutes, require_live_before_slot=args.require_live_before_slot,
    )
    print(f"{'CREATED' if created else 'NO_OP'} local pre-draft Evidence: {path.as_posix()}")
    if args.persist_gcs:
        reference = create_gcs_evidence_and_mirror(
            path, args.gcs_bucket, args.gcs_prefix, args.date, args.slot
        )
        print(
            "GCS_CANONICAL_EVIDENCE_READBACK=PASS "
            f"object={reference['object']} generation={reference['generation']} "
            f"sha256={reference['contentSha256']}"
        )


if __name__ == "__main__":
    main()
