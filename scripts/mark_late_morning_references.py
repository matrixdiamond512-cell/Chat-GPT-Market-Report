#!/usr/bin/env python3
"""Apply valid 08:00 CME/OSE snapshots and annotate unresolved late captures.

A valid pre-report reference may fill an unavailable structured row. A quote captured
after the report cutoff is diagnostic only and is never backfilled. The textual market
block is regenerated after any change so the report body and structured table agree.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LATEST=ROOT/"data/latest-report.json"
REFERENCE=ROOT/"data/market/morning-reference.json"
UNAVAILABLE=re.compile(r"取得不能|未取得|再実行中|取得継続")


def load(path:Path):return json.loads(path.read_text(encoding="utf-8"))
def dump(path:Path,payload)->None:path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def rewrite_market_block(report:dict)->None:
    text=str(report.get("fullText") or "");rows=((report.get("marketDataTable") or {}).get("rows") or [])
    if not text or len(rows)!=28:return
    block=["【主要市場データ】","項目\t終値・値\t前日比\t騰落率\t方向感"]
    block += ["\t".join(str(row.get(k) or "—") for k in ("label","value","change","rate","direction")) for row in rows]
    pattern=re.compile(r"【主要市場データ】\s*\n.*?(?=\n【[^\n]+】)",re.S)
    if pattern.search(text):report["fullText"]=pattern.sub("\n".join(block),text,count=1)


def main()->int:
    latest_payload=load(LATEST);report=latest_payload.get("latestReport") or latest_payload.get("report") or latest_payload;reference=load(REFERENCE)
    if not isinstance(report,dict) or report.get("time")!="08:00":
        print("Latest report is not 08:00; no morning-reference action needed");return 0
    if reference.get("reportDate")!=report.get("date") or reference.get("reportSlot")!=report.get("time"):
        print("Reference does not match latest 08:00 report; no action");return 0
    rows=((report.get("marketDataTable") or {}).get("rows") or []);by_label={str(row.get("label") or ""):row for row in rows if isinstance(row,dict)}
    applied=[];annotated=[]
    for label,ref in (reference.get("items") or {}).items():
        if not isinstance(ref,dict):continue
        row=by_label.get(label)
        if not row:continue
        current=str(row.get("value") or "")
        status=str(ref.get("status") or "")
        if status.startswith("verified"):
            if UNAVAILABLE.search(current):
                row["value"]=str(ref.get("value") or current)
                row["change"]=str(ref.get("change") or "—")
                row["rate"]=str(ref.get("rate") or "—")
                row["direction"]=str(ref.get("direction") or "—")
                applied.append(label)
            continue
        if status=="reference_after_report" and UNAVAILABLE.search(current):
            as_of=str(ref.get("asOf") or "後刻")
            row["value"]=f"取得不能（08:00時点の参照値を保存できず。{as_of}取得値は時刻違いのため不採用）"
            row["change"]="—";row["rate"]="—";row["direction"]="取得不能";annotated.append(label)
    if applied or annotated:
        report.setdefault("dataProvenance",{})["morningReferencePolicy"]={
            "policy":"pre-report snapshots may fill unavailable rows; post-report references are diagnostic only",
            "appliedPreReport":applied,"annotatedPostReport":annotated,
        }
        rewrite_market_block(report);dump(LATEST,latest_payload)
    print(json.dumps({"appliedPreReport":applied,"annotatedPostReport":annotated},ensure_ascii=False));return 0

if __name__=="__main__":raise SystemExit(main())
