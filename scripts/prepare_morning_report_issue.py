"""Read-only creator entrypoint for an 08:00 report's SAME-RUN evidence.

The caller must supply the frozen ReportContext, acquisition response (or original
snapshot), and original full text. This command neither collects prices nor
publishes. It never reads data/market/latest.json or reconstructs old reports.
"""
import argparse
import json
from pathlib import Path
from capture_morning_creation_evidence import capture, snapshot_from_same_run_acquisition
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot
from reporting.gates import GateFailure

def prepare(context_payload, *, acquisition=None, snapshot=None, title, body):
    if (acquisition is None) == (snapshot is None):
        raise ValueError("EXACTLY_ONE_EVIDENCE_INPUT_REQUIRED")
    context = ReportContext(**context_payload)
    if context.report_time != "08:00":
        raise ValueError("08:00_ONLY")
    frozen = snapshot_from_same_run_acquisition(context_payload, acquisition) if acquisition is not None else MarketDataSnapshot.restore(snapshot)
    return capture(context_payload, frozen.to_dict(), title=title, full_text=body)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--acquisition", type=Path)
    source.add_argument("--snapshot", type=Path)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("OUTPUT_EXISTS")
        def load(path):
            return json.loads(path.read_text(encoding="utf-8-sig"))
        result = prepare(load(args.context),
                         acquisition=load(args.acquisition) if args.acquisition else None,
                         snapshot=load(args.snapshot) if args.snapshot else None,
                         title=args.title, body=args.body.read_text(encoding="utf-8-sig"))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"status":result["evidence_stage"],"report_id":result["report_id"],
                          "snapshot_id":result["snapshot_id"]}))
        return 0
    except (ValueError, TypeError, KeyError, OSError, GateFailure) as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)},ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
