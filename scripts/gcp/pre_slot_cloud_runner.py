"""Authenticated TEST_ONLY Cloud Run ingress for the existing 08:00 evidence path.

Only acquisition and private TEST_ONLY evidence are produced. No Docs, GitHub,
Drive, renderer, or publication API is called.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Mapping
from zoneinfo import ZoneInfo

from scripts.persist_report_slot_evidence import require_before_slot
from scripts.reporting.pre_slot_execution import execute_test_only_capture
from scripts.reporting.slot_recovery_contract import ContractError, sign_trigger_request

JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger("pre_slot_test_only")


def parse_schedule_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ContractError("SCHEDULER_TIME_MISSING")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("SCHEDULER_TIME_INVALID") from exc
    if parsed.tzinfo is None:
        raise ContractError("SCHEDULER_TIME_NAIVE")
    return parsed.astimezone(JST)


def build_internal_trigger(job_name: str, schedule_time: str, actual_start: datetime) -> dict:
    scheduled = parse_schedule_time(schedule_time)
    started = actual_start.astimezone(JST)
    if scheduled.strftime("%H:%M") not in {"07:47", "07:53", "07:57"}:
        raise ContractError("SCHEDULER_TIME_OUT_OF_SCOPE")
    if scheduled.weekday() > 4:
        raise ContractError("SCHEDULER_WEEKEND_NOT_SCHEDULED")
    if started.date() != scheduled.date():
        raise ContractError("SCHEDULER_START_DATE_MISMATCH")
    attempt = hashlib.sha256(f"{job_name}|{schedule_time}".encode("utf-8")).hexdigest()[:32]
    return {
        "schemaVersion": "market-report-pre-slot-trigger/v1",
        "attemptId": f"sched-{attempt}",
        "reportDate": scheduled.date().isoformat(),
        "reportSlot": "08:00",
        "scheduledAt": scheduled.isoformat(),
        "triggeredAt": started.isoformat(),
        "triggerSource": "external_direct_runner",
        "executionMode": "TEST_ONLY",
    }


class GCSAttemptLedger:
    """Create-only durable replay guard; an existing attempt always blocks."""
    def __init__(self, bucket, prefix: str):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")

    def claim(self, payload: Mapping) -> str:
        name = f"{self.prefix}/ledger/{payload['reportDate']}_08-00/{payload['attemptId']}.json"
        record = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(record, content_type="application/json", if_generation_match=0)
        except Exception as exc:
            if getattr(exc, "code", None) == 412 or exc.__class__.__name__ == "PreconditionFailed":
                raise ContractError("TEST_ATTEMPT_ALREADY_CLAIMED") from exc
            raise
        return name


class GCSPrivateEvidenceStore:
    """Private GCS create-only sink with generation-pinned exact-byte readback."""
    def __init__(self, bucket, prefix: str, attempt_id: str):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.attempt_id = attempt_id
        self.generations: dict[str, int] = {}

    def object_name(self, evidence_id: str) -> str:
        if len(evidence_id) != 64 or any(ch not in "0123456789abcdef" for ch in evidence_id):
            raise ContractError("EVIDENCE_ID_INVALID")
        return f"{self.prefix}/evidence/{self.attempt_id}/{evidence_id}.json"

    def put_if_absent(self, evidence_id: str, encoded: bytes) -> None:
        name = self.object_name(evidence_id)
        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(encoded, content_type="application/json", if_generation_match=0)
            blob.reload()
            if blob.generation is None:
                raise ContractError("GCS_GENERATION_MISSING")
            self.generations[evidence_id] = int(blob.generation)
        except Exception as exc:
            if getattr(exc, "code", None) == 412 or exc.__class__.__name__ == "PreconditionFailed":
                raise ContractError("EVIDENCE_IMMUTABLE_CONFLICT") from exc
            raise

    def read(self, evidence_id: str) -> bytes:
        generation = self.generations.get(evidence_id)
        if generation is None:
            raise ContractError("GCS_READBACK_GENERATION_MISSING")
        pinned = self.bucket.blob(self.object_name(evidence_id), generation=generation)
        return pinned.download_as_bytes(if_generation_match=generation)

    def delete_if_same_generation(self, evidence_id: str) -> bool:
        generation = self.generations.get(evidence_id)
        if generation is None:
            return False
        blob = self.bucket.blob(self._name(evidence_id), generation=generation)
        try:
            blob.delete(if_generation_match=generation)
            return True
        except Exception as exc:
            if getattr(exc, "code", None) == 404 or exc.__class__.__name__ == "NotFound":
                return True
            raise


def verify_scheduler_oidc(token: str, audience: str) -> str:
    if not token or not audience:
        raise ContractError("SCHEDULER_OIDC_MISSING")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(token, Request(), audience=audience)
    except Exception as exc:
        raise ContractError("SCHEDULER_OIDC_INVALID") from exc
    email = claims.get("email")
    if not isinstance(email, str) or claims.get("email_verified") is not True:
        raise ContractError("SCHEDULER_CALLER_EMAIL_UNVERIFIED")
    return email


def access_trigger_secret(secret_resource: str) -> bytes:
    if not secret_resource:
        raise ContractError("TRIGGER_SECRET_RESOURCE_MISSING")
    from google.cloud import secretmanager
    response = secretmanager.SecretManagerServiceClient().access_secret_version(
        request={"name": secret_resource}
    )
    value = bytes(response.payload.data)
    if len(value) < 32:
        raise ContractError("TRIGGER_SECRET_TOO_SHORT")
    return value


def run_existing_market_acquisition(trigger) -> bytes:
    """Run the existing full acquisition in a clean, disposable TEST_ONLY tree."""
    market_dir = ROOT / "data" / "market"
    shutil.rmtree(market_dir, ignore_errors=True)
    market_dir.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "logs" / "market_data_acquisition.jsonl"
    try:
        log_path.unlink()
    except FileNotFoundError:
        pass
    env = os.environ.copy()
    env.update({
        "MARKET_REPORT_SLOT": trigger.report_slot,
        "MARKET_REPORT_EXECUTION_MODE": "TEST_ONLY",
        "MARKET_REPORT_ID": f"{trigger.report_date}_08-00",
    })
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_market_data_acquisition.py"),
         "--slot", "08:00", "--mode", "full", "--print-summary"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    if completed.returncode != 0:
        LOG.error("market acquisition failed exit=%s", completed.returncode)
        raise ContractError(f"MARKET_ACQUISITION_EXIT_{completed.returncode}")
    source = market_dir / "latest.json"
    if not source.is_file():
        raise ContractError("MARKET_ACQUISITION_OUTPUT_MISSING")
    return source.read_bytes()


def _gcp_clients():
    from google.cloud import storage
    bucket_name = os.environ.get("TEST_ONLY_GCS_BUCKET", "")
    if not bucket_name:
        raise ContractError("TEST_ONLY_GCS_BUCKET_MISSING")
    client = storage.Client()
    return client.bucket(bucket_name)


def process_test_only_request(
    headers: Mapping[str, str],
    body: bytes,
    *,
    actual_start: datetime,
    allowed_callers: Mapping[str, str],
    audience: str,
    secret: bytes,
    verify_oidc: Callable[[str, str], str],
    claim_attempt: Callable[[Mapping], str],
    acquire: Callable,
    store_factory: Callable[[str], GCSPrivateEvidenceStore],
    clock: Callable[[], datetime],
) -> dict:
    """Authenticated Scheduler → existing contract/acquisition/freeze/readback."""
    if body not in (b"", b"{}"):
        raise ContractError("REQUEST_BODY_NOT_ALLOWED")
    auth = headers.get("X-Serverless-Authorization") or headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise ContractError("SCHEDULER_OIDC_MISSING")
    job_name = headers.get("X-CloudScheduler-JobName", "")
    scheduled = headers.get("X-CloudScheduler-ScheduleTime", "")
    expected_email = allowed_callers.get(job_name)
    if not expected_email:
        raise ContractError("SCHEDULER_JOB_NOT_ALLOWLISTED")
    caller_email = verify_oidc(auth[7:], audience)
    if caller_email.lower() != expected_email.lower():
        raise ContractError("SCHEDULER_CALLER_NOT_ALLOWLISTED")

    payload = build_internal_trigger(job_name, scheduled, actual_start)
    signature = sign_trigger_request(payload, secret)
    # The existing HMAC contract enforces real start lag, weekday, 08:00 cutoff,
    # replay freshness, and TEST_ONLY mode before acquisition begins.
    from scripts.reporting.slot_recovery_contract import verify_pre_slot_trigger
    trigger = verify_pre_slot_trigger(payload, signature, secret, now=actual_start)
    if trigger.execution_mode != "TEST_ONLY":
        raise ContractError("TEST_CAPTURE_REQUIRES_TEST_ONLY")
    require_before_slot(trigger.report_date, trigger.report_slot, now=actual_start)
    ledger_path = claim_attempt(payload)
    store = store_factory(trigger.attempt_id)
    with tempfile.TemporaryDirectory(prefix="pre-slot-test-only-") as tmp:
        result = execute_test_only_capture(
            payload=payload, signature=signature, secret=secret, acquisition=acquire,
            store=store, attempt_ledger=Path(tmp) / f"{trigger.attempt_id}.json",
            repository_root=ROOT, now=actual_start,
        )
    try:
        require_before_slot(trigger.report_date, trigger.report_slot, now=clock())
    except Exception:
        # A capture that crossed the slot cutoff is never a candidate. Remove
        # only the exact generation just created; the private 14-day lifecycle
        # remains the fallback cleanup if deletion cannot be confirmed.
        if not store.delete_if_same_generation(result["evidenceId"]):
            LOG.error("late TEST_ONLY evidence cleanup unconfirmed evidenceId=%s", result["evidenceId"])
        raise ContractError("TEST_CAPTURE_CROSSED_SLOT_CUTOFF")
    result.update({
        "status": "PASS_TEST_ONLY",
        "actualStartAt": actual_start.astimezone(JST).isoformat(),
        "scheduledAt": trigger.scheduled_at,
        "startLagSeconds": trigger.start_lag_seconds,
        "attemptLedgerObject": ledger_path,
        "evidenceObject": store.object_name(result["evidenceId"]) if hasattr(store, "object_name") else None,
        "evidenceGeneration": store.generations.get(result["evidenceId"]) if hasattr(store, "generations") else None,
        "evidenceBucket": os.environ.get("TEST_ONLY_GCS_BUCKET") or None,
        "evidenceSha256": result["readbackSha256"],
        "storage": "PRIVATE_GCS_CREATE_ONLY",
        "mainReadback": "NOT_RUN_TEST_ONLY_NO_MAIN_WRITE",
        "docsWrite": "NOT_RUN_TEST_ONLY_NO_DOCS_WRITE",
        "publication": "NOT_RUN_TEST_ONLY",
    })
    return result


def _response(start_response, status: str, payload: dict):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                            ("Content-Length", str(len(encoded))),
                            ("Cache-Control", "no-store")])
    return [encoded]


def application(environ, start_response):
    # First application action is the execution timestamp used for the
    # <=60-second gate. Scheduler's scheduled time is never substituted.
    actual_start = datetime.now(JST)
    started_monotonic = time.monotonic()
    if environ.get("REQUEST_METHOD") == "GET" and environ.get("PATH_INFO") == "/healthz":
        return _response(start_response, "200 OK", {"status": "READY_TEST_ONLY"})
    if environ.get("REQUEST_METHOD") != "POST" or environ.get("PATH_INFO") != "/capture":
        return _response(start_response, "404 Not Found", {"status": "NOT_FOUND"})
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
        if length < 0 or length > 1024:
            raise ContractError("REQUEST_BODY_SIZE_INVALID")
        body = environ["wsgi.input"].read(length) if length else b""
        headers = {
            "Authorization": environ.get("HTTP_AUTHORIZATION", ""),
            "X-Serverless-Authorization": environ.get("HTTP_X_SERVERLESS_AUTHORIZATION", ""),
            "X-CloudScheduler-JobName": environ.get("HTTP_X_CLOUDSCHEDULER_JOBNAME", ""),
            "X-CloudScheduler-ScheduleTime": environ.get("HTTP_X_CLOUDSCHEDULER_SCHEDULETIME", ""),
        }
        audience = os.environ["RUNNER_AUDIENCE"]
        allowed = json.loads(os.environ["ALLOWED_SCHEDULER_CALLERS_JSON"])
        if not isinstance(allowed, dict):
            raise ContractError("SCHEDULER_ALLOWLIST_INVALID")
        auth = headers.get("X-Serverless-Authorization") or headers.get("Authorization") or ""
        expected_email = allowed.get(headers.get("X-CloudScheduler-JobName", ""))
        if not expected_email:
            raise ContractError("SCHEDULER_JOB_NOT_ALLOWLISTED")
        if not auth.startswith("Bearer "):
            raise ContractError("SCHEDULER_OIDC_MISSING")
        verified_email = verify_scheduler_oidc(auth[7:], audience)
        if verified_email.lower() != expected_email.lower():
            raise ContractError("SCHEDULER_CALLER_NOT_ALLOWLISTED")
        secret = access_trigger_secret(os.environ.get("TRIGGER_SECRET_RESOURCE", ""))
        bucket = _gcp_clients()
        prefix = os.environ.get("TEST_ONLY_OBJECT_PREFIX", "test-only/08-00").strip("/")
        ledger = GCSAttemptLedger(bucket, prefix)
        def claim(payload):
            return ledger.claim(payload)
        def store_factory(attempt_id):
            return GCSPrivateEvidenceStore(bucket, prefix, attempt_id)
        result = process_test_only_request(
            headers, body, actual_start=actual_start, allowed_callers=allowed,
            audience=audience, secret=secret,
            verify_oidc=lambda token, aud: verified_email if token == auth[7:] and aud == audience else "",
            claim_attempt=claim, acquire=run_existing_market_acquisition,
            store_factory=store_factory, clock=lambda: datetime.now(JST),
        )
        LOG.info(json.dumps({"event": "test_only_capture", **result}, ensure_ascii=False, sort_keys=True))
        result["durationMs"] = int((time.monotonic() - started_monotonic) * 1000)
        return _response(start_response, "200 OK", result)
    except ContractError as exc:
        LOG.warning(json.dumps({"event": "test_only_blocked", "reason": str(exc),
                                "actualStartAt": actual_start.isoformat()}, sort_keys=True))
        return _response(start_response, "409 Conflict", {"status": "BLOCKED", "reason": str(exc),
                                                            "actualStartAt": actual_start.isoformat()})
    except Exception:
        LOG.exception("unexpected TEST_ONLY runner failure")
        return _response(start_response, "500 Internal Server Error", {"status": "ERROR",
                                                                        "reason": "INTERNAL_ERROR"})
