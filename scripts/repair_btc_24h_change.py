#!/usr/bin/env python3
"""Repair BTCUSD comparison for the 08:00 report.

BTC trades 24/7, so the morning dashboard must not apply the weekday
"previous business-day close" rule used by equities.  For BTCUSD, the displayed
前日比 is defined as the change from the report-time price to the nearest verified
Yahoo Finance BTC-USD hourly close around exactly 24 hours before the report time.

The report's published BTC price is preserved.  Only the comparison reference,
change, rate, and provenance are repaired.  The generated market JSONs are patched
as well so the dashboard cannot regress to 取得不能 after publication overwrites the
independent market snapshot.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST_REPORT = ROOT / "data" / "latest-report.json"
MARKET_LATEST = ROOT / "data" / "market" / "latest.json"
CHATGPT_INPUT = ROOT / "data" / "market" / "chatgpt-input.json"
JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc
USER_AGENT = "Mozilla/5.0 (compatible; MarketReportBot/1.0)"
NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numeric(value: Any) -> float | None:
    match = NUM_RE.search(str(value or ""))
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def report_object(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("latestReport") or payload.get("report") or payload
    return value if isinstance(value, dict) else {}


def report_datetime(report: dict[str, Any]) -> dt.datetime:
    date_text = str(report.get("date") or "").strip()
    time_text = str(report.get("time") or "08:00").strip()
    parsed = dt.datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    return parsed.replace(tzinfo=JST)


def fetch_hourly_btc() -> list[tuple[dt.datetime, float]]:
    params = urllib.parse.urlencode({"range": "5d", "interval": "1h"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    rows: list[tuple[dt.datetime, float]] = []
    for timestamp, close in zip(timestamps, closes):
        value = numeric(close)
        if value is None:
            continue
        rows.append((dt.datetime.fromtimestamp(float(timestamp), UTC), value))
    if not rows:
        raise RuntimeError("Yahoo BTC-USD hourly chart returned no usable closes")
    return rows


def nearest_reference(rows: list[tuple[dt.datetime, float]], target: dt.datetime) -> tuple[dt.datetime, float]:
    target_utc = target.astimezone(UTC)
    timestamp, value = min(rows, key=lambda item: abs((item[0] - target_utc).total_seconds()))
    distance = abs((timestamp - target_utc).total_seconds())
    if distance > 2 * 60 * 60:
        raise RuntimeError(f"No BTCUSD hourly reference within 2h of {target_utc.isoformat()}")
    return timestamp, value


def format_change(change: float) -> str:
    rounded = round(change)
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded:,.0f}"


def format_rate(rate: float) -> str:
    sign = "+" if rate > 0 else ""
    return f"{sign}{rate:.2f}%"


def patch_market_payload(path: Path, *, current: float, reference: float, change: float, rate: float,
                         report_time: dt.datetime, reference_time: dt.datetime, fetched_at: str) -> bool:
    payload = load_json(path, {})
    if not isinstance(payload, dict):
        return False
    markets = payload.get("markets")
    if not isinstance(markets, dict) or not isinstance(markets.get("btcusd"), dict):
        return False
    market = markets["btcusd"]
    market["value"] = current
    market["displayValue"] = f"{current:,.0f}"
    market["previousClose"] = reference
    market["change"] = change
    market["changePercent"] = rate
    market["changeText"] = f"{format_change(change)} / {format_rate(rate)}"
    market["comparisonBasis"] = "24h"
    market["comparisonLabel"] = "24時間前比"
    market["comparisonAsOf"] = reference_time.astimezone(JST).replace(microsecond=0).isoformat()
    market["comparisonSourceId"] = "yahoo_btc_usd_hourly_24h"
    market["comparisonSourceName"] = "Yahoo Finance Bitcoin USD"
    market["comparisonSourceUrl"] = "https://finance.yahoo.com/quote/BTC-USD/"
    market["asOf"] = report_time.replace(microsecond=0).isoformat()
    market["verificationStatus"] = "verified"
    market["error"] = None
    market["note"] = "BTCUSDは24時間365日取引のため、08:00レポートの前日比は同時刻24時間前比で計算。株式の前営業日終値ルールは適用しない。"
    market["lastVerifiedAt"] = fetched_at
    dump_json(path, payload)
    return True


def main() -> int:
    payload = load_json(LATEST_REPORT, {})
    if not isinstance(payload, dict):
        raise SystemExit("data/latest-report.json is invalid")
    report = report_object(payload)
    if not report or str(report.get("time") or "") != "08:00":
        print("BTCUSD 24h repair skipped: latest report is not 08:00")
        return 0

    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list):
        raise SystemExit("08:00 marketDataTable.rows is missing")
    btc_row = next((row for row in rows if isinstance(row, dict) and str(row.get("label") or "").strip() == "BTCUSD"), None)
    if not isinstance(btc_row, dict):
        raise SystemExit("BTCUSD row is missing from 08:00 marketDataTable")

    current = numeric(btc_row.get("value"))
    if current is None or current <= 0:
        raise SystemExit("BTCUSD report value is not numeric")

    report_time = report_datetime(report)
    target = report_time - dt.timedelta(hours=24)
    reference_time, reference = nearest_reference(fetch_hourly_btc(), target)
    change = current - reference
    rate = change / reference * 100.0
    fetched_at = dt.datetime.now(JST).replace(microsecond=0).isoformat()

    btc_row["change"] = format_change(change)
    btc_row["rate"] = format_rate(rate)
    if not str(btc_row.get("direction") or "").strip() or str(btc_row.get("direction")) in {"取得不能", "横ばい・方向確認"}:
        btc_row["direction"] = "上昇" if change > 0 else "下落" if change < 0 else "横ばい"

    provenance = report.setdefault("dataProvenance", {})
    provenance["btc24hComparisonRepair"] = {
        "rule": "BTCUSD 08:00 comparison uses report-time price versus nearest Yahoo BTC-USD hourly close exactly 24h earlier",
        "reportPrice": current,
        "referencePrice": reference,
        "reportTimeJST": report_time.replace(microsecond=0).isoformat(),
        "referenceTimeJST": reference_time.astimezone(JST).replace(microsecond=0).isoformat(),
        "change": change,
        "changePercent": rate,
        "source": "Yahoo Finance Bitcoin USD",
        "sourceUrl": "https://finance.yahoo.com/quote/BTC-USD/",
        "fetchedAt": fetched_at,
    }
    dump_json(LATEST_REPORT, payload)

    patched = []
    for path in (MARKET_LATEST, CHATGPT_INPUT):
        if patch_market_payload(
            path,
            current=current,
            reference=reference,
            change=change,
            rate=rate,
            report_time=report_time,
            reference_time=reference_time,
            fetched_at=fetched_at,
        ):
            patched.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        "btcReportPrice": current,
        "reference24h": reference,
        "change": change,
        "changePercent": rate,
        "referenceTimeJST": reference_time.astimezone(JST).replace(microsecond=0).isoformat(),
        "patched": ["data/latest-report.json", *patched],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
