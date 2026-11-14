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


def observe_run(root: Path, date: str, slot: str, run: dict, now: datetime) -> dict:
    """Read-only diagnostic; supplied run observations never authorize publication."""
    if slot not in SLOTS:
        raise ValueError("Unknown market report slot")
    target = datetime.fromisoformat(f"{date}T{slot}:00+09:00")
    def timestamp(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError("Timezone required")
        return parsed
    if now.utcoffset() is None:
        raise ValueError("Timezone required")
    scheduled = timestamp(run["scheduled_for"])
    start = timestamp(run["started_at"])
    end = timestamp(run["completed_at"]) if run.get("completed_at") else None
    if scheduled != target or (end and end < start):
        raise ValueError("Run slot or timestamp order mismatch")
    stages = {key: run.get(key, "UNKNOWN") for key in
              ("chatBody", "image", "DocsSave", "DocsReadback", "sourceBundle")}
    allowed = {"PASS", "FAIL", "NOT_RUN", "BLOCKED", "UNKNOWN"}
    if any(value not in allowed for value in stages.values()):
        raise ValueError("Unknown stage status")
    try:
        publication = verify(root, date, slot)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        publication = {"status": "FAIL", "reason": str(exc)}
    missing = [key for key, value in stages.items() if value != "PASS"]
    early_end = bool(end and end < target)
    success = publication["status"] == "PASS" and not missing and not early_end
    return {
        "reportId": f"{date}_{slot.replace(':', '-')}",
        "scheduledAt": run["scheduled_for"], "actualStart": run["started_at"],
        "actualEnd": run.get("completed_at"), "runId": run.get("runId"),
        "dataCutoff": run.get("dataCutoff"), "sourceCreatedAt": run.get("sourceCreatedAt"),
        "startOffsetSeconds": (start - target).total_seconds(),
        "taskStatus": run.get("status", "UNKNOWN"), "stages": stages,
        "publication": publication, "unverifiedStages": missing,
        "status": "PASS" if success else "FAIL" if end or now >= target else "PENDING",
        "reason": "EARLY_COMPLETION_WITHOUT_ACCEPTED_DELIVERY" if early_end else
                  "DELIVERY_PROOFS_MISSING" if not success else "OBSERVED_DELIVERY_CHECKS_PASS",
        "continuation": "BLOCKED_PLATFORM_CAPABILITY" if early_end else "NOT_ASSESSED",
        "proofScope": "Supplied run observations and local publication files; not live DOM or notice",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=SLOTS, required=True)
    parser.add_argument("--date")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run-observation", type=Path)
    args = parser.parse_args()
    date = args.date or datetime.now(JST).date().isoformat()
    result = observe_run(args.root, date, args.slot,
                         json.loads(args.run_observation.read_text(encoding="utf-8-sig")),
                         datetime.now(JST)) if args.run_observation else verify(args.root, date, args.slot)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
