#!/usr/bin/env python3
"""Repair 08:00 previous-close rows using date-matched daily history.

The 08:00 market table is a previous-close table, not an 08:00 intraday snapshot.
A close is valid when its market-data date matches the required prior session; the
clock time at which the close is retrieved is irrelevant. This script therefore may
repair a morning report later in the day with the correct prior-session close, while
still prohibiting stale-date carry-forward or substitution of a later intraday quote.

BTCUSD is intentionally left to its dedicated 24/7-market source because its daily
bar boundary is not the same as the exchange-session boundary used by the other
markets. This repair must never erase an already published BTC value merely because
Yahoo's UTC daily candle is not final at 08:00 JST.

The helper rewrites the textual 主要市場データ block and synchronizes the six-market
summary prices so the table, report cards, history JSON and portal cannot disagree.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import io
import csv
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
OUT = ROOT / "data" / "market" / "morning-daily-reference.json"
JAPAN_REFERENCE = ROOT / "data" / "market" / "japan-close-reference.json"
MORNING_REFERENCE = ROOT / "data" / "market" / "morning-reference.json"
RATES_REFERENCE = ROOT / "data" / "rates-bonds.json"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"
FRED_SERIES: dict[str, tuple[str, str]] = {
    "NYダウ": ("DJIA", "Dow Jones Industrial Average"),
    "NASDAQ総合": ("NASDAQCOM", "Nasdaq Composite"),
    "S&P500": ("SP500", "S&P 500"),
}
EQUITY_MARKETS = {"NYダウ": "XNYS", "NASDAQ総合": "XNAS", "S&P500": "XNYS", "Russell 2000": "XNYS"}
JAPAN_MARKETS = {"日経225現物"}
CME_MARKETS = {"CME日経225先物・円建て", "CME日経225先物・ドル建て", "COMEX金先物", "WTI原油"}
WEEKDAY_MARKETS = {"USD/JPY", "EUR/USD"}

# Full 08:00 contract coverage. This records which established acquisition
# stage owns each row; it does not imply that the stage's current value is fresh.
MORNING_ROW_OWNERS = {
    "NYダウ": "daily-close-repair+yahoo-fred-crosscheck",
    "NASDAQ総合": "daily-close-repair+yahoo-fred-crosscheck",
    "S&P500": "daily-close-repair+yahoo-fred-crosscheck",
    "Russell 2000": "daily-close-repair+yahoo-only",
    "日経225現物": "daily-close-repair+yahoo-only",
    "CME日経225先物・円建て": "morning-reference:timestamped-contract-candidate; official-front-and-settlement-unverified",
    "CME日経225先物・ドル建て": "morning-reference:timestamped-contract-candidate; official-front-and-settlement-unverified",
    "日経225先物（大阪取引所）": "jpx-existing-delayed-quote; official-prior-settlement-unverified",
    "USD/JPY": "daily-close-repair+yahoo-only",
    "EUR/USD": "daily-close-repair+yahoo-only",
    "COMEX金先物": "daily-close-repair+yahoo-only",
    "WTI原油": "daily-close-repair+yahoo-only",
    "BTCUSD": "yahoo-chart:latest-completed-UTC-daily-bar; expected-session-derived-from-08-cutoff",
    "VIX": "daily-close-repair+yahoo-only",
    "日経VI": "configured-acquisition:not-close-verified",
    "Fear & Greed Index": "configured-acquisition:not-close-verified",
    "米10年債利回り": "rates-bonds-builder:exact-session-only",
    "日本10年国債利回り": "rates-bonds-builder:exact-session-only",
    "日経225予想PER": "capture-japan-close-reference:exact-session-only",
    "日経225 PBR": "capture-japan-close-reference:exact-session-only",
    "日経225予想EPS": "capture-japan-close-reference:exact-session-only",
    "日経225 25日移動平均乖離率": "capture-japan-close-reference:exact-session-only",
    "日経225 200日移動平均乖離率": "capture-japan-close-reference:exact-session-only",
    "東証プライム売買代金": "capture-japan-close-reference:exact-session-only",
    "東証プライム売買高": "capture-japan-close-reference:exact-session-only",
    "東証プライム値上がり銘柄数": "capture-japan-close-reference:exact-session-only",
    "東証プライム値下がり銘柄数": "capture-japan-close-reference:exact-session-only",
    "東証プライム25日騰落レシオ": "capture-japan-close-reference:exact-session-only",
}

# label -> Yahoo symbol, source name, display decimals
# OSE futures and Japanese valuation/breadth rows are handled by their existing
# source-specific captures because other instruments must never be substituted.
SYMBOLS: dict[str, tuple[str, str, int]] = {
    "NYダウ": ("^DJI", "Yahoo Finance Dow Jones Industrial Average", 2),
    "NASDAQ総合": ("^IXIC", "Yahoo Finance Nasdaq Composite", 2),
    "S&P500": ("^GSPC", "Yahoo Finance S&P 500", 2),
    "Russell 2000": ("^RUT", "Yahoo Finance Russell 2000", 2),
    "日経225現物": ("^N225", "Yahoo Finance Nikkei 225", 2),
    "BTCUSD": ("BTC-USD", "Yahoo Finance Bitcoin USD UTC daily close", 0),
    "CME日経225先物・円建て": ("NIY=F", "Yahoo Finance CME Nikkei/Yen Futures", 0),
    "CME日経225先物・ドル建て": ("NKD=F", "Yahoo Finance CME Nikkei/USD Futures", 0),
    "USD/JPY": ("JPY=X", "Yahoo Finance USD/JPY", 3),
    "EUR/USD": ("EURUSD=X", "Yahoo Finance EUR/USD", 5),
    "COMEX金先物": ("GC=F", "Yahoo Finance COMEX Gold Futures", 2),
    "WTI原油": ("CL=F", "Yahoo Finance NYMEX WTI Futures", 2),
    "VIX": ("^VIX", "Yahoo Finance CBOE Volatility Index", 2),
}

DERIVED_FROM_NIKKEI_CLOSE = (
    "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率",
)

SUMMARY_MARKETS: dict[str, tuple[str, str, str]] = {
    "金": ("COMEX金先物", "ドル/oz", ""),
    "WTI原油": ("WTI原油", "ドル/bbl", ""),
    "日経225先物（大阪取引所）": ("日経225先物（大阪取引所）", "円", ""),
    "USD/JPY": ("USD/JPY", "円", ""),
    "EUR/USD": ("EUR/USD", "", ""),
    "BTCUSD": ("BTCUSD", "ドル", ""),
}


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_chart(symbol: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"range": "10d", "interval": "1d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    result = (((payload.get("chart") or {}).get("result") or [None])[0])
    if not isinstance(result, dict):
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}")
    return result


def fetch_fred_close(series_id: str, target_date: dt.date) -> float:
    """Fetch the exact-date daily close from FRED's public observation CSV."""
    params = urllib.parse.urlencode({"id": series_id, "cosd": target_date.isoformat(), "coed": target_date.isoformat()})
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=25) as response:
        body = response.read().decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(body)))
    for row in rows:
        if row.get("observation_date") == target_date.isoformat():
            value = finite(row.get(series_id))
            if value is not None:
                return value
    raise RuntimeError(f"FRED {series_id} has no numeric observation for {target_date.isoformat()}")


