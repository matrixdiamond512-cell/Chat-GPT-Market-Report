"""Read-only preflight for 08:00 infographic inputs. Never backfills evidence."""
import argparse
import json
from pathlib import Path

def check(report, view=None):
    missing = []
    for key in ("report_id", "revision", "bodyHash", "fullText"):
        if not report.get(key):
            missing.append("report." + key)
    if not (report.get("snapshot_id") or report.get("snapshotId")):
        missing.append("report.snapshot_id")
    if not (report.get("context") or report.get("report_context")):
        missing.append("report.context")
    if not (report.get("snapshot") or report.get("marketDataSnapshot") or report.get("market_data_snapshot")):
        missing.append("report.snapshot")
    if view is None:
        missing.append("view.not_provided")
    else:
        for key in ("report_id", "revision", "snapshot_id", "body_hash", "facts", "cards", "header"):
            if not view.get(key):
                missing.append("view." + key)
    if report.get("source_note") or report.get("report_status") in ("RECONSTRUCTED_UNVERIFIED", "UNVERIFIED"):
        missing.append("report.original_source_verification")
    return {"status": "BLOCKED" if missing else "READY_FOR_CANONICAL_VALIDATION",
            "missing_or_unverified": missing,
            "note": "Preflight is not canonical spec, price, PNG, Drive or publication validation."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--view", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    view = json.loads(args.view.read_text(encoding="utf-8-sig")) if args.view else None
    result = check(report, view)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
