#!/usr/bin/env python3
"""Repair missing economic-calendar results from verified alternate sources.

The primary calendar pipeline intentionally avoids storing raw provider data.
This repair stage fetches only the data needed for matching and writes only the
normalized result fields to the public JSON files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.postprocess_economic_calendar import (
    apply_numeric_result,
    base_meta,
    event_sort_key,
    iso_jst,
    load_json,
    parse_datetime,
    rebuild_days,
    write_json,
)


JST = ZoneInfo("Asia/Tokyo")
TRADINGVIEW_URL = "https://economic-calendar.tradingview.com/events"
DOL_CLAIMS_PDF_URL = "https://www.dol.gov/ui/data.pdf"
RESULT_COUNTRIES = ["US", "JP", "EU", "ES", "FR", "DE", "IT", "CN", "GB", "AU", "CA", "CH", "NZ"]


def fetch_json(url: str, timeout: int = 25) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
            "User-Agent": "WEB-Market-Report/1.2 (+GitHub Actions)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return payload if isinstance(payload, dict) else {}


def fetch_bytes(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/pdf,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; WEB-Market-Report/1.2)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_tradingview_rows(now: dt.datetime) -> list[dict[str, Any]]:
    start = (now.astimezone(dt.timezone.utc) - dt.timedelta(days=7)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    end = (now.astimezone(dt.timezone.utc) + dt.timedelta(days=8)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    query = urllib.parse.urlencode(
        {
            "from": start,
            "to": end,
            "countries": ",".join(RESULT_COUNTRIES),
        }
    )
    payload = fetch_json(f"{TRADINGVIEW_URL}?{query}")
    rows = payload.get("result", [])
    return [row for row in rows if isinstance(row, dict)]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_title(value: Any) -> str:
    text = clean(value).lower()
    replacements = (
        (r"\b(?:unemployment claims|initial jobless claims|jobless claims)\b", "initial unemployment claims"),
        (r"\bspanish\b", "spain"),
        (r"\bfrench\b", "france"),
        (r"\bgerman\b", "germany"),
        (r"\bitalian\b", "italy"),
        (r"\b(?:prelim|preliminary|final|revised|flash|s\.a\.|n\.s\.a\.)\b", " "),
        (r"(\d+)\s*[- ]?(?:y|yr|year)(?=\b)", r"\1 year"),
        (r"\bgovernment\b", " "),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def event_country_codes(event: dict[str, Any]) -> set[str]:
    currency = str(event.get("currency") or "")
    title = normalize_title(event.get("eventNameOriginal") or event.get("title"))
    if "spain" in title:
        return {"ES"}
    if "france" in title:
        return {"FR"}
    if "germany" in title:
        return {"DE"}
    if "italy" in title:
        return {"IT"}
    mapping = {
        "USD": {"US"},
        "JPY": {"JP"},
        "EUR": {"EU", "ES", "FR", "DE", "IT"},
        "CNY": {"CN"},
        "GBP": {"GB"},
        "AUD": {"AU"},
        "CAD": {"CA"},
        "CHF": {"CH"},
        "NZD": {"NZ"},
    }
    return mapping.get(currency, set())


def row_actual(row: dict[str, Any], hint: str = "") -> str:
    value = row.get("actualRaw", row.get("actual"))
    if value in (None, ""):
        return ""
    hint_match = re.search(r"([KMBT])\s*$", clean(hint), re.I)
    if hint_match and isinstance(value, (int, float)):
        suffix = hint_match.group(1).upper()
        divisor = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[suffix]
        scaled = float(value) / divisor
        return f"{scaled:.3f}".rstrip("0").rstrip(".") + suffix
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    unit = clean(row.get("unit"))
    if unit and unit not in {"Index", "Points", "Units"}:
        return f"{value}{unit}"
    return str(value)


def match_row(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    target_title = normalize_title(event.get("eventNameOriginal") or event.get("title"))
    target_countries = event_country_codes(event)
    scheduled = parse_datetime(event.get("datetimeJst"))
    if not target_title or scheduled is None:
        return None
    target_time = scheduled.astimezone(dt.timezone.utc)
    max_minutes = 120 if event.get("category") == "bond_auction" else 55
    best: tuple[float, dict[str, Any]] | None = None
    for row in rows:
        if row_actual(row, str(event.get("forecast") or "")) == "":
            continue
        row_country = clean(row.get("country"))
        if target_countries and row_country not in target_countries:
            continue
        row_time = parse_datetime(row.get("date"))
        if row_time is None:
            continue
        time_distance = abs((row_time.astimezone(dt.timezone.utc) - target_time).total_seconds())
        if time_distance > max_minutes * 60:
            continue
        row_title = normalize_title(row.get("title") or row.get("indicator"))
        if not row_title:
            continue
        similarity = SequenceMatcher(None, target_title, row_title).ratio()
        target_tokens = set(target_title.split())
        row_tokens = set(row_title.split())
        overlap = len(target_tokens & row_tokens) / max(1, len(target_tokens | row_tokens))
        containment = 1.0 if target_title in row_title or row_title in target_title else 0.0
        score = max(similarity, overlap, containment) - (time_distance / (max_minutes * 60)) * 0.08
        if score >= 0.42 and (best is None or score > best[0]):
            best = (score, row)
    return best[1] if best else None


def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("pypdf is required to read the official claims PDF") from error
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def compact_claims(value: str) -> str:
    number = int(value.replace(",", ""))
    return f"{number // 1000}K" if number % 1000 == 0 else f"{number / 1000:.3f}".rstrip("0").rstrip(".") + "K"


def extract_claims_from_text(text: str, event_date: dt.date) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", text)
    month_label = f"{event_date.strftime('%B')} {event_date.day}, {event_date.year}"
    date_pos = normalized.find(month_label)
    segment = normalized[max(0, date_pos - 1000) : date_pos + 9000] if date_pos >= 0 else normalized[:12000]
    actual_match = re.search(r"initial claims was\s+([0-9,]+)", segment, re.I)
    revised_match = re.search(
        r"previous week's level was revised.*?from\s+([0-9,]+)\s+to\s+([0-9,]+)",
        segment,
        re.I,
    )
    actual = compact_claims(actual_match.group(1)) if actual_match else ""
    revised = compact_claims(revised_match.group(2)) if revised_match else ""
    return actual, revised


def repair_claims_from_dol(event: dict[str, Any], now: dt.datetime, cache: dict[str, str]) -> bool:
    title = normalize_title(event.get("eventNameOriginal") or event.get("title"))
    if "initial unemployment claims" not in title:
        return False
    scheduled = parse_datetime(event.get("datetimeJst"))
    if scheduled is None or scheduled > now:
        return False
    if "dol_claims_pdf" not in cache:
        cache["dol_claims_pdf"] = pdf_text(fetch_bytes(DOL_CLAIMS_PDF_URL))
    actual, revised = extract_claims_from_text(cache["dol_claims_pdf"], scheduled.date())
    if not actual:
        return False
    return apply_numeric_result(
        event,
        actual,
        now,
        "us_dol_claims_pdf",
        "U.S. Department of Labor - Unemployment Insurance Weekly Claims",
        DOL_CLAIMS_PDF_URL,
        revised=revised,
        explanation_suffix="米労働省の公式Weekly Claims PDFから補完しました。",
    )


def mark_fetch_failure(event: dict[str, Any], now: dt.datetime, reason: str) -> bool:
    scheduled = parse_datetime(event.get("datetimeJst"))
    if scheduled is None or scheduled + dt.timedelta(hours=3) > now:
        return False
    message = f"取得不能（{reason}）"
    changed = event.get("resultExplanation") != message
    event["resultExplanation"] = message
    event["resultFetchStatus"] = "unavailable"
    event["updatedAt"] = iso_jst(now)
    return changed


def rebuild_outputs(root: Path, payload: dict[str, Any]) -> None:
    events = [item for item in payload.get("events", []) if isinstance(item, dict)]
    payload["days"] = rebuild_days(events)
    write_json(root / "data/events/latest.json", payload)
    write_json(root / "data/events.json", payload)
    completed = [item for item in events if item.get("status") == "released"]
    write_json(root / "data/events/completed.json", {**base_meta(payload), "events": sorted(completed, key=event_sort_key)})
    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        date = str(item.get("date") or "")
        if date:
            by_date.setdefault(date, []).append(item)
    for date, day_events in by_date.items():
        write_json(
            root / f"data/events/history/{date}.json",
            {**base_meta(payload), "date": date, "events": sorted(day_events, key=event_sort_key)},
        )


def process(root: Path, now: dt.datetime, fetch_live: bool = True, supplied_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = load_json(root / "data/events/latest.json", {})
    events = [item for item in payload.get("events", []) if isinstance(item, dict)]
    if not events:
        raise RuntimeError("data/events/latest.json にイベントがありません。")

    errors: list[str] = []
    rows = supplied_rows or []
    if fetch_live:
        try:
            rows = fetch_tradingview_rows(now)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"TradingView: {type(error).__name__}: {error}")

    matched = 0
    official = 0
    unavailable = 0
    dol_cache: dict[str, str] = {}
    for event in events:
        if event.get("status") == "released" or event.get("actual"):
            continue
        scheduled = parse_datetime(event.get("datetimeJst"))
        if scheduled is None or scheduled > now:
            continue
        row = match_row(event, rows)
        if row is not None:
            actual = row_actual(row, str(event.get("forecast") or ""))
            if actual:
                source_url = clean(row.get("source_url") or row.get("sourceUrl") or "https://www.tradingview.com/economic-calendar/")
                source_name = clean(row.get("source") or row.get("sourceName") or "TradingView Economic Calendar")
                if apply_numeric_result(
                    event,
                    actual,
                    now,
                    "tradingview_repair",
                    source_name,
                    source_url,
                    explanation_suffix="名称差・国コード差を補正してTradingView実績データから照合しました。",
                ):
                    matched += 1
                continue
        try:
            if repair_claims_from_dol(event, now, dol_cache):
                official += 1
                continue
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, ValueError) as error:
            errors.append(f"{event.get('title')}: {type(error).__name__}: {error}")

        title = normalize_title(event.get("eventNameOriginal") or event.get("title"))
        if event.get("category") == "bond_auction":
            if mark_fetch_failure(event, now, "代替カレンダーと公式発表元の双方で入札結果を照合できません"):
                unavailable += 1
        elif "initial unemployment claims" in title:
            if mark_fetch_failure(event, now, "米労働省公式PDFと代替カレンダーの双方で実績値を取得できません"):
                unavailable += 1

    sources = [item for item in payload.get("sources", []) if isinstance(item, dict) and item.get("id") != "event_result_repair"]
    sources.append(
        {
            "id": "event_result_repair",
            "name": "重要イベント実績値の補完取得",
            "status": "warning" if errors else "ok",
            "note": f"代替カレンダー照合 {matched}件、公式PDF補完 {official}件、取得不能理由明記 {unavailable}件。",
        }
    )
    payload["sources"] = sources
    payload["resultRepairAt"] = iso_jst(now)
    payload["resultRepairVersion"] = "1.0.0"
    if errors:
        current_errors = [item for item in payload.get("errors", []) if isinstance(item, dict) and item.get("code") != "EVENT_RESULT_REPAIR_FAILED"]
        current_errors.extend(
            {"code": "EVENT_RESULT_REPAIR_FAILED", "message": message, "at": iso_jst(now)}
            for message in errors
        )
        payload["errors"] = current_errors

    payload["events"] = events
    rebuild_outputs(root, payload)
    return {
        "matched": matched,
        "official": official,
        "unavailable": unavailable,
        "errors": len(errors),
        "pending": sum(item.get("status") == "result_pending" for item in events),
        "repairedAt": payload["resultRepairAt"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--now", help="ISO 8601 test time")
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = (
        dt.datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(JST)
        if args.now
        else dt.datetime.now(JST)
    )
    summary = process(args.root.resolve(), now)
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
