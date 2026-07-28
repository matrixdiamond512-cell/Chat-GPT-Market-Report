#!/usr/bin/env python3
"""Fetch and normalize economic calendar data for the static dashboard.

Provider: Financial Modeling Prep stable economic-calendar endpoint.
Authentication: FMP_API_KEY environment variable.
Output: economic-calendar.json (JST-normalized, browser-safe static JSON).

When the API key is not configured, the script writes a clear placeholder file
instead of failing silently. Once the secret is configured, the same workflow
replaces the placeholder with live calendar data.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
OUTPUT = Path(os.environ.get("ECONOMIC_CALENDAR_OUTPUT", "economic-calendar.json"))
COUNTRIES = {"US", "JP", "EU", "GB", "DE", "FR", "IT", "CA", "AU", "NZ", "CN"}
HIGH_WORDS = (
    "interest rate", "rate decision", "fomc", "boj", "ecb", "boe", "cpi", "pce",
    "nonfarm", "employment", "unemployment", "gdp", "press conference",
)
MEDIUM_WORDS = (
    "ppi", "pmi", "ism", "jolts", "retail sales", "durable goods", "consumer confidence",
    "industrial production", "trade balance", "jobless claims", "housing", "auction",
)


def now_jst() -> datetime:
    return datetime.now(JST)


def write_output(payload: dict[str, Any]) -> None:
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_date_range() -> tuple[str, str]:
    current = now_jst()
    start = (current - timedelta(days=1)).date().isoformat()
    end = (current + timedelta(days=7)).date().isoformat()
    return start, end


def placeholder(status: str, message: str) -> dict[str, Any]:
    start, end = get_date_range()
    return {
        "status": status,
        "message": message,
        "updatedAt": now_jst().isoformat(timespec="seconds"),
        "timezone": "Asia/Tokyo",
        "provider": "Financial Modeling Prep",
        "range": {"from": start, "to": end},
        "events": [],
    }


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Chat-GPT-Market-Report/1.0 economic-calendar-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    )
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(JST)


def importance_from(item: dict[str, Any], title: str) -> int:
    raw = str(item.get("impact") or item.get("importance") or "").lower()
    if raw in {"high", "3", "★★★"}:
        return 3
    if raw in {"medium", "moderate", "2", "★★"}:
        return 2
    if raw in {"low", "1", "★"}:
        return 1
    lowered = title.lower()
    if any(word in lowered for word in HIGH_WORDS):
        return 3
    if any(word in lowered for word in MEDIUM_WORDS):
        return 2
    return 1


def markets_for(country: str, title: str) -> list[str]:
    markets: set[str] = set()
    lowered = title.lower()
    if country == "US":
        markets.update(["USD/JPY", "EUR/USD", "日経225先物", "金", "BTCUSD"])
    elif country == "JP":
        markets.update(["USD/JPY", "日経225先物"])
    elif country in {"EU", "DE", "FR", "IT"}:
        markets.update(["EUR/USD", "金"])
    elif country == "GB":
        markets.update(["EUR/USD", "金"])
    elif country in {"CN", "AU", "NZ"}:
        markets.update(["日経225先物", "原油", "金"])
    elif country == "CA":
        markets.update(["USD/JPY", "原油"])
    if any(word in lowered for word in ("oil", "petroleum", "crude", "inventory")):
        markets.add("原油")
    if any(word in lowered for word in ("bitcoin", "crypto")):
        markets.add("BTCUSD")
    return [market for market in ["USD/JPY", "EUR/USD", "日経225先物", "金", "原油", "BTCUSD"] if market in markets]


def normalize_item(item: dict[str, Any]) -> dict[str, Any] | None:
    country = str(item.get("country") or item.get("currency") or "").upper().strip()
    if country not in COUNTRIES:
        return None
    title = str(item.get("event") or item.get("name") or item.get("title") or "").strip()
    if not title:
        return None
    dt = parse_datetime(item.get("date") or item.get("time") or item.get("datetime"))
    if dt is None:
        return None
    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M"),
        "datetimeJst": dt.isoformat(timespec="minutes"),
        "country": country,
        "title": title,
        "importance": importance_from(item, title),
        "impact": markets_for(country, title),
        "actual": item.get("actual"),
        "forecast": item.get("estimate") if item.get("estimate") is not None else item.get("consensus"),
        "previous": item.get("previous") if item.get("previous") is not None else item.get("prev"),
        "unit": item.get("unit") or "",
        "source": "Financial Modeling Prep",
    }


def main() -> int:
    api_key = os.environ.get("FMP_API_KEY", "").strip()
    if not api_key:
        write_output(placeholder("not_configured", "FMP_API_KEY is not configured."))
        print(f"Wrote not-configured placeholder to {OUTPUT}")
        return 0

    start, end = get_date_range()
    query = urllib.parse.urlencode({"from": start, "to": end, "apikey": api_key})
    url = f"https://financialmodelingprep.com/stable/economic-calendar?{query}"
    payload = fetch_json(url)

    if isinstance(payload, dict):
        if payload.get("Error Message") or payload.get("error"):
            raise RuntimeError(str(payload.get("Error Message") or payload.get("error")))
        rows = payload.get("economicCalendar") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    events = [event for row in rows if isinstance(row, dict) for event in [normalize_item(row)] if event]
    events.sort(key=lambda event: (event["datetimeJst"], -event["importance"], event["title"]))

    result = {
        "status": "ok",
        "updatedAt": now_jst().isoformat(timespec="seconds"),
        "timezone": "Asia/Tokyo",
        "provider": "Financial Modeling Prep",
        "range": {"from": start, "to": end},
        "events": events,
    }
    write_output(result)
    print(f"Wrote {len(events)} events to {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Economic calendar update failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
