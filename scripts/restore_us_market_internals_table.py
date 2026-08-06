#!/usr/bin/env python3
"""Restore and maintain exchange-specific US breadth rows in stocks.json.

This script changes only the US market-internals table data. It preserves all
other stock-analysis sections and recently improved page rendering.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
BREADTH_PATH = ROOT / "data" / "market" / "us-stock-breadth.json"
SCANNER_URL = "https://scanner.tradingview.com/america/scan"
JST = timezone(timedelta(hours=9))


def post_json(payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(
                SCANNER_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 MarketReportUSInternals/1.0",
                },
                method="POST",
            )
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network retry path
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"TradingView scanner request failed: {last_error}")


def scanner_payload(exchange: str, sma_column: str) -> dict[str, Any]:
    return {
        "filter": [
            {"left": "exchange", "operation": "equal", "right": exchange},
            {"left": "type", "operation": "equal", "right": "stock"},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",
            "close",
            "change",
            "High.52W",
            "Low.52W",
            sma_column,
            "exchange",
            "type",
            "subtype",
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 10000],
    }


def fetch_exchange(exchange: str) -> dict[str, Any]:
    raw: dict[str, Any] | None = None
    sma_column = "SMA200"
    for candidate in ("SMA200", "SMA200|1D"):
        try:
            trial = post_json(scanner_payload(exchange, candidate))
            rows = trial.get("data") or []
            if rows and any(
                len((row.get("d") or [])) > 5
                and isinstance((row.get("d") or [None] * 6)[5], (int, float))
                for row in rows
            ):
                raw = trial
                sma_column = candidate
                break
        except Exception:
            continue
    if raw is None:
        raise RuntimeError(f"{exchange}: 200-day moving-average data unavailable")

    advancers = decliners = unchanged = 0
    highs = lows = 0
    above_200 = below_200 = equal_200 = 0
    valid_change = valid_sma = 0

    for row in raw.get("data") or []:
        values = row.get("d") or []
        if len(values) < 6:
            continue
        close, change, high52, low52, sma200 = values[1:6]

        if isinstance(change, (int, float)) and math.isfinite(float(change)):
            valid_change += 1
            if change > 0:
                advancers += 1
            elif change < 0:
                decliners += 1
            else:
                unchanged += 1

        if isinstance(close, (int, float)) and math.isfinite(float(close)):
            close_value = float(close)
            if isinstance(high52, (int, float)) and high52:
                if close_value >= float(high52) * (1 - 1e-7):
                    highs += 1
            if isinstance(low52, (int, float)) and low52:
                if close_value <= float(low52) * (1 + 1e-7):
                    lows += 1
            if isinstance(sma200, (int, float)) and math.isfinite(float(sma200)):
                valid_sma += 1
                difference = close_value - float(sma200)
                tolerance = max(abs(float(sma200)) * 1e-7, 1e-9)
                if difference > tolerance:
                    above_200 += 1
                elif difference < -tolerance:
                    below_200 += 1
                else:
                    equal_200 += 1

    if valid_change == 0 or valid_sma == 0:
        raise RuntimeError(f"{exchange}: no valid breadth rows")

    return {
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "total": valid_change,
        "newHigh52Week": highs,
        "newLow52Week": lows,
        "aboveSMA200": above_200,
        "belowSMA200": below_200,
        "equalSMA200": equal_200,
        "sma200Valid": valid_sma,
        "sma200Column": sma_column,
        "advanceDeclineRatio": round(advancers / decliners, 6) if decliners else None,
    }


def previous_us_weekday(now_jst: datetime) -> str:
    day = (now_jst - timedelta(days=1)).date()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def breadth_comment(row: dict[str, Any]) -> str:
    ratio = row.get("advanceDeclineRatio")
    if not isinstance(ratio, (int, float)):
        return "市場内部の広がりを確認。"
    direction = "上昇優勢" if ratio > 1 else "下落優勢" if ratio < 1 else "拮抗"
    return f"{direction}。A/D比 {ratio:.2f}倍。"


def sma_comment(row: dict[str, Any]) -> str:
    above = int(row.get("aboveSMA200") or 0)
    below = int(row.get("belowSMA200") or 0)
    equal = int(row.get("equalSMA200") or 0)
    total = above + below + equal
    rate = above / total * 100 if total else 0
    if rate >= 60:
        tone = "長期上昇トレンドの広がりは強い。"
    elif rate >= 50:
        tone = "長期トレンドはやや上向き。"
    elif rate >= 40:
        tone = "長期トレンドは拮抗。"
    else:
        tone = "長期下落トレンドの銘柄が優勢。"
    return f"200日線上 {rate:.1f}%。{tone}"


def update_files(nyse: dict[str, Any], nasdaq: dict[str, Any]) -> None:
    now = datetime.now(JST)
    market_date = os.getenv("US_INTERNALS_MARKET_DATE", "").strip() or previous_us_weekday(now)

    payload = {
        "schemaVersion": "1.1.0",
        "marketDate": market_date,
        "fetchedAt": now.isoformat(timespec="seconds"),
        "status": "verified",
        "source": {
            "name": "TradingView America Stock Screener",
            "url": "https://www.tradingview.com/markets/stocks-usa/market-movers-all-stocks/",
            "method": "exchange-filtered scanner including 200-day SMA",
        },
        "exchanges": {"NYSE": nyse, "NASDAQ": nasdaq},
        "combinedAdvanceRate": round(
            (nyse["advancers"] + nasdaq["advancers"])
            / max(1, nyse["advancers"] + nyse["decliners"] + nasdaq["advancers"] + nasdaq["decliners"]),
            6,
        ),
        "judgement": "上昇優勢"
        if nyse["advancers"] + nasdaq["advancers"] > nyse["decliners"] + nasdaq["decliners"]
        else "下落優勢",
        "note": "NYSEとNASDAQを分け、値上がり・値下がり銘柄数と200日移動平均線の上・下を集計。",
    }
    BREADTH_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    us = stocks.setdefault("marketInternals", {}).setdefault("us", {})
    rows = us.setdefault("rows", [])
    labels_to_replace = {
        "上昇銘柄 / 下落銘柄",
        "NYSE 値上がり / 値下がり",
        "NASDAQ 値上がり / 値下がり",
        "NYSE 200日線上 / 下",
        "NASDAQ 200日線上 / 下",
        "NYSE 200日線より上 / 下",
        "NASDAQ 200日線より上 / 下",
    }
    preserved = [
        row for row in rows
        if not (isinstance(row, list) and row and str(row[0]) in labels_to_replace)
    ]
    insert_at = next(
        (index + 1 for index, row in enumerate(preserved)
         if isinstance(row, list) and row and str(row[0]).startswith("VIX")),
        len(preserved),
    )
    restored_rows = [
        [
            "NYSE 値上がり / 値下がり",
            f'{nyse["advancers"]:,} / {nyse["decliners"]:,}',
            "-",
            f'{breadth_comment(nyse)} 基準日 {market_date}',
        ],
        [
            "NASDAQ 値上がり / 値下がり",
            f'{nasdaq["advancers"]:,} / {nasdaq["decliners"]:,}',
            "-",
            f'{breadth_comment(nasdaq)} 基準日 {market_date}',
        ],
        [
            "NYSE 200日線上 / 下",
            f'{nyse["aboveSMA200"]:,} / {nyse["belowSMA200"]:,}',
            "-",
            f'{sma_comment(nyse)} 基準日 {market_date}',
        ],
        [
            "NASDAQ 200日線上 / 下",
            f'{nasdaq["aboveSMA200"]:,} / {nasdaq["belowSMA200"]:,}',
            "-",
            f'{sma_comment(nasdaq)} 基準日 {market_date}',
        ],
    ]
    us["rows"] = preserved[:insert_at] + restored_rows + preserved[insert_at:]
    stocks["updatedAt"] = now.strftime("%Y/%m/%d %H:%M")
    stocks["dataAsOf"] = market_date + "T16:00:00-04:00"
    stocks["usBreadth"] = payload
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    nyse = fetch_exchange("NYSE")
    nasdaq = fetch_exchange("NASDAQ")
    update_files(nyse, nasdaq)
    print(json.dumps({"NYSE": nyse, "NASDAQ": nasdaq}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