def fetch_fred_observation(series_id: str, target_date: dt.date) -> tuple[float, float | None, str]:
    """Return exact-date value, prior observation delta, and source URL."""
    params = urllib.parse.urlencode({"id": series_id, "cosd": (target_date - dt.timedelta(days=14)).isoformat(), "coed": target_date.isoformat()})
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=25) as response:
        body = response.read().decode("utf-8-sig", errors="replace")
    points: list[tuple[dt.date, float]] = []
    for row in csv.DictReader(io.StringIO(body)):
        day = dt.date.fromisoformat(row.get("observation_date", ""))
        value = finite(row.get(series_id))
        if value is not None and day <= target_date:
            points.append((day, value))
    exact = [point for point in points if point[0] == target_date]
    if not exact:
        raise RuntimeError(f"FRED {series_id} has no numeric observation for {target_date.isoformat()}")
    previous = [point for point in points if point[0] < target_date]
    change = exact[0][1] - previous[-1][1] if previous else None
    return exact[0][1], change, url


def _market_holidays(market: str, year: int) -> set[dt.date]:
    try:
        import holidays
    except ImportError as exc:
        raise RuntimeError("market calendar dependency 'holidays' is unavailable") from exc
    calendar = holidays.financial_holidays(market, years={year})
    return set(calendar.keys())


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def completed_bars(
    result: dict[str, Any], report_date: dt.date, *, timezone_override: str | None = None
) -> list[tuple[dt.date, float]]:
    meta = result.get("meta") or {}
    tz_name = str(timezone_override or meta.get("exchangeTimezoneName") or "UTC")
    # UTC is available in the standard library even on Windows installations
    # that do not bundle the IANA tzdata database.
    tz = dt.timezone.utc if tz_name.upper() in {"UTC", "ETC/UTC", "GMT"} else ZoneInfo(tz_name)
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote.get("close") or []
    bars: list[tuple[dt.date, float]] = []
    for stamp, close in zip(timestamps, closes):
        value = finite(close)
        if value is None:
            continue
        date_value = dt.datetime.fromtimestamp(float(stamp), dt.timezone.utc).astimezone(tz).date()
        if date_value < report_date:
            bars.append((date_value, value))
    bars.sort(key=lambda item: item[0])
    return bars


