#!/usr/bin/env python3
"""Capture date-strict Japanese close/valuation/breadth data for next morning report.

The collector accepts only records that explicitly match the target Japan trading
date. Sources that lag are recorded as unavailable and retried by the workflow. No
older value is carried forward under a newer date.

Sources:
- Yahoo daily history: Nikkei close and 25/200-day deviations
- 投資の森: Nikkei PER/PBR/EPS and Prime advancers/decliners
- Traders Web domestic market: Prime/TSE closing volume and turnover when the page
  contains a close block for the exact target date
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market" / "japan-close-reference.json"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"

PER_URL = "https://nikkeiyosoku.com/nikkeiper/"
BREADTH_URL = "https://nikkeiyosoku.com/jp_index_rate/"
TRADERS_URL = "https://www.traders.co.jp/market_jp/"


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    text = raw.decode(encoding, errors="replace")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def yahoo_nikkei(target: dt.date) -> dict[str, Any] | None:
    symbol = "^N225"
    params = urllib.parse.urlencode({"range":"1y","interval":"1d","events":"history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    result = (((payload.get("chart") or {}).get("result") or [None])[0])
    if not isinstance(result, dict):
        return None
    tz_name = str((result.get("meta") or {}).get("exchangeTimezoneName") or "Asia/Tokyo")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Tokyo")
    timestamps = result.get("timestamp") or []
    closes = ((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
    bars: list[tuple[dt.date,float]] = []
    for stamp, raw_close in zip(timestamps, closes):
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close):
            continue
        day = dt.datetime.fromtimestamp(float(stamp), dt.timezone.utc).astimezone(tz).date()
        bars.append((day, close))
    bars.sort(key=lambda x:x[0])
    idx = next((i for i,(day,_) in enumerate(bars) if day == target), None)
    if idx is None:
        return None
    day, close = bars[idx]
    previous = bars[idx-1][1] if idx > 0 else None
    change = close - previous if previous not in (None,0) else None
    rate = change / previous * 100 if change is not None and previous else None
    def dev(period: int) -> float | None:
        if idx+1 < period:
            return None
        values = [value for _,value in bars[idx-period+1:idx+1]]
        average = sum(values)/period
        return (close/average-1)*100 if average else None
    return {
        "date": day.isoformat(), "close": close, "change": change, "rate": rate,
        "dev25": dev(25), "dev200": dev(200),
        "sourceName":"Yahoo Finance Nikkei 225 daily history",
        "sourceUrl":"https://finance.yahoo.com/quote/%5EN225/history/",
    }


def parse_valuation(target: dt.date) -> dict[str, Any] | None:
    text = get_text(PER_URL)
    key = f"{target.month}/{target.day}"
    pattern = re.compile(
        rf"(?:^|\s){re.escape(key)}\s+([0-9,]+(?:\.\d+)?)\s+([+\-]?[0-9,]+(?:\.\d+)?)\s+"
        r"([0-9]+(?:\.\d+)?)\s+([0-9]+(?:\.\d+)?)\s+([0-9,]+(?:\.\d+)?)\s+([0-9,]+(?:\.\d+)?)"
    )
    m = pattern.search(text)
    if not m:
        return None
    num=lambda x: float(x.replace(",",""))
    return {
        "date":target.isoformat(), "nikkei":num(m.group(1)), "change":num(m.group(2)),
        "per":num(m.group(3)), "pbr":num(m.group(4)), "eps":num(m.group(5)), "bps":num(m.group(6)),
        "sourceName":"投資の森 日経平均PER・PBR",
        "sourceUrl":PER_URL,
    }


def parse_breadth(target: dt.date) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    text = get_text(BREADTH_URL)
    row_re = re.compile(
        r"(?<!\d)(\d{1,2})/(\d{1,2})\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+"
        r"([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)"
    )
    rows=[]
    for m in row_re.finditer(text):
        month, day = int(m.group(1)), int(m.group(2))
        try:
            date_value = dt.date(target.year, month, day)
        except ValueError:
            continue
        vals=[int(m.group(i).replace(",","")) for i in range(3,11)]
        rows.append({"date":date_value.isoformat(),"primeAdvancers":vals[2],"primeDecliners":vals[3]})
    current=next((row for row in rows if row["date"]==target.isoformat()),None)
    return current, rows


def compute_ratio25(rows: list[dict[str, Any]], target: dt.date) -> float | None:
    eligible=[r for r in rows if r["date"]<=target.isoformat()]
    eligible.sort(key=lambda r:r["date"])
    tail=eligible[-25:]
    if len(tail)<25:
        return None
    down=sum(int(r["primeDecliners"]) for r in tail)
    up=sum(int(r["primeAdvancers"]) for r in tail)
    return up/down*100 if down else None


def parse_traders_close(target: dt.date) -> dict[str, Any] | None:
    """Parse a Traders Web close block only when its timestamp matches target."""
    text = get_text(TRADERS_URL)
    date_key = target.strftime("%Y/%m/%d")
    candidates: list[str] = []
    for match in re.finditer(re.escape(date_key), text):
        start = max(0, match.start() - 500)
        end = min(len(text), match.start() + 4500)
        block = text[start:end]
        if "出来高" in block and "売買代金" in block and ("騰落" in block or "日経平均" in block):
            candidates.append(block)
    if not candidates:
        return None

    for block in candidates:
        volume_match = re.search(r"出来高\s*([0-9,.]+)\s*(億株|万株|百万株)", block)
        turnover_match = re.search(r"売買代金\s*([0-9,.]+)\s*(兆円|億円)", block)
        breadth_match = re.search(r"騰落\s*上\s*([0-9,]+)\s*/\s*下\s*([0-9,]+)", block)
        if not (volume_match or turnover_match or breadth_match):
            continue
        result: dict[str, Any] = {"date": target.isoformat(), "sourceName":"トレーダーズ・ウェブ 国内市場", "sourceUrl":TRADERS_URL}
        if volume_match:
            raw=float(volume_match.group(1).replace(",",""));unit=volume_match.group(2)
            million = raw*100 if unit=="億株" else raw*0.01 if unit=="万株" else raw
            result["primeVolumeMillionShares"] = million
        if turnover_match:
            raw=float(turnover_match.group(1).replace(",",""));unit=turnover_match.group(2)
            trillion = raw if unit=="兆円" else raw/10000
            result["primeTurnoverTrillionYen"] = trillion
        if breadth_match:
            result["primeAdvancers"] = int(breadth_match.group(1).replace(",",""))
            result["primeDecliners"] = int(breadth_match.group(2).replace(",",""))
        return result
    return None


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--date", default=now_jst().date().isoformat())
    args=parser.parse_args()
    target=dt.date.fromisoformat(args.date)
    items: dict[str,Any]={}
    unavailable: dict[str,str]={}

    try:
        nikkei=yahoo_nikkei(target)
    except Exception as exc:
        nikkei=None; unavailable["日経225現物"]=f"Yahoo取得失敗: {exc}"
    if nikkei:
        items["日経225現物"]={"value":f"{nikkei['close']:,.2f}","date":target.isoformat(),"sourceName":nikkei["sourceName"],"sourceUrl":nikkei["sourceUrl"]}
        if nikkei.get("dev25") is not None:
            items["日経225 25日移動平均乖離率"]={"value":f"{nikkei['dev25']:+.2f}%","date":target.isoformat(),"sourceName":nikkei["sourceName"],"sourceUrl":nikkei["sourceUrl"]}
        if nikkei.get("dev200") is not None:
            items["日経225 200日移動平均乖離率"]={"value":f"{nikkei['dev200']:+.2f}%","date":target.isoformat(),"sourceName":nikkei["sourceName"],"sourceUrl":nikkei["sourceUrl"]}
    elif "日経225現物" not in unavailable:
        unavailable["日経225現物"]=f"{target.isoformat()}の確定日足がソースに未反映"

    try:
        valuation=parse_valuation(target)
    except Exception as exc:
        valuation=None; unavailable["日経225予想PER/PBR/EPS"]=f"取得失敗: {exc}"
    if valuation:
        for label,key,suffix in (("日経225予想PER","per","倍"),("日経225 PBR","pbr","倍"),("日経225予想EPS","eps","円")):
            items[label]={"value":f"{valuation[key]:,.2f}{suffix}","date":target.isoformat(),"sourceName":valuation["sourceName"],"sourceUrl":valuation["sourceUrl"]}
    elif "日経225予想PER/PBR/EPS" not in unavailable:
        unavailable["日経225予想PER/PBR/EPS"]=f"{target.isoformat()}行がソースに未反映"

    try:
        breadth, history=parse_breadth(target)
    except Exception as exc:
        breadth=None; history=[]; unavailable["東証プライム騰落"]=f"取得失敗: {exc}"
    if breadth:
        items["東証プライム値上がり銘柄数"]={"value":str(breadth["primeAdvancers"]),"date":target.isoformat(),"sourceName":"投資の森 値上がり・値下がり銘柄数","sourceUrl":BREADTH_URL}
        items["東証プライム値下がり銘柄数"]={"value":str(breadth["primeDecliners"]),"date":target.isoformat(),"sourceName":"投資の森 値上がり・値下がり銘柄数","sourceUrl":BREADTH_URL}
        ratio=compute_ratio25(history,target)
        if ratio is not None:
            items["東証プライム25日騰落レシオ"]={"value":f"{ratio:.2f}%","date":target.isoformat(),"sourceName":"投資の森 東証プライム騰落銘柄数から25営業日で算出","sourceUrl":BREADTH_URL}
        else:
            unavailable["東証プライム25日騰落レシオ"]=f"{target.isoformat()}までの連続25営業日分を同一ソースから取得できず"
    elif "東証プライム騰落" not in unavailable:
        unavailable["東証プライム騰落"]=f"{target.isoformat()}行がソースに未反映"

    try:
        traders=parse_traders_close(target)
    except Exception as exc:
        traders=None; unavailable["東証プライム売買高"]=f"トレーダーズ・ウェブ取得失敗: {exc}"
    if traders:
        if traders.get("primeVolumeMillionShares") is not None:
            value=float(traders["primeVolumeMillionShares"])
            items["東証プライム売買高"]={"value":f"{value:,.0f}百万株","date":target.isoformat(),"sourceName":traders["sourceName"],"sourceUrl":traders["sourceUrl"]}
            unavailable.pop("東証プライム売買高",None)
        if traders.get("primeTurnoverTrillionYen") is not None:
            value=float(traders["primeTurnoverTrillionYen"])
            items["東証プライム売買代金"]={"value":f"{value:.2f}兆円","date":target.isoformat(),"sourceName":traders["sourceName"],"sourceUrl":traders["sourceUrl"]}
        if "東証プライム値上がり銘柄数" not in items and traders.get("primeAdvancers") is not None:
            items["東証プライム値上がり銘柄数"]={"value":str(traders["primeAdvancers"]),"date":target.isoformat(),"sourceName":traders["sourceName"],"sourceUrl":traders["sourceUrl"]}
        if "東証プライム値下がり銘柄数" not in items and traders.get("primeDecliners") is not None:
            items["東証プライム値下がり銘柄数"]={"value":str(traders["primeDecliners"]),"date":target.isoformat(),"sourceName":traders["sourceName"],"sourceUrl":traders["sourceUrl"]}
    elif "東証プライム売買高" not in unavailable:
        unavailable["東証プライム売買高"]=f"{target.isoformat()}の大引けブロックがトレーダーズ・ウェブに取得時点で見つからず"

    required=["日経225現物","日経225予想PER","日経225 PBR","日経225予想EPS","日経225 25日移動平均乖離率","日経225 200日移動平均乖離率","東証プライム売買高","東証プライム値上がり銘柄数","東証プライム値下がり銘柄数","東証プライム25日騰落レシオ"]
    payload={
        "schemaVersion":"1.1.0","generatedAt":now_jst().isoformat(),"dataDate":target.isoformat(),
        "complete": all(label in items for label in required),
        "items":items,"unavailable":unavailable,
        "rule":"accept exact target-date records only; never carry stale records forward",
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"date":target.isoformat(),"itemCount":len(items),"complete":payload["complete"],"unavailable":unavailable},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
