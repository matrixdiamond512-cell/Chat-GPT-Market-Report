#!/usr/bin/env python3
"""Resolve a canonical WEB market-report slot for automated market data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


JST = dt.timezone(dt.timedelta(hours=9))
REPORT_SLOTS = ("07:00", "12:00", "16:00", "21:00")
SCHEDULE_TO_SLOT = {
    "55 20 * * 0-4": "07:00",
    "50 21 * * 0-4": "07:00",
    "50 2 * * 1-5": "12:00",
    "50 6 * * 1-5": "16:00",
    "50 11 * * 1-5": "21:00",
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
    hour_minute = now.astimezone(JST).strftime("%H:%M")
    if hour_minute < "09:30":
        return "07:00"
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
        # Scheduled GitHub Actions can start much later than their cron time.
        # Resolve from the actual Japan time so a delayed 15:50 run cannot
        # overwrite a 21:00 snapshot with the stale 16:00 slot label.
        return slot_for_time(now or dt.datetime.now(JST))
    if event_name == "push":
        report_slot = latest_report_slot(reports_file)
        if report_slot:
            return report_slot
    return slot_for_time(now or dt.datetime.now(JST))


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