def expected_prior_session(report_date: dt.date, label: str) -> dt.date:
    if label == "BTCUSD":
        # At 08:00 JST the current UTC daily candle has one hour left. Use only
        # the last fully closed UTC day bar; Monday therefore resolves to
        # Saturday's completed bar, while Tuesday resolves to Sunday's bar.
        cutoff_utc = (dt.datetime.combine(report_date, dt.time(8), tzinfo=JST) - dt.timedelta(seconds=1)).astimezone(dt.timezone.utc)
        return cutoff_utc.date() - dt.timedelta(days=1)
    market = EQUITY_MARKETS.get(label)
    if label in JAPAN_MARKETS:
        try:
            import jpholiday
        except ImportError as exc:
            raise RuntimeError("market calendar dependency 'jpholiday' is unavailable") from exc
        is_session = lambda day: day.weekday() < 5 and not jpholiday.is_holiday(day) and not (day.month == 1 and day.day <= 3 or day.month == 12 and day.day == 31)
    elif label in CME_MARKETS:
        market = "XCME"
    holidays_by_year: dict[int, set[dt.date]] = {}

    def is_session(day: dt.date) -> bool:
        if label in JAPAN_MARKETS:
            return day.weekday() < 5 and not jpholiday.is_holiday(day) and not (day.month == 1 and day.day <= 3 or day.month == 12 and day.day == 31)
        if day.weekday() >= 5:
            return False
        if market:
            if day.year not in holidays_by_year:
                holidays_by_year[day.year] = _market_holidays(market, day.year)
            return day not in holidays_by_year[day.year]
        return True

    candidate = report_date - dt.timedelta(days=1)
    while not is_session(candidate):
        candidate -= dt.timedelta(days=1)
    return candidate


def fmt_number(value: float, places: int) -> str:
    return f"{value:,.{places}f}"


def fmt_change(value: float, places: int) -> str:
    return f"{value:+,.{places}f}"


def direction(change: float, label: str) -> str:
    if label == "VIX":
        return "上昇" if change > 0 else "低下" if change < 0 else "横ばい"
    return "上昇" if change > 0 else "下落" if change < 0 else "横ばい"


def set_unavailable(row: dict[str, Any], reason: str) -> None:
    row["value"] = f"取得不能（{reason}）"
    row["change"] = "—"
    row["rate"] = "—"
    row["direction"] = "取得不能"


def apply_reference_candidate(
    row: dict[str, Any], candidate: dict[str, Any], expected_date: dt.date, *, label: str
) -> tuple[bool, str]:
    """Apply only a dated, numeric, source-attributed candidate for the exact session."""
    as_of = str(candidate.get("asOf") or "")
    data_date = str(candidate.get("date") or as_of or "")[:10]
    if data_date != expected_date.isoformat():
        return False, f"data date mismatch: expected {expected_date}, got {data_date or 'empty'}"
    if label.startswith("CME") or label.startswith("日経225先物（大阪"):
        if "T" not in as_of:
            return False, "quote timestamp missing"
        try:
            observed = dt.datetime.fromisoformat(as_of)
            cutoff = dt.datetime.combine(expected_date, dt.time(8, 5), tzinfo=JST)
            if observed.tzinfo is None or observed.astimezone(JST) > cutoff:
                return False, "quote was observed after the 08:05 cutoff"
        except ValueError:
            return False, "quote timestamp invalid"
    raw_value = candidate.get("value")
    if isinstance(raw_value, str):
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", raw_value)
        raw_value = match.group(0).replace(",", "") if match else None
    value = finite(raw_value)
    source_name = str(candidate.get("sourceName") or candidate.get("source") or "").strip()
    source_url = str(candidate.get("sourceUrl") or "").strip()
    if value is None or not source_name or not source_url:
        return False, "numeric value or source provenance missing"
    places = 3 if label in {"米10年債利回り", "日本10年国債利回り"} else 2
    suffix = "%" if label in {"米10年債利回り", "日本10年国債利回り"} else "円" if label == "日経225先物（大阪取引所）" else ""
    row["value"] = fmt_number(value, places) + suffix
    change = finite(candidate.get("change"))
    change_bp = finite(candidate.get("changeBp"))
    if change is not None:
        row["change"] = fmt_change(change, 3 if label in {"米10年債利回り", "日本10年国債利回り"} else 2)
        previous = value - change
        row["rate"] = f"{(change / previous * 100):+.2f}%" if previous else "—"
    elif change_bp is not None:
        row["change"] = f"{change_bp:+.1f}bp"
        row["rate"] = "—"
    else:
        row["change"] = "—"
        row["rate"] = "—"
    row["direction"] = str(candidate.get("direction") or ("上昇" if (change or change_bp or 0) > 0 else "下落" if (change or change_bp or 0) < 0 else "横ばい"))
    return True, ""


