#!/usr/bin/env python3
"""Verify that market data is ready before a scheduled market report is published.

The check validates the committed GitHub market-data layer first. For 08:00 it
also requires the morning CME/OSE reference layer, so missing morning futures
cannot silently become generic '取得不能' rows in the published report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
MORNING_REFERENCE_REQUIRED = (
    "CME日経225先物・円建て",
    "CME日経225先物・ドル建て",
    "日経225先物（大阪取引所）",
)


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def validate_morning_reference(now: dt.datetime, slot: str, blocking: list[str], warnings: list[str]) -> dict[str, Any]:
    if slot != "08:00":
        return {}

    path = ROOT / "data" / "market" / "morning-reference.json"
    reference = load_json(path, {})
    if not reference:
        blocking.append("08:00 morning-reference.json is missing or unreadable")
        return {}

    expected_date = now.date().isoformat()
    if reference.get("reportDate") != expected_date:
        blocking.append(
            f"morning reference reportDate mismatch: expected {expected_date}, got {reference.get('reportDate') or 'empty'}"
        )
    if reference.get("reportSlot") != "08:00":
        blocking.append(
            f"morning reference slot mismatch: expected 08:00, got {reference.get('reportSlot') or 'empty'}"
        )

    generated = parse_time(reference.get("generatedAt"))
    if generated is None:
        blocking.append("morning reference generatedAt is missing or invalid")
    elif generated.date() != now.date():
        blocking.append(f"morning reference was generated on {generated.date().isoformat()}, not today")

    items = reference.get("items") or {}
    for label in MORNING_REFERENCE_REQUIRED:
        item = items.get(label)
        if not isinstance(item, dict):
            blocking.append(f"morning reference missing required item: {label}")
            continue
        value = str(item.get("value") or "").strip()
        status = str(item.get("status") or "")
        if not value:
            blocking.append(f"morning reference value empty: {label}")
        if not status.startswith("verified"):
            blocking.append(f"morning reference not verified: {label} status={status or 'empty'}")
        if label.startswith("CME") and "CME公式清算値" not in str(item.get("note") or ""):
            warnings.append(f"{label}: keep source distinction clear; reference is not CME official settlement")

    return reference


def report_input_status(report_input: dict[str, Any]) -> str:
    if not report_input or "expectedCount" not in report_input:
        return "NOT_YET_GENERATED"
    markets = report_input.get("markets") or {}
    if report_input.get("expectedCount") != 28 or len(markets) != 28 or report_input.get("dataComplete") is not True:
        return "PARTIAL"
    if any(not isinstance(item, dict) or not is_number(item.get("value")) or item.get("verificationStatus") != "verified" for item in markets.values()):
        return "PARTIAL"
    return "COMPLETE"


def validate_report_input(now: dt.datetime, slot: str, blocking: list[str], warnings: list[str]) -> dict[str, Any]:
    """Validate the published 28-row close contract separately from live quotes."""
    if slot != "08:00":
        return {}
    path = ROOT / "data" / "market" / "chatgpt-input.json"
    report_input = load_json(path, {})
    if not report_input or "expectedCount" not in report_input:
        warnings.append("08:00 report-level 28-item input is not generated yet; report completeness is not asserted by this snapshot check.")
        return {}
    if report_input.get("reportSlot") != "08:00":
        blocking.append(f"08:00 report input slot mismatch: got {report_input.get('reportSlot') or 'empty'}")
    expected_count = report_input.get("expectedCount")
    markets = report_input.get("markets") or {}
    expected_ids = {
        "dow", "nasdaq", "sp500", "russell2000", "nikkei225_cash",
        "nikkei225_futures_cme_yen", "nikkei225_futures_cme_usd", "nikkei225_futures_ose",
        "usdjpy", "eurusd", "gold", "wti", "btcusd", "vix", "nikkei_vi", "fear_greed",
        "us10y", "jp10y", "nikkei225_per", "nikkei225_pbr", "nikkei225_eps",
        "nikkei225_dev25", "nikkei225_dev200", "tse_prime_turnover", "tse_prime_volume",
        "tse_prime_advancers", "tse_prime_decliners", "tse_prime_ad_ratio25",
    }
    if expected_count != 28 or len(markets) != 28 or set(markets) != expected_ids:
        missing = sorted(expected_ids - set(markets))
        blocking.append(f"08:00 report input is incomplete: expected 28 named items, found {len(markets)}; missing={missing}")
    if report_input.get("dataComplete") is not True:
        unavailable = report_input.get("unavailableLabels") or []
        detail = ", ".join(map(str, unavailable[:10])) or "dataComplete is not true"
        blocking.append("08:00 report input has missing/unverified items: " + detail)
    for symbol_id, market in markets.items():
        if not isinstance(market, dict) or not is_number(market.get("value")) or market.get("verificationStatus") != "verified":
            blocking.append(f"08:00 report input item is missing a verified numeric value: {symbol_id}")
    previous_close_date = str(report_input.get("previousCloseDate") or "")
    if previous_close_date and previous_close_date >= now.date().isoformat():
        blocking.append(f"08:00 report input is not a prior-session close: {previous_close_date}")
    return report_input


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True, choices=("08:00", "12:00", "16:00", "21:00"))
    parser.add_argument("--max-age-minutes", type=int, default=30)
    parser.add_argument(
        "--latest",
        default=str(ROOT / "data" / "market" / "latest.json"),
        help="Path to committed latest market-data JSON",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "market" / "report_readiness.json"),
        help="Path for machine-readable readiness result",
    )
    args = parser.parse_args()

    now = dt.datetime.now(JST).replace(microsecond=0)
    latest_path = Path(args.latest)
    payload = load_json(latest_path, {})
    source_config = load_json(ROOT / "config" / "market_data_sources.json", {})

    blocking: list[str] = []
    warnings: list[str] = []

    if not payload:
        blocking.append("latest market-data JSON is missing or unreadable")

    report_slot = str(payload.get("reportSlot") or "")
    if report_slot != args.slot:
        blocking.append(f"report slot mismatch: expected {args.slot}, got {report_slot or 'empty'}")

    generated_at = parse_time(payload.get("generatedAt"))
    age_minutes: float | None = None
    if generated_at is None:
        blocking.append("generatedAt is missing or invalid")
    else:
        age_minutes = max(0.0, (now - generated_at).total_seconds() / 60.0)
        if generated_at.date() != now.date():
            blocking.append(
                f"market data is from a different JST date: {generated_at.date().isoformat()}"
            )
        if age_minutes > args.max_age_minutes:
            blocking.append(
                f"market data is stale: {age_minutes:.1f} minutes old; limit is {args.max_age_minutes}"
            )

    overall_status = str(payload.get("overallStatus") or "")
    if overall_status == "blocked" or not overall_status:
        blocking.append(f"overallStatus is {overall_status or 'empty'}")
    elif overall_status == "degraded":
        warnings.append("overallStatus is degraded; fallback values must be identified in the report")

    symbols = source_config.get("symbols") or {}
    markets = payload.get("markets") or {}
    required_ids = [
        symbol_id
        for symbol_id, config in symbols.items()
        if isinstance(config, dict) and config.get("required", False)
    ]

    missing_required: list[str] = []
    unusable_required: list[str] = []
    fallback_required: list[str] = []
    for symbol_id in required_ids:
        market = markets.get(symbol_id)
        if not isinstance(market, dict):
            missing_required.append(symbol_id)
            continue
        if not is_number(market.get("value")):
            unusable_required.append(symbol_id)
            continue
        verification = str(market.get("verificationStatus") or "")
        if verification not in {"verified", "fallback"}:
            unusable_required.append(symbol_id)
            continue
        if verification == "fallback" or market.get("fallbackUsed"):
            fallback_required.append(symbol_id)

    if missing_required:
        blocking.append("required markets missing: " + ", ".join(missing_required))
    if unusable_required:
        blocking.append("required markets unusable: " + ", ".join(unusable_required))
    if fallback_required:
        warnings.append("required markets using prior verified fallback: " + ", ".join(fallback_required))

    missing_from_payload = payload.get("missingRequired") or []
    if missing_from_payload:
        blocking.append("payload missingRequired is not empty: " + ", ".join(map(str, missing_from_payload)))

    morning_reference = validate_morning_reference(now, args.slot, blocking, warnings)
    report_input = validate_report_input(now, args.slot, blocking, warnings)

    close_sync = load_json(ROOT / "data" / "market" / "close_data_sync_status.json", {}) if args.slot == "08:00" else {}
    close_sync_generated = parse_time(close_sync.get("generatedAt"))
    close_sync_current = bool(close_sync_generated and close_sync_generated.date() == now.date())
    if args.slot == "08:00":
        if not close_sync_current:
            warnings.append("終値一覧の当朝同期結果がありません。空欄はChatGPT_Market_Input、GitHub検証済みデータ、Web再取得で補い、未更新を成功扱いしない。")
        elif close_sync.get("status") != "SUCCESS":
            warnings.append(
                "終値一覧同期は完全確認されていません "
                f"(status={close_sync.get('status') or 'unknown'}, "
                f"failedStage={close_sync.get('failedStage') or 'none'}); "
                "同期済みの値のみ前営業日終値として利用し、不足項目は代替取得する。"
            )

    ready = not blocking
    result = {
        "checkedAt": now.isoformat(),
        "reportSlot": args.slot,
        "ready": ready,
        "overallStatus": overall_status,
        "generatedAt": payload.get("generatedAt"),
        "ageMinutes": round(age_minutes, 1) if age_minutes is not None else None,
        "maxAgeMinutes": args.max_age_minutes,
        "requiredMarkets": required_ids,
        "morningReferenceRequired": list(MORNING_REFERENCE_REQUIRED) if args.slot == "08:00" else [],
        "morningReferenceDate": morning_reference.get("referenceDate") if morning_reference else None,
        "reportInputCompleteness": {"status": report_input_status(report_input), "availableCount": len(report_input.get("markets") or {}) if report_input else None, "expectedCount": report_input.get("expectedCount") if report_input else 28, "dataComplete": report_input.get("dataComplete") if report_input else None, "previousCloseDate": report_input.get("previousCloseDate") if report_input else None},
        "blockingReasons": blocking,
        "warnings": warnings,
        "closeDataSync": {
            "status": close_sync.get("status") if close_sync_current else "MISSING_OR_STALE",
            "targetDate": close_sync.get("targetDate"),
            "row": close_sync.get("row"),
            "failedStage": close_sync.get("failedStage"),
            "stages": close_sync.get("stages") or {},
            "missingRequiredFields": close_sync.get("missingRequiredFields") or [],
        },
        "reportSourcePriority": [
            "終値一覧 for date-matched previous-session close fields, only when closeDataSync status is SUCCESS",
            "ChatGPT_Market_Input for current report-slot market values",
            "data/market/latest.json when Google Sheets is missing, stale, or not synchronized",
            "data/market/chatgpt_input.csv as the equivalent tabular GitHub fallback",
            "data/market/morning-reference.json for 08:00 CME/OSE reference values",
            "last verified value only with explicit timestamp/fallback note",
        ],
        "rule": "Do not output '取得不能' merely because one persistence/display layer has no matching row when a current verified source value exists.",
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
