#!/usr/bin/env python3
"""Optional Google Sheets persistence for market data.

This script is intentionally non-blocking for the first dashboard recovery.
If Google credentials are not configured, it exits successfully and leaves the
GitHub JSON history as the source of record.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    latest_path = ROOT / "data" / "market" / "latest.json"
    if not spreadsheet_id or not service_account_json:
        print("Google Sheets persistence skipped: MARKET_DATA_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        return 0

    # Keep this script safe until the service account package choice is fixed.
    # The market data has already been persisted to data/market/*.json.
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    print(
        "Google Sheets persistence requested but not activated in this repository build. "
        f"Spreadsheet={spreadsheet_id}, status={latest.get('overallStatus')}. "
        "Use the existing GAS pipeline or add google-auth/google-api-python-client in a later step."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
