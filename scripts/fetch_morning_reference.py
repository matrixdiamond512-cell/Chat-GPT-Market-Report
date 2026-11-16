#!/usr/bin/env python3
"""Fetch source-verified morning CME/OSE reference values.

Snapshots captured at or before the report cutoff are durable: a later delayed GitHub
Actions retry must never overwrite a valid pre-report snapshot with a post-report
quote. Multiple pre-report captures keep the latest valid timestamp. Post-report
quotes are retained only as diagnostics when no valid snapshot exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
JST=dt.timezone(dt.timedelta(hours=9))
SOURCE_URL="https://nikkei225jp.com/cme/"
OUT=ROOT/"data"/"market"/"morning-reference.json"
USER_AGENT="Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"
REPORT_GRACE_MINUTES=5


def now_jst()->dt.datetime:return dt.datetime.now(JST).replace(microsecond=0)

def strip_tags(value:str)->str:
    value=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",value)
    value=re.sub(r"(?s)<[^>]+>"," ",value)
    return html.unescape(re.sub(r"\s+"," ",value)).strip()

def get_text(url:str)->str:
    request=urllib.request.Request(url,headers={"User-Agent":USER_AGENT})
    with urllib.request.urlopen(request,timeout=25) as response:
        raw=response.read();encoding=response.headers.get_content_charset() or "utf-8"
    return strip_tags(raw.decode(encoding,errors="replace"))

def number(value:str)->float:return float(value.replace(",",""))

def pct_from_change(value:float,change:float)->str:
    previous=value-change
    return "" if previous==0 else f"{(change/previous)*100:+.2f}%"

def fmt_integer(value:float)->str:return f"{value:,.0f}"

def _active_month_codes(year: int, month: int) -> list[tuple[int, int, str]]:
    """Return current and nearby quarterly futures expiries, newest first."""
    contracts: list[tuple[int, int, str]] = []
    for offset in range(0, 15):
        absolute = year * 12 + month - 1 + offset
        contract_year, month0 = divmod(absolute, 12)
        contract_month = month0 + 1
        if contract_month in {3, 6, 9, 12}:
            contracts.append((contract_year, contract_month, f"{contract_year % 100:02d}年{contract_month:02d}月限"))
    return contracts


def _quarterly_contract_for_date(year: int, month: int, *, roll_months_before: int = 1) -> tuple[int, int, str]:
    """Choose the nearest quarterly contract, rolling before its delivery month."""
    threshold = year * 12 + month - 1 + roll_months_before
    for contract_year, contract_month, label in _active_month_codes(year, month):
        if contract_year * 12 + contract_month - 1 >= threshold:
            return contract_year, contract_month, label
    raise ValueError(f"no quarterly contract found for {year}-{month:02d}")


def _contract_for_delivery_label(year: int, month: int) -> tuple[int, int, str]:
    return year, month, f"{year % 100:02d}年{month:02d}月限"


def parse_cme(text:str,currency:str,as_of:dt.date|None=None)->dict[str,str]|None:
    marker="CME￥" if currency=="yen" else "CME＄"
    session_date=as_of or dt.date.today()
    candidates: list[tuple[int, int, str]] = []
    year = session_date.year
    for offset in range(1, 4):
        absolute = year * 12 + session_date.month - 1 + offset
        contract_year, month0 = divmod(absolute, 12)
        contract_month = month0 + 1
        if contract_month in {3, 6, 9, 12} and contract_year * 12 + contract_month - 1 >= session_date.year * 12 + session_date.month:
            candidates.append(_contract_for_delivery_label(contract_year, contract_month))
    front_contract = _quarterly_contract_for_date(session_date.year, session_date.month)[2]
    candidates.extend(_active_month_codes(session_date.year, session_date.month)[:4])
    for _, _, expiry in dict.fromkeys(candidates):
        pattern=re.compile(re.escape(marker)+r"\s+"+re.escape(expiry)+r"\s+([0-9,]+)\s+([+\-][0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2}|\d{2}/\d{2})")
        match=pattern.search(text)
        if not match:continue
        value=number(match.group(1));change=number(match.group(2));stamp=match.group(6)
        return {"value":fmt_integer(value),"change":f"{change:+,.0f}","rate":pct_from_change(value,change),"direction":"上昇" if change>0 else "下落" if change<0 else "横ばい","stamp":stamp,"stampType":"time" if ":" in stamp else "date","contract":expiry,"contractIsFront":expiry==front_contract}
    return None

def parse_ose(text:str,as_of:dt.date|None=None)->dict[str,str]|None:
    session_date=as_of or dt.date.today()
    candidates = []
    for offset in range(1, 4):
        absolute = session_date.year * 12 + session_date.month - 1 + offset
        contract_year, month0 = divmod(absolute, 12)
        contract_month = month0 + 1
        if contract_month in {3, 6, 9, 12} and contract_year * 12 + contract_month - 1 >= session_date.year * 12 + session_date.month:
            candidates.append(_contract_for_delivery_label(contract_year, contract_month))
    front_contract = _quarterly_contract_for_date(session_date.year, session_date.month)[2]
    candidates.extend(_active_month_codes(session_date.year, session_date.month)[:4])
    for _, _, expiry in dict.fromkeys(candidates):
        pattern=re.compile(r"大証ラージ\s+"+re.escape(expiry)+r"\s+([0-9,]+)\s+([+\-][0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2})")
        match=pattern.search(text)
        if not match:continue
        value=number(match.group(1));change=number(match.group(2))
        return {"value":f"{fmt_integer(value)}円","change":f"{change:+,.0f}","rate":pct_from_change(value,change),"direction":"上昇" if change>0 else "下落" if change<0 else "横ばい","time":match.group(7),"contract":expiry,"contractIsFront":expiry==front_contract}
    return None

def cme_as_of(report_date:dt.date,parsed:dict[str,str])->str:
    if parsed.get("stampType")=="time":return f"{report_date.isoformat()}T{parsed['stamp']}:00+09:00"
    month,day=(int(part) for part in parsed["stamp"].split("/"))
    return dt.date(report_date.year,month,day).isoformat()

def slot_cutoff(report_date:dt.date,slot:str)->dt.datetime:
    hour,minute=(int(part) for part in slot.split(":"))
    return dt.datetime.combine(report_date,dt.time(hour,minute),tzinfo=JST)+dt.timedelta(minutes=REPORT_GRACE_MINUTES)

def parse_asof(value:str)->dt.datetime|None:
    if not value or "T" not in value:return None
    try:return dt.datetime.fromisoformat(value).astimezone(JST)
    except ValueError:return None

def reference_status(as_of:str,report_date:dt.date,slot:str)->str:
    if "T" not in as_of:return "verified_reference"
    parsed=parse_asof(as_of)
    if parsed is None:return "reference_invalid_time"
    return "verified_reference" if parsed<=slot_cutoff(report_date,slot) else "reference_after_report"

def note_for_status(base:str,status:str,slot:str)->str:
    return base+(f" {slot}より後の時刻なので当該レポートの値には上書きしない。" if status=="reference_after_report" else "")

def verified(item:dict[str,Any]|None)->bool:
    return isinstance(item,dict) and str(item.get("status") or "").startswith("verified")

def choose_item(old:dict[str,Any]|None,new:dict[str,Any])->dict[str,Any]:
    # A verified pre-report snapshot always beats a later diagnostic quote.
    if verified(old) and not verified(new):return dict(old)
    if not verified(old) and verified(new):return new
    if verified(old) and verified(new):
        old_dt=parse_asof(str(old.get("asOf") or ""));new_dt=parse_asof(str(new.get("asOf") or ""))
        if old_dt and new_dt:return new if new_dt>=old_dt else dict(old)
        # Date-only values are valid close references; prefer newly fetched value.
        return new
    return new

def load_existing(report_date:dt.date,slot:str)->dict[str,Any]:
    try:payload=json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return {}
    if payload.get("reportDate")!=report_date.isoformat() or payload.get("reportSlot")!=slot:return {}
    return payload


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--report-date",default=now_jst().date().isoformat());parser.add_argument("--slot",default="08:00");parser.add_argument("--input-path",default="");parser.add_argument("--output-path",default="");args=parser.parse_args()
    report_date=dt.date.fromisoformat(args.report_date);text=get_text(SOURCE_URL)
    yen=parse_cme(text,"yen",report_date);dollar=parse_cme(text,"dollar",report_date);ose=parse_ose(text,report_date)
    attempted:dict[str,dict[str,object]]={};reference_dates:list[str]=[]
    for label,parsed,product in (("CME日経225先物・円建て",yen,"CME NIY"),("CME日経225先物・ドル建て",dollar,"CME NKD")):
        if not parsed:continue
        as_of=cme_as_of(report_date,parsed)
        if parsed.get("stampType")=="date":reference_dates.append(as_of[:10])
        status=reference_status(as_of,report_date,args.slot);base=f"{parsed.get('contract')}のページ上最終表示値。CME公式清算値ではないため、その区別を維持する。"
        attempted[label]={"value":parsed["value"],"change":parsed["change"],"rate":parsed["rate"],"direction":parsed["direction"],"asOf":as_of,"contract":parsed["contract"],"contractIsFront":parsed.get("contractIsFront",False),"sourceName":f"nikkei225jp.com {product}","sourceUrl":SOURCE_URL,"status":status,"note":note_for_status(base,status,args.slot)}
    if ose:
        as_of=f"{report_date.isoformat()}T{ose['time']}:00+09:00";status=reference_status(as_of,report_date,args.slot);base=f"大証ラージ{ose.get('contract')}。JPX/OSEの値とクロスチェックして使用する。"
        attempted["日経225先物（大阪取引所）"]={"value":ose["value"],"change":ose["change"],"rate":ose["rate"],"direction":ose["direction"],"asOf":as_of,"contract":ose["contract"],"contractIsFront":ose.get("contractIsFront",False),"sourceName":"JPX/OSE mirrored quote on nikkei225jp.com","sourceUrl":SOURCE_URL,"status":status,"note":note_for_status(base,status,args.slot)}
    if not attempted:raise SystemExit("No morning reference values parsed")

    if args.input_path:
        source_path=Path(args.input_path)
        try: existing=json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): existing={}
        if existing.get("reportDate")!=report_date.isoformat() or existing.get("reportSlot")!=args.slot:
            raise SystemExit("Input market reference JSON must match the report date and slot")
        old_items=existing.get("items") or {};items=dict(old_items)
    else:
        existing=load_existing(report_date,args.slot);old_items=existing.get("items") or {};items=dict(old_items)
    for label,item in attempted.items():items[label]=choose_item(old_items.get(label),item)
    payload={"schemaVersion":"1.3.0","generatedAt":now_jst().isoformat(),"reportDate":report_date.isoformat(),"reportSlot":args.slot,"referenceDate":max(reference_dates) if reference_dates else existing.get("referenceDate") or report_date.isoformat(),"reportCutoff":slot_cutoff(report_date,args.slot).isoformat(),"items":items,"lastAttempt":{"at":now_jst().isoformat(),"items":attempted},"preservationRule":"verified pre-report snapshots are never overwritten by post-report retries"}
    output_path=Path(args.output_path) if args.output_path else OUT
    output_path.parent.mkdir(parents=True,exist_ok=True);output_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"reportDate":payload["reportDate"],"verified":[k for k,v in items.items() if verified(v)],"attemptStatus":{k:v.get("status") for k,v in attempted.items()}},ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main())
