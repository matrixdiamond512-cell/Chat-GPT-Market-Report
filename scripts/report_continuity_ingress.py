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
    if (scheduled.tzinfo is None or scheduled.utcoffset() != timedelta(0)
            or scheduled.second or scheduled.microsecond):
        raise ValueError("INVALID_SCHEDULE_TIME")
    return scheduled.astimezone(timezone.utc)


def create_app(*, bindings: Mapping[str, SchedulerBinding], audience: str,
               processor: Callable[[ReportIdentity, bytes, SchedulerBinding], Mapping[str, object]],
               verifier: Callable[[str, str], Mapping[str, object]] = verify_google_oidc,
               clock: Callable[[], datetime] | None = None):
    """Return a WSGI app; no data provider or Storage client is constructed here."""
    if not audience or not bindings:
        raise ValueError("OIDC audience and Scheduler bindings are required")
    now = clock or (lambda: datetime.now(timezone.utc))

    def respond(start_response, status: str, result: Mapping[str, object]):
        payload = json.dumps(dict(result), separators=(",", ":")).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"),
                                ("Content-Length", str(len(payload))),
                                ("Cache-Control", "no-store")])
        return [payload]

    def app(environ, start_response):
        if environ.get("REQUEST_METHOD") != "POST":
            return respond(start_response, "405 Method Not Allowed", {"error": "METHOD_NOT_ALLOWED"})
        match = _BEARER.fullmatch(environ.get("HTTP_AUTHORIZATION", ""))
        if not match:
            return respond(start_response, "401 Unauthorized", {"error": "UNAUTHENTICATED"})
        job_name = environ.get("HTTP_X_CLOUDSCHEDULER_JOBNAME", "")
        binding = bindings.get(job_name)
        if binding is None:
            return respond(start_response, "403 Forbidden", {"error": "JOB_NOT_ALLOWLISTED"})
        try:
            claims = verifier(match.group(1), audience)
        except Exception:
            return respond(start_response, "401 Unauthorized", {"error": "UNAUTHENTICATED"})
        issuer = claims.get("iss")
        email = claims.get("email")
        if (issuer not in ("https://accounts.google.com", "accounts.google.com")
                or claims.get("aud") != audience
                or claims.get("email_verified") is not True
                or not isinstance(email, str)
                or email.lower() != binding.service_account_email.lower()):
            return respond(start_response, "403 Forbidden", {"error": "CALLER_NOT_AUTHORIZED"})

        try:
            scheduled = _utc_schedule(environ.get("HTTP_X_CLOUDSCHEDULER_SCHEDULETIME", ""))
            current = now()
            if current.tzinfo is None:
                raise ValueError("INVALID_CLOCK")
            identity = resolve_report_identity(
                schedule_time_utc=scheduled.isoformat().replace("+00:00", "Z"),
                attempt_minutes=binding.attempt_minutes,
                now=current,
            )
        except (ValueError, TypeError, OverflowError):
            return respond(start_response, "400 Bad Request", {"error": "SCHEDULE_NOT_ALLOWED"})
        if (identity.target.strftime("%H:%M") != binding.target_slot
                or (binding.weekdays_only and identity.target.weekday() >= 5)):
            return respond(start_response, "400 Bad Request", {"error": "SCHEDULE_NOT_ALLOWED"})
        if identity.status != "ACTIVE":
            return respond(start_response, "409 Conflict", {"error": "SCHEDULE_EXPIRED"})

        try:
            length_text = environ.get("CONTENT_LENGTH", "")
            if not length_text or not length_text.isdecimal():
                raise ValueError("INVALID_CONTENT_LENGTH")
            length = int(length_text)
            if length < 1:
                raise ValueError("EMPTY_BODY")
            if length > MAX_BODY_BYTES:
                return respond(start_response, "413 Payload Too Large", {"error": "PAYLOAD_TOO_LARGE"})
            if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("CONTENT_TYPE_REQUIRED")
            body = environ["wsgi.input"].read(length)
            if len(body) != length:
                raise ValueError("CONTENT_LENGTH_MISMATCH")
            # Scheduler's request body is immutable configuration, not report data.
            if body != SCHEDULER_TRIGGER_BODY:
                raise ValueError("UNEXPECTED_TRIGGER_BODY")
        except (KeyError, ValueError):
            return respond(start_response, "400 Bad Request", {"error": "INVALID_TRIGGER"})
        try:
            result = processor(identity, body, binding)
        except Exception:
            return respond(start_response, "500 Internal Server Error", {"error": "PROCESSING_FAILED"})
        return respond(start_response, "200 OK", result)

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
    return result
