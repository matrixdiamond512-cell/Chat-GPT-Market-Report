#!/usr/bin/env python3
"""A failed historical 08:00 QA is expected only for quarantined, known-unverified sources.

Never convert a historical failure into a passing report; keep QA ready=false.
"""
import argparse
import json
from pathlib import Path

def expected_quarantine(reports, qa, date):
    if qa.get("ready") is not False or qa.get("reportDate") != date or qa.get("reportSlot") != "08:00":
        return False
    if qa.get("historicalMode") is not True:
        return False
    if not qa.get("blockingReasons"):
        return False
    matching = [r for r in reports if isinstance(r, dict) and r.get("date") == date and r.get("time") == "08:00"]
    return len(matching) == 1 and matching[0].get("report_status") == "RECONSTRUCTED_UNVERIFIED"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--qa",type=Path,required=True)
    p.add_argument("--reports",type=Path,required=True)
    args=p.parse_args()
    qa=json.loads(args.qa.read_text(encoding="utf-8"))
    reports=json.loads(args.reports.read_text(encoding="utf-8"))
    if not expected_quarantine(reports,qa,args.date):
        raise SystemExit("Historical QA error is NOT an expected quarantined-source failure.")
    print("Expected historical quarantine; source stays unpublished and QA remains ready=false.")

if __name__=="__main__":
    main()
