"""Schedule freshness is independent of source integrity and market-feed health."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
OWNED_REASONS = {"LATEST_REPORT_BEHIND_SCHEDULE", "LATEST_REPORT_MISSING", "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED"}

def expected_slot(now=None, schedule=None):
    now = now or dt.datetime.now(JST)
    if now.tzinfo is None:
        raise ValueError("freshness requires timezone-aware time")
    now = now.astimezone(JST)
    if schedule is None:
        schedule = json.loads((ROOT / "config/report_schedule.json").read_text(encoding="utf-8"))
    if schedule.get("timezone") != "Asia/Tokyo":
        raise ValueError("unsupported report timezone")
    for offset in range(8):
        day = now.date() - dt.timedelta(days=offset)
        category = "weekday" if day.weekday() < 5 else ("saturday" if day.weekday() == 5 else "sunday")
        slots = schedule[category]["publicationSlots"]
        for slot in sorted(slots, reverse=True):
            candidate = dt.datetime.fromisoformat(f"{day}T{slot}:00+09:00")
            if candidate <= now:
                return candidate
    raise ValueError("no scheduled publication slot within one week")

def delivery_health(report, *, now=None, schedule=None):
    expected = expected_slot(now, schedule)
    published = None
    if isinstance(report, dict) and report.get("date") and report.get("time"):
        try:
            published = dt.datetime.fromisoformat(f"{report['date']}T{report['time']}:00+09:00")
        except ValueError:
            pass
    state = "MISSING" if published is None else ("BEHIND_SCHEDULE" if published < expected else "CURRENT")
    # A later, unscheduled/future timestamp cannot satisfy the expected slot.
    if published is not None and published > expected:
        state = "MISSING"
    reason = "" if state == "CURRENT" else ("LATEST_REPORT_MISSING" if state == "MISSING" else "LATEST_REPORT_BEHIND_SCHEDULE")
    return {"state": state, "expectedReportKey": expected.strftime("%Y-%m-%d_%H-%M"),
            "publishedReportKey": published.strftime("%Y-%m-%d_%H-%M") if published else "",
            "staleReason": reason}

def apply_delivery_health(dashboard, report, *, now=None, schedule=None):
    health = delivery_health(report, now=now, schedule=schedule)
    previous = str(dashboard.get("staleReason") or "")
    old_health = dashboard.get("reportDelivery") or {}
    if previous in OWNED_REASONS:
        base = old_health.get("independentHealth") or {"status": "partial", "isStale": False, "staleReason": ""}
        dashboard.update(base)
    base = {k: dashboard.get(k, default) for k, default in
            (("status", "partial"), ("isStale", False), ("staleReason", ""))}
    market = dashboard.get("marketData") or {}
    if market.get("overallStatus") in {"degraded", "blocked"}:
        base["status"] = "degraded"
        dashboard["status"] = "degraded"
    health["independentHealth"] = base
    if report.get("report_status") == "RECONSTRUCTED_UNVERIFIED":
        health = {**health, "staleReason": "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED"}
    dashboard["reportDelivery"] = health
    if health["staleReason"]:
        dashboard.update(status="degraded", isStale=True, staleReason=health["staleReason"])
    return dashboard

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=ROOT / "data/dashboard.json")
    args = parser.parse_args()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    health = delivery_health(dashboard.get("latestReport") or {})
    print(json.dumps(health, ensure_ascii=False))
    return 0 if health["state"] == "CURRENT" else 1

if __name__ == "__main__":
    raise SystemExit(main())
