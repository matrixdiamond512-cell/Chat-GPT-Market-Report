"""Freeze an original 08:00 draft with its existing verified snapshot (G0-G2).

This is an issuance-boundary handoff utility, not a market-data collector,
Drive writer, or evidence of actual publication. Never alters source inputs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot
from reporting.report import ReportObject
from reporting.gates import Transaction, GateFailure

def snapshot_from_same_run_acquisition(context_payload, acquisition):
    """Require each required series to be verified and fresh before freezing G2 evidence."""
    from reporting.gates import SOURCES
    if not isinstance(acquisition, dict) or not isinstance(acquisition.get("markets"), dict):
        raise ValueError("ACQUISITION_MARKETS_INVALID")
    required = {name for name, config in SOURCES.items() if config.get("required")}
    rows = acquisition["markets"]
    if not required.issubset(rows):
        raise ValueError("ACQUISITION_REQUIRED_MARKETS_MISSING")
    for key in required:
        row = rows[key]
        if not isinstance(row, dict) or row.get("id") != key:
            raise ValueError("ACQUISITION_INSTRUMENT_MISMATCH")
        if row.get("verificationStatus") != "verified" or row.get("freshnessStatus") != "fresh":
            raise ValueError("ACQUISITION_UNVERIFIED_OR_STALE")
        if not row.get("sourceId") or not row.get("sourceUrl") or not row.get("asOf"):
            raise ValueError("ACQUISITION_PROVENANCE_MISSING")
    return MarketDataSnapshot.from_acquisition(ReportContext(**context_payload), acquisition)


def capture(context_payload, snapshot_payload, *, title, full_text):
    context = ReportContext(**context_payload)
    snapshot = MarketDataSnapshot.restore(snapshot_payload)
    if context.report_time != "08:00":
        raise ValueError("08:00_ONLY")
    if not isinstance(full_text, str) or not full_text:
        raise ValueError("ORIGINAL_FULL_TEXT_REQUIRED")
    if not isinstance(title, str) or full_text.splitlines()[0] != title:
        raise ValueError("TITLE_BODY_MISMATCH")
    tx = Transaction.begin(context, snapshot)
    report = ReportObject.build(context, snapshot, title, full_text)
    tx = tx.attach_report(report)  # G2; source text and market rows must pass
    assert tx.passed == ("G0", "G1", "G2")
    digest = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    return {
        "capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": context.report_date,
        "time": context.report_time,
        "title": title,
        "report_id": context.report_id,
        "revision": context.revision,
        "snapshot_id": snapshot.snapshot_id,
        "bodyHash": digest,
        "fullText": full_text,
        "context": context.to_dict(),
        "snapshot": snapshot.to_dict(),
        "evidence_stage": "G2_DRAFT_NOT_SAVED",
        "validated_gates": list(tx.passed),
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--context", type=Path, required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path, help="Previously frozen original snapshot")
    source.add_argument("--acquisition", type=Path, help="Same-run verified acquisition JSON; never reconstructed from report")
    p.add_argument("--body", type=Path, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.output.exists():
            raise ValueError("OUTPUT_EXISTS")
        def load(path):
            return json.loads(path.read_text(encoding="utf-8-sig"))
        context_payload = load(a.context)
        if a.acquisition:
            frozen_snapshot = snapshot_from_same_run_acquisition(context_payload, load(a.acquisition))
            snapshot_payload = frozen_snapshot.to_dict()
        else:
            snapshot_payload = load(a.snapshot)
        result = capture(context_payload, snapshot_payload,
                         title=a.title, full_text=a.body.read_text(encoding="utf-8-sig"))
        with a.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"status":"G2_DRAFT_NOT_SAVED","report_id":result["report_id"],
                          "snapshot_id":result["snapshot_id"]}))
        return 0
    except (ValueError, KeyError, TypeError, OSError, GateFailure) as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)},ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
