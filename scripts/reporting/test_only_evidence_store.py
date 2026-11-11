"""Strict TEST ONLY GCS adapters for scheduler Evidence and watchdog readback.

The module refuses buckets/prefixes outside the named isolated test boundary.
It never lists or deletes objects and never reaches production publication paths.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from scripts.persist_report_slot_evidence import (
    canonical_bytes,
    validate_stored_slot_evidence,
)

TEST_ONLY_BUCKET = "market-report-test-only-mr-pre-slot-test-evidence"
TEST_ONLY_PREFIX = "test-only/scheduler-e2e"
REPORT_ID_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}_(08|12|16|21)-00$")


class TestOnlyStorageError(RuntimeError):
    """A TEST ONLY GCS operation failed or returned inconsistent bytes."""


class TestOnlyConflict(TestOnlyStorageError):
    """The create-only Evidence object already exists with different bytes."""


def _http_status(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    response = getattr(exc, "response", None)
    if code is None:
        code = getattr(response, "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _validate_target(bucket_name: str, prefix: str) -> str:
    if bucket_name != TEST_ONLY_BUCKET:
        raise TestOnlyStorageError("TEST_ONLY_BUCKET_REQUIRED")
    safe_prefix = prefix.strip("/")
    if safe_prefix != TEST_ONLY_PREFIX:
        raise TestOnlyStorageError("TEST_ONLY_PREFIX_REQUIRED")
    return safe_prefix


def _report_identity(report_id: str) -> tuple[str, str]:
    if not REPORT_ID_RE.fullmatch(report_id):
        raise TestOnlyStorageError("REPORT_ID_INVALID")
    report_date, slot = report_id.rsplit("_", 1)
    return report_date, slot.replace("-", ":")


def _object_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise TestOnlyStorageError("GCS_TIME_CREATED_NAIVE")
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TestOnlyStorageError("GCS_TIME_CREATED_INVALID") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise TestOnlyStorageError("GCS_TIME_CREATED_NAIVE")
        return parsed.astimezone(timezone.utc)
    raise TestOnlyStorageError("GCS_TIME_CREATED_MISSING")


class TestOnlyEvidenceStore:
    def __init__(self, client, *, bucket_name: str, prefix: str = TEST_ONLY_PREFIX):
        self.prefix = _validate_target(bucket_name, prefix)
        self.bucket_name = bucket_name
        self.client = client

    def _blob(self, object_name: str, *, generation: int | None = None):
        if not object_name.startswith(self.prefix + "/"):
            raise TestOnlyStorageError("OBJECT_OUTSIDE_TEST_ONLY_PREFIX")
        return self.client.bucket(self.bucket_name).blob(object_name, generation=generation)

    def read_input(self, report_id: str) -> dict[str, Any]:
        _report_identity(report_id)
        object_name = f"{self.prefix}/inputs/{report_id}.json"
        blob = self._blob(object_name)
        try:
            blob.reload()
            generation = int(blob.generation)
            if generation <= 0:
                raise TestOnlyStorageError("INPUT_GENERATION_INVALID")
            payload = blob.download_as_bytes(if_generation_match=generation)
        except TestOnlyStorageError:
            raise
        except Exception as exc:
            status = _http_status(exc)
            code = "INPUT_MISSING" if status == 404 else "INPUT_READ_BLOCKED"
            raise TestOnlyStorageError(code) from exc
        if not payload:
            raise TestOnlyStorageError("INPUT_EMPTY")
        try:
            market_payload = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TestOnlyStorageError("INPUT_INVALID_JSON") from exc
        if not isinstance(market_payload, dict):
            raise TestOnlyStorageError("INPUT_NOT_OBJECT")
        return {
            "object": object_name,
            "generation": generation,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": payload,
            "payload": market_payload,
        }

    def create_evidence(self, report_date: str, report_slot: str, evidence: dict) -> dict[str, Any]:
        report_id = f"{report_date}_{report_slot.replace(':', '-')}"
        _report_identity(report_id)
        object_name = f"{self.prefix}/evidence/{report_id}-r{evidence.get('revision')}.json"
        payload = canonical_bytes(evidence)
        blob = self._blob(object_name)
        created = True
        metadata = {
            "report_id": report_id,
            "revision": str(evidence.get("revision")),
            "evidence_id": str(evidence.get("evidenceId")),
        }
        try:
            blob.metadata = metadata
            blob.upload_from_string(
                payload,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if _http_status(exc) != 412:
                raise TestOnlyStorageError("EVIDENCE_CREATE_FAILED") from exc
            created = False

        try:
            blob.reload()
            generation = int(blob.generation)
            if generation <= 0:
                raise TestOnlyStorageError("EVIDENCE_GENERATION_INVALID")
            stored_at = _object_time(blob.time_created)
            readback = blob.download_as_bytes(if_generation_match=generation)
        except TestOnlyStorageError:
            raise
        except Exception as exc:
            raise TestOnlyStorageError("EVIDENCE_READBACK_FAILED") from exc

        if readback != payload:
            raise TestOnlyConflict("EVIDENCE_CREATE_ONLY_CONFLICT")
        sha256 = hashlib.sha256(readback).hexdigest()
        checked = validate_stored_slot_evidence(readback, report_date, report_slot)
        if checked.get("reportId") != report_id or checked.get("revision") != evidence.get("revision"):
            raise TestOnlyStorageError("EVIDENCE_READBACK_IDENTITY_MISMATCH")
        cutoff = _report_identity(report_id)
        del cutoff
        cutoff_at = datetime.fromisoformat(f"{report_date}T{report_slot}:00+09:00").astimezone(timezone.utc)
        if stored_at >= cutoff_at:
            raise TestOnlyStorageError("EVIDENCE_OBJECT_CREATED_AFTER_CUTOFF")
        return {
            "object": object_name,
            "generation": generation,
            "sha256": sha256,
            "bytes": len(readback),
            "stored_at": stored_at.isoformat(),
            "created": created,
            "report_id": report_id,
            "revision": checked["revision"],
            "evidence_id": checked["evidenceId"],
        }

    def read_evidence(self, report_date: str, report_slot: str) -> dict[str, Any]:
        report_id = f"{report_date}_{report_slot.replace(':', '-')}"
        _report_identity(report_id)
        object_name = f"{self.prefix}/evidence/{report_id}-r1.json"
        blob = self._blob(object_name)
        try:
            blob.reload()
        except Exception as exc:
            status = _http_status(exc)
            if status == 404:
                return {"state": "ABSENT", "object": object_name}
            return {"state": "UNKNOWN", "object": object_name, "error": "GCS_READ_BLOCKED"}
        try:
            generation = int(blob.generation)
            if generation <= 0:
                raise TestOnlyStorageError("EVIDENCE_GENERATION_INVALID")
            stored_at = _object_time(blob.time_created)
            payload = blob.download_as_bytes(if_generation_match=generation)
            checked = validate_stored_slot_evidence(payload, report_date, report_slot)
            cutoff_at = datetime.fromisoformat(
                f"{report_date}T{report_slot}:00+09:00"
            ).astimezone(timezone.utc)
            if stored_at >= cutoff_at:
                raise TestOnlyStorageError("EVIDENCE_OBJECT_CREATED_AFTER_CUTOFF")
            return {
                "state": "VALID",
                "object": object_name,
                "generation": generation,
                "stored_at": stored_at.isoformat(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "evidence": checked,
            }
        except (TestOnlyStorageError, ValueError, TypeError, KeyError):
            return {"state": "INVALID", "object": object_name, "error": "EVIDENCE_VALIDATION_FAILED"}
        except Exception:
            return {"state": "UNKNOWN", "object": object_name, "error": "GCS_READBACK_FAILED"}

