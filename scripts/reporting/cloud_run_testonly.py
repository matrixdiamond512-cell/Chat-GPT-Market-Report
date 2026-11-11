"""TEST ONLY Cloud Run HTTP adapters for authenticated Evidence and watchdog flows.

Cloud Run IAM rejects unauthenticated callers. This handler independently verifies
the Google-signed OIDC ID token before trusting its email claim, and separately
checks the unauthenticated Cloud Scheduler job/time headers against fixed config.
Request-body dates, job names, and identities are never used.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
import logging
import os
import re
from typing import Any, Callable

from scripts.persist_report_slot_evidence import build_slot_evidence
from scripts.reporting.scheduler_reliability import (
    JST,
    ScheduleRequestError,
    assess_evidence_watchdog,
    validate_scheduled_invocation,
)
from scripts.reporting.test_only_evidence_store import (
    TEST_ONLY_BUCKET,
    TEST_ONLY_PREFIX,
    TestOnlyEvidenceStore,
    TestOnlyStorageError,
)

try:
    import functions_framework
except ImportError:  # E2 fixture tests do not need the serving framework.
    functions_framework = None


MAX_BODY_BYTES = 1024 * 1024
WATCHDOG_LEAD_MINUTES = 3
LOGGER = logging.getLogger("market_report_test_only")


class RuntimeConfigurationError(ValueError):
    pass


def _request_header(headers, name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        return None
    return str(value).strip() or None


def _bearer_token(headers) -> str:
    value = _request_header(headers, "Authorization")
    if not value:
        raise PermissionError("OIDC_TOKEN_MISSING")
    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise PermissionError("OIDC_BEARER_TOKEN_INVALID")
    return token.strip()


def verify_scheduler_oidc(
    headers,
    *,
    audience: str,
    expected_principal: str,
    verifier: Callable[[str, str], dict] | None = None,
) -> str:
    """Return only a cryptographically verified Scheduler service-account email."""
    if not audience or not expected_principal:
        raise RuntimeConfigurationError("OIDC_EXPECTED_CLAIMS_NOT_CONFIGURED")
    token = _bearer_token(headers)
    if verifier is None:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(token, Request(), audience=audience)
    else:
        claims = verifier(token, audience)
    if not isinstance(claims, dict):
        raise PermissionError("OIDC_CLAIMS_INVALID")
    email = claims.get("email")
    verified = claims.get("email_verified")
    if email != expected_principal or verified not in (True, "true"):
        raise PermissionError("OIDC_PRINCIPAL_MISMATCH")
    token_audience = claims.get("aud")
    if token_audience != audience and token_audience != [audience]:
        raise PermissionError("OIDC_AUDIENCE_MISMATCH")
    return email


def validate_watchdog_invocation(
    *,
    verified_principal: str,
    expected_principal: str,
    job_name: str | None,
    expected_job_resource: str,
    report_slot: str,
    schedule_time: str | None,
    started_at: datetime,
):
    """Validate a dedicated watchdog job scheduled exactly three minutes pre-slot."""
    if verified_principal != expected_principal or not expected_principal:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_AUTH:principal_mismatch")
    expected_job_id = expected_job_resource.rsplit("/", 1)[-1] if expected_job_resource else ""
    parts = expected_job_resource.split("/") if expected_job_resource else []
    if (
        len(parts) != 6
        or parts[0] != "projects"
        or parts[2] != "locations"
        or parts[4] != "jobs"
        or job_name != expected_job_id
    ):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_AUTH:job_name_mismatch")
    if report_slot not in {"08:00", "12:00", "16:00", "21:00"}:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:unsupported_slot")
    if not isinstance(schedule_time, str) or not schedule_time.strip():
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:schedule_time_MISSING")
    try:
        scheduled_at = datetime.fromisoformat(schedule_time.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:schedule_time_INVALID") from exc
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:schedule_time_TIMEZONE_REQUIRED")
    scheduled_at = scheduled_at.astimezone(JST)
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_at_TIMEZONE_REQUIRED")
    current = started_at.astimezone(JST)
    if current < scheduled_at:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_before_schedule")
    day = scheduled_at.date()
    if day.weekday() >= 5:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:report_date_not_weekday")
    hour, minute = (int(part) for part in report_slot.split(":"))
    cutoff = datetime.combine(day, time(hour, minute), JST)
    if scheduled_at != cutoff - timedelta(minutes=WATCHDOG_LEAD_MINUTES):
        raise ScheduleRequestError("BLOCKED_WATCHDOG_SCHEDULE_TIME_MISMATCH")
    if current >= cutoff:
        raise ScheduleRequestError("BLOCKED_WATCHDOG_AFTER_CUTOFF")
    return day.isoformat(), report_slot, f"{day.isoformat()}_{report_slot.replace(':', '-')}", scheduled_at


def _config_from_env() -> dict[str, str]:
    required = (
        "TEST_ONLY_ENVIRONMENT",
        "SERVICE_MODE",
        "OIDC_AUDIENCE",
        "EXPECTED_PRINCIPAL",
        "EXPECTED_JOB_RESOURCE",
        "EXPECTED_REPORT_SLOT",
    )
    config = {name.lower(): os.environ.get(name, "").strip() for name in required}
    missing = [name for name in required if not config[name.lower()]]
    if missing:
        raise RuntimeConfigurationError("RUNTIME_CONFIG_MISSING:" + ",".join(missing))
    if config["test_only_environment"] != "TEST_ONLY":
        raise RuntimeConfigurationError("TEST_ONLY_ENVIRONMENT_REQUIRED")
    if config["service_mode"] not in {"producer", "watchdog"}:
        raise RuntimeConfigurationError("SERVICE_MODE_INVALID")
    if config["expected_report_slot"] not in {"08:00", "12:00", "16:00", "21:00"}:
        raise RuntimeConfigurationError("EXPECTED_REPORT_SLOT_INVALID")
    if os.environ.get("TEST_ONLY_BUCKET") != TEST_ONLY_BUCKET:
        raise RuntimeConfigurationError("TEST_ONLY_BUCKET_REQUIRED")
    if os.environ.get("TEST_ONLY_PREFIX", TEST_ONLY_PREFIX) != TEST_ONLY_PREFIX:
        raise RuntimeConfigurationError("TEST_ONLY_PREFIX_REQUIRED")
    config["test_only_bucket"] = TEST_ONLY_BUCKET
    config["test_only_prefix"] = TEST_ONLY_PREFIX
    config["producer_job_resource"] = os.environ.get(
        "EVIDENCE_JOB_RESOURCE", config["expected_job_resource"]
    ).strip()
    config["producer_service_name"] = os.environ.get("EVIDENCE_SERVICE_NAME", "").strip()
    if config["service_mode"] == "watchdog" and not config["producer_service_name"]:
        raise RuntimeConfigurationError("EVIDENCE_SERVICE_NAME_REQUIRED")
    return config


def _safe_request_id(headers) -> str | None:
    value = _request_header(headers, "X-Cloud-Trace-Context")
    if not value:
        return None
    return re.sub(r"[^A-Za-z0-9./=_-]", "", value)[:128]


def _json_response(body: dict, status: int):
    return json.dumps(body, ensure_ascii=True, sort_keys=True), status, {"Content-Type": "application/json"}


def _emit(event: str, **fields) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, ensure_ascii=True, sort_keys=True))


def _validate_http_request(request):
    if request.method != "POST":
        return _json_response({"state": "BLOCKED", "code": "POST_REQUIRED"}, 405)
    if len(request.get_data(cache=True, as_text=False)) > MAX_BODY_BYTES:
        return _json_response({"state": "BLOCKED", "code": "REQUEST_TOO_LARGE"}, 413)
    return None


def _new_clients(config):
    from google.cloud import logging_v2, storage

    return (
        TestOnlyEvidenceStore(
            storage.Client(),
            bucket_name=config["test_only_bucket"],
            prefix=config["test_only_prefix"],
        ),
        logging_v2.Client(),
    )


def _latest_attempt(logging_client, *, service_name: str, report_id: str):
    safe_service = service_name.replace('"', "")
    safe_report = report_id.replace('"', "")
    filter_text = (
        'resource.type="cloud_run_revision" '
        f'resource.labels.service_name="{safe_service}" '
        'jsonPayload.event="evidence_attempt" '
        f'jsonPayload.report_id="{safe_report}"'
    )
    entries = logging_client.list_entries(
        filter_=filter_text,
        order_by="timestamp desc",
        page_size=1,
    )
    entry = next(iter(entries), None)
    if entry is None:
        return None
    payload = entry.payload
    raw = payload.get("started_at") if isinstance(payload, dict) else None
    if not isinstance(raw, str):
        raise TestOnlyStorageError("LATEST_ATTEMPT_LOG_INVALID")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TestOnlyStorageError("LATEST_ATTEMPT_LOG_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TestOnlyStorageError("LATEST_ATTEMPT_LOG_INVALID")
    return parsed


def _producer(request, config, *, verifier=None, store=None, started_at=None):
    started = started_at or datetime.now(timezone.utc)
    principal = verify_scheduler_oidc(
        request.headers,
        audience=config["oidc_audience"],
        expected_principal=config["expected_principal"],
        verifier=verifier,
    )
    job_name = _request_header(request.headers, "X-CloudScheduler-JobName")
    schedule_time = _request_header(request.headers, "X-CloudScheduler-ScheduleTime")
    invocation = validate_scheduled_invocation(
        verified_principal=principal,
        expected_principal=config["expected_principal"],
        job_name=job_name,
        expected_job_name=config["expected_job_resource"],
        report_slot=config["expected_report_slot"],
        schedule_time=schedule_time,
        started_at=started,
    )
    # Record the authenticated, schedule-bound attempt before any GCS access.
    # The independent watchdog can then distinguish "no invocation" from a
    # producer that started and failed while reading/building/saving Evidence.
    _emit(
        "evidence_attempt",
        outcome="STARTED",
        request_id=_safe_request_id(request.headers),
        report_id=invocation.report_id,
        report_slot=invocation.report_slot,
        scheduled_at=invocation.scheduled_at.astimezone(timezone.utc).isoformat(),
        started_at=started.astimezone(timezone.utc).isoformat(),
        attempt_id=invocation.attempt_id,
    )
    if store is None:
        store, _ = _new_clients(config)
    source = store.read_input(invocation.report_id)
    evidence = build_slot_evidence(
        invocation.report_date,
        invocation.report_slot,
        source["payload"],
        source["bytes"],
        max_age_minutes=15,
        evidence_created_at=started,
        acquisition_path=(
            f"gs://{config['test_only_bucket']}/{source['object']}#{source['generation']}"
        ),
    )
    from scripts.persist_report_slot_evidence import require_evidence_slot_guard

    before_save = datetime.now(timezone.utc)
    require_evidence_slot_guard(invocation.report_date, invocation.report_slot, now=before_save)
    result = store.create_evidence(invocation.report_date, invocation.report_slot, evidence)
    _emit(
        "evidence_attempt",
        outcome="EVIDENCE_READY",
        request_id=_safe_request_id(request.headers),
        report_id=invocation.report_id,
        report_slot=invocation.report_slot,
        scheduled_at=invocation.scheduled_at.astimezone(timezone.utc).isoformat(),
        started_at=started.astimezone(timezone.utc).isoformat(),
        attempt_id=invocation.attempt_id,
        input_object=source["object"],
        input_generation=source["generation"],
        input_sha256=source["sha256"],
        evidence_object=result["object"],
        evidence_generation=result["generation"],
        evidence_sha256=result["sha256"],
    )
    return {
        "state": "EVIDENCE_READY",
        "environment": "TEST_ONLY",
        "reportId": invocation.report_id,
        "reportSlot": invocation.report_slot,
        "scheduledAt": invocation.scheduled_at.isoformat(),
        "startedAt": started.astimezone(JST).isoformat(),
        "attemptId": invocation.attempt_id,
        "inputGeneration": source["generation"],
        "inputSha256": source["sha256"],
        **result,
    }


def _watchdog(request, config, *, verifier=None, store=None, logging_client=None, now=None):
    current = now or datetime.now(timezone.utc)
    principal = verify_scheduler_oidc(
        request.headers,
        audience=config["oidc_audience"],
        expected_principal=config["expected_principal"],
        verifier=verifier,
    )
    report_date, report_slot, report_id, scheduled_at = validate_watchdog_invocation(
        verified_principal=principal,
        expected_principal=config["expected_principal"],
        job_name=_request_header(request.headers, "X-CloudScheduler-JobName"),
        expected_job_resource=config["expected_job_resource"],
        report_slot=config["expected_report_slot"],
        schedule_time=_request_header(request.headers, "X-CloudScheduler-ScheduleTime"),
        started_at=current,
    )
    if store is None or logging_client is None:
        default_store, default_logging = _new_clients(config)
        store = store or default_store
        logging_client = logging_client or default_logging
    snapshot = store.read_evidence(report_date, report_slot)
    try:
        latest_attempt = _latest_attempt(
            logging_client,
            service_name=config["producer_service_name"],
            report_id=report_id,
        )
    except Exception:
        snapshot = {"state": "UNKNOWN", "object": snapshot.get("object"), "error": "ATTEMPT_AUDIT_READ_FAILED"}
        latest_attempt = None
    decision = assess_evidence_watchdog(
        report_date,
        report_slot,
        now=current,
        evidence_state=snapshot["state"],
        latest_attempt_at=latest_attempt,
    )
    response = {
        **decision,
        "environment": "TEST_ONLY",
        "scheduledAt": scheduled_at.isoformat(),
        "evidenceObject": snapshot.get("object"),
        "evidenceGeneration": snapshot.get("generation"),
        "evidenceSha256": snapshot.get("sha256"),
        "evidenceStoredAt": snapshot.get("stored_at"),
        "evidenceBytes": snapshot.get("bytes"),
        "auditReadStatus": "PASS" if latest_attempt is not None else "NO_ATTEMPT_FOUND",
        "notification": "NOT_SENT",
    }
    _emit(
        "evidence_watchdog",
        report_id=report_id,
        report_slot=report_slot,
        state=decision["state"],
        latest_attempt_at=decision["latestAttemptAt"],
        evidence_state=snapshot["state"],
        evidence_generation=snapshot.get("generation"),
        evidence_sha256=snapshot.get("sha256"),
        notification="NOT_SENT",
        request_id=_safe_request_id(request.headers),
    )
    return response


def dispatch_request(request, config, *, verifier=None, store=None, logging_client=None, clock=None):
    blocked = _validate_http_request(request)
    if blocked is not None:
        return blocked
    try:
        if config["service_mode"] == "producer":
            body = _producer(
                request,
                config,
                verifier=verifier,
                store=store,
                started_at=clock() if clock else None,
            )
        else:
            body = _watchdog(
                request,
                config,
                verifier=verifier,
                store=store,
                logging_client=logging_client,
                now=clock() if clock else None,
            )
        return _json_response(body, 200)
    except PermissionError as exc:
        _emit("evidence_request_rejected", code=str(exc), request_id=_safe_request_id(request.headers))
        return _json_response({"state": "BLOCKED", "code": str(exc)}, 401)
    except ScheduleRequestError as exc:
        code = str(exc)
        status = 403 if "AUTH:" in code else 400
        _emit("evidence_request_rejected", code=code, request_id=_safe_request_id(request.headers))
        return _json_response({"state": "BLOCKED", "code": code}, status)
    except (RuntimeConfigurationError, TestOnlyStorageError, ValueError, KeyError, TypeError) as exc:
        code = str(exc)
        _emit("evidence_request_blocked", code=code, request_id=_safe_request_id(request.headers))
        return _json_response({"state": "BLOCKED", "code": code}, 409 if "CONFLICT" in code else 422)
    except Exception as exc:
        _emit(
            "evidence_request_failed",
            error_type=type(exc).__name__,
            request_id=_safe_request_id(request.headers),
        )
        return _json_response({"state": "UNKNOWN", "code": "INTERNAL_TEST_ONLY_ERROR"}, 503)


def cloud_run_http(request):
    """Functions Framework entry point. Cloud Run IAM must remain required."""
    invalid = _validate_http_request(request)
    if invalid is not None:
        return invalid
    try:
        config = _config_from_env()
        return dispatch_request(request, config)
    except RuntimeConfigurationError as exc:
        _emit("test_only_runtime_configuration_blocked", code=str(exc))
        return _json_response({"state": "BLOCKED", "code": str(exc)}, 503)


if functions_framework is not None:
    cloud_run_http = functions_framework.http(cloud_run_http)
