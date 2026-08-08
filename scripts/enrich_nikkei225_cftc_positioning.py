#!/usr/bin/env python3
"""Add 26-week CFTC TFF Leveraged Funds positioning to Nikkei 225 supply-demand JSON.

Official CFTC Traders in Financial Futures (TFF), futures-only dataset is used because
Nikkei 225 is a financial futures contract. The relevant contract is CFTC code 240743
(NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE).

No values are guessed. If the CFTC request fails, a previous verified series is retained
as stale when available; otherwise the section is marked unavailable. Nikkei 225 cash
closes are contextual only and are fetched from Yahoo Finance as a secondary source.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

DATA_PATH = Path("data/nikkei225-supply-demand.json")
CFTC_DATASET_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
CFTC_PAGE_URL = "https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if"
CFTC_CONTRACT_CODE = "240743"
CFTC_CONTRACT_NAME = "NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EN225"
YAHOO_HISTORY_URL = "https://finance.yahoo.com/quote/%5EN225/history/"
LOOKBACK_WEEKS = 26
JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)",
    "Accept": "application/json,text/plain,*/*",
}


def now_jst() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def n(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def date_only(value: Any) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def judgement(net: int, net_change: int) -> str:
    if net > 0 and net_change > 0:
        return "買い越し拡大"
    if net > 0 and net_change < 0:
        return "買い越し縮小"
    if net < 0 and net_change < 0:
        return "売り越し拡大"
    if net < 0 and net_change > 0:
        return "売り越し縮小"
    if net > 0:
        return "買い越し横ばい"
    if net < 0:
        return "売り越し横ばい"
    return "中立"


def change_comment(long_change: int, short_change: int) -> str:
    if long_change > 0 and short_change < 0:
        return "ロング増・ショート減"
    if long_change > 0 and short_change > 0:
        return "ロング・ショートとも増加"
    if long_change < 0 and short_change < 0:
        return "ロング・ショートとも減少"
    if long_change < 0 and short_change > 0:
        return "ロング減・ショート増"
    if long_change > 0:
        return "ロング増加"
    if long_change < 0:
        return "ロング減少"
    if short_change > 0:
        return "ショート増加"
    if short_change < 0:
        return "ショート減少"
    return "前週から横ばい"


def fetch_cftc() -> list[dict[str, Any]]:
    params = {
        "$where": f"cftc_contract_market_code='{CFTC_CONTRACT_CODE}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": str(LOOKBACK_WEEKS),
    }
    r = requests.get(CFTC_DATASET_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError(f"CFTC TFF returned insufficient rows: {len(rows) if isinstance(rows, list) else 'invalid'}")

    out: list[dict[str, Any]] = []
    for row in rows:
        report_date = date_only(row.get("report_date_as_yyyy_mm_dd"))
        long_pos = n(row.get("lev_money_positions_long"))
        short_pos = n(row.get("lev_money_positions_short"))
        if not report_date or long_pos is None or short_pos is None:
            continue
        out.append({
            "date": report_date,
            "long": long_pos,
            "short": short_pos,
            "net": long_pos - short_pos,
        })
    if len(out) < 2:
        raise RuntimeError("CFTC TFF rows did not contain usable Leveraged Funds fields")
    out.sort(key=lambda x: x["date"])
    return out[-LOOKBACK_WEEKS:]


def fetch_nikkei_prices(report_dates: list[str]) -> tuple[dict[str, float], str | None]:
    if not report_dates:
        return {}, "CFTC report dates are empty"
    start = datetime.fromisoformat(min(report_dates)).replace(tzinfo=timezone.utc) - timedelta(days=10)
    end = datetime.fromisoformat(max(report_dates)).replace(tzinfo=timezone.utc) + timedelta(days=3)
    params = {
        "period1": str(int(start.timestamp())),
        "period2": str(int(end.timestamp())),
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    try:
        r = requests.get(YAHOO_CHART_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        result = r.json().get("chart", {}).get("result") or []
        if not result:
            return {}, "Yahoo Finance chart response contained no result"
        item = result[0]
        timestamps = item.get("timestamp") or []
        closes = ((item.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        daily: dict[str, float] = {}
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            day = datetime.fromtimestamp(int(ts), timezone.utc).astimezone(JST).date().isoformat()
            daily[day] = float(close)
        mapped: dict[str, float] = {}
        available = sorted(daily)
        for target in report_dates:
            candidates = [d for d in available if d <= target]
            if not candidates:
                continue
            chosen = candidates[-1]
            if (datetime.fromisoformat(target) - datetime.fromisoformat(chosen)).days <= 7:
                mapped[target] = daily[chosen]
        if not mapped:
            return {}, "Yahoo Finance returned no close matching CFTC report weeks"
        return mapped, None
    except Exception as exc:  # secondary source failure must not fail CFTC section
        return {}, f"Yahoo Finance price history unavailable: {exc}"


def build_section(cftc_rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_dates = [x["date"] for x in cftc_rows]
    prices, price_error = fetch_nikkei_prices(report_dates)
    total = len(cftc_rows)
    series: list[dict[str, Any]] = []
    for i, row in enumerate(cftc_rows):
        weeks_ago = total - 1 - i
        label = "今週" if weeks_ago == 0 else f"{weeks_ago}週前"
        series.append({
            "label": label,
            "week": row["date"],
            "long": row["long"],
            "short": row["short"],
            "net": row["net"],
            "price": prices.get(row["date"]),
        })

    latest, previous = cftc_rows[-1], cftc_rows[-2]
    long_change = latest["long"] - previous["long"]
    short_change = latest["short"] - previous["short"]
    net_change = latest["net"] - previous["net"]
    price_count = sum(1 for x in series if x.get("price") is not None)

    return {
        "sourceName": "CFTC Traders in Financial Futures (TFF) - Futures Only",
        "sourceUrl": CFTC_PAGE_URL,
        "apiUrl": CFTC_DATASET_URL,
        "contract": CFTC_CONTRACT_NAME,
        "cftcContractMarketCode": CFTC_CONTRACT_CODE,
        "classification": "Leveraged Funds",
        "classificationNote": "金融先物のためTFFのLeveraged Fundsを使用。ゴールド等のDisaggregated COTにあるManaged Moneyとは分類体系が異なります。",
        "comment": "CFTC週次ポジションはCME円建て日経225先物のLeveraged Fundsを示す中期補助指標です。大阪取引所の日経225先物建玉、JPX投資部門別、参加者別建玉とは別データとして扱います。",
        "asOfDate": latest["date"],
        "status": "verified",
        "releaseFrequency": "weekly",
        "lookbackWeeks": total,
        "fetchedAt": now_jst(),
        "priceSourceName": "Yahoo Finance 日経225 (^N225) historical close",
        "priceSourceUrl": YAHOO_HISTORY_URL,
        "priceStatus": "available" if price_count >= 2 else "unavailable",
        "pricePointCount": price_count,
        "priceReason": price_error,
        "latest": {
            "net": latest["net"],
            "netChange": net_change,
            "long": latest["long"],
            "longChange": long_change,
            "short": latest["short"],
            "shortChange": short_change,
            "judgement": judgement(latest["net"], net_change),
            "judgementSub": change_comment(long_change, short_change),
        },
        "series": series,
    }


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    previous = data.get("speculativePositioning") if isinstance(data.get("speculativePositioning"), dict) else None
    try:
        rows = fetch_cftc()
        data["speculativePositioning"] = build_section(rows)
    except Exception as exc:
        reason = f"CFTC TFF positioning acquisition failed: {exc}"
        if previous and previous.get("series"):
            stale = dict(previous)
            stale["status"] = "stale"
            stale["error"] = reason
            stale["lastAttemptAt"] = now_jst()
            data["speculativePositioning"] = stale
        else:
            data["speculativePositioning"] = {
                "sourceName": "CFTC Traders in Financial Futures (TFF) - Futures Only",
                "sourceUrl": CFTC_PAGE_URL,
                "apiUrl": CFTC_DATASET_URL,
                "contract": CFTC_CONTRACT_NAME,
                "cftcContractMarketCode": CFTC_CONTRACT_CODE,
                "classification": "Leveraged Funds",
                "asOfDate": None,
                "status": "unavailable",
                "releaseFrequency": "weekly",
                "lookbackWeeks": 0,
                "fetchedAt": now_jst(),
                "error": reason,
                "series": [],
            }

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    section = data.get("speculativePositioning") or {}
    print(json.dumps({
        "status": section.get("status"),
        "asOfDate": section.get("asOfDate"),
        "lookbackWeeks": section.get("lookbackWeeks"),
        "classification": section.get("classification"),
        "latest": section.get("latest"),
        "priceStatus": section.get("priceStatus"),
        "error": section.get("error"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
