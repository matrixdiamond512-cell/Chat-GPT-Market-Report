"""Prepare a formal 08:00 report envelope from ORIGINAL report + verified context/snapshot.

Never recover missing acquisition evidence from a displayed market price.
Read-only inputs, exclusive output. No Drive or publication action.
"""
import argparse
import hashlib
import json
from pathlib import Path
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot
from reporting.infographic import ValidationFailure, validate_market_data, SourceLock

def assemble(report, context_raw, snapshot_raw):
    if report.get("source_note") or report.get("report_status") in ("RECONSTRUCTED_UNVERIFIED", "UNVERIFIED"):
        raise ValidationFailure("ORIGINAL_REPORT_NOT_VERIFIED")
    if not isinstance(report.get("fullText"), str) or not report["fullText"].strip():
        raise ValidationFailure("ORIGINAL_BODY_REQUIRED")
    if report.get("context") or report.get("snapshot") or report.get("marketDataSnapshot"):
        raise ValidationFailure("REPORT_ALREADY_HAS_BOUND_EVIDENCE")
    try:
        context = ReportContext(**context_raw)
        snapshot = MarketDataSnapshot.restore(snapshot_raw)
        snapshot.validate_context(context)
    except (TypeError, KeyError, ValueError) as exc:
        raise ValidationFailure("SNAPSHOT_CONTEXT_INVALID", str(exc)) from exc
    if context.report_time != "08:00" or report.get("date") != context.report_date or report.get("time") != context.report_time:
        raise ValidationFailure("REPORT_SLOT_IDENTITY_MISMATCH")
    if not isinstance(report.get("title"), str) or not report["title"] or report["title"] not in report["fullText"]:
        raise ValidationFailure("REPORT_TITLE_SOURCE_MISMATCH")
    # Never overwrite conflicting existing identity or body hash.
    body_hash = hashlib.sha256(report["fullText"].encode("utf-8")).hexdigest()
    # A digest created at handoff time is not evidence of the original published body.
    if not isinstance(report.get("bodyHash"), str) or not report["bodyHash"]:
        raise ValidationFailure("ORIGINAL_BODY_HASH_REQUIRED")
    if report["bodyHash"] != body_hash:
        raise ValidationFailure("ORIGINAL_BODY_HASH_MISMATCH")
    expected = {"report_id": context.report_id, "revision": context.revision,
                "snapshot_id": snapshot.snapshot_id, "bodyHash": body_hash}
    for key, value in expected.items():
        if key in report and report[key] != value:
            raise ValidationFailure("EXISTING_IDENTITY_MISMATCH", key)
    bound = dict(report)
    bound.update(expected)
    bound["context"] = context.to_dict()
    bound["snapshot"] = snapshot.to_dict()
    SourceLock.create(bound).verify(bound)
    result = validate_market_data(bound)
    if result["status"] != "PASS":
        raise ValidationFailure("MARKET_DATA_NOT_PASS")
    return bound

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValidationFailure("OUTPUT_EXISTS")
        def load(path):
            return json.loads(path.read_text(encoding="utf-8-sig"))
        bound = assemble(load(args.report), load(args.context), load(args.snapshot))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(bound, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"status": "READY_FOR_VIEW_AND_SPEC_VALIDATION",
                          "report_id": bound["report_id"],
                          "snapshot_id": bound["snapshot_id"]}))
        return 0
    except (ValidationFailure, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": getattr(exc, "reason", str(exc))},
                         ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
