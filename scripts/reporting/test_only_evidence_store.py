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
LIVE_PRE_SLOT_PREFIX = "test-only/08-00"
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
    def __init__(self, client, *, bucket_name: str, prefix: str = TEST_ONLY_PREFIX, clock=None):
        self.prefix = _validate_target(bucket_name, prefix)
        self.bucket_name = bucket_name
        self.client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _blob(self, object_name: str, *, generation: int | None = None):
        if not object_name.startswith(self.prefix + "/"):
            raise TestOnlyStorageError("OBJECT_OUTSIDE_TEST_ONLY_PREFIX")
        return self.client.bucket(self.bucket_name).blob(object_name, generation=generation)

    def _pre_slot_blob(self, object_name: str, *, generation: int | None = None):
        if not object_name.startswith(LIVE_PRE_SLOT_PREFIX + "/"):
            raise TestOnlyStorageError("OBJECT_OUTSIDE_PRE_SLOT_PREFIX")
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
        cutoff_at = datetime.fromisoformat(
            f"{report_date}T{report_slot}:00+09:00"
        ).astimezone(timezone.utc)
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise TestOnlyStorageError("SAVE_CLOCK_INVALID")
        if now.astimezone(timezone.utc) >= cutoff_at:
            raise TestOnlyStorageError("EVIDENCE_SAVE_AFTER_CUTOFF")
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


    def read_pre_slot_evidence(self, report_date: str, report_slot: str) -> dict[str, Any]:
        """Read live 08:00 ledger-linked Evidence without writing or scanning other slots."""
        report_id = f"{report_date}_{report_slot.replace(':', '-')}"
        _report_identity(report_id)
        if report_slot != "08:00":
            return {"state": "UNKNOWN", "error": "LIVE_EVIDENCE_SLOT_UNSUPPORTED"}
        ledger_prefix = f"{LIVE_PRE_SLOT_PREFIX}/ledger/{report_id}/"
        evidence_prefix = f"{LIVE_PRE_SLOT_PREFIX}/evidence/"
        try:
            ledgers = list(self.client.list_blobs(
                self.bucket_name, prefix=ledger_prefix, max_results=100
            ))
            if len(ledgers) >= 100:
                return {"state": "UNKNOWN", "error": "LEDGER_SCAN_LIMIT_REACHED"}
            attempts = []
            cutoff_at = datetime.fromisoformat(
                f"{report_date}T08:00:00+09:00"
            ).astimezone(timezone.utc)
            for item in ledgers:
                name = getattr(item, "name", "")
                attempt_id = name[len(ledger_prefix):] if name.startswith(ledger_prefix) else ""
                if not re.fullmatch(r"sched-[a-f0-9]{32}\.json", attempt_id):
                    return {"state": "INVALID", "error": "LEDGER_OBJECT_NAME_INVALID"}
                attempt_id = attempt_id[:-5]
                try:
                    generation = int(item.generation)
                    if generation <= 0:
                        raise ValueError("generation")
                    blob = self._pre_slot_blob(name, generation=generation)
                    blob.reload()
                    payload = blob.download_as_bytes(if_generation_match=generation)
                    ledger = json.loads(payload.decode("utf-8"))
                    if (
                        not isinstance(ledger, dict)
                        or ledger.get("schemaVersion") != "market-report-pre-slot-trigger/v1"
                        or ledger.get("executionMode") != "TEST_ONLY"
                        or ledger.get("reportDate") != report_date
                        or ledger.get("reportSlot") != report_slot
                        or ledger.get("attemptId") != attempt_id
                    ):
                        return {"state": "INVALID", "error": "LEDGER_IDENTITY_INVALID"}
                    triggered_at = _object_time(ledger.get("triggeredAt"))
                    scheduled_at = _object_time(ledger.get("scheduledAt"))
                    if triggered_at >= cutoff_at or scheduled_at >= cutoff_at:
                        return {"state": "INVALID", "error": "LEDGER_AFTER_CUTOFF"}
                    attempts.append((attempt_id, triggered_at))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError):
                    return {"state": "INVALID", "error": "LEDGER_VALIDATION_FAILED"}
            if not attempts:
                return {"state": "ABSENT", "object": ledger_prefix}
            found = []
            for attempt_id, triggered_at in attempts:
                attempt_prefix = f"{evidence_prefix}{attempt_id}/"
                objects = list(self.client.list_blobs(
                    self.bucket_name, prefix=attempt_prefix, max_results=10
                ))
                if len(objects) >= 10:
                    return {"state": "UNKNOWN", "error": "EVIDENCE_SCAN_LIMIT_REACHED"}
                for item in objects:
                    name = getattr(item, "name", "")
                    leaf = name[len(attempt_prefix):] if name.startswith(attempt_prefix) else ""
                    match = re.fullmatch(r"([a-f0-9]{64})\.json", leaf)
                    if not match:
                        return {"state": "INVALID", "error": "EVIDENCE_OBJECT_NAME_INVALID"}
                    generation = int(item.generation)
                    if generation <= 0:
                        return {"state": "INVALID", "error": "EVIDENCE_GENERATION_INVALID"}
                    blob = self._blob(name, generation=generation)
                    blob.reload()
                    stored_at = _object_time(blob.time_created)
                    payload = blob.download_as_bytes(if_generation_match=generation)
                    sha256 = hashlib.sha256(payload).hexdigest()
                    if sha256 != match.group(1):
                        return {"state": "INVALID", "error": "EVIDENCE_OBJECT_SHA256_MISMATCH"}
                    try:
                        checked = validate_stored_slot_evidence(payload, report_date, report_slot)
                    except Exception:
                        return {"state": "INVALID", "error": "EVIDENCE_SCHEMA_INVALID"}
                    if (
                        checked.get("reportId") != report_id
                        or checked.get("revision") != 1
                        or stored_at >= cutoff_at
                        or checked.get("evidenceStatus") != "READY_FOR_DRAFT"
                        or checked.get("acquisitionSource", {}).get("overallStatus") != "verified"
                    ):
                        return {"state": "INVALID", "error": "EVIDENCE_IDENTITY_OR_CUTOFF_INVALID"}
                    found.append({
                        "state": "VALID", "object": name, "generation": generation,
                        "stored_at": stored_at.isoformat(), "sha256": sha256,
                        "bytes": len(payload), "evidence": checked,
                        "attempt_id": attempt_id, "attempt_at": triggered_at.isoformat(),
                    })
            if not found:
                latest = max(attempts, key=lambda row: row[1])[1]
                return {
                    "state": "ABSENT", "object": evidence_prefix,
                    "latest_attempt_at": latest.isoformat(),
                }
            identities = {
                (row["sha256"], row["evidence"].get("evidenceId"))
                for row in found
            }
            if len(identities) != 1:
                return {"state": "INVALID", "error": "EVIDENCE_ATTEMPT_CONFLICT"}
            result = max(found, key=lambda row: row["stored_at"])
            result["latest_attempt_at"] = max(attempts, key=lambda row: row[1])[1].isoformat()
            return result
        except (TestOnlyStorageError, ValueError, TypeError, KeyError):
            return {"state": "UNKNOWN", "error": "LIVE_EVIDENCE_READ_FAILED"}
        except Exception:
            return {"state": "UNKNOWN", "error": "LIVE_EVIDENCE_READ_FAILED"}

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

