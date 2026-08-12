from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest-report.json"
DASHBOARD = ROOT / "data/dashboard.json"
REPORTS_DIR = ROOT / "reports"
JST = dt.timezone(dt.timedelta(hours=9))


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_report(report: dict) -> None:
    for key in ("date", "time", "title"):
        if not report.get(key):
            raise SystemExit(f"latest report missing required field: {key}")
    if report.get("time") == "08:00":
        table = report.get("marketDataTable") or {}
        rows = table.get("rows") or []
        if len(rows) != 28:
            raise SystemExit(f"08:00 latest report requires 28 marketDataTable rows, got {len(rows)}")


def sync_report_file(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{report['date']}_{report['time'].replace(':', '-')}.json"
    path = REPORTS_DIR / filename
    dump_json(path, report)
    return path


def sync_dashboard(report: dict) -> None:
    dashboard = load_json(DASHBOARD, {})
    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    key = f"{report['date']} {report['time']}"
    data_as_of = f"{report['date']}T{report['time']}:00+09:00"

    dashboard.setdefault("schemaVersion", "1.1.0")
    dashboard.setdefault("pageId", "dashboard")
    dashboard["generatedAt"] = now
    dashboard["publishedAt"] = now
    dashboard["dataAsOf"] = data_as_of
    dashboard["status"] = "ok"
    dashboard["isStale"] = False
    dashboard["staleReason"] = ""
    dashboard["currentReportKey"] = key
    dashboard["latestReport"] = report

    sources = dashboard.get("sources")
    if not isinstance(sources, list):
        sources = []
    found = False
    for source in sources:
        if isinstance(source, dict) and source.get("id") == "MARKET_REPORTS_JSON":
            source["asOf"] = key
            source["status"] = "ok"
            found = True
            break
    if not found:
        sources.insert(0, {
            "id": "MARKET_REPORTS_JSON",
            "name": "マーケットレポート本文の構造化JSON",
            "path": "reports.json",
            "asOf": key,
            "status": "ok",
            "note": "data/latest-report.json を正本として reports.json と dashboard.json を自動同期。",
        })
    dashboard["sources"] = sources
    dump_json(DASHBOARD, dashboard)


def main() -> None:
    payload = load_json(LATEST, {})
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict):
        raise SystemExit("data/latest-report.json does not contain a report object")
    validate_report(report)
    report_path = sync_report_file(report)
    sync_dashboard(report)
    print(f"Synced {report['date']} {report['time']} -> {report_path.relative_to(ROOT)}, data/dashboard.json")


if __name__ == "__main__":
    main()