def load_close_candidates(report_date: dt.date) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    candidates: dict[str, dict[str, Any]] = {}
    gaps: dict[str, str] = {}
    japan_payload = load(JAPAN_REFERENCE) if JAPAN_REFERENCE.exists() else {}
    expected_jp = expected_prior_session(report_date, "日経225現物").isoformat()
    if japan_payload.get("dataDate") == expected_jp:
        for label, item in (japan_payload.get("items") or {}).items():
            if label in MORNING_ROW_OWNERS and isinstance(item, dict):
                value_text = str(item.get("value") or "")
                parsed_value = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value_text)
                if item.get("sourceName") and item.get("sourceUrl") and parsed_value and finite(parsed_value.group(0).replace(",", "")) is not None:
                    candidates[label] = item
                else:
                    gaps[label] = "Japanese candidate missing exact source URL or numeric value"
    else:
        for label in ("日経225現物", "日経VI", "日経225予想PER", "日経225 PBR", "日経225予想EPS", *DERIVED_FROM_NIKKEI_CLOSE, "東証プライム売買代金", "東証プライム売買高", "東証プライム値上がり銘柄数", "東証プライム値下がり銘柄数", "東証プライム25日騰落レシオ"):
            gaps[label] = f"Japan close reference date mismatch: expected {expected_jp}, got {japan_payload.get('dataDate') or 'empty'}"

    # Reuse the existing configured market-data acquisition for rows whose
    # source declares the exchange-local session date. Never infer a close from
    # a JST timestamp: U.S. sessions commonly cross the JST date boundary.
    market_payload = load(ROOT / "data" / "market" / "latest.json") if (ROOT / "data" / "market" / "latest.json").exists() else {}
    market_ids = {
        "Russell 2000": "russell2000", "USD/JPY": "usdjpy", "EUR/USD": "eurusd",
        "COMEX金先物": "gold", "WTI原油": "wti", "VIX": "vix",
    }
    market_ids.update({"NYダウ": "dow", "NASDAQ総合": "nasdaq", "S&P500": "sp500"})
    market_values = market_payload.get("markets") or {}
    for label, market_id in market_ids.items():
        if label in candidates or label in FRED_SERIES:
            continue
        item = market_values.get(market_id)
        if not isinstance(item, dict) or item.get("verificationStatus") != "verified":
            continue
        expected_date = expected_prior_session(report_date, label).isoformat()
        if str(item.get("sessionDate") or "") != expected_date:
            gaps[label] = f"market snapshot session date mismatch: expected {expected_date}, got {item.get('sessionDate') or 'empty'}"
            continue
        if finite(item.get("value")) is None or not item.get("sourceName") or not item.get("sourceUrl"):
            gaps[label] = "market snapshot missing numeric value or source provenance"
            continue
        candidates[label] = {
            "date": expected_date,
            "value": item.get("value"),
            "change": item.get("change"),
            "changePercent": item.get("changePercent"),
            "previousClose": item.get("previousClose"),
            "sourceName": item.get("sourceName"),
            "sourceUrl": item.get("sourceUrl"),
            "symbol": item.get("sourceId"),
            "retrievedAt": item.get("fetchedAt"),
        }

    morning_payload = load(MORNING_REFERENCE) if MORNING_REFERENCE.exists() else {}
    if morning_payload.get("reportDate") == report_date.isoformat() and morning_payload.get("reportSlot") == "08:00":
        for label, item in (morning_payload.get("items") or {}).items():
            if label in {"CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）"} and isinstance(item, dict):
                status = str(item.get("status") or "")
                as_of_text = str(item.get("asOf") or "")
                try:
                    observed = dt.datetime.fromisoformat(as_of_text)
                    cutoff = dt.datetime.combine(report_date, dt.time(8, 5), tzinfo=JST)
                    before_cutoff = observed.tzinfo is not None and observed.astimezone(JST) <= cutoff
                except ValueError:
                    before_cutoff = False
                if status.startswith("verified") and before_cutoff and item.get("contract") and item.get("contractIsFront") is True and item.get("sourceUrl"):
                    candidates[label] = {**item, "date": report_date.isoformat(), "contractIsFront": bool(item.get("contractIsFront"))}

    rates_payload = load(RATES_REFERENCE) if RATES_REFERENCE.exists() else {}
    rates = rates_payload.get("rates") or []
    if isinstance(rates, list):
        for item in rates:
            if not isinstance(item, dict):
                continue
            label = str(item.get("name") or "")
            if label not in {"米10年債利回り", "日本10年国債利回り"}:
                continue
            source_text = str(item.get("source") or "")
            source_url = str(item.get("sourceUrl") or "")
            if not source_url:
                if source_text == "FRED DGS10":
                    source_url = "https://fred.stlouisfed.org/series/DGS10"
                elif "財務省" in source_text:
                    source_url = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"
                elif "TradingView" in source_text:
                    source_url = "https://www.tradingview.com/symbols/TVC-JP10Y/"
            if item.get("status") in {"confirmed", "verified"} and source_url:
                rate_date = item.get("asOf")
                if rate_date is None:
                    continue
                market_date = expected_prior_session(report_date, label).isoformat()
                if str(rate_date) != market_date:
                    gaps[label] = f"rate observation date mismatch: expected {market_date}, got {rate_date}"
                    continue
                candidates[label] = {
                    "value": item.get("value"), "changeBp": item.get("changeBp"),
                    "date": rate_date, "sourceName": item.get("source"),
                    "sourceUrl": source_url,
                    "previousClose": (finite(item.get("value")) - finite(item.get("changeBp")) / 100.0)
                    if finite(item.get("value")) is not None and finite(item.get("changeBp")) is not None else None,
                }
    return candidates, gaps


