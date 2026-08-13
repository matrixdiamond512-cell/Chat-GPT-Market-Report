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

def parse_cme(text:str,currency:str)->dict[str,str]|None:
    marker="CME￥" if currency=="yen" else "CME＄"
    pattern=re.compile(re.escape(marker)+r"\s+26年09月限\s+([0-9,]+)\s+([+\-][0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2}|\d{2}/\d{2})")
    match=pattern.search(text)
    if not match:return None
    value=number(match.group(1));change=number(match.group(2));stamp=match.group(6)
    return {"value":fmt_integer(value),"change":f"{change:+,.0f}","rate":pct_from_change(value,change),"direction":"上昇" if change>0 else "下落" if change<0 else "横ばい","stamp":stamp,"stampType":"time" if ":" in stamp else "date"}

def parse_ose(text:str)->dict[str,str]|None:
    pattern=re.compile(r"大証ラージ\s+26年9月限\s+([0-9,]+)\s+([+\-][0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2})")
    match=pattern.search(text)
    if not match:return None
    value=number(match.group(1));change=number(match.group(2))
    return {"value":f"{fmt_integer(value)}円","change":f"{change:+,.0f}","rate":pct_from_change(value,change),"direction":"上昇" if change>0 else "下落" if change<0 else "横ばい","time":match.group(7)}

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
    parser=argparse.ArgumentParser();parser.add_argument("--report-date",default=now_jst().date().isoformat());parser.add_argument("--slot",default="08:00");args=parser.parse_args()
    report_date=dt.date.fromisoformat(args.report_date);text=get_text(SOURCE_URL)
    yen=parse_cme(text,"yen");dollar=parse_cme(text,"dollar");ose=parse_ose(text)
    attempted:dict[str,dict[str,object]]={};reference_dates:list[str]=[]
    for label,parsed,product in (("CME日経225先物・円建て",yen,"CME NIY"),("CME日経225先物・ドル建て",dollar,"CME NKD")):
        if not parsed:continue
        as_of=cme_as_of(report_date,parsed)
        if parsed.get("stampType")=="date":reference_dates.append(as_of[:10])
        status=reference_status(as_of,report_date,args.slot);base="26年09月限のページ上最終表示値。CME公式清算値ではないため、その区別を維持する。"
        attempted[label]={"value":parsed["value"],"change":parsed["change"],"rate":parsed["rate"],"direction":parsed["direction"],"asOf":as_of,"sourceName":f"nikkei225jp.com {product}","sourceUrl":SOURCE_URL,"status":status,"note":note_for_status(base,status,args.slot)}
    if ose:
        as_of=f"{report_date.isoformat()}T{ose['time']}:00+09:00";status=reference_status(as_of,report_date,args.slot);base="大証ラージ26年9月限。JPX/OSEの値とクロスチェックして使用する。"
        attempted["日経225先物（大阪取引所）"]={"value":ose["value"],"change":ose["change"],"rate":ose["rate"],"direction":ose["direction"],"asOf":as_of,"sourceName":"JPX/OSE mirrored quote on nikkei225jp.com","sourceUrl":SOURCE_URL,"status":status,"note":note_for_status(base,status,args.slot)}
    if not attempted:raise SystemExit("No morning reference values parsed")

    existing=load_existing(report_date,args.slot);old_items=existing.get("items") or {};items=dict(old_items)
    for label,item in attempted.items():items[label]=choose_item(old_items.get(label),item)
    payload={"schemaVersion":"1.3.0","generatedAt":now_jst().isoformat(),"reportDate":report_date.isoformat(),"reportSlot":args.slot,"referenceDate":max(reference_dates) if reference_dates else existing.get("referenceDate") or report_date.isoformat(),"reportCutoff":slot_cutoff(report_date,args.slot).isoformat(),"items":items,"lastAttempt":{"at":now_jst().isoformat(),"items":attempted},"preservationRule":"verified pre-report snapshots are never overwritten by post-report retries"}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"reportDate":payload["reportDate"],"verified":[k for k,v in items.items() if verified(v)],"attemptStatus":{k:v.get("status") for k,v in attempted.items()}},ensure_ascii=False))
    return 0

if __name__=="__main__":raise SystemExit(main())
