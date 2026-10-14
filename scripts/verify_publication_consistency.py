#!/usr/bin/env python3
"""Fail closed when the latest report and all public projections diverge."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from report_identity import canonical_path as shared_canonical_path, display_report_datetime, internal_report_key, slot_key as shared_slot_key

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
    return shared_slot_key(report)


def slot_datetime(report: dict) -> datetime:
    try:
        return datetime.fromisoformat(
            f"{report['date']}T{report['time']}:00+09:00"
        )
    except ValueError as exc:
        raise SystemExit(f"invalid report slot {report.get('date')} {report.get('time')}: {exc}") from exc


def verify_dashboard_copy(latest: dict, dashboard: dict) -> None:
    """The dashboard stores the complete canonical latest report."""
    projected = dashboard.get("latestReport")
    if not isinstance(projected, dict):
        raise SystemExit("dashboard.latestReport is missing")
    if projected != latest:
        raise SystemExit("dashboard.latestReport does not match complete latest report")


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
    expected_internal_key = internal_report_key(latest)
    if args.expected_key and args.expected_key != expected_internal_key:
        raise SystemExit(
            f"latest report slot mismatch: expected {args.expected_key}, "
            f"got {expected_internal_key}"
        )
    if not args.allow_future and slot_datetime(latest) > datetime.now(JST):
        raise SystemExit(f"future report cannot be public latest: {date_text} {time_text}")

    canonical_path = shared_canonical_path(latest, Path(args.reports))
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
    if dashboard.get("currentReportKey") != expected_internal_key:
        raise SystemExit(
            f"dashboard currentReportKey mismatch: "
            f"{dashboard.get('currentReportKey')!r} != {expected_internal_key!r}"
        )
    verify_dashboard_copy(latest, dashboard)

    print(
        f"Publication consistency verified: {display_report_datetime(latest)} "
        f"(key={expected_internal_key}); "
        f"canonical={canonical_path}; dashboard={args.dashboard}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
