#!/usr/bin/env python3
"""Remove legacy market-report-derived rows from the public event calendar.

The public important-events page must use only the normalized calendar feed.
Older rows extracted or manually seeded from market-report prose are excluded
from latest, upcoming, completed, legacy-compatible, and history JSON files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
ALLOWED_SOURCE_TYPES = {"forex_factory_weekly"}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_normalized_event(event: dict[str, Any]) -> bool:
    return (
        event.get("sourceType") in ALLOWED_SOURCE_TYPES
        and bool(event.get("sourceKey"))
        and bool(event.get("date"))
        and bool(event.get("time"))
    )


def event_key(event: dict[str, Any]) -> str:
    return str(event.get("sourceKey") or event.get("id") or "")


def event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (str(event.get("date", "")), str(event.get("time", "")), str(event.get("title", "")))


def filter_events(events: Any) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in events if isinstance(events, list) else []:
        if not isinstance(item, dict) or not is_normalized_event(item):
            continue
        key = event_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return sorted(cleaned, key=event_sort_key, reverse=True)


def rebuild_days(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    dates = sorted({str(item.get("date")) for item in events if item.get("date")}, reverse=True)
    for date in dates:
        rows = [item for item in events if item.get("date") == date]
        days.append(
            {
                "date": date,
                "eventCount": len(rows),
                "releasedCount": sum(item.get("status") == "released" for item in rows),
                "resultPendingCount": sum(item.get("status") == "result_pending" for item in rows),
            }
        )
    return days


def parse_event_time(event: dict[str, Any]) -> dt.datetime | None:
    value = str(event.get("datetimeJst") or "")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(JST)


def base_meta(payload: dict[str, Any]) -> dict[str, Any]:
    keys = ("schemaVersion", "pageId", "generatedAt", "dataAsOf", "timezone", "status", "isStale", "sources", "errors")
    return {key: payload.get(key) for key in keys}


def append_cleanup_source(payload: dict[str, Any], removed: int) -> None:
    sources = [
        item
        for item in payload.get("sources", [])
        if isinstance(item, dict) and item.get("id") != "legacy_event_cleanup"
    ]
    sources.append(
        {
            "id": "legacy_event_cleanup",
            "name": "旧マーケットレポート由来イベントの除外",
            "status": "ok",
            "note": f"正規カレンダー以外の旧レコードを{removed}件除外。",
        }
    )
    payload["sources"] = sources


def clean(root: Path, now: dt.datetime | None = None) -> dict[str, int]:
    now = now or dt.datetime.now(JST)
    latest_path = root / "data/events/latest.json"
    payload = load_json(latest_path, {})
    original = [item for item in payload.get("events", []) if isinstance(item, dict)]
    events = filter_events(original)
    removed = len(original) - len(events)

    payload["events"] = events
    payload["days"] = rebuild_days(events)
    payload["legacyRecordsRemoved"] = removed
    payload["legacyCleanupAt"] = now.astimezone(JST).isoformat(timespec="seconds")
    payload["legacyCleanupVersion"] = "1.0.0"
    append_cleanup_source(payload, removed)

    meta = base_meta(payload)
    upcoming_days = 7
    retention = payload.get("retention", {})
    if isinstance(retention, dict):
        upcoming_days = int(retention.get("upcomingDays", upcoming_days) or upcoming_days)
    upcoming_end = now + dt.timedelta(days=upcoming_days)
    upcoming = []
    for event in events:
        stamp = parse_event_time(event)
        if stamp and now <= stamp <= upcoming_end:
            upcoming.append(event)
    completed = [event for event in events if event.get("status") == "released"]

    write_json(latest_path, payload)
    write_json(root / "data/events.json", payload)
    write_json(root / "data/events/upcoming.json", {**meta, "rangeDays": upcoming_days, "events": sorted(upcoming, key=event_sort_key)})
    write_json(root / "data/events/completed.json", {**meta, "events": sorted(completed, key=event_sort_key, reverse=True)})
    write_json(
        root / "economic-calendar.json",
        {
            "schemaVersion": payload.get("schemaVersion", "2.0.0"),
            "status": payload.get("status"),
            "updatedAt": payload.get("generatedAt"),
            "timezone": payload.get("timezone", "Asia/Tokyo"),
            "provider": "forex_factory_weekly",
            "range": {"days": upcoming_days},
            "events": sorted(upcoming, key=event_sort_key),
            "errors": payload.get("errors", []),
        },
    )

    history_removed = 0
    history_dir = root / "data/events/history"
    for path in history_dir.glob("*.json") if history_dir.exists() else []:
        day_payload = load_json(path, {})
        before = [item for item in day_payload.get("events", []) if isinstance(item, dict)]
        after = filter_events(before)
        history_removed += len(before) - len(after)
        day_payload["events"] = sorted(after, key=event_sort_key)
        day_payload["legacyCleanupAt"] = payload["legacyCleanupAt"]
        write_json(path, day_payload)

    by_date: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_date.setdefault(str(event["date"]), []).append(event)
    for date, rows in by_date.items():
        write_json(
            history_dir / f"{date}.json",
            {**meta, "date": date, "events": sorted(rows, key=event_sort_key), "legacyCleanupAt": payload["legacyCleanupAt"]},
        )

    return {"events": len(events), "removed": removed, "historyRemoved": history_removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    summary = clean(args.root.resolve())
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
