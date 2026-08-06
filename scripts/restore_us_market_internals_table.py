#!/usr/bin/env python3
"""Update the complete U.S. market-internals table after the U.S. close.

Only the U.S. side is advanced. The Tokyo side is left untouched. The resulting
page is archived under the current Japan calendar date with independent U.S. and
Tokyo data dates, so a Tokyo-close update and a U.S.-close update can coexist.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from archive_stocks_snapshot import archive_snapshot

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
BREADTH_PATH = ROOT / "data" / "market" / "us-stock-breadth.json"
SCANNER_URL = "https://scanner.tradingview.com/america/scan"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=14d&interval=1d&events=history"
JST = timezone(timedelta(hours=9))
NEW_YORK = ZoneInfo("America/New_York")

INDEX_SPECS = [
    ("Dow（NYダウ）", "^DJI", 2),
    ("S&P500", "^GSPC", 2),
    ("Nasdaq（総合）", "^IXIC", 2),
    ("SOX（半導体指数）", "^SOX", 2),
    ("Russell2000（小型株）", "^RUT", 2),
    ("VIX（恐怖指数）", "^VIX", 2),
]


def request_json(url: str, *, payload: dict[str, Any] | None = None, attempts: int = 3) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 MarketReportStocks/2.0",
                    "Accept": "application/json,text/plain,*/*",
                },
                method="POST" if body is not None else "GET",
            )
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network retry path
            error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"request failed: {url}: {error}")


def fetch_daily_quote(symbol: str) -> dict[str, Any]:
    url = YAHOO_CHART.format(symbol=quote(symbol, safe=""))
    raw = request_json(url)
    result = ((raw.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"Yahoo chart returned no result: {symbol}")
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    records: list[tuple[int, float]] = []
    for timestamp, close in zip(timestamps, closes):
        if isinstance(timestamp, (int, float)) and isinstance(close, (int, float)) and math.isfinite(float(close)):
            records.append((int(timestamp), float(close)))
    if len(records) < 2:
        raise RuntimeError(f"Yahoo chart has fewer than two valid closes: {symbol}")
    previous_ts, previous_close = records[-2]
    latest_ts, latest_close = records[-1]
    market_date = datetime.fromtimestamp(latest_ts, timezone.utc).astimezone(NEW_YORK).date().isoformat()
    change = latest_close - previous_close
    change_pct = change / previous_close * 100 if previous_close else 0.0
    return {
        "symbol": symbol,
        "marketDate": market_date,
        "timestamp": latest_ts,
        "close": latest_close,
        "previousClose": previous_close,
        "change": change,
        "changePercent": change_pct,
    }


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
            "name", "close", "change", "High.52W", "Low.52W", sma_column,
            "exchange", "type", "subtype",
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 10000],
    }


def fetch_exchange(exchange: str) -> dict[str, Any]:
    raw: dict[str, Any] | None = None
    sma_column = "SMA200"
    for candidate in ("SMA200", "SMA200|1D"):
        try:
            trial = request_json(SCANNER_URL, payload=scanner_payload(exchange, candidate))
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

    advancers = decliners = unchanged = highs = lows = 0
    above_200 = below_200 = equal_200 = valid_change = valid_sma = 0
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
            if isinstance(high52, (int, float)) and high52 and close_value >= float(high52) * (1 - 1e-7):
                highs += 1
            if isinstance(low52, (int, float)) and low52 and close_value <= float(low52) * (1 + 1e-7):
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


def format_close(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def format_change(change: float, change_pct: float, decimals: int = 2) -> str:
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:,.{decimals}f}（{sign}{change_pct:.2f}%）"


def index_comment(name: str, change_pct: float) -> str:
    direction = "上昇" if change_pct > 0 else "下落" if change_pct < 0 else "横ばい"
    if name.startswith("VIX"):
        meaning = "警戒感は後退" if change_pct < 0 else "警戒感は上昇" if change_pct > 0 else "警戒感は横ばい"
        return f"前日比{direction}。{meaning}。"
    if name.startswith("SOX"):
        return f"前日比{direction}。半導体株全体の方向を確認。"
    if name.startswith("Russell"):
        return f"前日比{direction}。小型株への資金の広がりを確認。"
    return f"前日比{direction}。指数の終値ベースで確認。"


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


def update_files(
    quotes: dict[str, dict[str, Any]],
    nyse: dict[str, Any],
    nasdaq: dict[str, Any],
    equal_weight_difference: float,
) -> None:
    now = datetime.now(JST).replace(microsecond=0)
    dates = {quote_data["marketDate"] for quote_data in quotes.values()}
    if len(dates) != 1:
        raise RuntimeError(f"U.S. index dates are inconsistent: {sorted(dates)}")
    market_date = os.getenv("US_INTERNALS_MARKET_DATE", "").strip() or dates.pop()

    payload = {
        "schemaVersion": "2.0.0",
        "marketDate": market_date,
        "fetchedAt": now.isoformat(),
        "status": "verified",
        "source": {
            "name": "Yahoo Finance daily chart + TradingView America Stock Screener",
            "method": "completed daily closes and exchange-filtered breadth including SMA200",
        },
        "indices": quotes,
        "exchanges": {"NYSE": nyse, "NASDAQ": nasdaq},
        "combinedAdvanceRate": round(
            (nyse["advancers"] + nasdaq["advancers"])
            / max(1, nyse["advancers"] + nyse["decliners"] + nasdaq["advancers"] + nasdaq["decliners"]),
            6,
        ),
        "judgement": "上昇優勢"
        if nyse["advancers"] + nasdaq["advancers"] > nyse["decliners"] + nasdaq["decliners"]
        else "下落優勢",
        "note": "米国主要指数、NYSE/NASDAQ騰落、52週高安、200日線上下を同一取引日で保存。",
    }
    BREADTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    BREADTH_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    us = stocks.setdefault("marketInternals", {}).setdefault("us", {})
    rows: list[list[str]] = []
    for label, symbol, decimals in INDEX_SPECS:
        q = quotes[symbol]
        rows.append([
            label,
            format_close(q["close"], decimals),
            format_change(q["change"], q["changePercent"], decimals),
            f"{index_comment(label, q['changePercent'])} 基準日 {market_date}",
        ])
    rows.extend([
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
        [
            "52週高値 / 安値",
            f'{nyse["newHigh52Week"] + nasdaq["newHigh52Week"]:,} / {nyse["newLow52Week"] + nasdaq["newLow52Week"]:,}',
            "-",
            f"NYSE・NASDAQ合算。基準日 {market_date}",
        ],
        [
            "Equal-Weight比較",
            f'{equal_weight_difference:+.2f}pt',
            "-",
            f"RSP騰落率－SPY騰落率。プラスは均等加重優位。基準日 {market_date}",
        ],
    ])

    us["title"] = "主要指数と市場内部（米国）"
    us["flag"] = "US"
    us["columns"] = ["指標名", "終値", "前日比", "評価・概況"]
    us["rows"] = rows
    us["dataDate"] = market_date
    us["updatedAt"] = now.isoformat()

    stocks.setdefault("marketDates", {})["us"] = market_date
    stocks.setdefault("marketUpdatedAt", {})["us"] = now.isoformat()
    stocks["updatedAt"] = now.isoformat()
    stocks["usBreadth"] = payload
    stocks["sourceStatus"] = "米国市場と東京市場を独立更新・市場別基準日を明示"
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    archive_snapshot(STOCKS_PATH)


def main() -> int:
    quotes = {symbol: fetch_daily_quote(symbol) for _, symbol, _ in INDEX_SPECS}
    rsp = fetch_daily_quote("RSP")
    spy = fetch_daily_quote("SPY")
    target_date = quotes["^DJI"]["marketDate"]
    if rsp["marketDate"] != target_date or spy["marketDate"] != target_date:
        raise RuntimeError("Equal-weight comparison date does not match U.S. index date")
    nyse = fetch_exchange("NYSE")
    nasdaq = fetch_exchange("NASDAQ")
    update_files(quotes, nyse, nasdaq, rsp["changePercent"] - spy["changePercent"])
    print(json.dumps({
        "marketDate": target_date,
        "NYSE": nyse,
        "NASDAQ": nasdaq,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
