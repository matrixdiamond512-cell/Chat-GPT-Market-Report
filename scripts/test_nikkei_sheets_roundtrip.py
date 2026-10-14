#!/usr/bin/env python3
"""Acquire Nikkei's official daily series and round-trip them through a private test Sheet only."""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from scripts import fetch_market_data as market_data
    from scripts.write_market_data_to_sheets import (
        SHEET_HEADERS,
        SheetsClient,
        SheetsSyncError,
        create_authorized_session,
        load_service_account_info,
        sync_payload,
    )
else:
    sys.path.insert(0, str(ROOT))
    from scripts import fetch_market_data as market_data
    from scripts.write_market_data_to_sheets import (
        SHEET_HEADERS,
        SheetsClient,
        SheetsSyncError,
        create_authorized_session,
        load_service_account_info,
        sync_payload,
    )

INPUT_SHEET = "Codex_Test_Nikkei_Input"
HISTORY_SHEET = "Codex_Test_Nikkei_History"
RULES_SHEET = "Codex_Test_Nikkei_Rules"
TARGETS = {
    "nikkei225_cash": "nikkei_nk225_official_daily_csv",
    "nikkei_vi": "nikkei_nk225vi_official_daily_csv",
    "nikkei225_dev25": "nikkei_nk225_official_sma25",
    "nikkei225_dev200": "nikkei_nk225_official_sma200",
}


def acquire_official_nikkei() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    config = market_data.load_json(ROOT / "config" / "market_data_sources.json", {})
    validation = market_data.load_json(ROOT / "config" / "market_data_validation.json", {})
    results: dict[str, dict[str, Any]] = {}
    dates: set[str] = set()

    for symbol_id, source_id in TARGETS.items():
        symbol = (config.get("symbols") or {}).get(symbol_id)
        if not symbol:
            raise SheetsSyncError("NIKKEI_SYMBOL_CONFIG_MISSING")
        source = next((item for item in symbol.get("sources", []) if item.get("id") == source_id), None)
        if not source:
            raise SheetsSyncError("NIKKEI_SOURCE_CONFIG_MISSING")
        fetcher = market_data.FETCHERS.get(str(source.get("kind") or ""))
        if not fetcher:
            raise SheetsSyncError("NIKKEI_FETCHER_MISSING")

        raw = fetcher(source)
        checks = dict(validation.get("defaults") or {})
        checks.update((validation.get("symbols") or {}).get(symbol_id, {}))
        if source.get("validationStaleHours") is not None:
            checks["staleHours"] = source["validationStaleHours"]
        valid, code, _reason = market_data.validate_candidate(symbol_id, symbol, checks, raw, None)
        observed = market_data.parse_iso(raw.get("asOf"))
        value = market_data.safe_float(raw.get("value"))
        source_matches = raw.get("sourceId") == source_id
        if not valid or not observed or observed > market_data.now_jst() or value is None or not source_matches:
            raise SheetsSyncError("NIKKEI_VALIDATION_" + (code if not valid else "DATE_VALUE_OR_SOURCE"))
        results[symbol_id] = {"raw": raw, "source": source, "marketDate": observed.date().isoformat()}
        dates.add(observed.date().isoformat())

    if len(dates) != 1:
        raise SheetsSyncError("NIKKEI_MARKET_DATE_MISMATCH")
    return results, {"marketDate": next(iter(dates)), "sourceIds": {k: TARGETS[k] for k in TARGETS}}


