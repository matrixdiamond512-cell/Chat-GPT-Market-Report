#!/usr/bin/env python3
"""Fetch NYSE/NASDAQ breadth, persist history/JSON, and sync Google Sheets.

Source methodology: TradingView America scanner, exchange-filtered listed stock
instruments.  The script never substitutes a previous day's count as current.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from stock_freshness import current_block, current_of, envelope, last_good_from, normal_date
from restore_us_market_internals_table import fetch_daily_quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market" / "us-stock-breadth.json"
HISTORY = ROOT / "data" / "market" / "us-stock-breadth-history.json"
TEST_LOG = ROOT / "data" / "market" / "tradingview-10day-test.json"
STOCKS = ROOT / "data" / "stocks.json"
JST = timezone(timedelta(hours=9))
SCANNER_URL = "https://scanner.tradingview.com/america/scan"
SOURCE_NAME = "TradingView America Stock Screener"
SOURCE_URL = "https://www.tradingview.com/markets/stocks-usa/market-movers-all-stocks/"
DETAIL_SHEET = "US_Stock_Breadth"
CLOSE_SHEET = "終値一覧"

DETAIL_HEADERS = [
    "日付", "NYSE値上がり銘柄数", "NYSE値下がり銘柄数",
    "NYSE52週高値銘柄数", "NYSE52週安値銘柄数", "NYSE Advance/Decline比率",
    "NYSE前日比", "NYSE20営業日平均比", "NASDAQ値上がり銘柄数",
    "NASDAQ値下がり銘柄数", "NASDAQ52週高値銘柄数", "NASDAQ52週安値銘柄数",
    "NASDAQ Advance/Decline比率", "NASDAQ前日比", "NASDAQ20営業日平均比",
    "米国株合算値上がり比率", "市場内部判定", "データ取得元", "取得日時", "注記"
]
CLOSE_HEADERS = [
    "NYSE値上がり銘柄数", "NYSE値下がり銘柄数",
    "NASDAQ値上がり銘柄数", "NASDAQ値下がり銘柄数",
    "米国株値上がり比率", "米国株市場内部判定"
]


def post_json(payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = Request(
                SCANNER_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 MarketReportBreadth/1.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=40) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"US breadth source request failed: {error}")


def fetch_exchange(exchange: str) -> dict[str, Any]:
    payload = {
        "filter": [
            {"left": "exchange", "operation": "equal", "right": exchange},
            {"left": "type", "operation": "equal", "right": "stock"},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "change", "High.52W", "Low.52W", "exchange", "type", "subtype"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 10000],
    }
    raw = post_json(payload)
    rows = raw.get("data") or []
    advances = declines = unchanged = highs = lows = valid = 0
    for row in rows:
        values = row.get("d") or []
        if len(values) < 5:
            continue
        close, change, high52, low52 = values[1], values[2], values[3], values[4]
        if not isinstance(change, (int, float)) or not math.isfinite(float(change)):
            continue
        valid += 1
        if change > 0:
            advances += 1
        elif change < 0:
            declines += 1
        else:
            unchanged += 1
        if isinstance(close, (int, float)) and isinstance(high52, (int, float)) and high52:
            if float(close) >= float(high52) * (1 - 1e-7):
                highs += 1
        if isinstance(close, (int, float)) and isinstance(low52, (int, float)) and low52:
            if float(close) <= float(low52) * (1 + 1e-7):
                lows += 1
    if valid == 0:
        raise RuntimeError(f"{exchange}: no valid scanner rows")
    return {
        "advancers": advances,
        "decliners": declines,
        "unchanged": unchanged,
        "total": valid,
        "newHigh52Week": highs,
        "newLow52Week": lows,
        "advanceDeclineRatio": round(advances / declines, 6) if declines else None,
    }


def load_history() -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    try:
        value = json.loads(HISTORY.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def load_existing_payload() -> dict[str, Any]:
    if not OUT.exists():
        return {}
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def record_tradingview_test_attempt(
    *,
    attempted_at: str,
    status: str,
    market_date: str | None,
    market_date_reference: dict[str, Any] | None,
    error: str | None = None,
    exchanges: dict[str, dict[str, Any]] | None = None,
) -> None:
    try:
        log = json.loads(TEST_LOG.read_text(encoding="utf-8"))
        if not isinstance(log, dict):
            log = {}
    except Exception:
        log = {}

    attempts = list(log.get("attempts") or [])
    reference_date = (
        normal_date(market_date_reference.get("marketDate"))
        if isinstance(market_date_reference, dict)
        else None
    )
    attempts.append({
        "attemptedAt": attempted_at,
        "status": status,
        "marketDate": normal_date(market_date),
        "referenceMarketDate": reference_date,
        "source": SOURCE_NAME,
        "error": error,
    })

    sessions = [
        session for session in (log.get("sessions") or [])
        if isinstance(session, dict) and normal_date(session.get("marketDate"))
    ]
    if status == "verified" and normal_date(market_date):
        exchange_counts = {
            name: {
                key: row.get(key)
                for key in ("advancers", "decliners", "unchanged", "total")
            }
            for name, row in (exchanges or {}).items()
        }
        record = {
            "marketDate": normal_date(market_date),
            "fetchedAt": attempted_at,
            "status": "verified",
            "source": SOURCE_NAME,
            "dateReference": market_date_reference,
            "exchanges": exchange_counts,
        }
        existing_index = next(
            (i for i, session in enumerate(sessions)
             if normal_date(session.get("marketDate")) == record["marketDate"]),
            None,
        )
        if existing_index is None:
            sessions.append(record)
        else:
            sessions[existing_index] = record

    sessions.sort(key=lambda session: str(session.get("marketDate") or ""))
    sessions = sessions[-30:]
    attempts = attempts[-50:]
    successful_count = len({
        normal_date(session.get("marketDate"))
        for session in sessions
        if session.get("status") == "verified"
    })
    started_at = log.get("startedAt")
    if successful_count and not started_at:
        started_at = next(
            session["fetchedAt"]
            for session in sessions
            if session.get("status") == "verified"
        )
    TEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    TEST_LOG.write_text(
        json.dumps({
            "schemaVersion": "1.0.0",
            "testName": "TradingView America Stock Screener",
            "requiredSuccessfulSessions": 10,
            "status": "complete" if successful_count >= 10 else (
                "in_progress" if successful_count else "waiting_for_first_success"
            ),
            "startedAt": started_at,
            "successfulSessionCount": successful_count,
            "remainingSuccessfulSessions": max(0, 10 - successful_count),
            "updatedAt": attempted_at,
            "sessions": sessions,
            "attempts": attempts,
            "lastAttempt": attempts[-1],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def enrich(exchange: dict[str, Any], previous: dict[str, Any] | None, prior20: list[dict[str, Any]]) -> None:
    ratio = exchange.get("advanceDeclineRatio")
    previous_ratio = (previous or {}).get("advanceDeclineRatio")
    exchange["previousDayChange"] = round(ratio - previous_ratio, 6) if isinstance(ratio, (int, float)) and isinstance(previous_ratio, (int, float)) else None
    ratios = [x.get("advanceDeclineRatio") for x in prior20 if isinstance(x.get("advanceDeclineRatio"), (int, float))]
    avg20 = sum(ratios[-20:]) / len(ratios[-20:]) if ratios else None
    exchange["average20Day"] = round(avg20, 6) if avg20 is not None else None
    exchange["versus20DayAveragePercent"] = round((ratio / avg20 - 1) * 100, 4) if isinstance(ratio, (int, float)) and avg20 not in (None, 0) else None


def judgement(rate: float) -> str:
    if rate >= 0.65:
        return "上昇優勢（強い）"
    if rate >= 0.55:
        return "上昇優勢"
    if rate <= 0.35:
        return "下落優勢（強い）"
    if rate <= 0.45:
        return "下落優勢"
    return "拮抗"


def update_stocks_json(payload: dict[str, Any]) -> None:
    if not STOCKS.exists():
        return
    try:
        stocks = json.loads(STOCKS.read_text(encoding="utf-8"))
    except Exception:
        return
    us = stocks.setdefault("marketInternals", {}).setdefault("us", {})
    rows = us.setdefault("rows", [])
    nyse = payload["exchanges"]["NYSE"]
    nasdaq = payload["exchanges"]["NASDAQ"]
    replacements = {
        "NYSE 値上がり / 値下がり": f'{nyse["advancers"]:,} / {nyse["decliners"]:,}',
        "NASDAQ 値上がり / 値下がり": f'{nasdaq["advancers"]:,} / {nasdaq["decliners"]:,}',
        "NYSE 52週高値 / 安値": f'{nyse["newHigh52Week"]:,} / {nyse["newLow52Week"]:,}',
        "NASDAQ 52週高値 / 安値": f'{nasdaq["newHigh52Week"]:,} / {nasdaq["newLow52Week"]:,}',
    }
    existing = {str(r[0]): r for r in rows if isinstance(r, list) and r}
    for label, value in replacements.items():
        if label in existing:
            existing[label][1] = value
            existing[label][2] = "-"
            existing[label][3] = f'基準日 {payload["marketDate"]}'
        else:
            rows.append([label, value, "-", f'基準日 {payload["marketDate"]}'])
    previous = stocks.get("usBreadth") or {}
    current = dict(payload.get("current") or payload)
    stocks["usBreadth"] = {**current, "lastGood": last_good_from(previous)}
    STOCKS.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def col_name(index: int) -> str:
    result = ""
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def sync_sheets(payload: dict[str, Any]) -> None:
    spreadsheet_id = os.getenv("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials:
        print("Sheets sync skipped: credentials not configured")
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    client = SheetsClient(create_authorized_session(load_service_account_info(credentials)), spreadsheet_id)
    sheets = client.ensure_sheets([DETAIL_SHEET, CLOSE_SHEET])
    market_date = payload["marketDate"]
    nyse, nasdaq = payload["exchanges"]["NYSE"], payload["exchanges"]["NASDAQ"]
    detail_row = [
        market_date, nyse["advancers"], nyse["decliners"], nyse["newHigh52Week"], nyse["newLow52Week"],
        nyse["advanceDeclineRatio"], nyse["previousDayChange"], nyse["versus20DayAveragePercent"],
        nasdaq["advancers"], nasdaq["decliners"], nasdaq["newHigh52Week"], nasdaq["newLow52Week"],
        nasdaq["advanceDeclineRatio"], nasdaq["previousDayChange"], nasdaq["versus20DayAveragePercent"],
        payload["combinedAdvanceRate"], payload["judgement"], SOURCE_NAME, payload["fetchedAt"], payload["note"],
    ]
    values = client.get_values(DETAIL_SHEET, "A:T")
    if not values:
        client.update(DETAIL_SHEET, "A1", [DETAIL_HEADERS])
        values = [DETAIL_HEADERS]
    date_to_row = {str(row[0])[:10]: i + 1 for i, row in enumerate(values[1:], start=1) if row}
    row_no = date_to_row.get(market_date)
    if row_no:
        client.update(DETAIL_SHEET, f"A{row_no}:T{row_no}", [detail_row])
    else:
        client.append(DETAIL_SHEET, "A:T", [detail_row])
    client.format_table(sheets[DETAIL_SHEET], len(DETAIL_HEADERS), max(len(values) + (0 if row_no else 1), 2))

    close_values = client.get_values(CLOSE_SHEET, "A:ZZ")
    if not close_values:
        raise RuntimeError("終値一覧 sheet is empty")
    headers = list(close_values[0])
    for header in CLOSE_HEADERS:
        if header not in headers:
            headers.append(header)
    client.update(CLOSE_SHEET, "A1", [headers])
    target_row = None
    for idx, row in enumerate(close_values[1:], start=2):
        if row and str(row[0])[:10].replace("/", "-") == market_date:
            target_row = idx
            break
    if target_row is None:
        target_row = len(close_values) + 1
        client.update(CLOSE_SHEET, f"A{target_row}", [[market_date]])
    basic = [nyse["advancers"], nyse["decliners"], nasdaq["advancers"], nasdaq["decliners"], payload["combinedAdvanceRate"], payload["judgement"]]
    for header, value in zip(CLOSE_HEADERS, basic):
        col = col_name(headers.index(header))
        client.update(CLOSE_SHEET, f"{col}{target_row}", [[value]])


def resolve_market_date(explicit: str, stocks: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Use a live Yahoo daily close as the session-date reference.

    Older breadth history and stale aggregate dates must never relabel a current
    TradingView scan. The upstream U.S. close refresh must have published the
    same session before this collector is allowed to save the scan.
    """
    quote = fetch_daily_quote("^DJI")
    reference_date = normal_date(quote.get("marketDate"))
    if not reference_date or datetime.fromisoformat(reference_date).weekday() >= 5:
        raise RuntimeError(f"Yahoo Finance returned an invalid U.S. session date: {quote.get('marketDate')!r}")

    stock_date = normal_date((stocks.get("marketDates") or {}).get("us"))
    if stock_date != reference_date:
        raise RuntimeError(
            f"U.S. close refresh is not current: stocks.marketDates.us={stock_date!r}, "
            f"Yahoo Finance ^DJI={reference_date!r}"
        )

    if explicit:
        explicit_date = normal_date(explicit)
        if explicit_date != reference_date:
            raise RuntimeError(
                f"requested market date {explicit!r} does not match the latest verified U.S. session {reference_date}"
            )

    reference = {
        "name": "Yahoo Finance daily chart",
        "symbol": "^DJI",
        "marketDate": reference_date,
    }
    return reference_date, reference


