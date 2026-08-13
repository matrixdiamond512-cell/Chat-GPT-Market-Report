#!/usr/bin/env python3
"""Overlay exact-date Japanese close reference onto the 08:00 28-row table.

Only items whose reference date equals the expected previous Japanese session are
accepted. The overlay never changes continuous-market quotes or CME report-time rows.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
LATEST=ROOT/"data/latest-report.json"
REFERENCE=ROOT/"data/market/japan-close-reference.json"
JST=dt.timezone(dt.timedelta(hours=9))

ALLOWED={
    "日経225現物","日経225予想PER","日経225 PBR","日経225予想EPS",
    "日経225 25日移動平均乖離率","日経225 200日移動平均乖離率",
    "東証プライム値上がり銘柄数","東証プライム値下がり銘柄数","東証プライム25日騰落レシオ",
}


def load(path:Path,default:Any)->Any:
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return default


def save(path:Path,payload:Any)->None:
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def expected_prior(report_date:dt.date)->dt.date:
    return report_date-dt.timedelta(days=3 if report_date.weekday()==0 else 1)


def numeric(value:Any)->float|None:
    m=re.search(r"[-+]?\d[\d,]*(?:\.\d+)?",str(value or ""))
    if not m:return None
    try:return float(m.group(0).replace(",",""))
    except ValueError:return None


def direction(label:str,value:str)->str:
    if "乖離率" in label:
        n=numeric(value)
        return "上方乖離" if n and n>0 else "下方乖離" if n and n<0 else "乖離なし"
    return "確定値"


def rewrite_market_block(report:dict[str,Any])->None:
    text=str(report.get("fullText") or "")
    rows=((report.get("marketDataTable") or {}).get("rows") or [])
    if not text or len(rows)!=28:return
    block=["【主要市場データ】","項目\t終値・値\t前日比\t騰落率\t方向感"]
    block += ["\t".join(str(row.get(k) or "—") for k in ("label","value","change","rate","direction")) for row in rows]
    pattern=re.compile(r"【主要市場データ】\s*\n.*?(?=\n【[^\n]+】)",re.S)
    if pattern.search(text):report["fullText"]=pattern.sub("\n".join(block),text,count=1)


def main()->int:
    payload=load(LATEST,{})
    report=payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report,dict) or report.get("time")!="08:00":
        print("Latest report is not 08:00; Japan close overlay skipped");return 0
    report_date=dt.date.fromisoformat(str(report.get("date")))
    expected=expected_prior(report_date)
    ref=load(REFERENCE,{})
    if ref.get("dataDate")!=expected.isoformat():
        print(f"Japan close reference date mismatch: expected {expected}, got {ref.get('dataDate') or 'empty'}");return 0
    rows=((report.get("marketDataTable") or {}).get("rows") or [])
    if len(rows)!=28:raise SystemExit("08:00 marketDataTable must contain 28 rows")
    by={str(r.get("label") or "").strip():r for r in rows if isinstance(r,dict)}
    applied=[]
    for label,item in (ref.get("items") or {}).items():
        if label not in ALLOWED or label not in by or not isinstance(item,dict):continue
        if str(item.get("date") or "")!=expected.isoformat():continue
        value=str(item.get("value") or "").strip()
        if not value:continue
        row=by[label]
        row["value"]=value
        row["change"]="—"
        row["rate"]="—"
        row["direction"]=direction(label,value)
        applied.append(label)
    rewrite_market_block(report)
    report.setdefault("dataProvenance",{})["japanCloseReference"]={
        "dataDate":expected.isoformat(),"appliedAt":dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "appliedLabels":applied,"source":"data/market/japan-close-reference.json",
    }
    save(LATEST,payload)
    print(json.dumps({"dataDate":expected.isoformat(),"applied":applied},ensure_ascii=False))
    return 0


if __name__=="__main__":raise SystemExit(main())
