"""Fail-closed Cloud Scheduler contract and independent Evidence watchdog decisions.

The HTTP adapter must first verify the Cloud Scheduler OIDC token against the
expected service account. It then passes the authenticated principal and the
platform-supplied X-CloudScheduler-* headers here. JSON body fields never select
or override the report date, slot, or scheduled time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

JST = timezone(timedelta(hours=9), "Asia/Tokyo")
SLOTS = ("08:00", "12:00", "16:00", "21:00")
SCHEDULE_LEAD_MINUTES = 13
WARNING_MINUTES_BEFORE_SLOT = 3


class ScheduleRequestError(ValueError):
    """A scheduler request failed identity, time, or target validation."""


@dataclass(frozen=True)
class VerifiedSlotInvocation:
    report_date: str
    report_slot: str
    report_id: str
    scheduled_at: datetime
    started_at: datetime
    attempt_id: str

    @property
    def idempotency_key(self) -> str:
        # Cloud Scheduler keeps its original schedule-time header on retries.
        return self.attempt_id

    @property
    def cutoff_at(self) -> datetime:
        hour, minute = (int(part) for part in self.report_slot.split(":"))
        return datetime.combine(date.fromisoformat(self.report_date), time(hour, minute), JST)


def _parse_instant(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ScheduleRequestError(f"BLOCKED_SCHEDULE_REQUEST:{field}_MISSING")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleRequestError(f"BLOCKED_SCHEDULE_REQUEST:{field}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScheduleRequestError(f"BLOCKED_SCHEDULE_REQUEST:{field}_TIMEZONE_REQUIRED")
    return parsed.astimezone(JST)


def validate_scheduled_invocation(
    *,
    verified_principal: str | None,
    expected_principal: str,
    job_name: str | None,
    expected_job_name: str,
    report_slot: str,
    schedule_time: str | None,
    started_at: datetime,
) -> VerifiedSlotInvocation:
    """Validate explicit Cloud Scheduler headers for one current report slot.

    `verified_principal` must come from verified OIDC claims, never from a
    request body/header. The schedule-time header is the platform's original
    occurrence timestamp and remains stable through retries.
    """
    if not expected_principal or verified_principal != expected_principal:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_AUTH:principal_mismatch")
    if not expected_job_name or job_name != expected_job_name:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_AUTH:job_name_mismatch")
    if report_slot not in SLOTS:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:unsupported_slot")
    scheduled_at = _parse_instant(schedule_time, "schedule_time")
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_at_timezone_required")
    started = started_at.astimezone(JST)

    # Date comes from the authenticated platform occurrence, normalized to JST.
    report_date = scheduled_at.date().isoformat()
    day = scheduled_at.date()
    if day.weekday() >= 5:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:report_date_not_weekday")
    hour, minute = (int(part) for part in report_slot.split(":"))
    cutoff = datetime.combine(day, time(hour, minute), JST)
    if scheduled_at != cutoff - timedelta(minutes=SCHEDULE_LEAD_MINUTES):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:scheduled_at_not_allowed")
    if started < scheduled_at:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_before_schedule")
    if started >= cutoff:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")
    if started - scheduled_at > timedelta(minutes=15):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_DELAY_EXCEEDED")

    report_id = f"{report_date}_{report_slot.replace(':', '-')}"
    attempt_id = f"{expected_job_name}@{scheduled_at.astimezone(timezone.utc).isoformat()}"
    return VerifiedSlotInvocation(
        report_date=report_date,
        report_slot=report_slot,
        report_id=report_id,
        scheduled_at=scheduled_at,
        started_at=started,
        attempt_id=attempt_id,
    )


def assess_evidence_watchdog(
    report_date: str,
    report_slot: str,
    *,
    now: datetime,
    evidence_state: str,
    latest_attempt_at: datetime | None = None,
) -> dict[str, str]:
    """Create a deterministic warning decision; never sends a notification."""
    if report_slot not in SLOTS:
        raise ValueError("BLOCKED_WATCHDOG:unsupported_slot")
    day = date.fromisoformat(report_date)
    if day.isoformat() != report_date or day.weekday() >= 5:
        raise ValueError("BLOCKED_WATCHDOG:report_date_not_weekday")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("BLOCKED_WATCHDOG:naive_clock")
    hour, minute = (int(part) for part in report_slot.split(":"))
    cutoff = datetime.combine(day, time(hour, minute), JST)
    current = now.astimezone(JST)
    if evidence_state not in {"VALID", "ABSENT", "INVALID", "UNKNOWN"}:
        raise ValueError("BLOCKED_WATCHDOG:evidence_state_invalid")
    if latest_attempt_at is None:
        attempt = "none"
    elif latest_attempt_at.tzinfo is None or latest_attempt_at.utcoffset() is None:
        raise ValueError("BLOCKED_WATCHDOG:naive_attempt_clock")
    else:
        attempt = latest_attempt_at.astimezone(JST).isoformat()
    if evidence_state == "VALID":
        state = "EVIDENCE_READY"
    elif evidence_state == "UNKNOWN":
        state = "EVIDENCE_STATE_UNKNOWN"
    elif current >= cutoff:
        state = "BLOCKED_EVIDENCE_MISSING" if evidence_state == "ABSENT" else "BLOCKED_EVIDENCE_INVALID"
    elif current >= cutoff - timedelta(minutes=WARNING_MINUTES_BEFORE_SLOT):
        state = "WARNING_EVIDENCE_MISSING" if evidence_state == "ABSENT" else "WARNING_EVIDENCE_INVALID"
    else:
        state = "WAITING_FOR_EVIDENCE"
    return {
        "state": state,
        "reportId": f"{report_date}_{report_slot.replace(':', '-')}" ,
        "latestAttemptAt": attempt,
        "notification": "NOT_SENT",
    }

