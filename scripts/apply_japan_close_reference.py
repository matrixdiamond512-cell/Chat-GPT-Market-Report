#!/usr/bin/env python3
"""Fill unavailable Japanese close rows in the 08:00 table from exact-date captures.

The 08:00 report is a previous-close report. Japanese close/valuation/breadth values
come from data/market/japan-close-reference.json. Japan 10-year JGB yield is reused
from the dedicated rates/bonds dataset when that dataset has a confirmed observation
for the exact prior Japanese session. This removes the unnecessary dependency on a
private Google Sheet for data that the portal has already verified elsewhere.

Only exact-date records are accepted. Existing usable rows are preserved, so a
complete row is never degraded by a value-only overlay.
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
RATES=ROOT/"data/rates-bonds.json"
JST=dt.timezone(dt.timedelta(hours=9))
UNAVAILABLE=re.compile(r"取得不能|未取得|未公表|取得継続|入力に値なし")

ALLOWED={
    "日経225現物","日経225予想PER","日経225 PBR","日経225予想EPS",
    "日経225 25日移動平均乖離率","日経225 200日移動平均乖離率",
    "東証プライム売買代金","東証プライム売買高",
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
        return "上方乖離" if n is not None and n>0 else "下方乖離" if n is not None and n<0 else "乖離なし"
    return "確定値"


def rewrite_market_block(report:dict[str,Any])->None:
    text=str(report.get("fullText") or "")
    rows=((report.get("marketDataTable") or {}).get("rows") or [])
    if not text or len(rows)!=28:return
    block=["【主要市場データ】","項目\t終値・値\t前日比\t騰落率\t方向感"]
    block += ["\t".join(str(row.get(k) or "—") for k in ("label","value","change","rate","direction")) for row in rows]
    pattern=re.compile(r"【主要市場データ】\s*\n.*?(?=\n【[^\n]+】)",re.S)
    if pattern.search(text):report["fullText"]=pattern.sub("\n".join(block),text,count=1)


def apply_rates_reference(by:dict[str,dict[str,Any]],expected:dt.date)->dict[str,Any]:
    result={"applied":[],"reason":""}
    row=by.get("日本10年国債利回り")
    if not isinstance(row,dict):
        result["reason"]="market table row missing"
        return result
    current=str(row.get("value") or "").strip()
    if current and not UNAVAILABLE.search(current):
        result["reason"]="existing usable value preserved"
        return result

    payload=load(RATES,{})
    rates=payload.get("rates") if isinstance(payload,dict) else None
    if not isinstance(rates,list):
        result["reason"]="rates-bonds dataset missing"
        return result

    item=next((x for x in rates if isinstance(x,dict) and x.get("name")=="日本10年国債利回り"),None)
    if not isinstance(item,dict):
        result["reason"]="Japan 10Y row missing in rates-bonds"
        return result
    if str(item.get("asOf") or "")!=expected.isoformat():
        result["reason"]=f"rates-bonds date mismatch: {item.get('asOf') or 'empty'}"
        return result
    if str(item.get("status") or "").lower() not in {"confirmed","verified"}:
        result["reason"]=f"rates-bonds status not confirmed: {item.get('status') or 'empty'}"
        return result

    value=numeric(item.get("value"))
    if value is None:
        result["reason"]="Japan 10Y value is not numeric"
        return result
    change=numeric(item.get("changeBp"))
    row["value"]=f"{value:.3f}%"
    row["change"]=(f"{change:+.1f}bp" if change is not None else "—")
    row["rate"]="—"
    row["direction"]=("上昇" if change is not None and change>0 else "低下" if change is not None and change<0 else "横ばい")
    result["applied"].append("日本10年国債利回り")
    result["source"]=str(item.get("source") or "data/rates-bonds.json")
    result["asOf"]=str(item.get("asOf") or "")
    return result


def main()->int:
    payload=load(LATEST,{})
    report=payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report,dict) or report.get("time")!="08:00":
        print("Latest report is not 08:00; Japan close overlay skipped");return 0
    report_date=dt.date.fromisoformat(str(report.get("date")))
    expected=expected_prior(report_date)
    rows=((report.get("marketDataTable") or {}).get("rows") or [])
    if len(rows)!=28:raise SystemExit("08:00 marketDataTable must contain 28 rows")
    by={str(r.get("label") or "").strip():r for r in rows if isinstance(r,dict)}

    applied=[];preserved=[]
    ref=load(REFERENCE,{})
    if ref.get("dataDate")==expected.isoformat():
        for label,item in (ref.get("items") or {}).items():
            if label not in ALLOWED or label not in by or not isinstance(item,dict):continue
            if str(item.get("date") or "")!=expected.isoformat():continue
            value=str(item.get("value") or "").strip()
            if not value:continue
            row=by[label]
            current=str(row.get("value") or "").strip()
            if current and not UNAVAILABLE.search(current):
                preserved.append(label);continue
            row["value"]=value
            row["change"]="—"
            row["rate"]="—"
            row["direction"]=direction(label,value)
            applied.append(label)
    else:
        print(f"Japan close reference date mismatch: expected {expected}, got {ref.get('dataDate') or 'empty'}")

    rates_result=apply_rates_reference(by,expected)
    applied += rates_result.get("applied") or []

    if applied:rewrite_market_block(report)
    report.setdefault("dataProvenance",{})["japanCloseReference"]={
        "dataDate":expected.isoformat(),"appliedAt":dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "appliedLabels":applied,"preservedUsableLabels":preserved,
        "source":"data/market/japan-close-reference.json",
        "ratesReference":rates_result,
    }
    save(LATEST,payload)
    print(json.dumps({"dataDate":expected.isoformat(),"applied":applied,"preserved":preserved,"rates":rates_result},ensure_ascii=False))
    return 0


if __name__=="__main__":raise SystemExit(main())