def main() -> int:
    now = datetime.now(JST)
    stocks = json.loads(STOCKS.read_text(encoding="utf-8")) if STOCKS.exists() else {}
    history = load_history()
    previous = history[-1] if history else None
    previous_output = current_of(load_existing_payload())
    market_date = None
    market_date_reference = None
    try:
        market_date, market_date_reference = resolve_market_date(
            os.getenv("US_BREADTH_MARKET_DATE", "").strip(), stocks
        )
        nyse = fetch_exchange("NYSE")
        nasdaq = fetch_exchange("NASDAQ")
    except Exception as error:  # noqa: BLE001
        fetched_at = now.isoformat(timespec="seconds")
        current = current_block(
            status="unavailable",
            data_date=None,
            as_of=None,
            updated_at=fetched_at,
            source={"name": SOURCE_NAME, "url": SOURCE_URL, "method": "exchange-filtered America scanner"},
            marketDate=None,
            marketDateReference=market_date_reference,
            fetchedAt=fetched_at,
            exchanges={},
            error=f"当日の米国Breadthを取得できませんでした: {error}",
        )
        payload = envelope(current, previous)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        old_component = (stocks.get("usBreadth") or {})
        stocks["usBreadth"] = {**current, "lastGood": last_good_from(old_component)}
        STOCKS.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record_tradingview_test_attempt(
            attempted_at=fetched_at,
            status="failed",
            market_date=market_date,
            market_date_reference=market_date_reference,
            error=current["error"],
        )
        print(json.dumps({"status": "unavailable", "error": current["error"]}, ensure_ascii=False))
        return 0
    enrich(nyse, (previous or {}).get("exchanges", {}).get("NYSE"), [x.get("exchanges", {}).get("NYSE", {}) for x in history])
    enrich(nasdaq, (previous or {}).get("exchanges", {}).get("NASDAQ"), [x.get("exchanges", {}).get("NASDAQ", {}) for x in history])
    total_adv = nyse["advancers"] + nasdaq["advancers"]
    total_dec = nyse["decliners"] + nasdaq["decliners"]
    combined = total_adv / (total_adv + total_dec) if total_adv + total_dec else 0
    fetched_at = now.isoformat(timespec="seconds")
    preserved_indices = (
        previous_output.get("indices")
        if previous_output.get("marketDate") == market_date
        and isinstance(previous_output.get("indices"), dict)
        else {}
    )
    preserved_index_source = (
        previous_output.get("source")
        if preserved_indices and isinstance(previous_output.get("source"), dict)
        else None
    )
    current = current_block(
        status="verified",
        data_date=market_date,
        as_of=f"{market_date}T16:00:00-04:00",
        updated_at=fetched_at,
        source={"name": SOURCE_NAME, "url": SOURCE_URL, "method": "exchange-filtered America scanner"},
        marketDate=market_date,
        marketDateReference=market_date_reference,
        indexSource=preserved_index_source,
        indices=preserved_indices,
        fetchedAt=fetched_at,
        exchanges={"NYSE": nyse, "NASDAQ": nasdaq},
        combinedAdvanceRate=round(combined, 6),
        judgement=judgement(combined),
        note="値上がり・値下がりは前日比change、52週高値・安値は終値と52週高安の一致で集計。",
    )
    payload = envelope(current, previous)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_history = [x for x in history if x.get("marketDate") != market_date] + [payload]
    HISTORY.write_text(json.dumps(new_history[-400:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_stocks_json(payload)
    sync_sheets(payload)
    record_tradingview_test_attempt(
        attempted_at=fetched_at,
        status="verified",
        market_date=market_date,
        market_date_reference=market_date_reference,
        exchanges={"NYSE": nyse, "NASDAQ": nasdaq},
    )
    print(json.dumps({"marketDate": market_date, "NYSE": nyse, "NASDAQ": nasdaq, "combinedAdvanceRate": payload["combinedAdvanceRate"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

