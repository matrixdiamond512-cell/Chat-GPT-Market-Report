#!/usr/bin/env python3
"""Exercise the Sheets writer against a dedicated test spreadsheet only."""

from __future__ import annotations

import json
import os
import sys

from scripts.write_market_data_to_sheets import (
    SHEET_HEADERS,
    SheetsClient,
    SheetsSyncError,
    create_authorized_session,
    load_service_account_info,
    sync_payload,
)


TEST_INPUT_SHEET = "Codex_Test_Market_Input"
TEST_HISTORY_SHEET = "Codex_Test_Market_History"
TEST_RULES_SHEET = "Codex_Test_Market_Rules"
TEST_SNAPSHOT_TIME = "2026-10-11T00:00:00+09:00"
TEST_SYMBOL_ID = "codex_test_only"


def padded(row: list[object], width: int) -> list[object]:
    return row + [""] * max(0, width - len(row))


def run_roundtrip() -> dict[str, object]:
    test_spreadsheet_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_spreadsheet_id or not production_spreadsheet_id or not service_account_json:
        raise SheetsSyncError("TEST_SHEET_CONFIG_MISSING")
    if production_spreadsheet_id and test_spreadsheet_id == production_spreadsheet_id:
        raise SheetsSyncError("TEST_SHEET_MUST_BE_SEPARATE_FROM_PRODUCTION")

    payload = {
        "generatedAt": TEST_SNAPSHOT_TIME,
        "reportSlot": "test-only",
        "overallStatus": "verified",
        "markets": {
            TEST_SYMBOL_ID: {
                "displayName": "Synthetic Test Item",
                "value": 12345.67,
                "displayValue": "TEST_ONLY",
                "unit": "test",
                "verificationStatus": "verified",
                "freshnessStatus": "fresh",
                "fallbackUsed": False,
                "asOf": TEST_SNAPSHOT_TIME,
                "fetchedAt": TEST_SNAPSHOT_TIME,
                "sourceId": "synthetic_test_fixture",
                "sourceName": "Synthetic test fixture; not market data",
                "sourceUrl": "",
                "marketType": "test",
                "session": "test-only",
                "note": "Test-only value; do not use for a report.",
            }
        },
    }
    client = SheetsClient(create_authorized_session(load_service_account_info(service_account_json)), test_spreadsheet_id)

    first = sync_payload(client, payload, TEST_INPUT_SHEET, TEST_HISTORY_SHEET, TEST_RULES_SHEET)
    input_readback = client.get_values(TEST_INPUT_SHEET, "A1:AA2")
    history_readback = client.get_values(TEST_HISTORY_SHEET, "A:AA")
    if len(input_readback) < 2:
        raise SheetsSyncError("TEST_INPUT_READBACK_MISSING")
    header = padded(input_readback[0], len(SHEET_HEADERS))
    row = padded(input_readback[1], len(SHEET_HEADERS))
    if header != SHEET_HEADERS or row[4] != TEST_SYMBOL_ID or row[6] != "使用可" or row[7] != payload["markets"][TEST_SYMBOL_ID]["value"]:
        raise SheetsSyncError("TEST_INPUT_READBACK_MISMATCH")

    second = sync_payload(client, payload, TEST_INPUT_SHEET, TEST_HISTORY_SHEET, TEST_RULES_SHEET)
    history_after_retry = client.get_values(TEST_HISTORY_SHEET, "A:AA")
    snapshot_id = f"{TEST_SNAPSHOT_TIME}|{TEST_SYMBOL_ID}"
    matches = [line for line in history_after_retry[1:] if line and line[0] == snapshot_id]
    if len(matches) != 1 or second["historyRowsAdded"] != 0:
        raise SheetsSyncError("TEST_HISTORY_DUPLICATE_PREVENTION_FAILED")
    if first["inputRows"] != 1 or len(history_readback) < 2:
        raise SheetsSyncError("TEST_HISTORY_READBACK_MISSING")

    return {
        "status": "PASS",
        "testItemCount": 1,
        "inputReadback": "PASS",
        "historyReadback": "PASS",
        "duplicatePrevented": True,
        "secondSyncHistoryRowsAdded": second["historyRowsAdded"],
        "targetSpreadsheetIdOmitted": True,
    }


def main() -> int:
    try:
        print(json.dumps(run_roundtrip(), ensure_ascii=False, separators=(",", ":")))
        return 0
    except SheetsSyncError as exc:
        print(json.dumps({"status": "FAIL", "errorCode": str(exc).split(":", 1)[0]}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "errorCode": type(exc).__name__}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

