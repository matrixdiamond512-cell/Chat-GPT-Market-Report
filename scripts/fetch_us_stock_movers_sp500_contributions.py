#!/usr/bin/env python3
"""Fetch verified S&P 500 stock movers and estimated contribution rankings.

Data sources:
- Slickcharts S&P 500 holdings/weights (SPY holdings based)
- TradingView America scanner for current completed-session close/change

The S&P contribution number is explicitly an estimate in basis points (bp):
    contribution_bp = holding_weight_percent * daily_change_percent
This is equivalent to the stock's estimated contribution to the index daily return
in basis points when the holding weight is treated as the index weight proxy.

Safety rules:
- use the market date already verified by the US breadth pipeline;
- require a large majority of S&P symbols to match TradingView scanner data;
- require five positive and five negative movers/contributors;
- never present the estimate as an official S&P Dow Jones Indices contribution;
- never overwrite newer stocks.json data with an older market date;
- if the current verified date is already stored with identical values, do not churn files.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
BREADTH_PATH = ROOT / "data" / "market" / "us-stock-breadth.json"
MOVERS_PATH = ROOT / "data" / "market" / "us-stock-movers.json"
CONTRIB_PATH = ROOT / "data" / "market" / "sp500-contributions.json"
JST = timezone(timedelta(hours=9))

SLICKCHARTS_URL = "https://www.slickcharts.com/sp500"
TRADINGVIEW_URL = "https://scanner.tradingview.com/america/scan"
SOURCE_HOLDINGS = "Slickcharts S&P 500 Companies by Weight (SPY holdings based)"
SOURCE_PRICES = "TradingView America Stock Screener"
USER_AGENT = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def parse_number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("−", "-").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
        return number if math.isfinite(number) else None
    except ValueError:
        return None


def verified_market_date(stocks: dict[str, Any]) -> str:
    breadth = load_json(BREADTH_PATH, {})
    date = str(breadth.get("marketDate") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return date
    date = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return date
    raise RuntimeError("verified U.S. market date is unavailable")


def fetch_sp500_holdings() -> list[dict[str, Any]]:
    response = requests.get(
        SLICKCHARTS_URL,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=40,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    table = None
    for candidate in soup.find_all("table"):
        header = " ".join(list(candidate.stripped_strings)[:30])
        if "Symbol" in header and "Weight" in header and "% Chg" in header:
            table = candidate
            break
    if table is None:
        raise RuntimeError("Slickcharts S&P 500 holdings table was not found")

    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 7:
            continue
        company = " ".join(cells[1].stripped_strings).strip()
        symbol = " ".join(cells[2].stripped_strings).strip().upper()
        weight = parse_number(" ".join(cells[3].stripped_strings))
        if not company or not symbol or weight is None or weight <= 0:
            continue
        rows.append({
            "company": company,
            "symbol": symbol,
            "key": normalize_symbol(symbol),
            "weightPct": weight,
        })

    unique = {row["key"]: row for row in rows if row["key"]}
    rows = list(unique.values())
    if len(rows) < 490:
        raise RuntimeError(f"S&P 500 holdings coverage too low: {len(rows)} symbols")
    total_weight = sum(row["weightPct"] for row in rows)
    if not 95 <= total_weight <= 105:
        raise RuntimeError(f"S&P holding weights total is implausible: {total_weight:.2f}%")
    return rows


def fetch_tradingview_rows() -> dict[str, dict[str, Any]]:
    payload = {
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "close", "change", "exchange", "type", "subtype"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 10000],
    }
    response = requests.post(
        TRADINGVIEW_URL,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        json=payload,
        timeout=50,
    )
    response.raise_for_status()
    raw = response.json()
    result: dict[str, dict[str, Any]] = {}
    allowed = {"NASDAQ", "NYSE", "AMEX", "NYSE ARCA", "NYSEARCA"}
    for item in raw.get("data") or []:
        values = item.get("d") or []
        if len(values) < 7:
            continue
        symbol, description, close, change, exchange = values[:5]
        key = normalize_symbol(str(symbol or ""))
        close_num = close if isinstance(close, (int, float)) and math.isfinite(float(close)) else None
        change_num = change if isinstance(change, (int, float)) and math.isfinite(float(change)) else None
        if not key or close_num is None or change_num is None:
            continue
        exchange_text = str(exchange or "").upper().strip()
        if exchange_text and exchange_text not in allowed:
            continue
        result.setdefault(key, {
            "symbol": str(symbol),
            "description": str(description or symbol),
            "close": float(close_num),
            "changePct": float(change_num),
            "exchange": str(exchange or ""),
        })
    if len(result) < 3000:
        raise RuntimeError(f"TradingView U.S. scanner coverage too low: {len(result)} rows")
    return result


def combine(holdings: list[dict[str, Any]], scanner: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for holding in holdings:
        quote = scanner.get(holding["key"])
        if not quote:
            continue
        change_pct = float(quote["changePct"])
        weight_pct = float(holding["weightPct"])
        rows.append({
            "symbol": holding["symbol"],
            "company": holding["company"],
            "close": float(quote["close"]),
            "changePct": change_pct,
            "weightPct": weight_pct,
            "contributionBps": weight_pct * change_pct,
            "exchange": quote.get("exchange") or "",
        })
    if len(rows) < 480:
        missing = len(holdings) - len(rows)
        raise RuntimeError(f"S&P/TradingView matched coverage too low: {len(rows)} matched, {missing} missing")
    return rows


def fmt_price(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def mover_public(row: dict[str, Any], rank: int, market_date: str) -> dict[str, Any]:
    change = float(row["changePct"])
    return {
        "rank": rank,
        "symbol": row["symbol"],
        "name": f'{row["company"]}（{row["symbol"]}）',
        "close": fmt_price(float(row["close"])),
        "change": f"{change:+.2f}%",
        "reason": f"S&P500構成銘柄の前日比騰落率。基準日 {market_date}。材料要因は別途ニュース確認。",
    }


def contribution_public(row: dict[str, Any], rank: int, market_date: str) -> dict[str, Any]:
    bps = float(row["contributionBps"])
    return {
        "rank": rank,
        "symbol": row["symbol"],
        "name": f'{row["company"]}（{row["symbol"]}）',
        "close": fmt_price(float(row["close"])),
        "change": f'{float(row["changePct"]):+.2f}%',
        "weight": f'{float(row["weightPct"]):.2f}%',
        "contribution": f"{bps:+.2f}bp",
        "contributionBps": round(bps, 4),
        "reason": f"Slickcharts構成比×当日騰落率による推計。基準日 {market_date}。",
    }


def build_payloads(rows: list[dict[str, Any]], market_date: str, fetched_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    gainers = sorted((r for r in rows if r["changePct"] > 0), key=lambda r: r["changePct"], reverse=True)[:5]
    losers = sorted((r for r in rows if r["changePct"] < 0), key=lambda r: r["changePct"])[:5]
    top_contrib = sorted((r for r in rows if r["contributionBps"] > 0), key=lambda r: r["contributionBps"], reverse=True)[:5]
    bottom_contrib = sorted((r for r in rows if r["contributionBps"] < 0), key=lambda r: r["contributionBps"])[:5]
    if min(len(gainers), len(losers), len(top_contrib), len(bottom_contrib)) < 5:
        raise RuntimeError("U.S. mover/contribution rankings did not produce five rows each")

    movers = {
        "schemaVersion": "1.0.0",
        "status": "verified",
        "dataDate": market_date,
        "updatedAt": fetched_at,
        "universe": "S&P 500 constituents",
        "source": {"holdings": SOURCE_HOLDINGS, "prices": SOURCE_PRICES},
        "gainers": [mover_public(row, i, market_date) for i, row in enumerate(gainers, 1)],
        "losers": [mover_public(row, i, market_date) for i, row in enumerate(losers, 1)],
    }
    contributions = {
        "schemaVersion": "1.0.0",
        "status": "verified-estimate",
        "dataDate": market_date,
        "updatedAt": fetched_at,
        "unit": "bp",
        "method": "estimated contribution bp = Slickcharts SPY-holdings-based weight(%) × TradingView daily change(%)",
        "official": False,
        "source": {"holdings": SOURCE_HOLDINGS, "prices": SOURCE_PRICES},
        "top": [contribution_public(row, i, market_date) for i, row in enumerate(top_contrib, 1)],
        "bottom": [contribution_public(row, i, market_date) for i, row in enumerate(bottom_contrib, 1)],
    }
    return movers, contributions


def same_rankings(old: dict[str, Any], new: dict[str, Any], keys: tuple[str, ...]) -> bool:
    if old.get("dataDate") != new.get("dataDate"):
        return False
    for key in keys:
        old_rows = old.get(key) or []
        new_rows = new.get(key) or []
        def signature(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
            return [(r.get("symbol"), r.get("close"), r.get("change"), r.get("contribution"), r.get("weight")) for r in rows]
        if signature(old_rows) != signature(new_rows):
            return False
    return True


def merge_into_stocks(stocks: dict[str, Any], movers: dict[str, Any], contributions: dict[str, Any]) -> None:
    market_date = movers["dataDate"]
    current_date = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    if current_date and current_date > market_date:
        raise RuntimeError(f"refusing stale U.S. mover update: {market_date} < {current_date}")
    stocks.setdefault("movers", {})["us"] = {
        "title": "米国市場の大幅上昇・下落銘柄（S&P500構成銘柄）",
        "flag": "US",
        "status": "verified",
        "dataDate": market_date,
        "updatedAt": movers["updatedAt"],
        "source": f"{SOURCE_PRICES} / {SOURCE_HOLDINGS}",
        "gainers": movers["gainers"],
        "losers": movers["losers"],
    }
    stocks.setdefault("contributions", {})["us"] = {
        "title": "米国市場（S&P500寄与度 推計・bp）",
        "flag": "US",
        "status": "verified-estimate",
        "dataDate": market_date,
        "updatedAt": contributions["updatedAt"],
        "unit": "bp",
        "official": False,
        "method": contributions["method"],
        "source": f"{SOURCE_HOLDINGS} / {SOURCE_PRICES}",
        "top": contributions["top"],
        "bottom": contributions["bottom"],
    }
    stocks["updatedAt"] = movers["updatedAt"]


def sync_stock_analysis_json(stocks: dict[str, Any]) -> None:
    spreadsheet_id = os.getenv("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_raw:
        print("Stock_Analysis_JSON sync skipped: Google credentials not configured")
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    client = SheetsClient(create_authorized_session(load_service_account_info(credentials_raw)), spreadsheet_id)
    values = client.get_values("Stock_Analysis_JSON", "A1:B2")
    if len(values) < 2:
        print("Stock_Analysis_JSON sync skipped: B2 payload not found")
        return
    raw = str(values[1][1] if len(values[1]) > 1 else "").strip()
    if not raw:
        print("Stock_Analysis_JSON sync skipped: B2 payload is empty")
        return
    payload = json.loads(raw)
    payload.setdefault("movers", {})["us"] = stocks["movers"]["us"]
    payload.setdefault("contributions", {})["us"] = stocks["contributions"]["us"]
    payload["updatedAt"] = stocks["updatedAt"]
    client.update("Stock_Analysis_JSON", "B2", [[json.dumps(payload, ensure_ascii=False)]])


def main() -> int:
    stocks = load_json(STOCKS_PATH, {})
    if not stocks:
        raise SystemExit("data/stocks.json is unavailable")
    market_date = verified_market_date(stocks)
    current_us = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    if current_us and current_us != market_date:
        raise SystemExit(f"US breadth/stocks market-date mismatch: breadth={market_date}, stocks={current_us}")

    holdings = fetch_sp500_holdings()
    scanner = fetch_tradingview_rows()
    rows = combine(holdings, scanner)
    fetched_at = now_jst().isoformat()
    movers, contributions = build_payloads(rows, market_date, fetched_at)

    old_movers = load_json(MOVERS_PATH, {})
    old_contrib = load_json(CONTRIB_PATH, {})
    already_current = same_rankings(old_movers, movers, ("gainers", "losers")) and same_rankings(old_contrib, contributions, ("top", "bottom"))
    if already_current:
        print(json.dumps({"status": "already-current", "marketDate": market_date}, ensure_ascii=False))
        return 0

    merge_into_stocks(stocks, movers, contributions)
    MOVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOVERS_PATH.write_text(json.dumps(movers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONTRIB_PATH.write_text(json.dumps(contributions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_stock_analysis_json(stocks)
    print(json.dumps({
        "status": "verified",
        "marketDate": market_date,
        "matchedSymbols": len(rows),
        "topMover": movers["gainers"][0]["name"],
        "topContribution": contributions["top"][0]["name"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
