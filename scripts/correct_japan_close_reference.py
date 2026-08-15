#!/usr/bin/env python3
"""Cross-check and correct the exact-date Nikkei close reference.

Yahoo's daily chart can occasionally expose a value that is not the official Tokyo
close for the requested session. The valuation page already used by this project
contains an exact-date Nikkei close and daily change alongside PER/PBR/EPS. Treat
that exact-date row as the close anchor, then use the historical daily series only
for the moving-average window calculation after replacing the target-day close.

This script patches data/market/japan-close-reference.json in place. It never carries
an older valuation row forward to a newer date.
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
REFERENCE = ROOT / "data" / "market" / "japan-close-reference.json"
PER_URL = "https://nikkeiyosoku.com/nikkeiper/"
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"
JST = dt.timezone(dt.timedelta(hours=9))


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    text = raw.decode(encoding, errors="replace")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_valuation(target: dt.date) -> dict[str, float] | None:
    text = get_text(PER_URL)
    key = f"{target.month}/{target.day}"
    pattern = re.compile(
        rf"(?:^|\s){re.escape(key)}\s+([0-9,]+(?:\.\d+)?)\s+([+\-]?[0-9,]+(?:\.\d+)?)\s+"
        r"([0-9]+(?:\.\d+)?)\s+([0-9]+(?:\.\d+)?)\s+([0-9,]+(?:\.\d+)?)\s+([0-9,]+(?:\.\d+)?)"
    )
    m = pattern.search(text)
    if not m:
        return None
    num = lambda value: float(value.replace(",", ""))
    return {
        "close": num(m.group(1)),
        "change": num(m.group(2)),
        "per": num(m.group(3)),
        "pbr": num(m.group(4)),
        "eps": num(m.group(5)),
        "bps": num(m.group(6)),
    }


def yahoo_bars() -> tuple[list[tuple[dt.date, float]], str]:
    symbol = "^N225"
    params = urllib.parse.urlencode({"range": "1y", "interval": "1d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    result = (((payload.get("chart") or {}).get("result") or [None])[0])
    if not isinstance(result, dict):
        raise RuntimeError("Yahoo chart returned no result")
    tz_name = str((result.get("meta") or {}).get("exchangeTimezoneName") or "Asia/Tokyo")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Tokyo")
    timestamps = result.get("timestamp") or []
    closes = ((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
    bars: list[tuple[dt.date, float]] = []
    for stamp, raw_close in zip(timestamps, closes):
        try:
            value = float(raw_close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        day = dt.datetime.fromtimestamp(float(stamp), dt.timezone.utc).astimezone(tz).date()
        bars.append((day, value))
    bars.sort(key=lambda item: item[0])
    return bars, "https://finance.yahoo.com/quote/%5EN225/history/"


def deviation(bars: list[tuple[dt.date, float]], idx: int, period: int) -> float | None:
    if idx + 1 < period:
        return None
    values = [value for _, value in bars[idx - period + 1 : idx + 1]]
    average = sum(values) / period
    return (bars[idx][1] / average - 1.0) * 100.0 if average else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    target = dt.date.fromisoformat(args.date)

    payload = load(REFERENCE)
    if str(payload.get("dataDate") or "") != target.isoformat():
        raise SystemExit(f"Japan close reference date mismatch: {payload.get('dataDate')} != {target}")

    valuation = parse_valuation(target)
    if not valuation:
        print(f"Exact-date valuation row for {target} is not available; correction skipped")
        return 0

    close = float(valuation["close"])
    change = float(valuation["change"])
    previous = close - change
    rate = change / previous * 100.0 if previous else 0.0

    items = payload.setdefault("items", {})
    old_close_text = str((items.get("日経225現物") or {}).get("value") or "")
    old_close = None
    try:
        old_close = float(old_close_text.replace(",", ""))
    except (TypeError, ValueError):
        pass

    items["日経225現物"] = {
        "value": f"{close:,.2f}",
        "change": f"{change:+,.2f}",
        "rate": f"{rate:+.2f}%",
        "direction": "上昇" if change > 0 else "下落" if change < 0 else "横ばい",
        "date": target.isoformat(),
        "sourceName": "投資の森 日経平均PER・PBR（同日終値・前日差）",
        "sourceUrl": PER_URL,
        "status": "exact_date_close_anchor",
    }

    yahoo_raw = None
    try:
        bars, yahoo_url = yahoo_bars()
        idx = next((i for i, (day, _) in enumerate(bars) if day == target), None)
        if idx is not None:
            yahoo_raw = bars[idx][1]
            bars[idx] = (target, close)
            dev25 = deviation(bars, idx, 25)
            dev200 = deviation(bars, idx, 200)
            if dev25 is not None:
                items["日経225 25日移動平均乖離率"] = {
                    "value": f"{dev25:+.2f}%",
                    "date": target.isoformat(),
                    "sourceName": "Yahoo Finance日足履歴（対象日終値は投資の森同日値で補正）",
                    "sourceUrl": yahoo_url,
                    "status": "calculated_with_exact_date_close_anchor",
                }
            if dev200 is not None:
                items["日経225 200日移動平均乖離率"] = {
                    "value": f"{dev200:+.2f}%",
                    "date": target.isoformat(),
                    "sourceName": "Yahoo Finance日足履歴（対象日終値は投資の森同日値で補正）",
                    "sourceUrl": yahoo_url,
                    "status": "calculated_with_exact_date_close_anchor",
                }
    except Exception as exc:
        payload.setdefault("warnings", []).append(f"Nikkei deviation recalculation failed: {exc}")

    payload.setdefault("qualityChecks", {})["nikkeiCloseCrossCheck"] = {
        "checkedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "targetDate": target.isoformat(),
        "authoritativeClose": close,
        "authoritativeChange": change,
        "previousCloseDerived": previous,
        "oldReferenceClose": old_close,
        "yahooTargetDayRawClose": yahoo_raw,
        "differenceVsYahoo": (close - yahoo_raw) if yahoo_raw is not None else None,
        "rule": "Exact-date valuation-page close anchors the session; Yahoo is used only for the historical moving-average window after target-close replacement.",
    }
    payload["generatedAt"] = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    save(REFERENCE, payload)
    print(json.dumps(payload["qualityChecks"]["nikkeiCloseCrossCheck"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
