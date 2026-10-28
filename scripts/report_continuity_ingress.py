"""Authenticated Cloud Scheduler ingress for isolated P1 shadow acquisition.

Cloud Run IAM must remain enabled. Google OIDC authenticates the caller, while
the exact job/time/slot binding validates the Scheduler metadata headers, which
the OIDC token does not cryptographically sign. The HTTP body is a fixed trigger;
report identity is always derived from the authenticated Scheduler time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
import sys
from zoneinfo import ZoneInfo
from typing import Callable, Mapping

from scripts.resolve_market_report_slot import REPORT_SLOTS, ReportIdentity, resolve_report_identity

MAX_BODY_BYTES = 1024 * 1024
SCHEDULER_TRIGGER_BODY = b'{"schemaVersion":1,"trigger":"P1_SHADOW"}'
_BEARER = re.compile(r"Bearer ([A-Za-z0-9._~-]+)\Z")
SCHEDULER_ATTEMPTS = (3, 7, 13)


@dataclass(frozen=True)
class SchedulerBinding:
    job_name: str
    service_account_email: str
    attempt_minutes: int
    target_slot: str
    weekdays_only: bool = True


def verify_google_oidc(token: str, audience: str) -> Mapping[str, object]:
    """Verify Google signature, issuer, expiry and audience using google-auth."""
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, Request(), audience=audience)


def _utc_schedule(value: str) -> datetime:
    try:
        scheduled = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_SCHEDULE_TIME") from exc
    if scheduled.tzinfo is None or scheduled.second:
        raise ValueError("INVALID_SCHEDULE_TIME")
    # RFC3339 allows a nonzero UTC offset. Normalize to UTC *after* parsing;
    # retain the strict cron-minute check and discard only fractional seconds.
    return scheduled.astimezone(timezone.utc).replace(microsecond=0)


def create_app(*, bindings: Mapping[str, SchedulerBinding], audience: str,
               processor: Callable[[ReportIdentity, bytes, SchedulerBinding], Mapping[str, object]],
               verifier: Callable[[str, str], Mapping[str, object]] = verify_google_oidc,
               clock: Callable[[], datetime] | None = None):
    """Return a WSGI app; no data provider or Storage client is constructed here."""
    if not audience or not bindings:
        raise ValueError("OIDC audience and Scheduler bindings are required")
    # Cloud Scheduler sends a short job ID in X-CloudScheduler-JobName
    # (e.g. slot-0800-t13), while reviewed config uses full resource names.
    # A unique short ID must select exactly one full, account-bound binding.
    short_bindings = {full_name.rsplit("/", 1)[-1]: binding
                      for full_name, binding in bindings.items()}
    if len(short_bindings) != len(bindings):
        raise ValueError("SCHEDULER_SHORT_JOB_IDS_MUST_BE_UNIQUE")
    now = clock or (lambda: datetime.now(timezone.utc))
    def respond(start_response, status: str, result: Mapping[str, object],
                audit_context: dict[str, object]):
        # Cloud Run platform/IAM rejection happens before this WSGI function.
        # Fixed, non-sensitive reason codes prove the request reached the app;
        # never log headers, JWTs, claims, principal emails or request bodies.
        code = int(status.split(" ", 1)[0])
        allowed_reasons = {
            "METHOD_NOT_ALLOWED", "UNAUTHENTICATED", "JOB_NOT_ALLOWLISTED",
            "CALLER_NOT_AUTHORIZED", "SCHEDULE_NOT_ALLOWED", "SCHEDULE_EXPIRED",
            "PAYLOAD_TOO_LARGE", "INVALID_TRIGGER", "PROCESSING_FAILED",
        }
        reason = "ACCEPTED" if code < 400 else result.get("error")
        if reason not in allowed_reasons and reason != "ACCEPTED":
            reason = "OTHER_REJECTION"
        print(json.dumps({
            "event": "P1_INGRESS_RESULT",
            "severity": "WARNING" if code >= 400 else "INFO",
            "httpStatus": code,
            "reason": reason,
            **audit_context,
        }, separators=(",", ":"), sort_keys=True), file=sys.stderr, flush=True)
        payload = json.dumps(dict(result), separators=(",", ":")).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"),
                                ("Content-Length", str(len(payload))),
                                ("Cache-Control", "no-store")])
        return [payload]

    def app(environ, start_response):
        # Request-local state prevents concurrent/serial WSGI requests from
        # inheriting any prior authentication or schedule result.
        audit_context: dict[str, object] = {
            "oidcResult": "INCOMPLETE",
            "jobNameResult": "INCOMPLETE",
            "scheduleTimeResult": "INCOMPLETE",
        }
        if environ.get("REQUEST_METHOD") != "POST":
            return respond(start_response, "405 Method Not Allowed", {"error": "METHOD_NOT_ALLOWED"}, audit_context)
        job_name = environ.get("HTTP_X_CLOUDSCHEDULER_JOBNAME", "")
        binding = bindings.get(job_name)
        if binding is None and "/" not in job_name:
            binding = short_bindings.get(job_name)
        # Log only an allowlisted short job id; never copy untrusted header text.
        audit_context["jobId"] = (
            binding.job_name.rsplit("/", 1)[-1] if binding else "UNLISTED"
        )

        match = _BEARER.fullmatch(environ.get("HTTP_AUTHORIZATION", ""))
        if not match:
            audit_context["oidcResult"] = "FAIL"
            return respond(start_response, "401 Unauthorized", {"error": "UNAUTHENTICATED"}, audit_context)
        try:
            claims = verifier(match.group(1), audience)
        except Exception:
            audit_context["oidcResult"] = "FAIL"
            return respond(start_response, "401 Unauthorized", {"error": "UNAUTHENTICATED"}, audit_context)
        issuer = claims.get("iss")
        email = claims.get("email")
        allowed_callers = {item.service_account_email.lower() for item in bindings.values()}
        if (issuer not in ("https://accounts.google.com", "accounts.google.com")
                or claims.get("aud") != audience
                or claims.get("email_verified") is not True
                or not isinstance(email, str)
                or email.lower() not in allowed_callers):
            audit_context["oidcResult"] = "FAIL"
            return respond(start_response, "403 Forbidden", {"error": "CALLER_NOT_AUTHORIZED"}, audit_context)
        audit_context["oidcResult"] = "PASS"

        if binding is None:
            # Never log the untrusted job header value or treat a short name as
            # trusted unless it selected exactly one configured binding.
            if not job_name:
                job_form = "MISSING"
            elif any(job_name == allowed.rsplit("/", 1)[-1] for allowed in bindings):
                job_form = "SHORT_EXPECTED_ID"
            elif re.fullmatch(r"projects/[^/]+/locations/[^/]+/jobs/[^/]+", job_name):
                job_form = "OTHER_FULL_RESOURCE"
            elif "/" not in job_name:
                job_form = "OTHER_SHORT"
            else:
                job_form = "OTHER_FORMAT"
            print(json.dumps({
                "event": "P1_JOB_HEADER_DIAGNOSTIC",
                "severity": "WARNING",
                "jobHeaderForm": job_form,
                "schedulerMarkerPresent": bool(environ.get("HTTP_X_CLOUDSCHEDULER")),
                "scheduleHeaderPresent": bool(environ.get("HTTP_X_CLOUDSCHEDULER_SCHEDULETIME")),
                "alternateJobHeaderPresent": bool(
                    environ.get("HTTP_X_CLOUDSCHEDULER_JOB_NAME")
                    or environ.get("HTTP_X_CLOUD_SCHEDULER_JOB_NAME")
                ),
            }, separators=(",", ":"), sort_keys=True), file=sys.stderr, flush=True)
            audit_context["jobNameResult"] = "FAIL"
            return respond(start_response, "403 Forbidden", {"error": "JOB_NOT_ALLOWLISTED"}, audit_context)
        if email.lower() != binding.service_account_email.lower():
            audit_context["jobNameResult"] = "FAIL"
            return respond(start_response, "403 Forbidden", {"error": "CALLER_NOT_AUTHORIZED"}, audit_context)
        audit_context["jobNameResult"] = "PASS"

        raw_schedule = environ.get("HTTP_X_CLOUDSCHEDULER_SCHEDULETIME", "")
        try:
            scheduled = _utc_schedule(raw_schedule)
            current = now()
            if current.tzinfo is None:
                raise ValueError("INVALID_CLOCK")
            identity = resolve_report_identity(
                schedule_time_utc=scheduled.isoformat().replace("+00:00", "Z"),
                attempt_minutes=binding.attempt_minutes,
                now=current,
            )
        except (ValueError, TypeError, OverflowError) as exc:
            # Enumerated diagnostics distinguish missing/malformed headers from
            # slot/clock failures without emitting raw headers, tokens or claims.
            safe_codes = {
                "INVALID_SCHEDULE_TIME", "INVALID_CLOCK", "INVALID_SLOT",
                "INVALID_UTC_SCHEDULE", "INVALID_PUBLICATION_SLOT",
                "FUTURE_SCHEDULE", "AMBIGUOUS_IDENTITY",
            }
            code = str(exc)
            audit_context["scheduleHeaderPresent"] = bool(raw_schedule)
            audit_context["scheduleRejectCode"] = (
                "MISSING_SCHEDULE_HEADER" if not raw_schedule else
                code if code in safe_codes else "UNCLASSIFIED_SCHEDULE_ERROR"
            )
            audit_context["scheduleTimeResult"] = "FAIL"
            return respond(start_response, "400 Bad Request", {"error": "SCHEDULE_NOT_ALLOWED"}, audit_context)
        scheduled_jst = scheduled.astimezone(ZoneInfo("Asia/Tokyo"))
        schedule_context = {
            "schedulerDateJst": scheduled_jst.strftime("%Y-%m-%d"),
            "schedulerTimeJst": scheduled_jst.strftime("%H:%M"),
            "reportId": identity.report_id,
        }
        audit_context.update(schedule_context)
        if (identity.target.strftime("%H:%M") != binding.target_slot
                or (binding.weekdays_only and identity.target.weekday() >= 5)):
            audit_context["scheduleTimeResult"] = "FAIL"
            return respond(start_response, "400 Bad Request", {"error": "SCHEDULE_NOT_ALLOWED"}, audit_context)
        if identity.status != "ACTIVE":
            audit_context["scheduleTimeResult"] = "FAIL"
            return respond(start_response, "409 Conflict", {"error": "SCHEDULE_EXPIRED"}, audit_context)
        audit_context["scheduleTimeResult"] = "PASS"

        try:
            length_text = environ.get("CONTENT_LENGTH", "")
            if not length_text or not length_text.isdecimal():
                raise ValueError("INVALID_CONTENT_LENGTH")
            length = int(length_text)
            if length < 1:
                raise ValueError("EMPTY_BODY")
            if length > MAX_BODY_BYTES:
                return respond(start_response, "413 Payload Too Large", {"error": "PAYLOAD_TOO_LARGE"}, audit_context)
            if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("CONTENT_TYPE_REQUIRED")
            body = environ["wsgi.input"].read(length)
            if len(body) != length:
                raise ValueError("CONTENT_LENGTH_MISMATCH")
            # Scheduler's request body is immutable configuration, not report data.
            if body != SCHEDULER_TRIGGER_BODY:
                raise ValueError("UNEXPECTED_TRIGGER_BODY")
        except (KeyError, ValueError):
            return respond(start_response, "400 Bad Request", {"error": "INVALID_TRIGGER"}, audit_context)
        try:
            result = processor(identity, body, binding)
        except Exception:
            return respond(start_response, "500 Internal Server Error", {"error": "PROCESSING_FAILED"}, audit_context)
        return respond(start_response, "200 OK", result, audit_context)

    return app


def single_binding_map(entries: list[dict[str, object]]) -> dict[str, SchedulerBinding]:
    """Validate env-derived, deployment-reviewed allowlist data."""
    if not isinstance(entries, list):
        raise ValueError("INVALID_SCHEDULER_BINDINGS")
    result = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("INVALID_SCHEDULER_BINDING")
        job = item.get("job_name")
        email = item.get("service_account_email")
        offset = item.get("attempt_minutes")
        slot = item.get("target_slot")
        weekdays_only = item.get("weekdays_only", True)
        if (not isinstance(job, str)
                or not re.fullmatch(r"projects/[^/]+/locations/[^/]+/jobs/[^/]+", job)
                or not isinstance(email, str) or not email.endswith(".iam.gserviceaccount.com")
                or type(offset) is not int or offset not in SCHEDULER_ATTEMPTS
                or not isinstance(slot, str) or slot not in REPORT_SLOTS
                or type(weekdays_only) is not bool
                or job in result):
            raise ValueError("INVALID_SCHEDULER_BINDING")
        result[job] = SchedulerBinding(job, email, offset, slot, weekdays_only)
    if len({binding.service_account_email.lower() for binding in result.values()}) != len(result):
        raise ValueError("SCHEDULER_SERVICE_ACCOUNTS_MUST_BE_UNIQUE")
    if len({job.rsplit("/", 1)[-1] for job in result}) != len(result):
        raise ValueError("SCHEDULER_SHORT_JOB_IDS_MUST_BE_UNIQUE")
    return result