def run() -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not production_id or not credentials:
        raise SheetsSyncError("TEST_SHEET_CONFIG_MISSING")
    if test_id == production_id:
        raise SheetsSyncError("TEST_SHEET_MUST_BE_SEPARATE_FROM_PRODUCTION")

    config = market_data.load_json(ROOT / "config" / "market_data_sources.json", {})
    acquired, verified = acquire_official_nikkei()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    generated_at = max(str(item["raw"]["asOf"]) for item in acquired.values())
    markets: dict[str, dict[str, Any]] = {}
    for symbol_id, item in acquired.items():
        raw, source = item["raw"], item["source"]
        value = float(raw["value"])
        symbol_config = (config.get("symbols") or {}).get(symbol_id) or {}
        places = int(symbol_config.get("displayDecimalPlaces", 2))
        name = str(source.get("name") or symbol_id)
        markets[symbol_id] = {
            "displayName": str(symbol_config.get("displayName") or symbol_id),
            "value": value,
            "displayValue": f"{value:,.{places}f}",
            "unit": str(symbol_config.get("unit") or ""),
            "asOf": str(raw["asOf"]),
            "fetchedAt": now,
            "verifiedAt": now,
            "lastVerifiedAt": now,
            "verificationStatus": "verified",
            "freshnessStatus": "fresh",
            "fallbackUsed": False,
            "sourceId": source["id"],
            "sourceName": name,
            "sourceUrl": str(source.get("sourceUrl") or source.get("url") or ""),
            "marketType": str(source.get("marketType") or ""),
            "session": str(source.get("session") or ""),
            "note": "Official Nikkei private test-sheet validation; never a production close-list update.",
        }
    payload = {
        "generatedAt": generated_at,
        "reportSlot": "nikkei-official-private-test",
        "overallStatus": "verified",
        "markets": markets,
    }

    client = SheetsClient(
        create_authorized_session(load_service_account_info(credentials)),
        test_id,
    )
    first = sync_payload(client, payload, INPUT_SHEET, HISTORY_SHEET, RULES_SHEET)
    input_rows = client.get_values(INPUT_SHEET, "A1:AA10")
    if not input_rows or input_rows[0][:len(SHEET_HEADERS)] != SHEET_HEADERS:
        raise SheetsSyncError("NIKKEI_INPUT_HEADER_MISMATCH")
    readback = {str(row[4]): row for row in input_rows[1:] if len(row) > 14 and row[4]}
    for symbol_id, item in acquired.items():
        row = readback.get(symbol_id)
        if not row or row[20] != item["source"]["name"]:
            raise SheetsSyncError("NIKKEI_INPUT_IDENTITY_READBACK_MISMATCH")
        if not isinstance(row[7], (int, float)) or not math.isclose(float(row[7]), float(item["raw"]["value"]), rel_tol=0, abs_tol=1e-9):
            raise SheetsSyncError("NIKKEI_INPUT_VALUE_READBACK_MISMATCH")
        observed = market_data.parse_iso(str(row[14]))
        if not observed or observed.date().isoformat() != verified["marketDate"]:
            raise SheetsSyncError("NIKKEI_INPUT_DATE_READBACK_MISMATCH")

    second = sync_payload(client, payload, INPUT_SHEET, HISTORY_SHEET, RULES_SHEET)
    history_rows = client.get_values(HISTORY_SHEET, "A:AA")
    duplicates: dict[str, int] = {}
    for symbol_id in TARGETS:
        snapshot_id = f"{generated_at}|{symbol_id}"
        duplicates[symbol_id] = sum(1 for row in history_rows[1:] if row and row[0] == snapshot_id)
    if any(count != 1 for count in duplicates.values()) or second.get("historyRowsAdded") != 0:
        raise SheetsSyncError("NIKKEI_DUPLICATE_PREVENTION_FAILED")

    return {
        "status": "PASS",
        "symbols": list(TARGETS),
        "sourceIds": verified["sourceIds"],
        "marketDate": verified["marketDate"],
        "sourceMatches": True,
        "numericReadbacks": len(TARGETS),
        "dateReadbacks": len(TARGETS),
        "duplicateOccurrences": duplicates,
        "historyReadback": first.get("historyReadback"),
        "retryHistoryRowsAdded": second.get("historyRowsAdded"),
        "productionSpreadsheetUsed": False,
    }


def main() -> int:
    try:
        result = run()
    except (SheetsSyncError, market_data.FetchError, ValueError) as exc:
        code = exc.code if isinstance(exc, market_data.FetchError) else str(exc).split(":", 1)[0]
        print(json.dumps({"status": "FAIL", "errorCode": code}, ensure_ascii=False, separators=(",", ":")))
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
