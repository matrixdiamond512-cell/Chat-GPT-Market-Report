#!/usr/bin/env python3
"""Update economic-calendar.json from Trading Economics.

This script is intentionally dependency-free so it can run inside GitHub
Actions without installing Python packages. It only publishes high-importance
events and keeps a browser-friendly JSON shape for the dashboard.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


JST = timezone(timedelta(hours=9))
PROVIDER = "Trading Economics"
DEFAULT_OUTPUT = "economic-calendar.json"
DEFAULT_COUNTRIES = [
    "united states",
    "japan",
    "euro area",
    "germany",
    "france",
    "united kingdom",
    "china",
    "canada",
    "australia",
    "new zealand",
]

COUNTRY_LABELS = {
    "united states": "\u7c73\u56fd",
    "japan": "\u65e5\u672c",
    "euro area": "\u30e6\u30fc\u30ed\u570f",
    "eurozone": "\u30e6\u30fc\u30ed\u570f",
    "germany": "\u30c9\u30a4\u30c4",
    "france": "\u30d5\u30e9\u30f3\u30b9",
    "united kingdom": "\u82f1\u56fd",
    "china": "\u4e2d\u56fd",
    "canada": "\u30ab\u30ca\u30c0",
    "australia": "\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea\u30a2",
    "new zealand": "NZ",
}

COUNTRY_MARKETS = {
    "united states": ["USD/JPY", "EUR/USD", "\u65e5\u7d4c225\u5148\u7269", "\u91d1", "BTCUSD"],
    "japan": ["USD/JPY", "\u65e5\u7d4c225\u5148\u7269"],
    "euro area": ["EUR/USD", "\u91d1"],
    "eurozone": ["EUR/USD", "\u91d1"],
    "germany": ["EUR/USD", "\u65e5\u7d4c225\u5148\u7269"],
    "france": ["EUR/USD", "\u65e5\u7d4c225\u5148\u7269"],
    "united kingdom": ["GBP/USD", "EUR/USD", "\u91d1"],
    "china": ["\u65e5\u7d4c225\u5148\u7269", "\u539f\u6cb9", "\u91d1"],
    "canada": ["USD/JPY", "\u539f\u6cb9"],
    "australia": ["AUD/USD", "\u91d1", "\u65e5\u7d4c225\u5148\u7269"],
    "new zealand": ["NZD/USD", "AUD/USD"],
}


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def api_key() -> str:
    for name in ("TRADING_ECONOMICS_API_KEY", "TE_API_KEY", "TRADINGECONOMICS_API_KEY"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return ""


def countries() -> list[str]:
    raw = os.environ.get("TE_CALENDAR_COUNTRIES") or os.environ.get("TRADING_ECONOMICS_COUNTRIES")
    if not raw:
        return DEFAULT_COUNTRIES
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return values or DEFAULT_COUNTRIES


def output_path() -> Path:
    return Path(os.environ.get("ECONOMIC_CALENDAR_OUTPUT", DEFAULT_OUTPUT))


def date_range(base: datetime) -> tuple[str, str]:
    days_back = env_int("ECONOMIC_CALENDAR_DAYS_BACK", 1)
    days_forward = env_int("ECONOMIC_CALENDAR_DAYS_FORWARD", 7)
    start = (base.date() - timedelta(days=max(0, days_back))).isoformat()
    end = (base.date() + timedelta(days=max(0, days_forward))).isoformat()
    return start, end


def empty_payload(status: str, message: str | None = None) -> dict[str, Any]:
    base = now_jst()
    start, end = date_range(base)
    payload: dict[str, Any] = {
        "status": status,
        "updatedAt": base.isoformat(),
        "timezone": "Asia/Tokyo",
        "provider": PROVIDER,
        "range": {"from": start, "to": end},
        "filters": {"importance": 3, "countries": countries()},
        "events": [],
        "errors": [],
    }
    if message:
        payload["errors"].append({"message": message})
    return payload


def write_json(payload: dict[str, Any]) -> None:
    path = output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_json(url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Chat-GPT-Market-Report/1.0 (+GitHub Actions)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("events", "data", "Calendar"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def build_url(country: str, start: str, end: str, credential: str, include_dates: bool = True) -> str:
    country_path = urllib.parse.quote(country, safe="")
    query = urllib.parse.urlencode({"c": credential, "importance": 3, "f": "json"})
    if include_dates:
        return f"https://api.tradingeconomics.com/calendar/country/{country_path}/{start}/{end}?{query}"
    return f"https://api.tradingeconomics.com/calendar/country/{country_path}?{query}"


def normalize_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("none", "nan", "null"):
        return ""
    return re.sub(r"\s+", " ", text)


def parse_importance(value: Any) -> int:
    text = clean_value(value).lower()
    if text in ("high", "3", "3.0"):
        return 3
    if text in ("medium", "2", "2.0"):
        return 2
    if text in ("low", "1", "1.0"):
        return 1
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_datetime(value: Any) -> datetime | None:
    text = clean_value(value)
    if not text:
        return None

    dotnet = re.match(r"^/Date\((\d+)\)/$", text)
    if dotnet:
        return datetime.fromtimestamp(int(dotnet.group(1)) / 1000, tz=timezone.utc).astimezone(JST)

    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(JST)


def event_datetime(row: dict[str, Any]) -> datetime | None:
    for key in ("Date", "date", "datetime", "Datetime", "LastUpdate"):
        parsed = parse_datetime(row.get(key))
        if parsed:
            return parsed
    return None


def event_title(row: dict[str, Any]) -> str:
    for key in ("Event", "event", "Title", "title", "Name", "name"):
        value = clean_value(row.get(key))
        if value:
            return value
    category = clean_value(row.get("Category") or row.get("category"))
    return category


def country_label(raw_country: Any, requested_country: str) -> str:
    key = normalize_key(raw_country) or normalize_key(requested_country)
    return COUNTRY_LABELS.get(key, clean_value(raw_country) or requested_country.title())


def market_impact(raw_country: Any, title: str, category: str) -> str:
    key = normalize_key(raw_country)
    markets = list(COUNTRY_MARKETS.get(key, []))
    text = f"{title} {category}".lower()
    if re.search(r"oil|crude|petroleum|inventory|eia|opec", text) and "\u539f\u6cb9" not in markets:
        markets.append("\u539f\u6cb9")
    if re.search(r"bitcoin|crypto|btc", text) and "BTCUSD" not in markets:
        markets.append("BTCUSD")
    return " / ".join(markets)


def normalize_event(row: dict[str, Any], requested_country: str) -> dict[str, Any] | None:
    importance = parse_importance(row.get("Importance") or row.get("importance"))
    if importance < 3:
        return None

    dt = event_datetime(row)
    title = event_title(row)
    if not dt or not title:
        return None

    raw_country = row.get("Country") or row.get("country") or requested_country
    category = clean_value(row.get("Category") or row.get("category"))
    forecast = clean_value(row.get("Forecast") or row.get("forecast") or row.get("TEForecast"))

    return {
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M"),
        "datetimeJst": dt.isoformat(timespec="minutes"),
        "country": country_label(raw_country, requested_country),
        "countryName": clean_value(raw_country),
        "title": title,
        "category": category,
        "importance": importance,
        "impact": market_impact(raw_country, title, category),
        "actual": clean_value(row.get("Actual") or row.get("actual")),
        "forecast": forecast,
        "previous": clean_value(row.get("Previous") or row.get("previous")),
        "reference": clean_value(row.get("Reference") or row.get("reference")),
        "source": PROVIDER,
        "sourceUrl": clean_value(row.get("URL") or row.get("url")),
        "ticker": clean_value(row.get("Ticker") or row.get("Symbol") or row.get("ticker")),
    }


def fetch_events(credential: str, start: str, end: str, target_countries: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    events: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for country in target_countries:
        try:
            try:
                rows = request_json(build_url(country, start, end, credential, include_dates=True))
            except urllib.error.HTTPError as exc:
                if exc.code != 410:
                    raise
                rows = request_json(build_url(country, start, end, credential, include_dates=False))
            for row in rows:
                event = normalize_event(row, country)
                if event and start <= event["date"] <= end:
                    events.append(event)
        except urllib.error.HTTPError as exc:
            errors.append({"country": country, "status": str(exc.code), "message": exc.reason or "HTTP error"})
        except urllib.error.URLError as exc:
            errors.append({"country": country, "message": str(exc.reason)})
        except json.JSONDecodeError as exc:
            errors.append({"country": country, "message": f"JSON parse error: {exc}"})

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        key = (event["datetimeJst"], event["countryName"], event["title"])
        deduped[key] = event

    return sorted(deduped.values(), key=lambda item: (item["datetimeJst"], item["country"], item["title"])), errors


def status_from_result(events: list[dict[str, Any]], errors: list[dict[str, str]], target_count: int) -> str:
    if errors and not events:
        statuses = {item.get("status") for item in errors}
        if statuses and statuses <= {"401", "403"}:
            return "auth_error"
        return "error"
    if errors:
        return "partial"
    return "ok"


def main() -> int:
    credential = api_key()
    if not credential:
        write_json(empty_payload("not_configured", "TRADING_ECONOMICS_API_KEY is not set."))
        return 0

    base = now_jst()
    start, end = date_range(base)
    target_countries = countries()
    events, errors = fetch_events(credential, start, end, target_countries)
    payload = {
        "status": status_from_result(events, errors, len(target_countries)),
        "updatedAt": base.isoformat(),
        "timezone": "Asia/Tokyo",
        "provider": PROVIDER,
        "range": {"from": start, "to": end},
        "filters": {"importance": 3, "countries": target_countries},
        "events": events,
        "errors": errors,
    }
    write_json(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - last-resort workflow visibility
        write_json(empty_payload("error", f"Unexpected error: {exc}"))
        raise
