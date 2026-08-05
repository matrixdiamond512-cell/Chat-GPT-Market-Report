#!/usr/bin/env python3
"""Fetch, validate, and persist independent market data for the dashboard."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc
USER_AGENT = (
    "Mozilla/5.0 (compatible; MarketReportBot/1.0; "
    "+https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/)"
)


class FetchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def iso(value: dt.datetime | None = None) -> str:
    return (value or now_jst()).astimezone(JST).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def http_get(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
    request_headers = {"User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            return response.read(), content_type
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP_{exc.code}", f"HTTP {exc.code} {url}") from exc
    except urllib.error.URLError as exc:
        raise FetchError("SOURCE_TIMEOUT", f"{exc.reason} {url}") from exc
    except TimeoutError as exc:
        raise FetchError("SOURCE_TIMEOUT", f"Timeout {url}") from exc


def http_text(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> str:
    body, encoding = http_get(url, timeout, headers=headers)
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", "")
        if not text or text in {"-", "--", "N/A", "null", "None"}:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def parse_epoch(value: Any) -> str:
    number = safe_float(value)
    if number is not None:
        return dt.datetime.fromtimestamp(number, UTC).astimezone(JST).replace(microsecond=0).isoformat()
    text = str(value or "").strip()
    if text:
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(JST).replace(microsecond=0).isoformat()
        except ValueError:
            pass
    return iso()


def parse_date_time(date_text: str, time_text: str | None = None) -> str:
    date_text = str(date_text or "").strip()
    time_text = str(time_text or "00:00:00").strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
    ):
        try:
            parsed = dt.datetime.strptime(f"{date_text} {time_text}", fmt).replace(tzinfo=UTC)
            return parsed.astimezone(JST).replace(microsecond=0).isoformat()
        except ValueError:
            continue
    try:
        parsed_date = dt.date.fromisoformat(date_text[:10])
        return dt.datetime.combine(parsed_date, dt.time(0, 0), tzinfo=UTC).astimezone(JST).isoformat()
    except ValueError:
        return iso()


def parse_jst_month_day_time(month_day: str, time_text: str | None = None) -> str:
    month_day = str(month_day or "").strip()
    time_text = str(time_text or "00:00").strip()
    match = re.search(r"(\d{1,2})/(\d{1,2})", month_day)
    if not match:
        return iso()
    hour = 0
    minute = 0
    time_match = re.search(r"(\d{1,2}):(\d{2})", time_text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    current = now_jst()
    parsed = dt.datetime(
        current.year,
        int(match.group(1)),
        int(match.group(2)),
        hour,
        minute,
        tzinfo=JST,
    )
    if parsed - current > dt.timedelta(days=7):
        parsed = parsed.replace(year=parsed.year - 1)
    return parsed.replace(microsecond=0).isoformat()


def parse_nikkei_profile_timestamp(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"([A-Za-z]{3})/(\d{1,2})/(\d{4})\((\d{1,2}):(\d{2})\)", text)
    if not match:
        return iso()
    try:
        month = dt.datetime.strptime(match.group(1), "%b").month
        parsed = dt.datetime(
            int(match.group(3)),
            month,
            int(match.group(2)),
            int(match.group(4)),
            int(match.group(5)),
            tzinfo=JST,
        )
        return parsed.replace(microsecond=0).isoformat()
    except ValueError:
        return iso()


def format_value(value: float | None, places: int) -> str:
    if value is None:
        return ""
    rounded = round(value, places)
    if places <= 0:
        return f"{rounded:,.0f}"
    return f"{rounded:,.{places}f}"


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def candidate(
    source: dict[str, Any],
    value: float,
    *,
    previous_close: float | None = None,
    change: float | None = None,
    change_percent: float | None = None,
    as_of: str | None = None,
    raw_reference: str = "",
    classification: str | None = None,
) -> dict[str, Any]:
    if change is None and previous_close not in (None, 0):
        change = value - float(previous_close)
    if change_percent is None and previous_close not in (None, 0):
        change_percent = (value / float(previous_close) - 1) * 100
    return {
        "value": value,
        "previousClose": previous_close,
        "change": change,
        "changePercent": change_percent,
        "asOf": as_of or iso(),
        "fetchedAt": iso(),
        "sourceId": source["id"],
        "sourceName": source["name"],
        "sourceUrl": source.get("sourceUrl") or source.get("url"),
        "marketType": source.get("marketType"),
        "session": source.get("session"),
        "rawReference": raw_reference,
        "classification": classification or "",
        "status": "raw",
        "error": None,
    }


def fetch_yahoo_chart(source: dict[str, Any]) -> dict[str, Any]:
    symbol = source["symbol"]
    params = urllib.parse.urlencode({"range": "5d", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"
    text = http_text(url)
    try:
        payload = json.loads(text)
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise FetchError("PARSE_ERROR", f"Yahoo chart parse failed for {symbol}") from exc

    meta = result.get("meta") or {}
    value = safe_float(meta.get("regularMarketPrice"))
    previous = safe_float(meta.get("previousClose") or meta.get("chartPreviousClose"))

    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [safe_float(item) for item in quote.get("close") or []]
    timestamps = result.get("timestamp") or []
    valid = [(timestamps[i], closes[i]) for i in range(min(len(timestamps), len(closes))) if closes[i] is not None]
    if value is None and valid:
        value = valid[-1][1]

    if value is None:
        raise FetchError("PARSE_ERROR", f"Yahoo chart had no numeric value for {symbol}")
    as_of = parse_epoch(meta.get("regularMarketTime") or (valid[-1][0] if valid else None))
    as_of_date = parse_iso(as_of)
    if valid and as_of_date:
        completed = [
            close for timestamp, close in valid
            if dt.datetime.fromtimestamp(timestamp, UTC).astimezone(JST).date()
            < as_of_date.astimezone(JST).date()
        ]
        if completed:
            previous = completed[-1]
        elif len(valid) >= 2:
            previous = valid[-2][1]
    return candidate(source, value, previous_close=previous, as_of=as_of, raw_reference=symbol)


def fetch_stooq_quote(source: dict[str, Any]) -> dict[str, Any]:
    symbol = source["symbol"]
    url = f"https://stooq.com/q/l/?s={urllib.parse.quote(symbol)}&f=sd2t2ohlcv&h&e=csv"
    text = http_text(url)
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise FetchError("PARSE_ERROR", f"Stooq returned no rows for {symbol}")
    row = rows[0]
    value = safe_float(row.get("Close"))
    if value is None:
        raise FetchError("PARSE_ERROR", f"Stooq close was not numeric for {symbol}")
    as_of = parse_date_time(row.get("Date") or "", row.get("Time") or "")
    return candidate(source, value, as_of=as_of, raw_reference=symbol)


def fetch_cboe_history_csv(source: dict[str, Any]) -> dict[str, Any]:
    text = http_text(source["url"])
    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader if row.get("DATE") or row.get("Date")]
    if not rows:
        raise FetchError("PARSE_ERROR", "Cboe CSV returned no rows")
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else {}
    value = safe_float(last.get("CLOSE") or last.get("Close"))
    previous = safe_float(prev.get("CLOSE") or prev.get("Close"))
    if value is None:
        raise FetchError("PARSE_ERROR", "Cboe CSV close was not numeric")
    as_of = parse_date_time(last.get("DATE") or last.get("Date") or "")
    return candidate(source, value, previous_close=previous, as_of=as_of, raw_reference="VIX_History.csv")


def fetch_cnn_fear_greed(source: dict[str, Any]) -> dict[str, Any]:
    text = http_text(
        source["url"],
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
            "Origin": "https://edition.cnn.com",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError("PARSE_ERROR", "CNN graphdata was not JSON") from exc

    data = payload.get("fear_and_greed") or payload.get("fearAndGreed") or {}
    value = safe_float(data.get("score") or data.get("value"))
    if value is None:
        raise FetchError("PARSE_ERROR", "CNN graphdata had no numeric score")
    previous = safe_float(data.get("previous_close") or data.get("previousClose"))
    rating = str(data.get("rating") or data.get("classification") or "")
    timestamp = data.get("timestamp") or data.get("last_update") or payload.get("timestamp")
    as_of = parse_epoch(timestamp) if timestamp else iso()
    return candidate(
        source,
        value,
        previous_close=previous,
        as_of=as_of,
        raw_reference="fear_and_greed.score",
        classification=rating,
    )


def fetch_coinmarketcap_fear_greed(source: dict[str, Any]) -> dict[str, Any]:
    text = http_text(
        source["url"],
        headers={"Accept": "application/json", "Referer": "https://coinmarketcap.com/"},
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError("PARSE_ERROR", "CoinMarketCap response was not JSON") from exc

    status = payload.get("status") or {}
    if safe_float(status.get("error_code")) not in (None, 0):
        raise FetchError(
            "SOURCE_ERROR",
            f"CoinMarketCap error {status.get('error_code')}: {status.get('error_message') or ''}",
        )

    rows = payload.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: safe_float(row.get("timestamp")) or 0,
        reverse=True,
    )
    if not rows:
        raise FetchError("PARSE_ERROR", "CoinMarketCap returned no Fear and Greed rows")

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else {}
    value = safe_float(latest.get("value"))
    if value is None:
        raise FetchError("PARSE_ERROR", "CoinMarketCap Fear and Greed value was not numeric")
    timestamp = latest.get("timestamp") or latest.get("update_time")
    as_of = parse_epoch(timestamp) if timestamp else iso()
    return candidate(
        source,
        value,
        previous_close=safe_float(previous.get("value")),
        as_of=as_of,
        raw_reference="v3/fear-and-greed/historical data[0]",
        classification=str(latest.get("value_classification") or ""),
    )


def fetch_nikkei_profile(source: dict[str, Any]) -> dict[str, Any]:
    html_text = http_text(source["url"])
    text = strip_tags(html_text)

    titles = ["Nikkei 225 Futures Index"]
    if "nk225vi" in source.get("url", ""):
        titles = ["Nikkei Stock Average Volatility Index"]

    for title in titles:
        pattern = (
            re.escape(title)
            + r"\s+(?P<value>\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
            + r"\s+(?P<change_percent>[+-]?\d+(?:\.\d+)?)%"
            + r"\s+(?P<change>[+-]?\d+(?:\.\d+)?)"
            + r"\s+(?P<timestamp>[A-Za-z]{3}/\d{1,2}/\d{4}\(\d{1,2}:\d{2}\))"
        )
        match = re.search(pattern, text)
        if match:
            value = safe_float(match.group("value"))
            change = safe_float(match.group("change"))
            if value is None:
                break
            previous = value - change if change is not None else None
            return candidate(
                source,
                value,
                previous_close=previous,
                change=change,
                change_percent=safe_float(match.group("change_percent")),
                as_of=parse_nikkei_profile_timestamp(match.group("timestamp")),
                raw_reference=title,
            )

    lower_bound = min((idx for title in titles if (idx := text.find(title)) >= 0), default=-1)
    if lower_bound < 0:
        raise FetchError("PARSE_ERROR", "Nikkei profile title was not found")
    scoped = text[lower_bound : lower_bound + 500]
    numbers = []
    for match in re.finditer(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", scoped):
        value = safe_float(match.group(0))
        if value is not None:
            numbers.append(value)
    if not numbers:
        raise FetchError("PARSE_ERROR", "Nikkei profile had no numeric values")

    if "nk225vi" in source.get("url", ""):
        plausible = [value for value in numbers if 0 < value < 100]
    else:
        plausible = [value for value in numbers if value > 10000]
    if not plausible:
        raise FetchError("PARSE_ERROR", "Nikkei profile had no plausible value")
    value = plausible[0]
    date_match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", scoped)
    as_of = parse_date_time(date_match.group(0)) if date_match else iso()
    return candidate(source, value, as_of=as_of, raw_reference=source.get("url", "nikkei_profile"))


def fetch_jpx_html(source: dict[str, Any]) -> dict[str, Any]:
    quote_url = "https://port.jpx.co.jp/jpxhp/jcgi/wrap/qjsonp.aspx?F=ctl/future&DISPTYPE=day_through"
    if "disptype=night" in source["url"]:
        quote_url = quote_url.replace("day_through", "night")
    elif "disptype=daytime" in source["url"]:
        quote_url = quote_url.replace("day_through", "daytime")

    text = http_text(
        quote_url,
        headers={
            "Accept": "application/json,text/javascript,*/*",
            "Referer": source["url"],
        },
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError("PARSE_ERROR", "JPX futures endpoint was not JSON") from exc

    rows = ((payload.get("section1") or {}).get("data") or [])
    product = next(
        (
            row
            for row in rows
            if str(row.get("name") or "").strip() == "日経225先物"
            or "Nikkei 225" in str(row.get("namee") or "")
        ),
        None,
    )
    if not product:
        raise FetchError("PARSE_ERROR", "JPX futures JSON had no Nikkei 225 futures row")

    futures = product.get("future") or []
    front = next((row for row in futures if safe_float(row.get("DPP")) is not None), None)
    if not front:
        raise FetchError("PARSE_ERROR", "JPX Nikkei 225 futures row had no current quote")

    value = safe_float(front.get("DPP"))
    if value is None:
        raise FetchError("PARSE_ERROR", "JPX current quote was not numeric")
    change = safe_float(front.get("DYWP"))
    previous = value - change if change is not None else safe_float(front.get("ST"))
    as_of = parse_jst_month_day_time(front.get("DPP_H") or front.get("ZTD"), front.get("DPPT"))
    raw_reference = (
        f"JPX/OSE {product.get('name')} {front.get('DELI') or front.get('DELIE')}; "
        f"delayed quote endpoint; TTCODE={front.get('TTCODE')}"
    )
    return candidate(
        source,
        value,
        previous_close=previous,
        change=change,
        as_of=as_of,
        raw_reference=raw_reference,
    )


FETCHERS = {
    "yahoo_chart": fetch_yahoo_chart,
    "stooq_quote": fetch_stooq_quote,
    "cboe_history_csv": fetch_cboe_history_csv,
    "cnn_fear_greed": fetch_cnn_fear_greed,
    "coinmarketcap_fear_greed": fetch_coinmarketcap_fear_greed,
    "nikkei_profile": fetch_nikkei_profile,
    "jpx_html": fetch_jpx_html,
}


def validate_candidate(
    symbol_id: str,
    symbol_config: dict[str, Any],
    validation: dict[str, Any],
    cand: dict[str, Any],
    previous_verified: dict[str, Any] | None,
) -> tuple[bool, str, str]:
    value = safe_float(cand.get("value"))
    if value is None:
        return False, "EMPTY_VALUE", "value is not a finite number"

    if cand.get("marketType") != symbol_config.get("marketType"):
        source_reference_only = bool(cand.get("referenceOnly"))
        allow_reference = bool(validation.get("allowReferenceOnly"))
        if source_reference_only or not allow_reference:
            return False, "MARKET_TYPE_MISMATCH", (
                f"{cand.get('marketType')} is not {symbol_config.get('marketType')}"
            )

    min_value = validation.get("min")
    max_value = validation.get("max")
    if min_value is not None and value < float(min_value):
        return False, "OUT_OF_RANGE", f"{value} < {min_value}"
    if max_value is not None and value > float(max_value):
        return False, "OUT_OF_RANGE", f"{value} > {max_value}"

    as_of = parse_iso(cand.get("asOf"))
    stale_hours = validation.get("staleHours")
    if as_of and stale_hours is not None:
        age_hours = (now_jst() - as_of.astimezone(JST)).total_seconds() / 3600
        if age_hours > float(stale_hours):
            return False, "STALE_DATA", f"age {age_hours:.1f}h > {stale_hours}h"

    max_change_percent = validation.get("maxChangePercent")
    prev_value = safe_float((previous_verified or {}).get("value"))
    if prev_value not in (None, 0) and max_change_percent is not None:
        diff_pct = abs(value / prev_value - 1) * 100
        if diff_pct > float(max_change_percent):
            return False, "OUTLIER", f"change from previous verified {diff_pct:.2f}%"

    return True, "OK", ""


def sanitize_candidate_change(validation: dict[str, Any], cand: dict[str, Any]) -> str:
    """Discard implausible previous-close metadata without discarding the current value."""
    value = safe_float(cand.get("value"))
    previous = safe_float(cand.get("previousClose"))
    max_change = validation.get("maxChangePercent")
    if value is None or previous in (None, 0) or max_change is None:
        return ""
    change_percent = abs(value / previous - 1) * 100
    if change_percent <= float(max_change):
        return ""
    cand["previousClose"] = None
    cand["change"] = None
    cand["changePercent"] = None
    return (
        f"discarded previous close {previous} because implied change "
        f"{change_percent:.2f}% exceeded {max_change}%"
    )


def parse_iso(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=JST)
        return parsed
    except ValueError:
        return None


def format_market(symbol_id: str, config: dict[str, Any], validation: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    value = safe_float(cand.get("value"))
    previous = safe_float(cand.get("previousClose"))
    change = safe_float(cand.get("change"))
    change_pct = safe_float(cand.get("changePercent"))
    places = int(validation.get("decimalPlaces", 2))
    if change is None and value is not None and previous not in (None, 0):
        change = value - previous
    if change_pct is None and value is not None and previous not in (None, 0):
        change_pct = (value / previous - 1) * 100

    display_value = format_value(value, places)
    change_text = ""
    if change is not None:
        change_text = f"{change:+,.{places}f}"
        if change_pct is not None:
            change_text += f" / {change_pct:+.2f}%"
    elif change_pct is not None:
        change_text = f"{change_pct:+.2f}%"

    return {
        "id": symbol_id,
        "displayName": config["displayName"],
        "dashboardKey": config.get("dashboardKey", symbol_id),
        "value": value,
        "displayValue": display_value,
        "previousClose": previous,
        "change": change,
        "changePercent": change_pct,
        "changeText": change_text,
        "unit": config.get("unit", ""),
        "marketType": cand.get("marketType") or config.get("marketType"),
        "session": cand.get("session") or config.get("session"),
        "asOf": cand.get("asOf") or "",
        "fetchedAt": cand.get("fetchedAt") or iso(),
        "sourceId": cand.get("sourceId"),
        "sourceName": cand.get("sourceName"),
        "sourceUrl": cand.get("sourceUrl"),
        "rawReference": cand.get("rawReference") or "",
        "classification": cand.get("classification") or "",
        "verificationStatus": "verified",
        "freshnessStatus": "fresh",
        "fallbackUsed": False,
        "lastVerifiedAt": iso(),
        "error": None,
        "note": "",
    }


def fallback_market(symbol_id: str, config: dict[str, Any], previous: dict[str, Any] | None, errors: list[dict[str, Any]]) -> dict[str, Any]:
    if previous and safe_float(previous.get("value")) is not None:
        result = dict(previous)
        result.update(
            {
                "verificationStatus": "fallback",
                "freshnessStatus": "last_verified",
                "fallbackUsed": True,
                "error": "; ".join(f"{item['sourceId']}: {item['code']}" for item in errors[-3:]),
                "note": "今回の新規取得に失敗したため、前回確認値を保持しています。",
            }
        )
        return result
    return {
        "id": symbol_id,
        "displayName": config["displayName"],
        "dashboardKey": config.get("dashboardKey", symbol_id),
        "value": None,
        "displayValue": "",
        "previousClose": None,
        "change": None,
        "changePercent": None,
        "changeText": "",
        "unit": config.get("unit", ""),
        "marketType": config.get("marketType"),
        "session": config.get("session"),
        "asOf": "",
        "fetchedAt": iso(),
        "sourceId": "",
        "sourceName": "",
        "sourceUrl": "",
        "rawReference": "",
        "classification": "",
        "verificationStatus": "unavailable",
        "freshnessStatus": "missing",
        "fallbackUsed": False,
        "lastVerifiedAt": "",
        "error": "; ".join(f"{item['sourceId']}: {item['code']}" for item in errors[-3:]) or "NO_SOURCE_VALUE",
        "note": "確認済みの前回値がないため表示できません。",
    }


def fetch_symbol(
    symbol_id: str,
    symbol_config: dict[str, Any],
    validation: dict[str, Any],
    previous_verified: dict[str, Any] | None,
    retries: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    valid_candidates: list[dict[str, Any]] = []
    for source in sorted(symbol_config.get("sources", []), key=lambda item: item.get("priority", 99)):
        if source.get("referenceOnly") and not validation.get("allowReferenceOnly", False):
            errors.append(
                {
                    "symbol": symbol_id,
                    "sourceId": source["id"],
                    "code": "REFERENCE_ONLY",
                    "message": "reference source is not allowed for dashboard publication",
                }
            )
            continue
        fetcher = FETCHERS.get(source.get("kind"))
        if not fetcher:
            errors.append(
                {
                    "symbol": symbol_id,
                    "sourceId": source.get("id", ""),
                    "code": "UNSUPPORTED_SOURCE",
                    "message": str(source.get("kind")),
                }
            )
            continue

        for attempt in range(retries):
            try:
                raw = fetcher(source)
                raw["referenceOnly"] = source.get("referenceOnly", False)
                change_warning = sanitize_candidate_change(validation, raw)
                if change_warning:
                    errors.append(
                        {
                            "symbol": symbol_id,
                            "sourceId": source["id"],
                            "code": "INVALID_PREVIOUS_CLOSE",
                            "message": change_warning,
                            "attempt": attempt + 1,
                        }
                    )
                ok, code, reason = validate_candidate(symbol_id, symbol_config, validation, raw, previous_verified)
                if ok:
                    valid_candidates.append(raw)
                    break
                errors.append(
                    {
                        "symbol": symbol_id,
                        "sourceId": source["id"],
                        "code": code,
                        "message": reason,
                        "attempt": attempt + 1,
                    }
                )
                break
            except FetchError as exc:
                errors.append(
                    {
                        "symbol": symbol_id,
                        "sourceId": source.get("id", ""),
                        "code": exc.code,
                        "message": exc.message,
                        "attempt": attempt + 1,
                    }
                )
                if attempt + 1 < retries:
                    time.sleep(0.6 * (2**attempt))
            except Exception as exc:  # Keep one symbol from breaking every other symbol.
                errors.append(
                    {
                        "symbol": symbol_id,
                        "sourceId": source.get("id", ""),
                        "code": "UNEXPECTED_ERROR",
                        "message": str(exc),
                        "attempt": attempt + 1,
                    }
                )
                break

    if not valid_candidates:
        return fallback_market(symbol_id, symbol_config, previous_verified, errors), errors

    primary = valid_candidates[0]
    comparable = [
        item for item in valid_candidates[1:]
        if item.get("marketType") == primary.get("marketType")
        and item.get("session") == primary.get("session")
    ]
    max_divergence = validation.get("maxSourceDivergencePercent")
    if comparable and max_divergence is not None:
        primary_value = safe_float(primary.get("value"))
        check_value = safe_float(comparable[0].get("value"))
        if primary_value not in (None, 0) and check_value is not None:
            divergence = abs(primary_value / check_value - 1) * 100
            if divergence > float(max_divergence):
                errors.append(
                    {
                        "symbol": symbol_id,
                        "sourceId": f"{primary.get('sourceId')}|{comparable[0].get('sourceId')}",
                        "code": "SOURCE_DIVERGENCE",
                        "message": (
                            f"source values diverged by {divergence:.2f}% "
                            f"> {max_divergence}%"
                        ),
                    }
                )
                return fallback_market(symbol_id, symbol_config, previous_verified, errors), errors

    return format_market(symbol_id, symbol_config, validation, primary), errors


def merge_last_verified(existing: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    markets = dict((existing.get("markets") or {}))
    for symbol_id, market in (latest.get("markets") or {}).items():
        if market.get("verificationStatus") == "verified" and safe_float(market.get("value")) is not None:
            markets[symbol_id] = market
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": latest.get("generatedAt"),
        "lastUpdatedAt": iso(),
        "markets": markets,
    }


def build_payload(slot: str | None) -> dict[str, Any]:
    source_config = load_json(ROOT / "config" / "market_data_sources.json", {})
    validation_config = load_json(ROOT / "config" / "market_data_validation.json", {})
    previous_verified = load_json(ROOT / "data" / "market" / "last_verified.json", {"markets": {}})
    markets: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    retries = int((validation_config.get("defaults") or {}).get("maxRetries", 3))

    for symbol_id, symbol_config in (source_config.get("symbols") or {}).items():
        validation = dict((validation_config.get("defaults") or {}))
        validation.update((validation_config.get("symbols") or {}).get(symbol_id, {}))
        previous = (previous_verified.get("markets") or {}).get(symbol_id)
        market, symbol_errors = fetch_symbol(symbol_id, symbol_config, validation, previous, retries)
        markets[symbol_id] = market
        errors.extend(symbol_errors)

    required = [
        symbol_id
        for symbol_id, symbol_config in (source_config.get("symbols") or {}).items()
        if symbol_config.get("required", False)
    ]
    missing_required = [
        symbol_id
        for symbol_id in required
        if safe_float((markets.get(symbol_id) or {}).get("value")) is None
    ]
    fallback_count = sum(1 for item in markets.values() if item.get("fallbackUsed"))
    if missing_required:
        overall_status = "blocked"
    elif fallback_count:
        overall_status = "degraded"
    else:
        overall_status = "verified"

    payload = {
        "schemaVersion": "1.0.0",
        "pageId": "market-data",
        "generatedAt": iso(),
        "reportSlot": slot or "",
        "overallStatus": overall_status,
        "missingRequired": missing_required,
        "fallbackCount": fallback_count,
        "markets": markets,
        "errors": errors,
        "sources": [
            {
                "id": source["id"],
                "name": source["name"],
                "kind": source["kind"],
                "url": source.get("sourceUrl") or source.get("url"),
                "marketType": source.get("marketType"),
                "session": source.get("session"),
            }
            for symbol in (source_config.get("symbols") or {}).values()
            for source in symbol.get("sources", [])
        ],
    }
    return payload


def write_outputs(payload: dict[str, Any]) -> None:
    slot_slug = str(payload.get("reportSlot") or "").strip()
    if re.match(r"^\d{1,2}:\d{2}$", slot_slug):
        slot_slug = slot_slug.replace(":", "-").zfill(5)
    else:
        slot_slug = now_jst().strftime("%H-%M")
    history_name = now_jst().strftime("%Y-%m-%d") + "_" + slot_slug + ".json"
    write_json(ROOT / "data" / "market" / "latest.json", payload)
    write_json(ROOT / "data" / "market" / "history" / history_name, payload)
    last_verified = merge_last_verified(load_json(ROOT / "data" / "market" / "last_verified.json", {}), payload)
    write_json(ROOT / "data" / "market" / "last_verified.json", last_verified)

    status = {
        "executedAt": iso(),
        "overallStatus": payload.get("overallStatus"),
        "reportSlot": payload.get("reportSlot"),
        "missingRequired": payload.get("missingRequired", []),
        "fallbackCount": payload.get("fallbackCount", 0),
        "errorCount": len(payload.get("errors") or []),
        "markets": {
            key: {
                "value": value.get("displayValue"),
                "unit": value.get("unit"),
                "verificationStatus": value.get("verificationStatus"),
                "sourceId": value.get("sourceId"),
                "fallbackUsed": value.get("fallbackUsed"),
                "error": value.get("error"),
            }
            for key, value in (payload.get("markets") or {}).items()
        },
    }
    write_json(ROOT / "logs" / "market_data_status.json", status)
    for error in payload.get("errors") or []:
        append_jsonl(ROOT / "logs" / "market_data_errors.jsonl", {"at": iso(), **error})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default=os.environ.get("MARKET_REPORT_SLOT", ""))
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.slot)
    write_outputs(payload)
    if args.print_summary:
        print(json.dumps({
            "overallStatus": payload["overallStatus"],
            "reportSlot": payload.get("reportSlot"),
            "missingRequired": payload.get("missingRequired", []),
            "fallbackCount": payload.get("fallbackCount", 0),
            "markets": {
                key: {
                    "value": market.get("displayValue"),
                    "unit": market.get("unit"),
                    "status": market.get("verificationStatus"),
                    "source": market.get("sourceId"),
                }
                for key, market in payload.get("markets", {}).items()
            },
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
