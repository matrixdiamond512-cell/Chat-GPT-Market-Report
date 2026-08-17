#!/usr/bin/env python3
"""Fetch a bounded U.S. pre-market monitoring universe.

Yahoo Finance chart data is used only for the 04:00-09:30 New York session.
The collector uses six workers, retries failed symbols only, and reports
coverage so a partial observation cannot be presented as a market-wide claim.
"""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import requests
except ImportError:  # pragma: no cover - GitHub Actions installs requests
    requests = None
from zoneinfo import ZoneInfo

from stock_freshness import current_block, envelope, last_good_from

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market" / "us-premarket.json"
STOCKS = ROOT / "data" / "stocks.json"
NY = ZoneInfo("America/New_York")
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0)"

UNIVERSE_GROUPS: dict[str, tuple[str, ...]] = {
    "半導体・AI": ("NVDA", "AVGO", "AMD", "MU", "QCOM", "INTC", "AMAT", "LRCX"),
    "大型テック": ("MSFT", "AAPL", "AMZN", "GOOGL", "META", "ORCL", "NFLX", "CRM"),
    "高β・成長": ("TSLA", "PLTR", "UBER", "ABNB"),
    "金融": ("JPM", "BAC", "WFC", "C", "GS", "MS", "BRK-B"),
    "エネルギー": ("XOM", "CVX", "COP", "SLB"),
    "消費": ("WMT", "COST", "HD", "MCD", "NKE", "TGT"),
    "ヘルスケア": ("LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE"),
    "資本財・防衛": ("CAT", "GE", "BA", "RTX", "LMT"),
    "その他": ("DIS", "T"),
}
UNIVERSE = [symbol for symbols in UNIVERSE_GROUPS.values() for symbol in symbols]
SYMBOL_GROUP = {symbol: group for group, symbols in UNIVERSE_GROUPS.items() for symbol in symbols}
FUTURES = {
    "sp500": ("ES=F", "S&P500先物"), "nasdaq100": ("NQ=F", "Nasdaq100先物"),
    "dow": ("YM=F", "Dow先物"), "russell2000": ("RTY=F", "Russell2000先物"),
    "vix": ("^VIX", "VIX"), "us10y": ("^TNX", "米10年債"), "dxy": ("DX-Y.NYB", "ドル指数"),
    "usdjpy": ("JPY=X", "USD/JPY"), "gold": ("GC=F", "Gold"), "wti": ("CL=F", "WTI"), "btc": ("BTC-USD", "BTCUSD"),
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def yahoo_chart(symbol: str, retries: int = 2) -> dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests is not installed; run pip install requests")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?interval=1m&range=1d&includePrePost=true&events=div%2Csplits"
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            response = requests.get(url, headers={"User-Agent": UA}, timeout=12)
            response.raise_for_status()
            payload = response.json()
            result = ((payload.get("chart") or {}).get("result") or [None])[0]
            if not result:
                raise RuntimeError("Yahoo chart returned no result")
            return result
        except Exception as error:  # noqa: BLE001
            last_error = error
    raise RuntimeError(f"{symbol}: Yahoo premarket fetch failed: {last_error}")


def latest_premarket(symbol: str, expected_date: str) -> dict[str, Any]:
    result = yahoo_chart(symbol)
    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    meta = result.get("meta") or {}
    previous = meta.get("previousClose") or meta.get("chartPreviousClose")
    rows: list[tuple[datetime, float, float | None]] = []
    for index, ts in enumerate(timestamps):
        dt = datetime.fromtimestamp(int(ts), timezone.utc).astimezone(NY)
        if dt.date().isoformat() != expected_date or not (dt.hour >= 4 and (dt.hour < 9 or (dt.hour == 9 and dt.minute < 30))):
            continue
        close = (quote_data.get("close") or [None] * len(timestamps))[index]
        volume = (quote_data.get("volume") or [None] * len(timestamps))[index]
        if isinstance(close, (int, float)) and math.isfinite(float(close)):
            rows.append((dt, float(close), float(volume) if isinstance(volume, (int, float)) else None))
    if not rows:
        raise RuntimeError(f"{symbol}: no 04:00-09:30 data for {expected_date}")
    dt, price, volume = rows[-1]
    previous_float = float(previous) if isinstance(previous, (int, float)) and previous else None
    change_pct = (price / previous_float - 1) * 100 if previous_float else None
    if change_pct is None:
        raise RuntimeError(f"{symbol}: previous close unavailable")
    return {
        "symbol": symbol,
        "name": symbol,
        "sector": SYMBOL_GROUP.get(symbol, "クロスアセット"),
        "price": round(price, 6),
        "changePct": round(change_pct, 6),
        "change": f"{change_pct:+.2f}%",
        "volume": int(volume) if volume is not None else None,
        "asOf": dt.isoformat(timespec="minutes"),
    }


def fetch_universe(expected_date: str) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    # A failed symbol is retried inside yahoo_chart; successful symbols are not
    # fetched again, keeping the request budget bounded.
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(latest_premarket, symbol, expected_date): symbol for symbol in UNIVERSE}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:  # noqa: BLE001
                errors.append(f"{symbol}: {error}")
    return sorted(rows, key=lambda row: row["symbol"]), errors


