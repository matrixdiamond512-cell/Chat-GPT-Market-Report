#!/usr/bin/env python3
"""Build the portal's report archive from individual JSON files.
Run: python3 scripts/build_report_index.py
Never infer missing fullText; fail for incomplete sources.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
ARCHIVE = ROOT / "reports.json"
DASHBOARD = ROOT / "data" / "dashboard.json"
LATEST = ROOT / "data" / "latest-report.json"


def main():
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    if not isinstance(archive, list):
        raise ValueError("reports.json must be a JSON array")
    indexed = {(r.get("date"), r.get("time")): r for r in archive if isinstance(r, dict)}
    for file in sorted(REPORTS.glob("????-??-??_??-??.json")):
        record = json.loads(file.read_text(encoding="utf-8"))
        body = record.get("fullText")
        if not isinstance(body, str) or not body.strip():
            raise ValueError(f"Missing fullText: {file}")
        if not body.startswith(record.get("title", "")):
            raise ValueError(f"Title/fullText mismatch: {file}")
        indexed[(record["date"], record["time"])] = record
    ordered = sorted(indexed.values(), key=lambda r: (r.get("date", ""), r.get("time", "")), reverse=True)
    ARCHIVE.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not ordered:
        return
    latest = ordered[0]
    LATEST.write_text(json.dumps({"latestReport": latest, "dataAsOf": latest.get("updatedAt")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if DASHBOARD.exists():
        dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        dashboard["latestReport"] = latest
        dashboard["currentReportKey"] = latest["date"] + "_" + latest["time"].replace(":", "-")
        dashboard["dataAsOf"] = latest.get("updatedAt")
        if isinstance(dashboard.get("reports"), list):
            dashboard["reports"] = [r for r in ordered if r.get("date") == latest["date"]]
        DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Indexed {len(ordered)} reports; latest: {latest['title']}")


if __name__ == "__main__":
    main()
