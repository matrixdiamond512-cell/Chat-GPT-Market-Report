#!/usr/bin/env python3
"""Resolve a canonical WEB market-report slot for automated market data."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


JST = dt.timezone(dt.timedelta(hours=9))
SCHEDULE_FILE = Path(__file__).resolve().parents[1] / "config" / "report_schedule.json"
SCHEDULER_ATTEMPT_MINUTES = (0, 3, 7, 13)


def configured_publication_slots() -> tuple[str, ...]:
    try:
        schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"report schedule cannot be loaded: {SCHEDULE_FILE}: {exc}") from exc
    slots: set[str] = set()
    for value in schedule.values():
        if isinstance(value, dict):
            slots.update(str(slot) for slot in value.get("publicationSlots", []))
    return tuple(sorted(slots))


REPORT_SLOTS = configured_publication_slots()

# GitHub cron strings are UTC. These schedules implement staged acquisition:
# - 08:00: Monday-Saturday
# - 12:00 / 16:00 / 21:00: weekdays only
# There is no Saturday 09:00 summary report.
#
# Keep every independent/fallback/health 08:00 cron here. Scheduled jobs are
# resolved from the declared cron string rather than their actual runner start
# time, so a delayed GitHub Actions runner cannot retag the snapshot as a later
# report slot.
SCHEDULE_TO_SLOT = {
    "28 21 * * 0-5": "08:00",  # 06:30 attempt starts at 06:28 JST
    "58 21 * * 0-5": "08:00",  # 07:00
    "18 22 * * 0-5": "08:00",  # 07:20
    "28 22 * * 0-5": "08:00",  # 07:30
    "38 22 * * 0-5": "08:00",  # 07:40
    "43 22 * * 0-5": "08:00",  # 07:45
    "48 22 * * 0-5": "08:00",  # 07:50
    "55 21 * * 0-5": "08:00",  # 06:55 fallback
    "42 22 * * 0-5": "08:00",  # 07:42 fallback
    "53 22 * * 0-5": "08:00",  # 07:55 final readiness starts 07:53
    "55 22 * * 0-5": "08:00",  # legacy 07:55 health cron, kept for compatibility
    "30,35,40,45,50,55 2 * * 1-5": "12:00",
    "30,35,40,45,50,55 6 * * 1-5": "16:00",
    "30,35,40,45,50,55 11 * * 1-5": "21:00",
}


def reports_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("reports"), list):
        return [item for item in payload["reports"] if isinstance(item, dict)]
    for key in ("latestReport", "currentReport"):
        if isinstance(payload.get(key), dict):
            return [payload[key]]
    return []


def latest_report_slot(path: Path) -> str:
    """Return the latest published slot for display/history use only.

    Do not use this value to tag new acquisition data. A latest published report
    may belong to yesterday or to a different scheduled window.
    """
    if not path.is_file():
        return ""
    try:
        reports = reports_from_payload(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return ""
    eligible = [
        item for item in reports
        if str(item.get("time") or "") in REPORT_SLOTS
        and str(item.get("date") or "")
    ]
    if not eligible:
        return ""
    latest = max(eligible, key=lambda item: f"{item.get('date', '')} {item.get('time', '')}")
    return str(latest.get("time") or "")


def slot_for_time(now: dt.datetime) -> str:
    current = now.astimezone(JST)
    hour_minute = current.strftime("%H:%M")
    weekday = current.weekday()  # Monday=0, Sunday=6

    if weekday == 5:  # Saturday has only the 08:00 regular report.
        return "08:00"
    if hour_minute < "09:30":
        return "08:00"
    if hour_minute < "14:30":
        return "12:00"
    if hour_minute < "19:30":
        return "16:00"
    return "21:00"


def resolve_slot(
    event_name: str,
    event_schedule: str,
    requested_slot: str,
    reports_file: Path,
    now: dt.datetime | None = None,
) -> str:
    requested = requested_slot.strip()
    if event_name == "workflow_dispatch" and requested in REPORT_SLOTS:
        return requested
    if event_name == "schedule":
        # Use the declared cron mapping rather than the delayed job start time.
        scheduled_slot = SCHEDULE_TO_SLOT.get(event_schedule.strip())
        if scheduled_slot:
            return scheduled_slot
        return slot_for_time(now or dt.datetime.now(JST))
    if event_name == "push":
        # Never infer a new data tag from the latest published report. That was
        # the cause of same-day 08:00 data being retagged as 21:00 after code
        # changes. Push-triggered callers, if any remain, use the current JST
        # acquisition window instead.
        return slot_for_time(now or dt.datetime.now(JST))
    return slot_for_time(now or dt.datetime.now(JST))


@dataclass(frozen=True)
class ReportIdentity:
    report_id: str
    target: dt.datetime
    status: str


def resolve_report_identity(*, schedule_time_utc: str | None = None,
                            report_date: str | None = None,
                            report_slot: str | None = None,
                            attempt_minutes: int = 0,
                            now: dt.datetime) -> ReportIdentity:
    """Resolve once from trusted scheduled time or an explicit date/slot pair.

    EXPIRED preserves identity for audit/drafting but forbids new evidence.
    Scheduled events must have started. Explicit targets open at the earliest
    acquisition attempt (T-13); requests before that boundary remain future input.
    Scheduler timestamp authentication belongs to the ingress adapter.
    """
    if now.tzinfo is None:
        raise ValueError("INVALID_CLOCK")
    if schedule_time_utc is not None:
        if report_date is not None or report_slot is not None or attempt_minutes not in SCHEDULER_ATTEMPT_MINUTES:
            raise ValueError("AMBIGUOUS_IDENTITY")
        scheduled = dt.datetime.fromisoformat(schedule_time_utc.replace("Z", "+00:00"))
        if scheduled.tzinfo is None or scheduled.utcoffset() != dt.timedelta(0):
            raise ValueError("INVALID_UTC_SCHEDULE")
        target = (scheduled + dt.timedelta(minutes=attempt_minutes)).astimezone(JST)
        if target.second or target.microsecond:
            raise ValueError("INVALID_SLOT")
    else:
        if not report_date or not report_slot or attempt_minutes:
            raise ValueError("EXPLICIT_DATE_AND_SLOT_REQUIRED")
        target = dt.datetime.fromisoformat(f"{report_date}T{report_slot}:00").replace(tzinfo=JST)
        if target.date().isoformat() != report_date or target.strftime("%H:%M") != report_slot:
            raise ValueError("INVALID_SLOT")
        # This is an admission boundary, not an inferred scheduler event time.
        # Target identity always comes from the explicit date/slot above.
        scheduled = target - dt.timedelta(minutes=max(SCHEDULER_ATTEMPT_MINUTES))
    schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    group = "weekday" if target.weekday() < 5 else ("saturday" if target.weekday() == 5 else "sunday")
    if target.strftime("%H:%M") not in schedule[group]["publicationSlots"]:
        raise ValueError("INVALID_PUBLICATION_SLOT")
    if scheduled > now:
        raise ValueError("FUTURE_SCHEDULE")
    return ReportIdentity(target.strftime("%Y-%m-%d_%H-%M"), target,
                          "EXPIRED" if now >= target else "ACTIVE")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", default="")
    parser.add_argument("--event-schedule", default="")
    parser.add_argument("--requested-slot", default="auto")
    parser.add_argument("--reports-file", type=Path, default=Path("reports.json"))
    args = parser.parse_args()
    print(resolve_slot(
        args.event_name,
        args.event_schedule,
        args.requested_slot,
        args.reports_file,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
