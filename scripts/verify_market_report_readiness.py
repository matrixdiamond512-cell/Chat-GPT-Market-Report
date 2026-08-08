#!/usr/bin/env python3
"""Verify that market data is ready before a scheduled market report is published.

The check deliberately validates the committed GitHub market-data layer first.
Google Sheets is a persistence/consumption layer, not the only copy of verified
market data. If Sheets synchronization is unavailable, report generation may
fall back to data/market/latest.json or data/market/chatgpt_input.csv instead of
incorrectly declaring verified market values unavailable.
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
        "blockingReasons": blocking,
        "warnings": warnings,
        "reportSourcePriority": [
            "ChatGPT_Market_Input when the expected report slot is present and current",
            "data/market/latest.json when Google Sheets is missing, stale, or not synchronized",
            "data/market/chatgpt_input.csv as the equivalent tabular GitHub fallback",
            "last verified value only with explicit timestamp/fallback note",
        ],
        "rule": "Do not output '取得不能' merely because Google Sheets has no matching row when the committed GitHub market-data layer contains a current verified value.",
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
