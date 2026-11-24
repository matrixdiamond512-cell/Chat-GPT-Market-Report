"""Schedule freshness is independent of source integrity and market-feed health."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
OWNED_REASONS = {"LATEST_REPORT_BEHIND_SCHEDULE", "LATEST_REPORT_MISSING", "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED", "FORMAL_PUBLICATION_UNVERIFIED"}

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

def formal_publication(report, root=None):
    """Verify repository body-publication evidence; this does not observe Pages."""
    from reporting.publication_evidence import validate_receipt
    root = Path(root) if root is not None else ROOT
    result = {"state": "UNVERIFIED", "canonical": "NOT_CHECKED", "receipt": "NOT_CHECKED"}
    if not isinstance(report, dict) or not report.get("date") or not report.get("time"):
        return {**result, "reason": "LATEST_REPORT_MISSING"}
    try:
        # Parse before constructing a path; arbitrary strings cannot select files.
        slot = dt.datetime.fromisoformat(f"{report['date']}T{report['time']}:00+09:00")
        key = slot.strftime("%Y-%m-%d_%H-%M")
        result["reportKey"] = key
        if report.get("report_status") not in {"PUBLISHED", "DOC_READBACK_PASS"}:
            return {**result, "reason": "SOURCE_NOT_FORMAL"}
        canonical_path = root / "reports" / f"{key}.json"
        if not canonical_path.is_file():
            return {**result, "reason": "CANONICAL_MISSING"}
        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        projection = dict(report)
        if "marketData" not in canonical:
            projection.pop("marketData", None)
        if canonical != projection or not str(canonical.get("fullText") or "").strip():
            return {**result, "state": "FAILED", "canonical": "FAIL", "reason": "CANONICAL_MISMATCH"}
        result["canonical"] = "PASS"
        receipt_path = root / "publication-receipts" / f"{key}.json"
        if not receipt_path.is_file():
            return {**result, "reason": "RECEIPT_MISSING"}
        validate_receipt(json.loads(receipt_path.read_text(encoding="utf-8")), canonical)
        index = json.loads((root / "reports.json").read_text(encoding="utf-8"))
        matches = [x for x in index if isinstance(x, dict) and (x.get("date"), x.get("time")) == (report["date"], report["time"])]
        if matches != [canonical]:
            return {**result, "state": "FAILED", "receipt": "PASS", "reason": "INDEX_MISMATCH"}
        return {**result, "state": "VERIFIED", "receipt": "PASS", "index": "PASS",
                "bodyHash": canonical["bodyHash"], "revision": canonical["revision"]}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {**result, "state": "FAILED", "reason": "PUBLICATION_EVIDENCE_INVALID"}


def apply_delivery_health(dashboard, report, *, now=None, schedule=None, evidence_root=None):
    freshness = delivery_health(report, now=now, schedule=schedule)
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
    dashboard.setdefault("status", base["status"])
    dashboard.setdefault("isStale", base["isStale"])
    dashboard.setdefault("staleReason", base["staleReason"])
    formal = formal_publication(report, evidence_root)
    dashboard["reportDelivery"] = {"slotFreshness": freshness, "formalPublication": formal,
        "pagesDisplay": {"state": "NOT_VERIFIED", "reason": "LIVE_DOM_READBACK_NOT_PERFORMED"},
        "independentHealth": base}
    reason = freshness["staleReason"]
    if report.get("report_status") == "RECONSTRUCTED_UNVERIFIED":
        reason = "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED"
    if reason:
        dashboard.update(status="degraded", isStale=True, staleReason=reason)
    elif formal["state"] != "VERIFIED":
        if dashboard.get("status") == "ok":
            dashboard["status"] = "partial"
        if not dashboard.get("staleReason"):
            dashboard["staleReason"] = "FORMAL_PUBLICATION_UNVERIFIED"
    return dashboard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=ROOT / "data/dashboard.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    apply_delivery_health(dashboard, dashboard.get("latestReport") or {}, evidence_root=args.root)
    health = dashboard["reportDelivery"]
    print(json.dumps(health, ensure_ascii=False))
    return 0 if (health["slotFreshness"]["state"] == "CURRENT" and health["formalPublication"]["state"] == "VERIFIED") else 1

if __name__ == "__main__":
    raise SystemExit(main())