def row_item_for_build_input(label: str, row: dict[str, Any], metadata: dict[str, Any], report_date: dt.date) -> dict[str, Any]:
    item = metadata.get(label) or {}
    value_text = str(row.get("value") or "")
    numeric_match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value_text)
    data_date = item.get("dataDate") or item.get("date") or ""
    expected_date = expected_prior_session(report_date, label).isoformat()
    available = bool(
        label in metadata and data_date == expected_date
        and not value_text.startswith("取得不能") and numeric_match
        and item.get("sourceName") and item.get("sourceUrl")
    )
    return {
        "value": finite(numeric_match.group(0).replace(",", "")) if available else None,
        "previousClose": finite(item.get("previousClose")) if available else None,
        "displayValue": value_text,
        "change": finite(re.sub(r"[^0-9.+-]", "", str(row.get("change") or ""))) if available else None,
        "changePercent": finite(re.sub(r"[^0-9.+-]", "", str(row.get("rate") or ""))) if available else None,
        "asOf": data_date,
        "expectedSessionDate": expected_date,
        "fetchedAt": item.get("retrievedAt") or item.get("fetchedAt") or "",
        "sourceId": item.get("symbol") or item.get("seriesId") or item.get("contract") or label,
        "sourceName": item.get("sourceName") or "",
        "sourceUrl": item.get("sourceUrl") or "",
        "marketType": "previous_close",
        "session": "prior_market_session",
        "verificationStatus": "verified" if available and data_date else "unavailable",
        "error": None if available and data_date else item.get("reason") or "exact-date source evidence unavailable",
    }


def build_coverage_manifest(
    report_date: dt.date, items: dict[str, Any], unavailable: dict[str, str]
) -> dict[str, Any]:
    from build_chatgpt_report_input import ITEMS
    from enrich_latest_morning_from_sheet import MAP as CLOSE_SHEET_MAP

    contract = {entry[0]: entry for entry in ITEMS}
    coverage: dict[str, Any] = {}
    for label, owner in MORNING_ROW_OWNERS.items():
        entry = items.get(label) or {}
        row_contract = contract.get(label)
        sheet_map = CLOSE_SHEET_MAP.get(label) or {}
        columns = [str(value) for value in sheet_map.values() if value]
        expected_date = expected_prior_session(report_date, label).isoformat()
        coverage[label] = {
            "owner": owner,
            "marketInputId": row_contract[1] if row_contract else None,
            "marketType": row_contract[3] if row_contract else None,
            "session": row_contract[4] if row_contract else None,
            "expectedSessionDate": expected_date,
            "status": "verified" if entry.get("dataDate") == expected_date and label not in unavailable else "preserved_or_unavailable",
            "dataDate": entry.get("dataDate"),
            "closeSheetFields": columns,
            "destination": "終値一覧" if columns else "report-only; no direct 終値一覧 column",
            "reason": unavailable.get(label) or ("source exists but is not integrated into this repair" if label not in items else None),
        }
    return coverage


