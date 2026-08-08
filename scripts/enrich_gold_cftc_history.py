#!/usr/bin/env python3
"""Enrich gold supply-demand JSON with 26 weeks of CFTC Managed Money history.

The main gold updater keeps the latest CFTC snapshot. This script adds a compact
26-week series used by the WEB gold supply-demand chart. Missing external data is
never fabricated. If a refresh fails, the last committed history is preserved.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "gold-supply-demand.json"
CFTC_API = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"


def to_int(v: Any) -> int | None:
    try:
        return int(round(float(str(v).replace(",", "").strip())))
    except Exception:
        return None


def report_date(v: Any) -> str | None:
    s = str(v or "")[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def previous_committed_history() -> list[dict[str, Any]]:
    try:
        p = subprocess.run(
            ["git", "show", "HEAD:data/gold-supply-demand.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        old = json.loads(p.stdout)
        hist = ((old.get("cftc") or {}).get("historyWeeks") or [])
        return hist if isinstance(hist, list) else []
    except Exception:
        return []


def fetch_cftc_rows() -> list[dict[str, Any]]:
    params = {
        "$select": ",".join([
            "report_date_as_yyyy_mm_dd",
            "open_interest_all",
            "m_money_positions_long_all",
            "m_money_positions_short_all",
        ]),
        "$where": "cftc_contract_market_code='088691'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "26",
    }
    r = requests.get(CFTC_API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError("CFTC 26-week history returned insufficient rows")
    return rows


def fetch_gold_daily() -> list[tuple[str, float]]:
    r = requests.get(
        YAHOO_CHART,
        params={"range": "1y", "interval": "1d", "events": "history"},
        headers={"User-Agent": UA},
        timeout=30,
    )
    r.raise_for_status()
    result = ((r.json().get("chart") or {}).get("result") or [None])[0] or {}
    stamps = result.get("timestamp") or []
    closes = ((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
    out: list[tuple[str, float]] = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        try:
            d = datetime.fromtimestamp(int(ts), timezone.utc).date().isoformat()
            out.append((d, float(close)))
        except Exception:
            continue
    if not out:
        raise RuntimeError("Yahoo Gold Futures daily history returned no prices")
    return out


def price_on_or_before(prices: list[tuple[str, float]], target: str | None) -> float | None:
    if not target:
        return None
    matches = [p for d, p in prices if d <= target]
    return round(matches[-1], 2) if matches else None


def build_history(rows: list[dict[str, Any]], prices: list[tuple[str, float]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for row in reversed(rows):
        d = report_date(row.get("report_date_as_yyyy_mm_dd"))
        long_ = to_int(row.get("m_money_positions_long_all"))
        short = to_int(row.get("m_money_positions_short_all"))
        oi = to_int(row.get("open_interest_all"))
        net = long_ - short if long_ is not None and short is not None else None
        history.append({
            "asOfDate": d,
            "long": long_,
            "short": short,
            "net": net,
            "openInterest": oi,
            "goldPrice": price_on_or_before(prices, d),
            "longChange": None,
            "shortChange": None,
            "netChange": None,
        })

    for i in range(1, len(history)):
        cur = history[i]
        prev = history[i - 1]
        if cur.get("long") is not None and prev.get("long") is not None:
            cur["longChange"] = cur["long"] - prev["long"]
        if cur.get("short") is not None and prev.get("short") is not None:
            cur["shortChange"] = cur["short"] - prev["short"]
        if cur.get("net") is not None and prev.get("net") is not None:
            cur["netChange"] = cur["net"] - prev["net"]
    return history


def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    cftc = data.setdefault("cftc", {})
    old_history = previous_committed_history()

    try:
        rows = fetch_cftc_rows()
        prices = fetch_gold_daily()
        history = build_history(rows, prices)
        latest = history[-1]

        cftc["historyWeeks"] = history
        cftc["historyStatus"] = "verified"
        cftc["historyWeeksCount"] = len(history)
        cftc["managedMoneyLong"] = latest.get("long")
        cftc["managedMoneyShort"] = latest.get("short")
        cftc["managedMoneyNet"] = latest.get("net")
        cftc["managedMoneyLongChange"] = latest.get("longChange")
        cftc["managedMoneyShortChange"] = latest.get("shortChange")
        cftc["managedMoneyNetChange"] = latest.get("netChange")
        cftc["openInterest"] = latest.get("openInterest")
        cftc["goldPrice"] = latest.get("goldPrice")
        cftc["asOfDate"] = latest.get("asOfDate")
        cftc["historyFetchedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        cftc.pop("historyError", None)
        print(f"CFTC history updated: {len(history)} weeks through {latest.get('asOfDate')}")
    except Exception as exc:
        if old_history:
            cftc["historyWeeks"] = old_history
            cftc["historyStatus"] = "stale"
            cftc["historyWeeksCount"] = len(old_history)
        else:
            cftc["historyWeeks"] = []
            cftc["historyStatus"] = "unavailable"
            cftc["historyWeeksCount"] = 0
        cftc["historyError"] = f"{type(exc).__name__}: {exc}"
        print(f"CFTC history refresh failed; previous history preserved: {cftc['historyError']}")

    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
