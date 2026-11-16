#!/usr/bin/env python3
"""Save one validated official Treasury observation to the dedicated test Sheet only."""

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

INPUT_SHEET = "Codex_Test_Market_Input"
HISTORY_SHEET = "Codex_Test_Market_History"
RULES_SHEET = "Codex_Test_Market_Rules"


def acquire_treasury() -> tuple[dict[str, Any], dict[str, Any]]:
    config = market_data.load_json(ROOT / "config" / "market_data_sources.json", {})
    validation = market_data.load_json(ROOT / "config" / "market_data_validation.json", {})
    symbol = (config.get("symbols") or {}).get("us10y")
    if not symbol:
        raise SheetsSyncError("TREASURY_SYMBOL_CONFIG_MISSING")
    source = next((item for item in symbol.get("sources", []) if item.get("id") == "us_treasury_yield_curve"), None)
    if not source:
        raise SheetsSyncError("TREASURY_SOURCE_CONFIG_MISSING")
    fetcher = market_data.FETCHERS.get(str(source.get("kind") or ""))
    if not fetcher:
        raise SheetsSyncError("TREASURY_FETCHER_MISSING")

    raw = fetcher(source)
    checks = dict(validation.get("defaults") or {})
    checks.update((validation.get("symbols") or {}).get("us10y", {}))
    valid, code, _reason = market_data.validate_candidate("us10y", symbol, checks, raw, None)
    observed = market_data.parse_iso(raw.get("asOf"))
    now_jst = market_data.now_jst()
    value = raw.get("value")
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    not_future = bool(observed and observed <= now_jst)
    source_matches = raw.get("sourceId") == "us_treasury_yield_curve"
    if not valid or not numeric or not not_future or not source_matches:
        raise SheetsSyncError("TREASURY_VALIDATION_" + (code if not valid else "DATE_OR_VALUE_OR_SOURCE"))
    return raw, {
        "sourceId": "us_treasury_yield_curve",
        "marketDate": observed.date().isoformat(),
        "sourceMatches": source_matches,
        "notFutureDated": not_future,
        "numericValue": numeric,
        "validationCode": "OK",
    }


def run() -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not production_id or not credentials:
        raise SheetsSyncError("TEST_SHEET_CONFIG_MISSING")
    if test_id == production_id:
        raise SheetsSyncError("TEST_SHEET_MUST_BE_SEPARATE_FROM_PRODUCTION")

    raw, verified = acquire_treasury()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    generated_at = str(raw["asOf"])
    value = float(raw["value"])
    payload = {
        "generatedAt": generated_at,
        "reportSlot": "treasury-private-test",
        "overallStatus": "verified",
        "markets": {
            "us10y": {
                "displayName": "米10年債利回り（テスト保存）",
                "value": value,
                "displayValue": f"{value:.3f}%",
                "unit": "%",
                "asOf": raw["asOf"],
                "fetchedAt": now,
                "verifiedAt": now,
                "lastVerifiedAt": now,
                "verificationStatus": "verified",
                "freshnessStatus": "fresh",
                "fallbackUsed": False,
                "sourceId": verified["sourceId"],
                "sourceName": "U.S. Treasury Daily Treasury Par Yield Curve Rates",
                "sourceUrl": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml",
                "marketType": "yield",
                "session": "daily",
                "note": "Private test-sheet validation; not a production close-list update.",
            }
        },
    }
    client = SheetsClient(
        create_authorized_session(load_service_account_info(credentials)),
        test_id,
    )
    first = sync_payload(client, payload, INPUT_SHEET, HISTORY_SHEET, RULES_SHEET)
    input_rows = client.get_values(INPUT_SHEET, "A1:AA2")
    if len(input_rows) < 2:
        raise SheetsSyncError("TREASURY_INPUT_READBACK_MISSING")
    header = input_rows[0] + [""] * max(0, len(SHEET_HEADERS) - len(input_rows[0]))
    row = input_rows[1] + [""] * max(0, len(SHEET_HEADERS) - len(input_rows[1]))
    if header[:len(SHEET_HEADERS)] != SHEET_HEADERS:
        raise SheetsSyncError("TREASURY_INPUT_HEADER_MISMATCH")
    if row[4] != "us10y" or row[20] != "U.S. Treasury Daily Treasury Par Yield Curve Rates" or row[21] != "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml":
        raise SheetsSyncError("TREASURY_INPUT_IDENTITY_MISMATCH")
    if not isinstance(row[7], (int, float)) or not math.isclose(float(row[7]), value, rel_tol=0, abs_tol=1e-9):
        raise SheetsSyncError("TREASURY_INPUT_NUMERIC_READBACK_MISMATCH")
    sheet_date = market_data.parse_iso(str(row[14]))
    if not sheet_date or sheet_date.date().isoformat() != verified["marketDate"]:
        raise SheetsSyncError("TREASURY_INPUT_DATE_READBACK_MISMATCH")

    second = sync_payload(client, payload, INPUT_SHEET, HISTORY_SHEET, RULES_SHEET)
    history_rows = client.get_values(HISTORY_SHEET, "A:AA")
    snapshot_id = f"{generated_at}|us10y"
    occurrences = sum(1 for item in history_rows[1:] if item and item[0] == snapshot_id)
    if occurrences != 1 or second.get("historyRowsAdded") != 0:
        raise SheetsSyncError("TREASURY_DUPLICATE_PREVENTION_FAILED")

    return {
        "status": "PASS",
        "symbol": "us10y",
        "sourceId": verified["sourceId"],
        "marketDate": verified["marketDate"],
        "numericValuePresent": verified["numericValue"],
        "sourceMatches": verified["sourceMatches"],
        "notFutureDated": verified["notFutureDated"],
        "validationCode": verified["validationCode"],
        "testInputReadback": "PASS",
        "testHistoryReadback": first.get("historyReadback"),
        "duplicatePrevented": True,
        "retryHistoryRowsAdded": second.get("historyRowsAdded"),
        "productionSpreadsheetUsed": False,
    }


def main() -> int:
    try:
        print(json.dumps(run(), ensure_ascii=False, separators=(",", ":")))
        return 0
    except SheetsSyncError as exc:
        print(json.dumps({"status": "FAIL", "errorCode": str(exc).split(":", 1)[0]}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "errorCode": type(exc).__name__}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
