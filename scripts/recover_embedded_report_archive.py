#!/usr/bin/env python3
"""Recover four *existing* Google-Docs-backed reports from the saved latest envelope.

This does NOT draft market content, call providers or assert independently
authenticated market facts. It only archives previously saved report bodies.
Dry-run is the default; --apply is explicitly required.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SLOTS=("08:00","12:00","16:00","21:00")
# Verified from the four existing native Google Docs by live readback on
# 2026-10-15. One source (12:00) differs in four whitespace glyphs; the
# precise GitHub source text is preserved apart from leading BOM removal.
SOURCE_IDS_20261014={
    "08:00":"1Uay4NSMLVkYjgr-SZUYacUH9yuJ_dFWQ27cvQChhqt0",
    "12:00":"1o9XpixvwL9ZIyAHD-Jn8tfRf8VsjJMa8Jn13-Y85bzE",
    "16:00":"1ZVJa8uk0gJP6DM7sQHgc6M5xWcB185lUMx8L6P2-vrU",
    "21:00":"1lWs4U-tg4T-8ZEN86JU6OxcUqx9uAJkJRZv_b952ojs",
}
JST=timezone(timedelta(hours=9))

def read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path:Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def recover(root:Path,date:str,*,apply:bool)->dict:
    if date!="2026-10-14":
        raise ValueError("UNREVIEWED_SOURCE_DATE_BLOCKED")
    # The recovery is deliberately scoped to the four source documents
    # independently read back during the incident. No arbitrary file import.
    from report_source_contract import validate_saved_body
    from build_reports import _verified_source_revision
    from report_identity import internal_report_key
    envelope=read(root/"data/latest-report.json")
    entries=envelope.get("reports")
    if not isinstance(entries,list) or len(entries)!=4:
        raise ValueError("FOUR_EMBEDDED_SOURCES_REQUIRED")
    byslot={}
    for item in entries:
        if not isinstance(item,dict) or item.get("date")!=date or item.get("time") not in SLOTS:
            raise ValueError("SOURCE_DATE_OR_SLOT_MISMATCH")
        slot=item["time"]
        if slot in byslot:
            raise ValueError("DUPLICATE_EMBEDDED_SLOT")
        doc=item.get("sourceDocument")
        if not isinstance(doc,dict) or doc.get("id")!=SOURCE_IDS_20261014[slot] or (
            doc.get("url")!="https://docs.google.com/document/d/"+doc["id"]+"/edit"
        ):
            raise ValueError("SOURCE_DOC_ID_NOT_PRE_REVIEWED")
        report=copy.deepcopy(item)
        if not isinstance(report.get("fullText"),str):
            raise ValueError("MISSING_ORIGINAL_BODY")
        # Keep source spelling, numbers, paragraphs and sections; only
        # remove the common UTF-8 BOM at the very start of the document.
        report["fullText"]=report["fullText"].lstrip("\ufeff")
        if report.get("revision") not in (None,1):
            raise ValueError("REVISION_CONFLICT")
        report["revision"]=1  # first *GitHub canonical* archive revision
        digest=hashlib.sha256(report["fullText"].encode("utf-8")).hexdigest()
        if report.get("bodyHash") not in (None,digest):
            raise ValueError("EXISTING_BODY_HASH_CONFLICT")
        report["bodyHash"]=digest
        validate_saved_body(report)
        _verified_source_revision(report)
        byslot[slot]=report
    if tuple(sorted(byslot))!=tuple(sorted(SLOTS)):
        raise ValueError("MISSING_EXPECTED_SLOTS")
    now=datetime.now(JST)
    latest=envelope.get("latestReport")
    if not isinstance(latest,dict) or latest.get("date")!=date or latest.get("time")!="21:00":
        raise ValueError("LATEST_POINTER_CHANGED_RECHECK_REQUIRED")
    if datetime.fromisoformat(date+"T21:00:00+09:00")>now:
        raise ValueError("FUTURE_REPORT_NOT_ALLOWED")

    index_path=root/"reports.json"
    index=read(index_path)
    if not isinstance(index,list):
        raise ValueError("INDEX_NOT_ARRAY")
    keyset=set()
    for r in index:
        if not isinstance(r,dict):
            raise ValueError("INVALID_INDEX_ENTRY")
        key=(r.get("date"),r.get("time"))
        if key in keyset:
            raise ValueError("DUPLICATE_INDEX_ENTRY")
        keyset.add(key)
        if key[0]==date and key[1] in SLOTS:
            raise ValueError("EXISTING_INDEX_SOURCE_REQUIRES_SEPARATE_REVIEW")

    planned={}
    for slot,report in byslot.items():
        path=root/"reports"/(date+"_"+slot.replace(":","-")+".json")
        if path.exists():
            if read(path)!=report:
                raise ValueError("EXISTING_CANONICAL_CONFLICT_"+slot)
            planned[slot]="already-identical"
        else:
            planned[slot]="create"
    if not apply:
        return {"status":"DRY_RUN","date":date,"slots":planned,"source_readback":"NORMALIZED_PARAGRAPHS_CHECKED_OUTSIDE_CI"}

    for slot,report in byslot.items():
        if planned[slot]=="create":
            write(root/"reports"/(date+"_"+slot.replace(":","-")+".json"),report)
    envelope["reports"]=[byslot[s] for s in SLOTS]
    envelope["latestReport"]=byslot["21:00"]
    envelope["dataAsOf"]=date+"T21:00:00+09:00"
    write(root/"data/latest-report.json",envelope)
    dashboard=read(root/"data/dashboard.json")
    dashboard["latestReport"]=byslot["21:00"]
    dashboard["currentReportKey"]=internal_report_key(byslot["21:00"])
    dashboard["dataAsOf"]=envelope["dataAsOf"]
    write(root/"data/dashboard.json",dashboard)
    subprocess.run([sys.executable,str(root/"scripts/build_reports.py"),"--canonical-only"],
                   check=True,cwd=root)
    subprocess.run([sys.executable,str(root/"scripts/verify_publication_consistency.py")],
                   check=True,cwd=root)
    for slot in SLOTS:
        subprocess.run([sys.executable,str(root/"scripts/verify_scheduled_report_delivery.py"),
                        "--date",date,"--slot",slot],check=True,cwd=root)
    return {"status":"RECOVERED_VERIFIED_IN_WORKSPACE","date":date,"slots":planned,
            "production_published":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    print(json.dumps(recover(ROOT,args.date,apply=args.apply),ensure_ascii=False))
if __name__=="__main__":
    main()
