#!/usr/bin/env python3
"""Fail closed when the latest report and all public projections diverge."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def unwrap(payload: object, source: str) -> dict:
    if not isinstance(payload, dict):
        raise SystemExit(f"{source}: expected a JSON object")
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict):
        raise SystemExit(f"{source}: report object is missing")
    for key in ("date", "time", "title"):
        if not str(report.get(key) or "").strip():
            raise SystemExit(f"{source}: report missing {key}")
    return report


def key(report: dict) -> tuple[str, str]:
    return str(report["date"]), str(report["time"])


def slot_datetime(report: dict) -> datetime:
    try:
        return datetime.fromisoformat(
            f"{report['date']}T{report['time']}:00+09:00"
        )
    except ValueError as exc:
        raise SystemExit(f"invalid report slot {report.get('date')} {report.get('time')}: {exc}") from exc


def verify_dashboard_projection(latest: dict, dashboard: dict) -> None:
    """Check the dashboard's projection without requiring identical schemas."""
    projected = dashboard.get("latestReport")
    if not isinstance(projected, dict):
        raise SystemExit("dashboard.latestReport is missing")
    for field in ("date", "time", "title"):
        if not str(projected.get(field) or "").strip():
            raise SystemExit(f"dashboard.latestReport is missing {field}")
    if key(projected) != key(latest):
        raise SystemExit(
            f"dashboard.latestReport slot mismatch: {key(projected)} != {key(latest)}"
        )
    if str(projected.get("title") or "") != str(latest.get("title") or ""):
        raise SystemExit("dashboard.latestReport title does not match latest-report.json")
    for field in ("reportId", "revision", "bodyHash"):
        if field in latest and field in projected and latest[field] != projected[field]:
            raise SystemExit(f"dashboard.latestReport {field} does not match latest-report.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", default="data/latest-report.json")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--index", default="reports.json")
    parser.add_argument("--dashboard", default="data/dashboard.json")
    parser.add_argument("--expected-key", default="")
    parser.add_argument("--allow-future", action="store_true")
    args = parser.parse_args()

    latest = unwrap(load(Path(args.latest)), args.latest)
    date_text, time_text = key(latest)
    if args.expected_key and args.expected_key != f"{date_text} {time_text}":
        raise SystemExit(
            f"latest report slot mismatch: expected {args.expected_key}, "
            f"got {date_text} {time_text}"
        )
    if not args.allow_future and slot_datetime(latest) > datetime.now(JST):
        raise SystemExit(f"future report cannot be public latest: {date_text} {time_text}")

    canonical_path = Path(args.reports) / f"{date_text}_{time_text.replace(':', '-')}.json"
    if not canonical_path.exists():
        raise SystemExit(f"canonical report missing: {canonical_path}")
    canonical = unwrap(load(canonical_path), str(canonical_path))
    if canonical != latest:
        raise SystemExit(f"latest/canonical mismatch: {canonical_path}")

    index = load(Path(args.index))
    if not isinstance(index, list):
        raise SystemExit(f"{args.index}: expected a JSON array")
    matches = [item for item in index if isinstance(item, dict) and key(item) == (date_text, time_text)]
    if len(matches) != 1 or matches[0] != latest:
        raise SystemExit(
            f"latest/index mismatch for {date_text} {time_text}: matches={len(matches)}"
        )

    dashboard = load(Path(args.dashboard))
    if not isinstance(dashboard, dict):
        raise SystemExit(f"{args.dashboard}: expected a JSON object")
    expected_key = f"{date_text} {time_text}"
    if dashboard.get("currentReportKey") != expected_key:
        raise SystemExit(
            f"dashboard currentReportKey mismatch: "
            f"{dashboard.get('currentReportKey')!r} != {expected_key!r}"
        )
    verify_dashboard_projection(latest, dashboard)

    print(
        f"Publication consistency verified: {expected_key}; "
        f"canonical={canonical_path}; dashboard={args.dashboard}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