def coverage_status(universe_size: int, fetched_count: int) -> tuple[str, float]:
    ratio = (fetched_count / universe_size * 100) if universe_size else 0.0
    return ("ok" if ratio >= 90 else "partial" if ratio >= 70 else "unavailable", round(ratio, 2))


def breadth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    up = sum(1 for row in rows if row["changePct"] > 0.05)
    down = sum(1 for row in rows if row["changePct"] < -0.05)
    flat = len(rows) - up - down
    return {"up": up, "down": down, "flat": flat, "flatThresholdPct": 0.05, "label": "監視銘柄ベース"}


def sector_breadth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for group in UNIVERSE_GROUPS:
        items = [row for row in rows if row["sector"] == group]
        up = sum(1 for row in items if row["changePct"] > 0.05)
        down = sum(1 for row in items if row["changePct"] < -0.05)
        output[group] = {
            "up": up,
            "down": down,
            "flat": len(items) - up - down,
            "averageChangePct": round(sum(row["changePct"] for row in items) / len(items), 4) if items else None,
            "judgement": "強い" if up > down else "弱い" if down > up else "拮抗",
        }
    return output


def fetch_futures(expected_date: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, (symbol, label) in FUTURES.items():
        try:
            row = latest_premarket(symbol, expected_date)
            output[key] = {"symbol": symbol, "label": label, "change": row["change"], "changePct": row["changePct"], "asOf": row["asOf"]}
        except Exception as error:  # noqa: BLE001
            output[key] = {"symbol": symbol, "label": label, "status": "unavailable", "error": str(error)}
    return output


def analysis(status: str, rows: list[dict[str, Any]], futures: dict[str, Any], counts: dict[str, Any]) -> dict[str, Any]:
    if status == "unavailable":
        return {"label": "判定保留", "comment": "取得率70%未満のため、市場全体の強い断定は行いません。"}
    top_groups = [group for group, item in sector_breadth(rows).items() if item.get("judgement") == "強い"]
    nasdaq = (futures.get("nasdaq100") or {}).get("changePct")
    if isinstance(nasdaq, (int, float)) and nasdaq > 0 and counts["up"] > counts["down"] and len(top_groups) >= 2:
        comment = "大型テック以外にも買いが広がる、比較的質の高いリスクオン。"
    elif isinstance(nasdaq, (int, float)) and nasdaq > 0:
        comment = "指数は上昇しているが、監視銘柄の広がりは限定的。全面的なリスクオンとは断定しません。"
    else:
        comment = "指数先物・監視銘柄の方向が揃っているかを確認中です。"
    return {"label": "監視銘柄ベースの総合判定", "comment": comment}


def main() -> int:
    previous = load_json(OUT, {})
    expected_date = os.getenv("US_PREMARKET_MARKET_DATE", "").strip()[:10] or datetime.now(timezone.utc).astimezone(NY).date().isoformat()
    fetched_at = datetime.now(JST).replace(microsecond=0).isoformat()
    rows, errors = fetch_universe(expected_date)
    status, ratio = coverage_status(len(UNIVERSE), len(rows))
    visible_rows = rows if status != "unavailable" else []
    counts = breadth(visible_rows) if visible_rows else {}
    futures = fetch_futures(expected_date)
    visible_sectors = sector_breadth(visible_rows) if visible_rows else {}
    current = current_block(
        status=status,
        data_date=expected_date if status != "unavailable" else None,
        as_of=max((row.get("asOf") for row in rows), default=None),
        updated_at=fetched_at,
        source={"name": "Yahoo Finance Chart API", "method": "1m interval, includePrePost=true, New York 04:00-09:30"},
        universeSize=len(UNIVERSE), fetchedCount=len(rows), coverageRatio=ratio,
        topGainers=sorted(visible_rows, key=lambda row: row["changePct"], reverse=True)[:10],
        topLosers=sorted(visible_rows, key=lambda row: row["changePct"])[:10],
        topVolume=sorted((row for row in visible_rows if row.get("volume") is not None), key=lambda row: row["volume"], reverse=True)[:10],
        breadth=counts,
        sectorBreadth=visible_sectors,
        indexFutures=futures,
        analysis=analysis(status, rows, futures, counts),
        errors=errors[:50],
    )
    payload = envelope(current, previous)
    payload["marketDate"] = payload.get("dataDate")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stocks = load_json(STOCKS, {})
    if stocks:
        old_component = stocks.get("usPremarket") or {}
        stocks["usPremarket"] = {**current, "lastGood": last_good_from(old_component)}
        STOCKS.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "dataDate": current.get("dataDate"), "universeSize": len(UNIVERSE), "fetchedCount": len(rows), "coverageRatio": ratio}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

