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
    if view is not None:
        for left, right in (("report_id","report_id"), ("revision","revision"), ("bodyHash","body_hash")):
            if report.get(left) is not None and view.get(right) is not None and report[left] != view[right]:
                missing.append("identity_mismatch." + left)
        sid = report.get("snapshot_id") or report.get("snapshotId")
        if sid is not None and view.get("snapshot_id") is not None and sid != view["snapshot_id"]:
            missing.append("identity_mismatch.snapshot_id")
        snapshot = report.get("snapshot") or report.get("marketDataSnapshot") or report.get("market_data_snapshot")
        context = report.get("context") or report.get("report_context")
        if isinstance(snapshot, dict) and sid and snapshot.get("snapshot_id") != sid:
            missing.append("identity_mismatch.snapshot")
        if isinstance(context, dict) and report.get("report_id") and context.get("report_id") != report["report_id"]:
            missing.append("identity_mismatch.context_report")
        if isinstance(context, dict) and report.get("revision") and context.get("revision") != report["revision"]:
            missing.append("identity_mismatch.context_revision")
    snapshot = report.get("snapshot") or report.get("marketDataSnapshot") or report.get("market_data_snapshot")
    context = report.get("context") or report.get("report_context")
    if isinstance(snapshot, dict) and isinstance(context, dict):
        for key in ("report_id", "revision"):
            if snapshot.get(key) != context.get(key):
                missing.append("identity_mismatch.snapshot_context_" + key)
        if snapshot.get("data_cutoff") != context.get("data_cutoff"):
            missing.append("identity_mismatch.data_cutoff")
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
