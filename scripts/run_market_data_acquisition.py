#!/usr/bin/env python3
"""Run staged market-data acquisition and preserve the best verified values.

The workflow invokes this script repeatedly before each market report. The first
run for a report slot fetches every configured symbol. Later runs retry missing,
fallback, or stale symbols and refresh live markets without replacing an already
verified value with a failed retry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_market_data as market_data  # noqa: E402


ROOT = SCRIPT_DIR.parent
JST = dt.timezone(dt.timedelta(hours=9))

DEFAULT_REFRESH_MINUTES = 30
REFRESH_MINUTES: dict[str, int] = {
    "gold": 9,
    "wti": 9,
    "nikkei225_futures_ose": 9,
    "usdjpy": 9,
    "eurusd": 9,
    "btcusd": 9,
    "vix": 30,
    "nikkei_vi": 30,
    "fear_greed": 360,
    "crypto_fear_greed": 360,
}


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


def same_window(existing: dict[str, Any], slot: str, now: dt.datetime) -> bool:
    if not existing or str(existing.get("reportSlot") or "") != slot:
        return False
    generated = parse_time(existing.get("generatedAt"))
    return bool(generated and generated.date() == now.astimezone(JST).date())


def is_verified(market: dict[str, Any] | None) -> bool:
    return bool(
        market
        and market.get("verificationStatus") == "verified"
        and market_data.safe_float(market.get("value")) is not None
    )


def market_age_minutes(market: dict[str, Any] | None, now: dt.datetime) -> float | None:
    if not market:
        return None
    timestamp = parse_time(market.get("fetchedAt")) or parse_time(market.get("asOf"))
    if not timestamp:
        return None
    return max(0.0, (now.astimezone(JST) - timestamp).total_seconds() / 60.0)


def select_targets(
    symbols: dict[str, Any],
    existing_markets: dict[str, Any],
    *,
    full: bool,
    now: dt.datetime,
) -> list[str]:
    if full:
        return list(symbols)

    targets: list[str] = []
    for symbol_id in symbols:
        current = existing_markets.get(symbol_id) or {}
        if not is_verified(current):
            targets.append(symbol_id)
            continue
        max_age = REFRESH_MINUTES.get(symbol_id, DEFAULT_REFRESH_MINUTES)
        age = market_age_minutes(current, now)
        if age is None or age >= max_age:
            targets.append(symbol_id)
    return targets


def latest_symbol_error(errors: list[dict[str, Any]], symbol_id: str) -> str:
    matching = [item for item in errors if item.get("symbol") == symbol_id]
    if not matching:
        return ""
    item = matching[-1]
    source = str(item.get("sourceId") or "")
    code = str(item.get("code") or "")
    message = str(item.get("message") or "")
    return ": ".join(part for part in (source, code, message) if part)


def preserve_verified_after_failed_retry(
    current: dict[str, Any],
    attempted: dict[str, Any],
    *,
    error_text: str,
    attempted_at: str,
) -> dict[str, Any]:
    result = dict(current)
    result["attemptCount"] = int(current.get("attemptCount") or 0) + 1
    result["lastAttemptAt"] = attempted_at
    result["lastError"] = error_text or attempted.get("error") or "再取得に失敗"
    result["retryPreserved"] = True
    result["note"] = "同じ発行枠で取得済みの検証済み値を保持し、再取得を継続します。"
    return result


def annotate_attempt(
    market: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    attempted_at: str,
    error_text: str,
) -> dict[str, Any]:
    result = dict(market)
    result["attemptCount"] = int((previous or {}).get("attemptCount") or 0) + 1
    result["lastAttemptAt"] = attempted_at
    result["lastError"] = error_text
    result["retryPreserved"] = False
    return result


def build_staged_payload(slot: str, mode: str = "auto") -> dict[str, Any]:
    now = market_data.now_jst()
    attempted_at = market_data.iso(now)
    source_config = market_data.load_json(ROOT / "config" / "market_data_sources.json", {})
    validation_config = market_data.load_json(ROOT / "config" / "market_data_validation.json", {})
    previous_verified = market_data.load_json(
        ROOT / "data" / "market" / "last_verified.json", {"markets": {}}
    )
    existing = market_data.load_json(ROOT / "data" / "market" / "latest.json", {})

    symbols = source_config.get("symbols") or {}
    continuing = mode != "full" and same_window(existing, slot, now)
    existing_markets = dict(existing.get("markets") or {}) if continuing else {}
    targets = select_targets(symbols, existing_markets, full=not continuing, now=now)

    markets: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    recovered: list[str] = []
    preserved: list[str] = []
    retries = int((validation_config.get("defaults") or {}).get("maxRetries", 3))

    for symbol_id, symbol_config in symbols.items():
        current = existing_markets.get(symbol_id)
        if symbol_id not in targets and current:
            markets[symbol_id] = dict(current)
            continue

        validation = dict(validation_config.get("defaults") or {})
        validation.update((validation_config.get("symbols") or {}).get(symbol_id, {}))
        previous = (previous_verified.get("markets") or {}).get(symbol_id)
        attempted, symbol_errors = market_data.fetch_symbol(
            symbol_id,
            symbol_config,
            validation,
            previous,
            retries,
        )
        errors.extend(symbol_errors)
        error_text = latest_symbol_error(symbol_errors, symbol_id)

        if is_verified(attempted):
            markets[symbol_id] = annotate_attempt(
                attempted,
                current,
                attempted_at=attempted_at,
                error_text=error_text,
            )
            if current and not is_verified(current):
                recovered.append(symbol_id)
        elif is_verified(current):
            markets[symbol_id] = preserve_verified_after_failed_retry(
                current,
                attempted,
                error_text=error_text,
                attempted_at=attempted_at,
            )
            preserved.append(symbol_id)
        else:
            markets[symbol_id] = annotate_attempt(
                attempted,
                current,
                attempted_at=attempted_at,
                error_text=error_text or str(attempted.get("error") or ""),
            )

    required = [
        symbol_id
        for symbol_id, symbol_config in symbols.items()
        if symbol_config.get("required", False)
    ]
    missing_required = [
        symbol_id
        for symbol_id in required
        if market_data.safe_float((markets.get(symbol_id) or {}).get("value")) is None
    ]
    remaining_fallback = [
        symbol_id
        for symbol_id, item in markets.items()
        if item.get("verificationStatus") == "fallback"
    ]
    remaining_unavailable = [
        symbol_id
        for symbol_id, item in markets.items()
        if market_data.safe_float(item.get("value")) is None
        or item.get("verificationStatus") == "unavailable"
    ]
    fallback_count = sum(1 for item in markets.values() if item.get("fallbackUsed"))
    if missing_required:
        overall_status = "blocked"
    elif fallback_count or remaining_fallback:
        overall_status = "degraded"
    else:
        overall_status = "verified"

    previous_acquisition = (existing.get("acquisition") or {}) if continuing else {}
    run_count = int(previous_acquisition.get("runCount") or 0) + 1
    window_started_at = previous_acquisition.get("windowStartedAt") or attempted_at

    return {
        "schemaVersion": "1.1.0",
        "pageId": "market-data",
        "generatedAt": attempted_at,
        "reportSlot": slot,
        "overallStatus": overall_status,
        "missingRequired": missing_required,
        "fallbackCount": fallback_count,
        "markets": markets,
        "errors": errors,
        "acquisition": {
            "strategy": "staged_retry",
            "windowStartedAt": window_started_at,
            "lastAttemptAt": attempted_at,
            "runCount": run_count,
            "mode": "full" if not continuing else "incremental",
            "targetedSymbols": targets,
            "recoveredSymbols": recovered,
            "preservedVerifiedSymbols": preserved,
            "remainingFallback": remaining_fallback,
            "remainingUnavailable": remaining_unavailable,
        },
        "sources": [
            {
                "id": source["id"],
                "name": source["name"],
                "kind": source["kind"],
                "url": source.get("sourceUrl") or source.get("url"),
                "marketType": source.get("marketType"),
                "session": source.get("session"),
            }
            for symbol in symbols.values()
            for source in symbol.get("sources", [])
        ],
    }


def write_acquisition_status(payload: dict[str, Any]) -> None:
    acquisition = payload.get("acquisition") or {}
    status = {
        "generatedAt": payload.get("generatedAt"),
        "reportSlot": payload.get("reportSlot"),
        "overallStatus": payload.get("overallStatus"),
        "missingRequired": payload.get("missingRequired") or [],
        "fallbackCount": payload.get("fallbackCount", 0),
        **acquisition,
    }
    market_data.write_json(ROOT / "data" / "market" / "acquisition_status.json", status)
    market_data.append_jsonl(ROOT / "logs" / "market_data_acquisition.jsonl", status)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default=os.environ.get("MARKET_REPORT_SLOT", ""))
    parser.add_argument("--mode", choices=("auto", "full"), default="auto")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    slot = str(args.slot or "").strip()
    if slot not in {"08:00", "12:00", "16:00", "21:00"}:
        raise SystemExit(f"Unsupported report slot: {slot!r}")

    payload = build_staged_payload(slot, args.mode)
    market_data.write_outputs(payload)
    # Reset the ChatGPT input to the current independent acquisition while the
    # report is still being assembled. Publication of the 08:00 report later
    # replaces this with its exact structured 28-row contract.
    market_data.write_json(ROOT / "data" / "market" / "chatgpt-input.json", payload)
    write_acquisition_status(payload)

    if args.print_summary:
        print(json.dumps({
            "overallStatus": payload.get("overallStatus"),
            "reportSlot": payload.get("reportSlot"),
            "missingRequired": payload.get("missingRequired") or [],
            "fallbackCount": payload.get("fallbackCount", 0),
            "acquisition": payload.get("acquisition") or {},
            "markets": {
                key: {
                    "value": item.get("displayValue"),
                    "status": item.get("verificationStatus"),
                    "attemptCount": item.get("attemptCount", 0),
                    "source": item.get("sourceId"),
                    "lastError": item.get("lastError") or "",
                }
                for key, item in (payload.get("markets") or {}).items()
            },
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
