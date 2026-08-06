#!/usr/bin/env python3
"""Normalize qualitative economic-calendar events after provider ingestion.

The schedule provider includes speeches and market holidays alongside numeric
indicators. Those events do not publish an ``actual`` number, so leaving them as
``result_pending`` makes the WEB page look as though data collection failed.
This post-processor records an explicit non-numeric result and rebuilds the
public summaries without inventing market figures.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
QUALITATIVE_PATTERNS = re.compile(
    r"\b(?:speaks?|speech|testifies|press conference)\b|発言|会見|講演",
    re.IGNORECASE,
)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_datetime(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(JST)


def iso_jst(value: dt.datetime) -> str:
    return value.astimezone(JST).isoformat(timespec="seconds")


def is_qualitative_event(event: dict[str, Any]) -> bool:
    category = str(event.get("category") or "")
    if category in {"speech", "holiday"}:
        return True
    title = " ".join(
        str(event.get(key) or "")
        for key in ("eventNameOriginal", "title")
    )
    has_numeric_reference = bool(event.get("forecast") or event.get("previous"))
    return not has_numeric_reference and bool(QUALITATIVE_PATTERNS.search(title))


def normalize_event(event: dict[str, Any], now: dt.datetime) -> bool:
    if not is_qualitative_event(event):
        return False
    scheduled = parse_datetime(event.get("datetimeJst"))
    if scheduled is None or scheduled > now:
        event["resultExpected"] = False
        event["resultType"] = "qualitative"
        return False

    category = str(event.get("category") or "")
    is_holiday = category == "holiday"
    actual = "休場" if is_holiday else "数値発表なし（発言イベント）"
    explanation = (
        "休場イベントのため、予想・前回・実績の数値はありません。流動性低下と取引再開時の値動きを確認します。"
        if is_holiday
        else "数値の実績値が発表されるイベントではありません。発言内容と、金利・為替・株価指数先物の反応を確認します。"
    )
    narrative = "休場確認済み" if is_holiday else "発言イベント終了"
    reaction = "流動性と取引再開を確認" if is_holiday else "発言内容と市場反応を確認"

    changed = any(
        [
            event.get("actual") != actual,
            event.get("status") != "released",
            event.get("resultExplanation") != explanation,
            event.get("resultType") != "qualitative",
        ]
    )
    event.update(
        {
            "forecast": event.get("forecast") or ("対象外" if is_holiday else "数値発表なし"),
            "previous": event.get("previous") or ("対象外" if is_holiday else "数値発表なし"),
            "actual": actual,
            "resultComparison": "",
            "resultExplanation": explanation,
            "status": "released",
            "resultExpected": False,
            "resultType": "qualitative",
            "resultSource": event.get("officialSource") or {
                "id": "official_source",
                "name": "公式発表元",
                "url": "",
            },
            "resultSavedAt": event.get("resultSavedAt") or iso_jst(now),
            "updatedAt": iso_jst(now),
        }
    )
    conclusion = dict(event.get("conclusion") or {})
    conclusion.update({"narrative": narrative, "reaction": reaction})
    event["conclusion"] = conclusion
    return changed


def rebuild_days(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = sorted(
        {str(item.get("date")) for item in events if item.get("date")},
        reverse=True,
    )
    rows: list[dict[str, Any]] = []
    for date in dates:
        day_events = [item for item in events if item.get("date") == date]
        rows.append(
            {
                "date": date,
                "eventCount": len(day_events),
                "releasedCount": sum(item.get("status") == "released" for item in day_events),
                "resultPendingCount": sum(item.get("status") == "result_pending" for item in day_events),
            }
        )
    return rows


def base_meta(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schemaVersion",
        "pageId",
        "generatedAt",
        "publishedAt",
        "dataAsOf",
        "timezone",
        "status",
        "isStale",
        "sources",
        "errors",
    )
    return {key: payload.get(key) for key in keys if key in payload}


def event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("date") or ""),
        str(event.get("time") or ""),
        str(event.get("title") or ""),
    )


def process(root: Path, now: dt.datetime) -> dict[str, Any]:
    latest_path = root / "data/events/latest.json"
    payload = load_json(latest_path, {})
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise RuntimeError("data/events/latest.json に有効なイベント配列がありません。")

    events = [item for item in payload["events"] if isinstance(item, dict)]
    changed_count = sum(normalize_event(item, now) for item in events)
    payload["events"] = events
    payload["days"] = rebuild_days(events)
    payload["postprocessedAt"] = iso_jst(now)
    payload["postprocessVersion"] = "1.0.0"

    write_json(latest_path, payload)
    write_json(root / "data/events.json", payload)

    completed = [item for item in events if item.get("status") == "released"]
    write_json(
        root / "data/events/completed.json",
        {**base_meta(payload), "events": sorted(completed, key=event_sort_key)},
    )

    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        date = str(item.get("date") or "")
        if date:
            by_date.setdefault(date, []).append(item)
    for date, rows in by_date.items():
        write_json(
            root / f"data/events/history/{date}.json",
            {**base_meta(payload), "date": date, "events": sorted(rows, key=event_sort_key)},
        )

    return {
        "changed": changed_count,
        "events": len(events),
        "released": len(completed),
        "pending": sum(item.get("status") == "result_pending" for item in events),
        "postprocessedAt": payload["postprocessedAt"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--now", help="ISO 8601 test time")
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = (
        dt.datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(JST)
        if args.now
        else dt.datetime.now(JST)
    )
    summary = process(args.root.resolve(), now)
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
