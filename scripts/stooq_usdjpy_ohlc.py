"""Bounded, attributed USD/JPY daily OHLC fallback for missing BOJ-volume dates.

Stooq daily FX candles are *not* Bank of Japan Tokyo-session prices. They
must never replace a populated candle or any BOJ spot turnover.
"""
from __future__ import annotations

import csv
import io
import math
import urllib.parse
import urllib.request
from datetime import date

SOURCE_URL = "https://stooq.com/q/d/l/"
FIELDS = ("open", "high", "low", "close")


def parse_csv(raw: str, *, start_date: str, end_date: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for record in csv.DictReader(io.StringIO(raw)):
        day = str(record.get("Date", "")).strip()
        try:
            parsed = date.fromisoformat(day)
            values = {key: round(float(record[key.capitalize()]), 4) for key in FIELDS}
        except (ValueError, TypeError, KeyError):
            continue
        if not start_date <= day <= end_date:
            continue
        if not all(math.isfinite(v) and 50 <= v <= 300 for v in values.values()):
            continue
        if values["low"] > min(values["open"], values["close"]):
            continue
        if values["high"] < max(values["open"], values["close"]):
            continue
        rows[parsed.isoformat()] = {"date": day, **values}
    return rows


def fetch_history(*, start_date: str, end_date: str) -> dict[str, dict]:
    params = urllib.parse.urlencode({
        "s": "usdjpy", "i": "d",
        "d1": start_date.replace("-", ""), "d2": end_date.replace("-", ""),
    })
    url = SOURCE_URL + "?" + params
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=35) as response:
        raw = response.read().decode("utf-8-sig", "replace")
    records = parse_csv(raw, start_date=start_date, end_date=end_date)
    if not records:
        raise RuntimeError("Stooq returned no valid USDJPY daily OHLC records")
    print(f"Stooq USDJPY: {len(records)} daily bars / {min(records)}..{max(records)}")
    return records
