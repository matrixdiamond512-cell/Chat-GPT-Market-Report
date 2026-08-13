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

The helper also rewrites the textual 主要市場データ block from the structured 28-row
table so repo fullText and the web table cannot disagree.
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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
OUT = ROOT / "data" / "market" / "morning-daily-reference.json"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"

# label -> Yahoo symbol, source name, display decimals
# OSE futures and Japanese valuation/breadth rows are handled by the canonical
# close-sheet / Japan-close capture because a different market must never be
# substituted under the OSE label. BTCUSD is handled by its dedicated 24/7 source.
SYMBOLS: dict[str, tuple[str, str, int]] = {
    "NYダウ": ("^DJI", "Yahoo Finance Dow Jones Industrial Average", 2),
    "NASDAQ総合": ("^IXIC", "Yahoo Finance Nasdaq Composite", 2),
    "S&P500": ("^GSPC", "Yahoo Finance S&P 500", 2),
    "Russell 2000": ("^RUT", "Yahoo Finance Russell 2000", 2),
    "日経225現物": ("^N225", "Yahoo Finance Nikkei 225", 2),
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


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def completed_bars(result: dict[str, Any], report_date: dt.date) -> list[tuple[dt.date, float]]:
    meta = result.get("meta") or {}
    tz_name = str(meta.get("exchangeTimezoneName") or "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
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
    return report_date - dt.timedelta(days=3 if report_date.weekday() == 0 else 1)


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
    nikkei_date_verified = False
    for label, (symbol, source_name, places) in SYMBOLS.items():
        row = by_label.get(label)
        if row is None:
            unavailable[label] = "structured row missing"
            continue
        expected_date = expected_prior_session(report_date, label)
        try:
            result = fetch_chart(symbol)
            bars = completed_bars(result, report_date)
            if len(bars) < 2:
                raise RuntimeError("fewer than two completed pre-report daily bars")
            target_date, value = bars[-1]
            if target_date != expected_date:
                reason = (
                    f"{expected_date.isoformat()}基準の前日終値を取得できず。"
                    f"取得可能な最新日付は{target_date.isoformat()}のため不採用"
                )
                set_unavailable(row, reason)
                unavailable[label] = reason
                continue
            previous_date, previous = bars[-2]
            change = value - previous
            rate = (change / previous * 100.0) if previous else 0.0
            row["value"] = fmt_number(value, places)
            row["change"] = fmt_change(change, places)
            row["rate"] = f"{rate:+.2f}%"
            row["direction"] = direction(change, label)
            items[label] = {
                "symbol": symbol,
                "value": row["value"],
                "change": row["change"],
                "rate": row["rate"],
                "direction": row["direction"],
                "dataDate": target_date.isoformat(),
                "previousDate": previous_date.isoformat(),
                "sourceName": source_name,
                "sourceUrl": f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/history/",
                "status": "verified_date_matched_previous_close",
                "retrievedAt": now_jst().isoformat(),
            }
            repaired.append(label)
            if label == "日経225現物":
                nikkei_date_verified = True
        except Exception as exc:
            reason = f"{expected_date.isoformat()}基準の前日終値を取得できず: {exc}"
            set_unavailable(row, reason)
            unavailable[label] = reason

    # 25/200-day deviations cannot be trusted for the report date when the
    # underlying Nikkei close itself is not date-matched.
    if not nikkei_date_verified:
        expected_date = expected_prior_session(report_date, "日経225現物")
        for label in DERIVED_FROM_NIKKEI_CLOSE:
            row = by_label.get(label)
            if row is not None:
                reason = f"{expected_date.isoformat()}の日経225現物終値を確認できないため算定値を不採用"
                set_unavailable(row, reason)
                unavailable[label] = reason

    rewrite_market_block(report)
    report.setdefault("dataProvenance", {})["dailyCloseRepair"] = {
        "generatedAt": now_jst().isoformat(),
        "semantics": "previous_close",
        "rule": "08:00 uses date-matched prior-session closes; retrieval after 08:00 is allowed, stale-date carry-forward is prohibited; BTCUSD keeps its dedicated 24/7-market convention",
        "repairedLabels": repaired,
        "unavailable": unavailable,
    }
    save(LATEST, payload)
    save(OUT, {
        "schemaVersion": "2.1.0",
        "generatedAt": now_jst().isoformat(),
        "reportDate": report_date.isoformat(),
        "reportSlot": "08:00",
        "semantics": "previous_close",
        "items": items,
        "unavailable": unavailable,
    })
    print(json.dumps({"repaired": repaired, "unavailable": unavailable}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
