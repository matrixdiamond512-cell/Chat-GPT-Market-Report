#!/usr/bin/env python3
"""Repair and supplement normalized economic-calendar results.

The primary pipeline combines Forex Factory schedule data with TradingView
results. This post-processor handles two remaining gaps without inventing data:

* qualitative events such as speeches and holidays are recorded explicitly as
  non-numeric results instead of remaining in ``result_pending``;
* selected high-value indicators are supplemented from their official release
  pages when provider title differences prevent an automatic match.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
QUALITATIVE_PATTERNS = re.compile(
    r"\b(?:speaks?|speech|testifies|press conference)\b|発言|会見|講演",
    re.IGNORECASE,
)
DOL_RELEASES_URL = "https://www.dol.gov/newsroom/releases"
SPANISH_TREASURY_10Y_URL = "https://www.tesoro.es/en/tipo-de-obligaciones/10-a%C3%B1os"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_datetime(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(JST)


def iso_jst(value: dt.datetime) -> str:
    return value.astimezone(JST).isoformat(timespec="seconds")


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "WEB-Market-Report/1.1 (+GitHub Actions economic calendar)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<(?:script|style).*?>.*?</(?:script|style)>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def compact_number(value: str) -> str:
    number = int(str(value).replace(",", ""))
    if number % 1000 == 0:
        return f"{number // 1000}K"
    return f"{number / 1000:.3f}".rstrip("0").rstrip(".") + "K"


def parse_numeric(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([KMBT%]?)", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(match.group(2).upper(), 1.0)
    return number * multiplier


def result_comparison(actual: Any, forecast: Any) -> str:
    actual_value = parse_numeric(actual)
    forecast_value = parse_numeric(forecast)
    if actual_value is None or forecast_value is None:
        return ""
    tolerance = max(abs(forecast_value) * 0.0001, 1e-9)
    if actual_value > forecast_value + tolerance:
        return "市場予想を上回る"
    if actual_value < forecast_value - tolerance:
        return "市場予想を下回る"
    return "市場予想と一致"


def is_qualitative_event(event: dict[str, Any]) -> bool:
    category = str(event.get("category") or "")
    if category in {"speech", "holiday"}:
        return True
    title = " ".join(str(event.get(key) or "") for key in ("eventNameOriginal", "title"))
    has_numeric_reference = bool(event.get("forecast") or event.get("previous"))
    return not has_numeric_reference and bool(QUALITATIVE_PATTERNS.search(title))


def normalize_event(event: dict[str, Any], now: dt.datetime) -> bool:
    if not is_qualitative_event(event):
        return False
    scheduled = parse_datetime(event.get("datetimeJst"))
    if scheduled is None or scheduled > now:
        event["resultExpected"] = False
        event["resultType"] = "qualitative"
        return False

    category = str(event.get("category") or "")
    is_holiday = category == "holiday"
    actual = "休場" if is_holiday else "数値発表なし（発言イベント）"
    explanation = (
        "休場イベントのため、予想・前回・実績の数値はありません。流動性低下と取引再開時の値動きを確認します。"
        if is_holiday
        else "数値の実績値が発表されるイベントではありません。発言内容と、金利・為替・株価指数先物の反応を確認します。"
    )
    narrative = "休場確認済み" if is_holiday else "発言イベント終了"
    reaction = "流動性と取引再開を確認" if is_holiday else "発言内容と市場反応を確認"

    changed = any(
        [
            event.get("actual") != actual,
            event.get("status") != "released",
            event.get("resultExplanation") != explanation,
            event.get("resultType") != "qualitative",
        ]
    )
    event.update(
        {
            "forecast": event.get("forecast") or ("対象外" if is_holiday else "数値発表なし"),
            "previous": event.get("previous") or ("対象外" if is_holiday else "数値発表なし"),
            "actual": actual,
            "resultComparison": "",
            "resultExplanation": explanation,
            "status": "released",
            "resultExpected": False,
            "resultType": "qualitative",
            "resultSource": event.get("officialSource") or {
                "id": "official_source",
                "name": "公式発表元",
                "url": "",
            },
            "resultSavedAt": event.get("resultSavedAt") or iso_jst(now),
            "updatedAt": iso_jst(now),
        }
    )
    conclusion = dict(event.get("conclusion") or {})
    conclusion.update({"narrative": narrative, "reaction": reaction})
    event["conclusion"] = conclusion
    return changed


def apply_numeric_result(
    event: dict[str, Any],
    actual: str,
    now: dt.datetime,
    source_id: str,
    source_name: str,
    source_url: str,
    revised: str = "",
    explanation_suffix: str = "",
) -> bool:
    if not actual:
        return False
    comparison = result_comparison(actual, event.get("forecast"))
    explanation = (
        f"実績 {actual} は予想 {event.get('forecast') or 'なし'} に対して"
        f"{comparison or '比較保留'}。{explanation_suffix or '公式発表元から補完しました。'}"
    )
    changed = event.get("actual") != actual or event.get("status") != "released"
    event.update(
        {
            "actual": actual,
            "revised": revised or event.get("revised") or "",
            "resultComparison": comparison,
            "resultExplanation": explanation,
            "status": "released",
            "resultExpected": True,
            "resultType": "numeric",
            "resultSource": {"id": source_id, "name": source_name, "url": source_url},
            "resultSavedAt": iso_jst(now),
            "updatedAt": iso_jst(now),
        }
    )
    conclusion = dict(event.get("conclusion") or {})
    conclusion.update({"narrative": "結果確認済み", "reaction": comparison or "市場反応を確認"})
    event["conclusion"] = conclusion
    return changed


def event_title(event: dict[str, Any]) -> str:
    return " ".join(str(event.get(key) or "") for key in ("eventNameOriginal", "title")).lower()


def date_label(value: dt.date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def extract_dol_claims(page_text: str, event_date: dt.date) -> tuple[str, str]:
    text = html_to_text(page_text)
    start = text.find(date_label(event_date))
    if start < 0:
        return "", ""
    segment = text[start : start + 5000]
    if "Unemployment Insurance Weekly Claims Report" not in segment:
        return "", ""
    actual_match = re.search(r"initial claims was\s+([0-9,]+)", segment, re.I)
    revised_match = re.search(
        r"previous week's level was revised.*?from\s+([0-9,]+)\s+to\s+([0-9,]+)",
        segment,
        re.I,
    )
    actual = compact_number(actual_match.group(1)) if actual_match else ""
    revised = compact_number(revised_match.group(2)) if revised_match else ""
    return actual, revised


def signed_percent(direction: str, value: str) -> str:
    prefix = "-" if direction.lower() == "decreased" else ""
    return f"{prefix}{value}%"


def extract_bls_productivity(page_text: str, title: str) -> str:
    text = html_to_text(page_text)
    if "unit labor" in title or "単位労働" in title:
        match = re.search(
            r"Unit labor costs.*?\b(increased|decreased)\s+([0-9.]+)\s+percent",
            text,
            re.I,
        )
    else:
        match = re.search(
            r"labor productivity\s+\b(increased|decreased)\s+([0-9.]+)\s+percent",
            text,
            re.I,
        )
    return signed_percent(match.group(1), match.group(2)) if match else ""


def extract_spanish_auction(page_text: str, event_date: dt.date) -> str:
    text = html_to_text(page_text)
    labels = [
        f"{event_date.strftime('%A')}, {event_date.strftime('%B')} {event_date.day}, {event_date.year}",
        f"{event_date.day} {event_date.strftime('%B')} {event_date.year}",
    ]
    positions = [text.find(label) for label in labels if text.find(label) >= 0]
    if not positions:
        return ""
    position = min(positions)
    segment = text[max(0, position - 3500) : position + 700]
    yield_matches = re.findall(
        r"(?:Tipo de interés medio|Average interest rate)\s+([0-9.,]+)",
        segment,
        re.I,
    )
    coverage_matches = re.findall(
        r"(?:Ratio de cobertura|Coverage ratio)\s+([0-9.,]+)",
        segment,
        re.I,
    )
    if not yield_matches and not coverage_matches:
        return ""
    average_yield = yield_matches[-1].replace(",", ".") if yield_matches else ""
    coverage = coverage_matches[-1].replace(",", ".") if coverage_matches else ""
    parts = []
    if average_yield:
        parts.append(f"平均利回り {average_yield}%")
    if coverage:
        parts.append(f"応札倍率 {coverage}倍")
    return " / ".join(parts)


def supplement_official_results(events: list[dict[str, Any]], now: dt.datetime) -> tuple[int, list[str]]:
    changed = 0
    errors: list[str] = []
    cache: dict[str, str] = {}

    def cached_fetch(url: str) -> str:
        if url not in cache:
            cache[url] = fetch_text(url)
        return cache[url]

    for event in events:
        if event.get("status") == "released" or event.get("actual"):
            continue
        scheduled = parse_datetime(event.get("datetimeJst"))
        if scheduled is None or scheduled > now:
            continue
        title = event_title(event)
        try:
            if "unemployment claims" in title or "失業保険申請" in title:
                actual, revised = extract_dol_claims(cached_fetch(DOL_RELEASES_URL), scheduled.date())
                if actual:
                    changed += apply_numeric_result(
                        event,
                        actual,
                        now,
                        "us_dol_weekly_claims",
                        "U.S. Department of Labor - Unemployment Insurance Weekly Claims",
                        DOL_RELEASES_URL,
                        revised=revised,
                        explanation_suffix="米労働省の週間失業保険申請件数から補完しました。",
                    )
            elif "productivity" in title or "labor costs" in title or "労働生産性" in title or "単位労働" in title:
                archive_url = f"https://www.bls.gov/news.release/archives/prod2_{scheduled:%m%d%Y}.htm"
                actual = extract_bls_productivity(cached_fetch(archive_url), title)
                if actual:
                    changed += apply_numeric_result(
                        event,
                        actual,
                        now,
                        "bls_productivity_costs",
                        "U.S. Bureau of Labor Statistics - Productivity and Costs",
                        archive_url,
                        explanation_suffix="米労働統計局のProductivity and Costsから補完しました。",
                    )
            elif event.get("category") == "bond_auction" and (
                "spanish" in title or "spain" in title or "スペイン" in title
            ):
                actual = extract_spanish_auction(cached_fetch(SPANISH_TREASURY_10Y_URL), scheduled.date())
                if actual:
                    changed += apply_numeric_result(
                        event,
                        actual,
                        now,
                        "spanish_treasury_auction",
                        "Tesoro Público - 10-year Government Bond Auction",
                        SPANISH_TREASURY_10Y_URL,
                        explanation_suffix="スペイン財務当局の10年国債入札結果から補完しました。",
                    )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as error:
            errors.append(f"{event.get('title')}: {type(error).__name__}: {error}")
    return changed, errors


def ensure_official_fallback_source(payload: dict[str, Any], matched: int, errors: list[str]) -> None:
    sources = [item for item in payload.get("sources", []) if isinstance(item, dict)]
    sources = [item for item in sources if item.get("id") != "official_result_fallback"]
    sources.append(
        {
            "id": "official_result_fallback",
            "name": "公式発表元による実績値補完",
            "status": "warning" if errors else "ok",
            "note": f"公式発表元から{matched}件を補完。" + (f"取得エラー{len(errors)}件。" if errors else ""),
        }
    )
    payload["sources"] = sources
    if errors:
        payload_errors = list(payload.get("errors") or [])
        payload_errors.extend(
            {"code": "OFFICIAL_RESULT_FALLBACK_FAILED", "message": message, "at": payload.get("generatedAt")}
            for message in errors
        )
        payload["errors"] = payload_errors


def rebuild_days(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = sorted({str(item.get("date")) for item in events if item.get("date")}, reverse=True)
    rows: list[dict[str, Any]] = []
    for date in dates:
        day_events = [item for item in events if item.get("date") == date]
        rows.append(
            {
                "date": date,
                "eventCount": len(day_events),
                "releasedCount": sum(item.get("status") == "released" for item in day_events),
                "resultPendingCount": sum(item.get("status") == "result_pending" for item in day_events),
            }
        )
    return rows


def base_meta(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "schemaVersion",
        "pageId",
        "generatedAt",
        "publishedAt",
        "dataAsOf",
        "timezone",
        "status",
        "isStale",
        "sources",
        "errors",
    )
    return {key: payload.get(key) for key in keys if key in payload}


def event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("date") or ""),
        str(event.get("time") or ""),
        str(event.get("title") or ""),
    )


def process(root: Path, now: dt.datetime, fetch_official: bool = True) -> dict[str, Any]:
    latest_path = root / "data/events/latest.json"
    payload = load_json(latest_path, {})
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise RuntimeError("data/events/latest.json に有効なイベント配列がありません。")

    events = [item for item in payload["events"] if isinstance(item, dict)]
    qualitative_count = sum(normalize_event(item, now) for item in events)
    official_count = 0
    official_errors: list[str] = []
    if fetch_official:
        official_count, official_errors = supplement_official_results(events, now)
        ensure_official_fallback_source(payload, official_count, official_errors)

    payload["events"] = events
    payload["days"] = rebuild_days(events)
    payload["postprocessedAt"] = iso_jst(now)
    payload["postprocessVersion"] = "1.1.0"

    write_json(latest_path, payload)
    write_json(root / "data/events.json", payload)

    completed = [item for item in events if item.get("status") == "released"]
    write_json(
        root / "data/events/completed.json",
        {**base_meta(payload), "events": sorted(completed, key=event_sort_key)},
    )

    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        date = str(item.get("date") or "")
        if date:
            by_date.setdefault(date, []).append(item)
    for date, rows in by_date.items():
        write_json(
            root / f"data/events/history/{date}.json",
            {**base_meta(payload), "date": date, "events": sorted(rows, key=event_sort_key)},
        )

    return {
        "changed": qualitative_count + official_count,
        "qualitativeNormalized": qualitative_count,
        "officialResultsSaved": official_count,
        "officialErrors": len(official_errors),
        "events": len(events),
        "released": len(completed),
        "pending": sum(item.get("status") == "result_pending" for item in events),
        "postprocessedAt": payload["postprocessedAt"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--now", help="ISO 8601 test time")
    parser.add_argument("--no-official-fetch", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = (
        dt.datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(JST)
        if args.now
        else dt.datetime.now(JST)
    )
    summary = process(args.root.resolve(), now, fetch_official=not args.no_official_fetch)
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
