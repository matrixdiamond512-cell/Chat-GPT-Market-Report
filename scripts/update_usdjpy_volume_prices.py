"""Backfill the Tokyo spot-volume dashboard's missing USD/JPY DAILY OHLC.

BOJ spot turnover and Yahoo Finance daily FX candles are DIFFERENT data series.
Do not replace BOJ turnover with an FX quote provider's tick volume.
Existing Investing.com candles are preserved; newer missing candles are
labelled as Yahoo Finance data rather than misrepresented as Investing.com.
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PATH = Path(__file__).resolve().parents[1] / "data" / "usdjpy-volume.json"
JST = ZoneInfo("Asia/Tokyo")
SYMBOL = "JPY=X"  # Yahoo Finance: 1 US dollar in Japanese yen (NOT JPYUSD=X).
SOURCE_URL = "https://finance.yahoo.com/quote/JPY=X/history/"
FIELDS = ("open", "high", "low", "close")


def fetch_yahoo() -> dict[str, dict]:
    """Get DAILY USDJPY candles; try both Yahoo chart hosts with bounded retries."""
    errors = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = (f"https://{host}/v8/finance/chart/{SYMBOL}?"
               + urllib.parse.urlencode({"range": "2y", "interval": "1d"}))
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                    "Accept": "application/json", "Accept-Language": "en-US,en;q=0.8",
                })
                with urllib.request.urlopen(req, timeout=22) as response:
                    payload = json.load(response)
                result = (payload.get("chart", {}).get("result") or [None])[0]
                if not result or result.get("meta", {}).get("currency") != "JPY":
                    raise ValueError("USD/JPY symbol or JPY currency not confirmed")
                times = result.get("timestamp") or []
                candles = (result.get("indicators", {}).get("quote") or [None])[0] or {}
                rows = {}
                for i, timestamp in enumerate(times):
                    try:
                        values = {field: round(float(candles[field][i]), 4) for field in FIELDS}
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue  # Ignore incomplete, e.g. currently open, candles.
                    if not all(math.isfinite(v) and 50 <= v <= 300 for v in values.values()):
                        continue
                    if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
                        continue
                    date = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
                    rows[date] = {"date": date, **values}
                if len(rows) < 20:
                    raise ValueError(f"Only {len(rows)} valid daily OHLC records")
                return rows
            except (urllib.error.URLError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"{host} attempt {attempt + 1}: {type(exc).__name__}: {exc}")
                if attempt == 0:
                    time.sleep(2)
    raise RuntimeError(" / ".join(errors))


def backfill(payload: dict, candles: dict[str, dict], now: str) -> tuple[int, list[str]]:
    data = payload.setdefault("data", {})
    rows = data.get("records") or []
    old_prices = {p["date"]: dict(p) for p in data.get("priceRecords", []) if p.get("date")}
    filled = 0
    for row in rows:
        date = row.get("targetDate")
        candle = candles.get(date)
        if not candle:
            continue
        current = old_prices.get(date, {"date": date})
        changed = False
        for key in FIELDS:
            if row.get(key) is None:
                row[key] = candle[key]  # setdefault does NOT replace existing null values.
                changed = True
            if current.get(key) is None:
                current[key] = row.get(key)
        if changed:
            row["priceSourceId"] = "YAHOO_USDJPY"
            current["priceSourceId"] = "YAHOO_USDJPY"
            filled += 1
        old_prices[date] = current

    # Calculate percentage changes for newly retrieved dates using *one*
    # consistently sourced Yahoo series, not a mix of two vendor closes.
    yahoo_dates = sorted(candles)
    yahoo_previous = {}
    for idx in range(1, len(yahoo_dates)):
        current_day, prev_day = yahoo_dates[idx], yahoo_dates[idx - 1]
        if candles[prev_day]["close"]:
            yahoo_previous[current_day] = round(
                (candles[current_day]["close"] / candles[prev_day]["close"] - 1) * 100, 2)
    for row in rows:
        date = row["targetDate"]
        if row.get("priceChangePct") is None and date in yahoo_previous and row.get("priceSourceId") == "YAHOO_USDJPY":
            row["priceChangePct"] = yahoo_previous[date]
            old_prices[date]["priceChangePct"] = yahoo_previous[date]

    old_prices = {d: p for d, p in old_prices.items() if p.get("close") is not None}
    data["priceRecords"] = sorted(old_prices.values(), key=lambda p: p["date"], reverse=True)
    available_dates = sorted((r["targetDate"] for r in rows if all(r.get(k) is not None for k in FIELDS)))
    data["priceRange"] = {
        "startDate": available_dates[0] if available_dates else None,
        "endDate": available_dates[-1] if available_dates else None,
        "count": len(available_dates),
    }
    data["priceSourceName"] = "Investing.com（既存分）／Yahoo Finance（欠損分の日足OHLC）"
    newest = rows[0] if rows else {}
    missing20 = [r["targetDate"] for r in rows[:20] if any(r.get(k) is None for k in FIELDS) or r.get("priceChangePct") is None]
    if newest.get("close") is not None:
        level = "多い" if newest.get("vs20Pct", 0) >= 10 else "少ない" if newest.get("vs20Pct", 0) <= -10 else "概ね平均圏"
        data["latestJudgement"] = {
            "targetDate": newest["targetDate"], "publicationDate": newest["publicationDate"],
            "spotVolumeLevel": level,
            "summary": f"直近のUSD/JPYスポット出来高は20営業日平均を{'上回っています' if newest.get('vs20', 0) >= 0 else '下回っています'}。同日のUSD/JPY終値は{newest['close']:.2f}円です。",
        }
    data["priceAcquisition"] = {
        "checkedAt": now, "source": SOURCE_URL, "filledMissingDates": filled,
        "latestTargetDate": newest.get("targetDate"), "missingLast20Dates": missing20,
        "note": "Yahoo Financeの日足は日銀・東京市場の出来高集計時間とは異なります。",
    }
    components = payload.setdefault("components", {})
    components["usdjpyOhlc"] = {
        "status": "ok" if not missing20 else "partial",
        "sourceId": "YAHOO_USDJPY", "latestDate": available_dates[-1] if available_dates else None,
        "missingLast20Dates": missing20,
    }
    sources = payload.setdefault("sources", [])
    sources[:] = [s for s in sources if s.get("id") != "YAHOO_USDJPY"]
    sources.append({
        "id": "YAHOO_USDJPY", "name": "Yahoo Finance USD/JPY historical daily OHLC",
        "url": SOURCE_URL, "asOf": available_dates[-1] if available_dates else None,
        "status": "ok" if not missing20 else "partial", "fields": list(FIELDS) + ["priceChangePct"],
        "note": "Investing.com未取得日の補完。既存Investing.com OHLCは維持。",
    })
    return filled, missing20


def main() -> None:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    now = datetime.now(JST).isoformat(timespec="seconds")
    try:
        candles = fetch_yahoo()
        filled, missing = backfill(payload, candles, now)
        if missing:
            print(f"::warning::USDJPY OHLC missing for recent volume dates: {', '.join(missing)}")
        print(json.dumps({"filledDates": filled, "recentMissing": missing, "latestPriceDate": payload["data"]["priceRange"]["endDate"]}, ensure_ascii=False))
    except Exception as exc:
        message = f"Yahoo USDJPY daily OHLC fetch failed: {type(exc).__name__}: {exc}"
        print(f"::warning::{message}")
        payload.setdefault("components", {})["usdjpyOhlc"] = {"status": "error", "note": message, "checkedAt": now}
        payload.setdefault("data", {})["priceAcquisition"] = {"checkedAt": now, "error": message}
    PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
