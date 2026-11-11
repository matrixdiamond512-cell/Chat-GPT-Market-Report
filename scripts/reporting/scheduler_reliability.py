"""Fail-closed scheduling contract and independent Evidence watchdog decisions.

This module is pure policy logic. A production adapter must authenticate the
scheduler's OIDC identity before passing verified_principal and must obtain
started_at from its trusted runtime clock. Request JSON alone is not trusted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping

JST = timezone(timedelta(hours=9), "Asia/Tokyo")
SLOTS = ("08:00", "12:00", "16:00", "21:00")
ATTEMPT_MINUTES_BEFORE_SLOT = (13, 7, 3)
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
        # Every retry/duplicate for this slot converges on one immutable claim.
        return self.report_id

    @property
    def cutoff_at(self) -> datetime:
        day = date.fromisoformat(self.report_date)
        hour, minute = (int(part) for part in self.report_slot.split(":"))
        return datetime.combine(day, time(hour, minute), JST)


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
    payload: Mapping[str, object],
    *,
    verified_principal: str | None,
    expected_principal: str,
    started_at: datetime,
) -> VerifiedSlotInvocation:
    """Validate an authenticated, explicit schedule request for one current slot.

    The host must verify an OIDC token before invoking this function. It must
    pass the verified service-account subject separately from the JSON payload.
    """
    if not expected_principal or verified_principal != expected_principal:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_AUTH:principal_mismatch")
    if not isinstance(payload, Mapping):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:payload_invalid")

    report_date = payload.get("reportDate")
    report_slot = payload.get("reportSlot")
    report_id = payload.get("reportId")
    attempt_id = payload.get("attemptId")
    if not all(isinstance(v, str) and v.strip() for v in (report_date, report_slot, report_id, attempt_id)):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:identity_fields_missing")
    if report_slot not in SLOTS:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:unsupported_slot")
    try:
        day = date.fromisoformat(report_date)
    except ValueError as exc:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:report_date_invalid") from exc
    if day.isoformat() != report_date or day.weekday() >= 5:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:report_date_not_weekday")
    expected_id = f"{report_date}_{report_slot.replace(':', '-')}"
    if report_id != expected_id:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:report_id_mismatch")
    if len(attempt_id) > 128 or attempt_id != attempt_id.strip():
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:attempt_id_invalid")

    scheduled_at = _parse_instant(payload.get("scheduledAt"), "scheduled_at")
    target_hour, target_minute = (int(part) for part in report_slot.split(":"))
    cutoff = datetime.combine(day, time(target_hour, target_minute), JST)
    allowed_times = {cutoff - timedelta(minutes=n) for n in ATTEMPT_MINUTES_BEFORE_SLOT}
    if scheduled_at not in allowed_times:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:scheduled_at_not_allowed")
    if scheduled_at.date() != day:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:scheduled_date_mismatch")
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_at_timezone_required")
    started = started_at.astimezone(JST)
    if started < scheduled_at:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_REQUEST:started_before_schedule")
    if started >= cutoff:
        raise ScheduleRequestError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")
    if started - scheduled_at > timedelta(minutes=15):
        raise ScheduleRequestError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_DELAY_EXCEEDED")

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
    target_hour, target_minute = (int(part) for part in report_slot.split(":"))
    cutoff = datetime.combine(day, time(target_hour, target_minute), JST)
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
        "reportId": f"{report_date}_{report_slot.replace(':', '-')}",
        "latestAttemptAt": attempt,
        "notification": "NOT_SENT",
    }


