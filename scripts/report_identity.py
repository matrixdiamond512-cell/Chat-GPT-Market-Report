"""Shared identifiers for a market report slot.

The report slot is the identity; filenames and display labels are formats of
that identity and must not be compared as if they were interchangeable.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def slot_key(report: dict) -> tuple[str, str]:
    date = str(report.get("date") or "")
    time = str(report.get("time") or "")
    if not DATE_PATTERN.fullmatch(date) or not TIME_PATTERN.fullmatch(time):
        raise ValueError(f"invalid report slot: {date!r} {time!r}")
    datetime.strptime(date, "%Y-%m-%d")
    datetime.strptime(time, "%H:%M")
    return date, time


def internal_report_key(report: dict) -> str:
    date, time = slot_key(report)
    return f"{date}_{time.replace(':', '-')}"


def display_report_datetime(report: dict) -> str:
    date, time = slot_key(report)
    return f"{date} {time}"


def canonical_filename(report: dict) -> str:
    return f"{internal_report_key(report)}.json"


def canonical_path(report: dict, reports_dir: Path = Path("reports")) -> Path:
    return reports_dir / canonical_filename(report)