def build_chatgpt_input_payload(report: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import build_chatgpt_report_input as contract
    except ImportError:
        return None
    rows = ((report.get("marketDataTable") or {}).get("rows") or [])
    by_label = {str(row.get("label") or "").strip(): row for row in rows if isinstance(row, dict)}
    if len(by_label) != 28 or set(by_label) != {entry[0] for entry in contract.ITEMS}:
        return None
    items = report.get("dataProvenance", {}).get("dailyCloseRepair", {}).get("items", {})
    unavailable = report.get("dataProvenance", {}).get("dailyCloseRepair", {}).get("unavailable", {})
    markets = {}
    session_dates: dict[str, str] = {}
    unavailable_labels = []
    for label, symbol_id, unit, market_type, session in contract.ITEMS:
        market_item = row_item_for_build_input(label, by_label[label], {label: items.get(label, {})} if label in items else {}, dt.date.fromisoformat(str(report["date"])))
        market_item.update({"id": symbol_id, "displayName": label, "unit": unit, "marketType": market_type, "session": session})
        if market_item.get("verificationStatus") == "verified":
            session_dates[symbol_id] = market_item["asOf"]
        if label in unavailable or market_item["verificationStatus"] != "verified":
            market_item["verificationStatus"] = "unavailable"
            market_item["error"] = unavailable.get(label) or market_item["error"] or "date-matched close not verified"
            unavailable_labels.append(label)
        markets[symbol_id] = market_item
    return {
        "schemaVersion": "2.2.0", "pageId": "market-data", "reportDate": report.get("date"),
        "reportSlot": "08:00", "dataSemantics": "previous_close",
        "previousCloseDate": next(iter(set(session_dates.values()))) if len(set(session_dates.values())) == 1 else None,
        "sessionDates": session_dates,
        "overallStatus": "degraded" if unavailable_labels else "verified",
        "dataComplete": not unavailable_labels, "availableCount": 28 - len(unavailable_labels),
        "expectedCount": 28, "unavailableLabels": unavailable_labels, "fallbackCount": 0,
        "markets": markets, "contract": {"rowCount": 28, "semantics": "previous_close", "source": "validated report rows and acquisition provenance"},
    }


def require_cross_market_match(label: str, value: float, fred_value: float) -> float:
    tolerance = max(0.02, abs(fred_value) * 0.00001)
    if abs(value - fred_value) > tolerance:
        raise RuntimeError(
            f"Yahoo/FRED close divergence for {label}: Yahoo={value}, FRED={fred_value}, tolerance={tolerance}"
        )
    return tolerance


def rewrite_market_block(report: dict[str, Any]) -> None:
    text = str(report.get("fullText") or "")
    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else None
    if not text or not isinstance(rows, list) or len(rows) != 28:
        return
    block = ["【主要市場データ】", "項目\t終値・値\t前日比\t騰落率\t方向感"]
    for row in rows:
        block.append("\t".join(str(row.get(key) or "—") for key in ("label", "value", "change", "rate", "direction")))
    replacement = "\n".join(block) + "\n\n"
    pattern = re.compile(r"【主要市場データ】\s*\n.*?(?=\n【[^\n]+】)", re.S)
    if pattern.search(text):
        report["fullText"] = pattern.sub(replacement.rstrip("\n"), text, count=1)


def summary_price(label: str, row: dict[str, Any]) -> str:
    value = str(row.get("value") or "").strip()
    if not value or value.startswith("取得不能"):
        return value
    suffix = SUMMARY_MARKETS[label][1]
    if suffix and not value.endswith(suffix):
        if suffix == "円" and value.endswith("円"):
            return value
        return value + suffix
    return value


def synchronize_summary_prices(report: dict[str, Any], by_label: dict[str, dict[str, Any]]) -> None:
    markets = report.get("markets")
    if not isinstance(markets, list):
        return
    text = str(report.get("fullText") or "")
    for market in markets:
        if not isinstance(market, dict):
            continue
        name = str(market.get("name") or "")
        spec = SUMMARY_MARKETS.get(name)
        if not spec:
            continue
        table_label = spec[0]
        row = by_label.get(table_label)
        if not isinstance(row, dict):
            continue
        new_price = summary_price(name, row)
        if not new_price or new_price.startswith("取得不能"):
            continue
        old_price = str(market.get("price") or "")
        market["price"] = new_price
        if old_price and old_price != new_price:
            text = text.replace(old_price, new_price)
    report["fullText"] = text


def main() -> int:
    payload = load(LATEST)
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict) or report.get("time") != "08:00":
        print("Latest report is not 08:00; previous-close repair skipped")
        return 0
    report_date = dt.date.fromisoformat(str(report.get("date")))
    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list) or len(rows) != 28:
        raise SystemExit("08:00 marketDataTable must contain 28 rows before previous-close repair")
    by_label = {str(row.get("label") or "").strip(): row for row in rows if isinstance(row, dict)}

    items: dict[str, Any] = {}
    repaired: list[str] = []
    unavailable: dict[str, str] = {}
    external_candidates, external_gaps = load_close_candidates(report_date)
    nikkei_date_verified = False
    all_source_labels = list(MORNING_ROW_OWNERS)
    for label in all_source_labels:
        row = by_label.get(label)
        if row is None:
            unavailable[label] = "structured row missing"
            continue
        expected_date = expected_prior_session(report_date, label)
        original_row = dict(row)
        symbol_spec = SYMBOLS.get(label)
        try:
            if label in external_candidates:
                candidate = external_candidates[label]
                if label in {"CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）"}:
                    expiry = str(candidate.get("contract") or "")
                    contract_is_front = candidate.get("contractIsFront")
                    if not expiry:
                        raise RuntimeError("CME/OSE candidate contract is missing")
                applied, reason = apply_reference_candidate(by_label[label], candidate, expected_date, label=label)
                if applied:
                    items[label] = {
                        "value": by_label[label]["value"], "change": by_label[label]["change"],
                        "previousClose": candidate.get("previousClose"),
                        "rate": by_label[label]["rate"], "direction": by_label[label]["direction"],
                        "dataDate": expected_date.isoformat(), "sourceName": candidate.get("sourceName") or candidate.get("source"),
                        "sourceUrl": candidate.get("sourceUrl"), "contract": candidate.get("contract"),
                        "contractIsFront": contract_is_front if label in {"CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）"} else None,
                        "status": "verified_date_matched_previous_close",
                        "retrievedAt": now_jst().isoformat(),
                    }
                    repaired.append(label)
                    continue
                row.update(original_row)
                unavailable[label] = reason
                continue
            if label in external_gaps:
                row.update(original_row)
                unavailable[label] = external_gaps[label]
                continue
            if symbol_spec is None:
                reason = "no integrated exact-date source candidate"
                unavailable[label] = reason
                continue
            symbol, source_name, places = symbol_spec
            result = fetch_chart(symbol)
            bars = completed_bars(result, report_date, timezone_override="UTC" if label == "BTCUSD" else None)
            if len(bars) < 2:
                raise RuntimeError("fewer than two completed pre-report daily bars")
            if label == "BTCUSD":
                target_date = expected_date
                matching = [bar for bar in bars if bar[0] == expected_date]
                if not matching:
                    raise RuntimeError(f"latest completed UTC daily bar {expected_date.isoformat()} is unavailable")
                target_date, value = matching[-1]
            else:
                target_date, value = bars[-1]
            if target_date != expected_date:
                reason = (
                    f"{expected_date.isoformat()}基準の前日終値を取得できず。"
                    f"取得可能な最新日付は{target_date.isoformat()}のため不採用"
                )
                set_unavailable(row, reason)
                unavailable[label] = reason
                continue
            fred_observation: dict[str, Any] | None = None
            fred_spec = FRED_SERIES.get(label)
            if fred_spec:
                fred_id, fred_name = fred_spec
                fred_value, fred_change, fred_url = fetch_fred_observation(fred_id, expected_date)
                tolerance = require_cross_market_match(label, value, fred_value)
                fred_observation = {"seriesId": fred_id, "sourceName": f"FRED {fred_name}", "sourceUrl": fred_url, "dataDate": expected_date.isoformat(), "value": fred_value}
            earlier_bars = [bar for bar in bars if bar[0] < target_date]
            if not earlier_bars:
                raise RuntimeError("previous completed daily bar is unavailable for change calculation")
            previous_date, previous = earlier_bars[-1]
            change = value - previous
            if fred_spec and fred_change is not None:
                change = fred_change
            rate = (change / previous * 100.0) if previous else 0.0
            row["value"] = fmt_number(value, places)
            row["change"] = fmt_change(change, places)
            row["rate"] = f"{rate:+.2f}%"
            row["direction"] = direction(change, label)
            items[label] = {
                "symbol": symbol,
                "value": row["value"],
                "previousClose": fmt_number(previous, places),
                "change": row["change"],
                "rate": row["rate"],
                "direction": row["direction"],
                "dataDate": target_date.isoformat(),
                "previousDate": previous_date.isoformat(),
                "sourceName": source_name + ("; cross-checked with " + str(fred_observation["sourceName"]) if fred_observation else ""),
                "sourceUrl": (str(fred_observation["sourceUrl"]) if fred_observation else f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/history/"),
                "crossCheck": fred_observation,
                "status": "verified_date_matched_previous_close",
                "retrievedAt": now_jst().isoformat(),
            }
            repaired.append(label)
            if label == "日経225現物":
                nikkei_date_verified = True
        except Exception as exc:
            reason = f"{expected_date.isoformat()}基準の前日終値を取得できず: {exc}"
            if symbol_spec is not None:
                set_unavailable(row, reason)
            else:
                row.update(original_row)
            unavailable[label] = reason

    if not nikkei_date_verified and "日経225現物" not in repaired:
        expected_date = expected_prior_session(report_date, "日経225現物")
        for label in DERIVED_FROM_NIKKEI_CLOSE:
            row = by_label.get(label)
            if row is not None:
                reason = f"{expected_date.isoformat()}の日経225現物終値を確認できないため算定値を不採用"
                set_unavailable(row, reason)
                unavailable[label] = reason

    rewrite_market_block(report)
    synchronize_summary_prices(report, by_label)
    report.setdefault("dataProvenance", {})["dailyCloseRepair"] = {
        "generatedAt": now_jst().isoformat(),
        "semantics": "previous_close",
        "rule": "08:00 uses date-matched prior-session closes; retrieval after 08:00 is allowed, stale-date carry-forward is prohibited; BTCUSD keeps its dedicated 24/7-market convention",
        "repairedLabels": repaired,
        "unavailable": unavailable,
    }
    report["dataProvenance"]["morningCoverage"] = {
        "contractCount": len(MORNING_ROW_OWNERS),
        "verifiedCount": sum(1 for label in MORNING_ROW_OWNERS if label in items and label not in unavailable and items[label].get("dataDate")),
        "items": build_coverage_manifest(report_date, items, unavailable),
    }
    report["dataProvenance"]["dailyCloseRepair"]["items"] = {
        label: {
            **items.get(label, {}),
            **({"status": "unavailable", "reason": unavailable[label]} if label in unavailable else {}),
        }
        for label in MORNING_ROW_OWNERS
    }
    # Write the same validated market candidates into the independent 28-row
    # input contract. Unverified retained cells stay unavailable in metadata.
    market_latest_path = ROOT / "data" / "market" / "latest.json"
    try:
        market_payload = load(market_latest_path)
    except (OSError, json.JSONDecodeError):
        market_payload = {}
    if market_payload.get("reportSlot") == "08:00" and market_payload.get("reportDate") == report_date.isoformat():
        markets = market_payload.setdefault("markets", {})
        row_items = report["dataProvenance"]["dailyCloseRepair"]["items"]
        for label in MORNING_ROW_OWNERS:
            if label in by_label:
                source_item = row_items.get(label) or {}
                candidate_item = {
                    "dataDate": source_item.get("dataDate"),
                    "sourceName": source_item.get("sourceName"),
                    "sourceUrl": source_item.get("sourceUrl"),
                    "symbol": source_item.get("symbol") or source_item.get("seriesId") or source_item.get("contract"),
                    "retrievedAt": source_item.get("retrievedAt"),
                    "reason": source_item.get("reason"),
                }
                if label in unavailable:
                    candidate_item["reason"] = unavailable[label]
                market_id = next((entry[1] for entry in __import__("build_chatgpt_report_input").ITEMS if entry[0] == label), label)
                markets[market_id] = row_item_for_build_input(label, by_label[label], {label: candidate_item} if source_item.get("dataDate") else {}, report_date)
        market_payload["overallStatus"] = "degraded" if unavailable else "verified"
        market_payload["unavailableLabels"] = [label for label in MORNING_ROW_OWNERS if label in unavailable]
        market_payload["dataComplete"] = not unavailable
        market_payload["availableCount"] = sum(1 for label in MORNING_ROW_OWNERS if label in items and label not in unavailable and items[label].get("dataDate"))
        market_payload["expectedCount"] = 28
        save(market_latest_path, market_payload)
    input_payload = build_chatgpt_input_payload(report)
    if input_payload is not None:
        input_path = ROOT / "data" / "market" / "chatgpt-input.json"
        save(input_path, input_payload)
    save(LATEST, payload)
    save(OUT, {
        "schemaVersion": "2.2.0",
        "generatedAt": now_jst().isoformat(),
        "reportDate": report_date.isoformat(),
        "reportSlot": "08:00",
        "semantics": "previous_close",
        "items": items,
        "unavailable": unavailable,
        "coverage": report["dataProvenance"]["morningCoverage"],
    })
    print(json.dumps({"repaired": repaired, "unavailable": unavailable}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
