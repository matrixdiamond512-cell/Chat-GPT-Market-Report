#!/usr/bin/env python3
"""Fetch verified S&P 500 movers and estimated contribution rankings.

Primary source: Slickcharts S&P 500 Companies by Weight.
The page contains company, symbol, weight, price, daily change and daily % change.
The companion return-details page states the market-close date used by the current data.

Contribution values are estimates, not official S&P DJI contribution data:
    estimated contribution (bp) = weight (%) * daily change (%)

Safety rules:
- Slickcharts close date must equal the verified U.S. market date in the breadth/stocks data;
- require at least 490 unique S&P component rows and plausible aggregate weight;
- compare the holdings-weighted return with the verified S&P 500 daily return when available;
- require five positive and five negative movers/contributors;
- never overwrite a newer U.S. market date;
- label all contribution figures as estimates and never as official S&P DJI data.
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
SLICKCHARTS_RETURN_DETAILS_URL = "https://www.slickcharts.com/sp500/returns/details"
SOURCE_NAME = "Slickcharts S&P 500 Companies by Weight (SPY holdings based)"
USER_AGENT = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def parse_number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("−", "-").replace("＋", "+").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        result = float(match.group(0))
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def http_get(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.text


def verified_market_date(stocks: dict[str, Any]) -> str:
    breadth = load_json(BREADTH_PATH, {})
    breadth_date = str(breadth.get("marketDate") or "")[:10]
    stock_date = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    valid = lambda value: bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    if valid(breadth_date) and valid(stock_date) and breadth_date != stock_date:
        # Breadth is fetched and validated before this component.  A newer
        # breadth session is therefore the update target, not an error caused
        # by the still-old aggregate stocks.json that this script will replace.
        gap = abs((datetime.fromisoformat(breadth_date) - datetime.fromisoformat(stock_date)).days)
        if gap > 7:
            raise RuntimeError(f"verified U.S. market dates are implausibly far apart: breadth={breadth_date}, stocks={stock_date}")
        return max(breadth_date, stock_date)
    if valid(breadth_date):
        return breadth_date
    if valid(stock_date):
        return stock_date
    raise RuntimeError("verified U.S. market date is unavailable")


def slickcharts_market_date() -> str:
    text = BeautifulSoup(http_get(SLICKCHARTS_RETURN_DETAILS_URL), "html.parser").get_text(" ", strip=True)
    match = re.search(r"market\s+close\s+on\s+(20\d{2}-\d{2}-\d{2})", text, flags=re.I)
    if not match:
        raise RuntimeError("Slickcharts market-close date was not found")
    return match.group(1)


def fetch_components() -> list[dict[str, Any]]:
    soup = BeautifulSoup(http_get(SLICKCHARTS_URL), "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        header = " ".join(list(candidate.stripped_strings)[:40])
        if all(token in header for token in ("Company", "Symbol", "Weight", "Price", "Chg")):
            table = candidate
            break
    if table is None:
        raise RuntimeError("Slickcharts S&P 500 component table was not found")

    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 7:
            continue
        company = " ".join(cells[1].stripped_strings).strip()
        symbol = " ".join(cells[2].stripped_strings).strip().upper()
        weight = parse_number(" ".join(cells[3].stripped_strings))
        price = parse_number(" ".join(cells[4].stripped_strings))
        day_change = parse_number(" ".join(cells[5].stripped_strings))
        change_pct = parse_number(" ".join(cells[6].stripped_strings))
        if not company or not symbol or None in (weight, price, day_change, change_pct):
            continue
        if weight <= 0 or price <= 0:
            continue
        rows.append({
            "company": company,
            "symbol": symbol,
            "weightPct": float(weight),
            "close": float(price),
            "dayChange": float(day_change),
            "changePct": float(change_pct),
            "contributionBps": float(weight) * float(change_pct),
        })

    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique[row["symbol"]] = row
    rows = list(unique.values())
    if len(rows) < 490:
        raise RuntimeError(f"Slickcharts S&P 500 component coverage too low: {len(rows)}")
    total_weight = sum(row["weightPct"] for row in rows)
    if not 95 <= total_weight <= 105:
        raise RuntimeError(f"S&P component weight total is implausible: {total_weight:.2f}%")
    return rows


def sp500_verified_return_pct(stocks: dict[str, Any]) -> float | None:
    us = (stocks.get("marketInternals") or {}).get("us") or {}
    for row in us.get("rows") or []:
        if not isinstance(row, list) or len(row) < 3:
            continue
        if str(row[0]).strip() != "S&P500":
            continue
        match = re.search(r"\(([-+−＋]?\d+(?:\.\d+)?)%\)", str(row[2]))
        if match:
            return float(match.group(1).replace("−", "-").replace("＋", "+"))
    return None


def validate_weighted_return(rows: list[dict[str, Any]], stocks: dict[str, Any]) -> dict[str, Any]:
    weighted_pct = sum(row["contributionBps"] for row in rows) / 100.0
    verified_pct = sp500_verified_return_pct(stocks)
    difference = None if verified_pct is None else weighted_pct - verified_pct
    # SPY holdings weights and index weights are close but not identical, and displayed component
    # returns are rounded. A 0.20 percentage-point tolerance catches stale-day mismatches without
    # pretending the estimate is official index attribution.
    if difference is not None and abs(difference) > 0.20:
        raise RuntimeError(
            f"Slickcharts weighted return does not match verified S&P 500 session: "
            f"estimate={weighted_pct:.3f}%, verified={verified_pct:.3f}%, diff={difference:.3f}pt"
        )
    return {
        "estimatedWeightedReturnPct": round(weighted_pct, 4),
        "verifiedSP500ReturnPct": verified_pct,
        "differencePt": None if difference is None else round(difference, 4),
    }


def fmt_price(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_day_change(value: float) -> str:
    return f"{value:+,.2f}".rstrip("0").rstrip(".")


def mover_public(row: dict[str, Any], rank: int, market_date: str) -> dict[str, Any]:
    return {
        "rank": rank,
        "symbol": row["symbol"],
        "name": f'{row["company"]}（{row["symbol"]}）',
        "close": fmt_price(row["close"]),
        "dayChange": fmt_day_change(row["dayChange"]),
        "change": f'{row["changePct"]:+.2f}%',
        "reason": f"S&P500構成銘柄の前日比騰落率。基準日 {market_date}。材料要因は別途ニュース確認。",
    }


def contribution_public(row: dict[str, Any], rank: int, market_date: str) -> dict[str, Any]:
    bps = row["contributionBps"]
    return {
        "rank": rank,
        "symbol": row["symbol"],
        "name": f'{row["company"]}（{row["symbol"]}）',
        "close": fmt_price(row["close"]),
        "change": f'{row["changePct"]:+.2f}%',
        "weight": f'{row["weightPct"]:.2f}%',
        "contribution": f"{bps:+.2f}bp",
        "contributionBps": round(bps, 4),
        "reason": f"Slickcharts構成比×当日騰落率による推計。基準日 {market_date}。公式S&P寄与度ではない。",
    }


def build_payloads(
    rows: list[dict[str, Any]], market_date: str, fetched_at: str, validation: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    gainers = sorted((r for r in rows if r["changePct"] > 0), key=lambda r: r["changePct"], reverse=True)[:5]
    losers = sorted((r for r in rows if r["changePct"] < 0), key=lambda r: r["changePct"])[:5]
    top = sorted((r for r in rows if r["contributionBps"] > 0), key=lambda r: r["contributionBps"], reverse=True)[:5]
    bottom = sorted((r for r in rows if r["contributionBps"] < 0), key=lambda r: r["contributionBps"])[:5]
    if min(len(gainers), len(losers), len(top), len(bottom)) < 5:
        raise RuntimeError("S&P mover/contribution rankings did not produce five rows each")

    movers = {
        "schemaVersion": "1.1.0",
        "status": "verified",
        "dataDate": market_date,
        "updatedAt": fetched_at,
        "universe": "S&P 500 constituents",
        "source": {"name": SOURCE_NAME, "url": SLICKCHARTS_URL, "basisDateUrl": SLICKCHARTS_RETURN_DETAILS_URL},
        "validation": validation,
        "gainers": [mover_public(row, i, market_date) for i, row in enumerate(gainers, 1)],
        "losers": [mover_public(row, i, market_date) for i, row in enumerate(losers, 1)],
    }
    contributions = {
        "schemaVersion": "1.1.0",
        "status": "verified-estimate",
        "dataDate": market_date,
        "updatedAt": fetched_at,
        "unit": "bp",
        "official": False,
        "method": "estimated contribution bp = Slickcharts SPY-holdings-based weight(%) × daily component change(%)",
        "source": {"name": SOURCE_NAME, "url": SLICKCHARTS_URL, "basisDateUrl": SLICKCHARTS_RETURN_DETAILS_URL},
        "validation": validation,
        "top": [contribution_public(row, i, market_date) for i, row in enumerate(top, 1)],
        "bottom": [contribution_public(row, i, market_date) for i, row in enumerate(bottom, 1)],
    }
    return movers, contributions


def same_rankings(old: dict[str, Any], new: dict[str, Any], keys: tuple[str, ...]) -> bool:
    if old.get("dataDate") != new.get("dataDate"):
        return False
    for key in keys:
        def signature(items: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
            return [(x.get("symbol"), x.get("close"), x.get("change"), x.get("contribution"), x.get("weight")) for x in items]
        if signature(old.get(key) or []) != signature(new.get(key) or []):
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
        "source": SOURCE_NAME,
        "validation": movers["validation"],
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
        "source": SOURCE_NAME,
        "validation": contributions["validation"],
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
    expected_date = verified_market_date(stocks)
    source_date = slickcharts_market_date()
    if source_date != expected_date:
        raise SystemExit(f"Slickcharts is not on the verified U.S. session: source={source_date}, expected={expected_date}")

    rows = fetch_components()
    validation = validate_weighted_return(rows, stocks)
    fetched_at = now_jst().isoformat()
    movers, contributions = build_payloads(rows, expected_date, fetched_at, validation)

    old_movers = load_json(MOVERS_PATH, {})
    old_contrib = load_json(CONTRIB_PATH, {})
    if same_rankings(old_movers, movers, ("gainers", "losers")) and same_rankings(old_contrib, contributions, ("top", "bottom")):
        print(json.dumps({"status": "already-current", "marketDate": expected_date, "validation": validation}, ensure_ascii=False))
        return 0

    merge_into_stocks(stocks, movers, contributions)
    MOVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOVERS_PATH.write_text(json.dumps(movers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONTRIB_PATH.write_text(json.dumps(contributions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_stock_analysis_json(stocks)
    print(json.dumps({
        "status": "verified",
        "marketDate": expected_date,
        "componentCount": len(rows),
        "topGainer": movers["gainers"][0]["name"],
        "topLoser": movers["losers"][0]["name"],
        "topContribution": contributions["top"][0]["name"],
        "validation": validation,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
