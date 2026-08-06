#!/usr/bin/env python3
"""Validate U.S. initial unemployment claims against the official DOL PDF.

Calendar providers publish several claims series at the same timestamp. A fuzzy
match can confuse initial claims with continuing claims. This final validation
stage makes the official Weekly Claims PDF authoritative for the initial-claims
row and removes an implausible provider match when the PDF cannot be read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.postprocess_economic_calendar import apply_numeric_result, iso_jst, load_json, parse_datetime
from scripts.repair_missing_event_results import (
    DOL_CLAIMS_PDF_URL,
    extract_claims_from_text,
    fetch_bytes,
    normalize_title,
    pdf_text,
    rebuild_outputs,
)


JST = ZoneInfo("Asia/Tokyo")


def is_initial_claims(event: dict[str, Any]) -> bool:
    title = normalize_title(event.get("eventNameOriginal") or event.get("title"))
    return "initial unemployment claims" in title or "失業保険申請" in str(event.get("title") or "")


def numeric_thousands(value: Any) -> float | None:
    text = str(value or "").strip().upper().replace(",", "")
    try:
        if text.endswith("K"):
            return float(text[:-1])
        if text.endswith("M"):
            return float(text[:-1]) * 1000
        return float(text) / 1000
    except ValueError:
        return None


def clear_invalid_provider_match(event: dict[str, Any], now: dt.datetime, reason: str) -> bool:
    current = numeric_thousands(event.get("actual"))
    source_id = str((event.get("resultSource") or {}).get("id") or "")
    suspicious = current is not None and current >= 500 and source_id in {
        "tradingview_repair",
        "tradingview_economic_calendar",
    }
    if not suspicious:
        return False
    event.update(
        {
            "actual": "",
            "revised": "",
            "resultComparison": "",
            "resultExplanation": f"取得不能（{reason}）",
            "status": "result_pending",
            "resultFetchStatus": "unavailable",
            "updatedAt": iso_jst(now),
        }
    )
    event.pop("resultSource", None)
    event.pop("resultSavedAt", None)
    return True


def process(root: Path, now: dt.datetime, supplied_pdf_text: str | None = None) -> dict[str, Any]:
    payload = load_json(root / "data/events/latest.json", {})
    events = [item for item in payload.get("events", []) if isinstance(item, dict)]
    if not events:
        raise RuntimeError("data/events/latest.json にイベントがありません。")

    official_text = supplied_pdf_text
    fetch_error = ""
    if official_text is None:
        try:
            official_text = pdf_text(fetch_bytes(DOL_CLAIMS_PDF_URL))
        except Exception as error:  # workflow must record the exact failure rather than keep a false value
            fetch_error = f"{type(error).__name__}: {error}"
            official_text = ""

    corrected = 0
    cleared = 0
    for event in events:
        if not is_initial_claims(event):
            continue
        scheduled = parse_datetime(event.get("datetimeJst"))
        if scheduled is None or scheduled > now:
            continue
        actual, revised = extract_claims_from_text(official_text, scheduled.date()) if official_text else ("", "")
        if actual:
            before = (event.get("actual"), event.get("revised"), event.get("status"))
            apply_numeric_result(
                event,
                actual,
                now,
                "us_dol_claims_pdf",
                "U.S. Department of Labor - Unemployment Insurance Weekly Claims",
                DOL_CLAIMS_PDF_URL,
                revised=revised,
                explanation_suffix="同時刻に公表される継続受給者数との取り違えを防ぐため、米労働省の公式Weekly Claims PDFで検証しました。",
            )
            event["resultValidation"] = "official_pdf_verified"
            after = (event.get("actual"), event.get("revised"), event.get("status"))
            if before != after:
                corrected += 1
        elif clear_invalid_provider_match(
            event,
            now,
            "米労働省公式PDFを取得できず、継続受給者数とみられる値を新規申請件数として採用できません"
            + (f"。エラー: {fetch_error}" if fetch_error else ""),
        ):
            cleared += 1

    sources = [item for item in payload.get("sources", []) if isinstance(item, dict) and item.get("id") != "weekly_claims_validation"]
    sources.append(
        {
            "id": "weekly_claims_validation",
            "name": "米新規失業保険申請件数の公式検証",
            "status": "warning" if fetch_error else "ok",
            "note": f"公式PDFで訂正・検証 {corrected}件、誤照合値を除外 {cleared}件。" + (f" PDF取得エラー: {fetch_error}" if fetch_error else ""),
        }
    )
    payload["sources"] = sources
    payload["claimsValidatedAt"] = iso_jst(now)
    payload["claimsValidationVersion"] = "1.0.0"
    payload["events"] = events
    rebuild_outputs(root, payload)
    return {
        "corrected": corrected,
        "cleared": cleared,
        "fetchError": bool(fetch_error),
        "validatedAt": payload["claimsValidatedAt"],
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
