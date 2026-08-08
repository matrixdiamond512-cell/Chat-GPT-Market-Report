#!/usr/bin/env python3
"""Build 26-week CFTC Managed Money history for the gold supply-demand page.

Data sources:
- CFTC Disaggregated Futures Only (COMEX Gold, market code 088691)
- Yahoo Finance GC=F daily closes for a contextual gold-price overlay

The CFTC series is the primary data. Gold price is optional context and is left
null when a matching/preceding daily close cannot be verified.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "gold-cftc-history.json"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"
CFTC_API = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"


def now_iso() -> str:
    return datetime.now(JST).replace(microsecond=0).isoformat()


def num(value: Any) -> float | None:
    try:
        x = float(str(value).replace(",", "").strip())
        return x if math.isfinite(x) else None
    except Exception:
        return None


def integer(value: Any) -> int | None:
    x = num(value)
    return int(round(x)) if x is not None else None


def load_previous() -> dict[str, Any] | None:
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get(url: str, *, params: dict[str, Any] | None = None, timeout: int = 35) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": UA, "Accept": "application/json,*/*"},
    )
    response.raise_for_status()
    return response


def fetch_gold_daily() -> list[tuple[str, float]]:
    try:
        response = get(
            YAHOO_CHART,
            params={"range": "6mo", "interval": "1d", "events": "history"},
        )
        result = ((response.json().get("chart") or {}).get("result") or [None])[0] or {}
        timestamps = result.get("timestamp") or []
        closes = ((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
        out: list[tuple[str, float]] = []
        for ts, close in zip(timestamps, closes):
            price = num(close)
            if price is None:
                continue
            day = datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()
            out.append((day, price))
        out.sort(key=lambda row: row[0])
        return out
    except Exception:
        return []


def price_on_or_before(prices: list[tuple[str, float]], target: str) -> float | None:
    candidates = [price for day, price in prices if day <= target]
    return candidates[-1] if candidates else None


def build() -> dict[str, Any]:
    fields = ",".join(
        [
            "report_date_as_yyyy_mm_dd",
            "open_interest_all",
            "m_money_positions_long_all",
            "m_money_positions_short_all",
        ]
    )
    params = {
        "$select": fields,
        "$where": "cftc_contract_market_code='088691'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "26",
    }
    rows = get(CFTC_API, params=params).json()
    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError("CFTC returned insufficient COMEX Gold history")

    prices = fetch_gold_daily()
    history: list[dict[str, Any]] = []
    for row in reversed(rows):
        as_of = str(row.get("report_date_as_yyyy_mm_dd") or "")[:10]
        long_value = integer(row.get("m_money_positions_long_all"))
        short_value = integer(row.get("m_money_positions_short_all"))
        open_interest = integer(row.get("open_interest_all"))
        net = long_value - short_value if long_value is not None and short_value is not None else None
        history.append(
            {
                "asOfDate": as_of,
                "long": long_value,
                "short": short_value,
                "net": net,
                "openInterest": open_interest,
                "goldPrice": price_on_or_before(prices, as_of),
            }
        )

    for index, item in enumerate(history):
        previous = history[index - 1] if index else None
        item["longChange"] = (
            item["long"] - previous["long"]
            if previous and item.get("long") is not None and previous.get("long") is not None
            else None
        )
        item["shortChange"] = (
            item["short"] - previous["short"]
            if previous and item.get("short") is not None and previous.get("short") is not None
            else None
        )
        item["netChange"] = (
            item["net"] - previous["net"]
            if previous and item.get("net") is not None and previous.get("net") is not None
            else None
        )

    latest = history[-1]
    change = latest.get("netChange")
    judgement = "横ばい"
    if isinstance(change, (int, float)):
        judgement = "買い越し拡大" if change > 0 else "買い越し縮小" if change < 0 else "横ばい"

    return {
        "schemaVersion": "1.0.0",
        "status": "verified",
        "generatedAt": now_iso(),
        "asOfDate": latest.get("asOfDate"),
        "weeks": len(history),
        "latest": {
            "long": latest.get("long"),
            "short": latest.get("short"),
            "net": latest.get("net"),
            "longChange": latest.get("longChange"),
            "shortChange": latest.get("shortChange"),
            "netChange": latest.get("netChange"),
            "openInterest": latest.get("openInterest"),
            "goldPrice": latest.get("goldPrice"),
            "judgement": judgement,
        },
        "history": history,
        "sourceName": "CFTC Disaggregated COT - Futures Only",
        "sourceUrl": "https://publicreporting.cftc.gov/Commitments-of-Traders/Disaggregated-Futures-Only/72hh-3qpy",
        "goldPriceSourceName": "Yahoo Finance Gold Futures",
        "goldPriceSourceUrl": "https://finance.yahoo.com/quote/GC=F/",
        "note": "CFTC is weekly and lagged. Gold price is contextual and uses the latest available GC=F daily close on or before each report date.",
    }


def main() -> None:
    previous = load_previous()
    try:
        payload = build()
    except Exception as exc:
        if previous and isinstance(previous.get("history"), list) and previous.get("history"):
            payload = dict(previous)
            payload["status"] = "stale"
            payload["generatedAt"] = now_iso()
            payload["error"] = f"CFTC history update failed: {type(exc).__name__}: {exc}"
        else:
            payload = {
                "schemaVersion": "1.0.0",
                "status": "unavailable",
                "generatedAt": now_iso(),
                "history": [],
                "error": f"CFTC history update failed: {type(exc).__name__}: {exc}",
                "sourceName": "CFTC Disaggregated COT - Futures Only",
                "sourceUrl": "https://publicreporting.cftc.gov/Commitments-of-Traders/Disaggregated-Futures-Only/72hh-3qpy",
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} status={payload.get('status')} weeks={len(payload.get('history') or [])}")


if __name__ == "__main__":
    main()
