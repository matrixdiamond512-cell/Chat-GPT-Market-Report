"""Report producer readiness command. No OpenAI cost, no GitHub/Drive writes.

Example:
 python -m scripts.reporting.d3_release_preflight_cli \
   --date 2026-10-14 --slot 21:00 \
   --market data/market/history/2026-10-14_21-00.json \
   --evidence private/report-evidence-2026-10-14_21-00.json

Blocked report preflights exit nonzero by default; --diagnostic is only
for the CI monitoring view and never authorizes API execution.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .context import ReportContext
from .d3_release_evidence import inspect_saved_input


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    parser.add_argument("--slot",required=True,choices=["08:00","12:00","16:00","21:00"])
    parser.add_argument("--market",required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--diagnostic",action="store_true")
    args=parser.parse_args(argv)
    context=ReportContext.create(args.date,args.slot,
                                 args.date+"T"+args.slot+":00+09:00",
                                 mode="historical")
    try:
        markets=json.loads(Path(args.market).read_text(encoding="utf-8"))
    except (OSError,ValueError) as exc:
        markets=None
    try:
        evidence=json.loads(Path(args.evidence).read_text(encoding="utf-8")) if args.evidence else None
    except (OSError,ValueError):
        evidence=None
    review=inspect_saved_input(context=context,payload=markets,evidence=evidence)
    print(json.dumps(asdict(review),ensure_ascii=False,sort_keys=True))
    return 0 if (args.diagnostic or review.ready) else 3


if __name__=="__main__":
    raise SystemExit(main())
