#!/usr/bin/env python3
"""Sync the reduced Gold_Demand schema without touching obsolete columns."""
from __future__ import annotations

import json
import os
from pathlib import Path

from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
from write_gold_supply_demand_to_sheets import (
    GOLD_JSON,
    MARKET_JSON,
    SHEET,
    SOURCE_SHEET,
    HEADERS,
    SOURCE_HEADERS,
    SOURCE_ROWS,
    build_rows,
)


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not service_account_json:
        print("Gold Google Sheets sync skipped: MARKET_DATA_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        return 0

    gold = json.loads(Path(GOLD_JSON).read_text(encoding="utf-8"))
    market = json.loads(Path(MARKET_JSON).read_text(encoding="utf-8"))
    rows = build_rows(gold, market)

    info = load_service_account_info(service_account_json)
    client = SheetsClient(create_authorized_session(info), spreadsheet_id)
    sheets = client.ensure_sheets([SHEET, SOURCE_SHEET])

    # The active Gold_Demand contract is exactly 12 columns (A:L).
    # Never clear legacy A:AZ after the grid has been reduced to 12 columns.
    client.clear(SHEET, "A:L")
    client.update(SHEET, "A1", [HEADERS] + rows)

    # SourceMap is exactly 6 columns (A:F).
    client.clear(SOURCE_SHEET, "A:F")
    client.update(SOURCE_SHEET, "A1", [SOURCE_HEADERS] + SOURCE_ROWS)

    client.format_table(sheets[SHEET], len(HEADERS), len(rows) + 1)
    client.format_table(sheets[SOURCE_SHEET], len(SOURCE_HEADERS), len(SOURCE_ROWS) + 1)

    print(json.dumps({
        "sheet": SHEET,
        "rows": len(rows),
        "columns": len(HEADERS),
        "sourceRows": len(SOURCE_ROWS),
        "sourceColumns": len(SOURCE_HEADERS),
        "generatedAt": gold.get("generatedAt"),
        "result": "success",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
