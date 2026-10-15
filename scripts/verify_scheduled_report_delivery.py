#!/usr/bin/env python3
"""Fail when a scheduled report has not actually reached canonical, index, and dashboard."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from report_identity import canonical_path, internal_report_key
from reporting.publication_eligibility import is_publication_eligible

JST = timezone(timedelta(hours=9))
SLOTS = ("08:00", "12:00", "16:00", "21:00")


def verify(root: Path, date: str, slot: str) -> dict:
    if slot not in SLOTS:
        raise ValueError("Unknown market report slot")
    report_path = canonical_path({"date": date, "time": slot}, root / "reports")
    if not report_path.is_file():
        raise ValueError("Missing published canonical " + report_path.name)
    canonical = json.loads(report_path.read_text(encoding="utf-8"))
    key = (date, slot)
    if not is_publication_eligible(canonical):
        raise ValueError(
            f"Report is archived but not publication-eligible: "
            f"{date} {slot} ({canonical.get('report_status')})"
        )
    if (canonical.get("date"), canonical.get("time")) != key or not str(canonical.get("fullText") or "").strip():
        raise ValueError("Incomplete or wrong-slot canonical report")
    index = json.loads((root / "reports.json").read_text(encoding="utf-8"))
    entries = index if isinstance(index, list) else (index.get("reports") or index.get("items") or [])
    matches = [x for x in entries if isinstance(x, dict) and (x.get("date"), x.get("time")) == key]
    if len(matches) != 1 or matches[0] != canonical:
        raise ValueError("Canonical and history index are not identical")
    latest_data = json.loads((root / "data" / "latest-report.json").read_text(encoding="utf-8"))
    latest = latest_data.get("latestReport", latest_data)
    if (latest.get("date"), latest.get("time")) < key:
        raise ValueError("Latest report pointer is behind required slot")
    dashboard = json.loads((root / "data" / "dashboard.json").read_text(encoding="utf-8"))
    if dashboard.get("latestReport") != latest:
        raise ValueError("Dashboard and latest report pointer disagree")
    if dashboard.get("currentReportKey") != internal_report_key(latest):
        raise ValueError("Dashboard currentReportKey disagrees with latest report")
    return {"status": "PASS", "date": date, "slot": slot, "canonical": str(report_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=SLOTS, required=True)
    parser.add_argument("--date")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    date = args.date or datetime.now(JST).date().isoformat()
    print(json.dumps(verify(args.root, date, args.slot), ensure_ascii=False))


if __name__ == "__main__":
    main()
