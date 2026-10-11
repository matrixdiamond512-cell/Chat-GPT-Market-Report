#!/usr/bin/env python3
"""Normalize a manually collected TradingView MCP daily-bar batch for private review.

This is a manual bridge: TradingView MCP calls are made by the user/Codex session,
then their values are supplied as JSON. This script does not call TradingView,
run in GitHub Actions, update dashboard JSON, or publish market data.
"""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEST_SHEET = "TradingView_MCP_Candidates"
HEADERS = [
    "Snapshot ID",
    "Retrieved At (UTC)",
    "Report Field",
    "TradingView Symbol",
    "Observed Value",
    "Unit",
    "Market Type",
    "Market Session",
    "Interval",
    "Bar Anchor (UTC)",
    "Market Date",
    "Source",
    "Review Status",
]

# The explicit symbol/unit/session contract prevents a plausible-looking but
# different instrument from being silently relabelled as a report field.
FIELD_CONTRACT: dict[str, dict[str, str]] = {
    "dow": {"symbol": "TVC:DJI", "unit": "pt", "marketType": "index", "session": "us_cash"},
    "nasdaq": {"symbol": "NASDAQ:IXIC", "unit": "pt", "marketType": "index", "session": "us_cash"},
    "sp500": {"symbol": "SP:SPX", "unit": "pt", "marketType": "index", "session": "us_cash"},
    "russell2000": {"symbol": "CBOEFTSE:RUT", "unit": "pt", "marketType": "index", "session": "us_cash"},
    "nikkei225_cash": {"symbol": "TVC:NI225", "unit": "円", "marketType": "index", "session": "japan_cash"},
    "gold": {"symbol": "COMEX:GC1!", "unit": "USD/oz", "marketType": "continuous_futures", "session": "comex"},
    "wti": {"symbol": "NYMEX:CL1!", "unit": "USD/bbl", "marketType": "continuous_futures", "session": "nymex"},
    "nikkei225_futures_ose": {"symbol": "OSE:NK2251!", "unit": "円", "marketType": "futures_ose", "session": "ose"},
    "cme_nikkei225_jpy": {"symbol": "CME:NIY1!", "unit": "円", "marketType": "futures_cme", "session": "cme"},
    "cme_nikkei225_usd": {"symbol": "CME:NKD1!", "unit": "USD", "marketType": "futures_cme", "session": "cme"},
    "usdjpy": {"symbol": "FX:USDJPY", "unit": "JPY per USD", "marketType": "spot", "session": "forex_daily"},
    "eurusd": {"symbol": "FX:EURUSD", "unit": "USD per EUR", "marketType": "spot", "session": "forex_daily"},
    "btcusd": {"symbol": "BITSTAMP:BTCUSD", "unit": "USD", "marketType": "spot", "session": "utc_daily"},
    "vix": {"symbol": "CBOE:VIX", "unit": "pt", "marketType": "index", "session": "us_volatility"},
    "nikkei_vi": {"symbol": "TOCOM:NVI", "unit": "pt", "marketType": "index", "session": "japan_cash"},
    "jp10y": {"symbol": "TVC:JP10Y", "unit": "%", "marketType": "bond_yield", "session": "japan_yield"},
    "us10y": {"symbol": "TVC:US10Y", "unit": "%", "marketType": "bond_yield", "session": "us_yield"},
}


class CandidateImportError(ValueError):
    """Raised when an MCP snapshot does not meet the private-import contract."""


def parse_aware_datetime(value: Any, field: str) -> dt.datetime:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise CandidateImportError(f"{field} is required")
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CandidateImportError(f"{field} must be ISO-8601 or Unix seconds") from exc
        if parsed.tzinfo is None:
            raise CandidateImportError(f"{field} must include a timezone")
    else:
        raise CandidateImportError(f"{field} is required")
    return parsed.astimezone(dt.timezone.utc)


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or value is None:
        raise CandidateImportError(f"{field} must be a finite number")
    try:
        number = float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CandidateImportError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise CandidateImportError(f"{field} must be a finite number")
    return number


def snapshot_id(item_id: str, symbol: str, anchor: str) -> str:
    identity = f"{item_id}|{symbol}|{anchor}".encode("utf-8")
    return "tv-mcp-" + hashlib.sha256(identity).hexdigest()[:24]


def normalize_snapshot(snapshot: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise CandidateImportError("snapshot must be an object")
    retrieved = parse_aware_datetime(snapshot.get("retrievedAt"), "retrievedAt")
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    if retrieved > current + dt.timedelta(minutes=5):
        raise CandidateImportError("retrievedAt is in the future")
    items = snapshot.get("items")
    if not isinstance(items, list):
        raise CandidateImportError("items must be an array")

    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise CandidateImportError("each item must be an object")
        item_id = str(item.get("id") or "")
        if item_id not in FIELD_CONTRACT:
            raise CandidateImportError(f"unsupported report field: {item_id or '(empty)'}")
        if item_id in by_id:
            raise CandidateImportError(f"duplicate report field: {item_id}")
        by_id[item_id] = item
    missing = sorted(set(FIELD_CONTRACT) - set(by_id))
    if missing:
        raise CandidateImportError("incomplete 17-field batch: " + ", ".join(missing))

    candidates: list[dict[str, Any]] = []
    for item_id, contract in FIELD_CONTRACT.items():
        item = by_id[item_id]
        for key in ("symbol", "unit", "marketType", "session"):
            if item.get(key) != contract[key]:
                raise CandidateImportError(f"{item_id} {key} does not match the expected instrument contract")
        if item.get("interval") != "1D":
            raise CandidateImportError(f"{item_id} must use a 1D bar")
        anchor = parse_aware_datetime(item.get("barAnchorUtc"), f"{item_id}.barAnchorUtc")
        if anchor > retrieved:
            raise CandidateImportError(f"{item_id} bar anchor is later than retrieval time")
        market_date_text = str(item.get("marketDate") or "")
        try:
            market_date = dt.date.fromisoformat(market_date_text)
        except ValueError as exc:
            raise CandidateImportError(f"{item_id}.marketDate must be YYYY-MM-DD") from exc
        if market_date > retrieved.date():
            raise CandidateImportError(f"{item_id} market date is later than retrieval date")
        value = finite_number(item.get("value"), f"{item_id}.value")
        candidates.append({
            "id": item_id,
            "symbol": contract["symbol"],
            "value": value,
            "unit": contract["unit"],
            "marketType": contract["marketType"],
            "session": contract["session"],
            "interval": "1D",
            "barAnchorUtc": anchor.isoformat().replace("+00:00", "Z"),
            "marketDate": market_date.isoformat(),
            "snapshotId": snapshot_id(item_id, contract["symbol"], anchor.isoformat()),
            "source": "TradingView official MCP",
            "reviewStatus": "CANDIDATE_CLOSE_AND_SESSION_REVIEW_REQUIRED",
        })

    return {
        "schemaVersion": "tradingview-mcp-candidate-v1",
        "retrievedAt": retrieved.isoformat().replace("+00:00", "Z"),
        "candidateCount": len(candidates),
        "automationEnabled": False,
        "publicPublicationEnabled": False,
        "candidates": candidates,
    }


def sheet_rows(payload: dict[str, Any]) -> list[list[Any]]:
    retrieved = payload["retrievedAt"]
    return [
        [
            item["snapshotId"], retrieved, item["id"], item["symbol"], item["value"],
            item["unit"], item["marketType"], item["session"], item["interval"],
            item["barAnchorUtc"], item["marketDate"], item["source"], item["reviewStatus"],
        ]
        for item in payload["candidates"]
    ]


def write_test_sheet(payload: dict[str, Any]) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not account_json:
        raise CandidateImportError("test spreadsheet ID or service-account credential is not configured")
    if production_id and test_id == production_id:
        raise CandidateImportError("refusing to write: test spreadsheet ID matches production spreadsheet ID")

    try:
        from scripts.write_market_data_to_sheets import (
            SheetsClient, create_authorized_session, load_service_account_info
        )
    except ModuleNotFoundError:
        from write_market_data_to_sheets import (
            SheetsClient, create_authorized_session, load_service_account_info
        )

    info = load_service_account_info(account_json)
    client = SheetsClient(create_authorized_session(info), test_id)
    sheet_id = client.ensure_sheets([TEST_SHEET])[TEST_SHEET]
    prior = client.get_values(TEST_SHEET, "A1:M1000")
    if prior and prior[0] and prior[0][:len(HEADERS)] != HEADERS:
        raise CandidateImportError("candidate test tab has an unexpected header; refusing to alter it")
    if not prior:
        client.update(TEST_SHEET, "A1", [HEADERS])
        prior = [HEADERS]
    existing_ids = {str(row[0]) for row in prior[1:] if row and row[0]}
    pending = [row for row in sheet_rows(payload) if row[0] not in existing_ids]
    if pending:
        client.append(TEST_SHEET, "A:M", pending)
    readback = client.get_values(TEST_SHEET, "A1:M1000")
    ids = [str(row[0]) for row in readback[1:] if row and row[0]]
    requested_ids = [row[0] for row in sheet_rows(payload)]
    if any(ids.count(key) != 1 for key in requested_ids):
        raise CandidateImportError("test-sheet readback failed snapshot identity/duplicate check")
    actual_by_id = {str(row[0]): row for row in readback[1:] if row and row[0]}
    expected_by_id = {str(row[0]): row for row in sheet_rows(payload)}
    for key, expected in expected_by_id.items():
        actual = actual_by_id.get(key, [])
        normalized = list(actual[:len(HEADERS)]) + [""] * max(0, len(HEADERS) - len(actual))
        if normalized != expected:
            raise CandidateImportError("test-sheet readback mismatch")
    return {
        "sheet": TEST_SHEET,
        "candidateRows": len(requested_ids),
        "rowsAppended": len(pending),
        "readback": "verified",
        "duplicatePrevention": "verified",
        "productionSpreadsheetWritten": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON exported from the manual TradingView MCP read")
    parser.add_argument("--output", type=Path, help="normalized candidate JSON output")
    parser.add_argument("--write-test-sheet", action="store_true", help="append to a dedicated private test tab; never writes production")
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
        normalized = normalize_snapshot(snapshot)
        if args.output:
            args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result: dict[str, Any] = {
            "candidateCount": normalized["candidateCount"],
            "validation": "candidate_only",
            "automationEnabled": False,
            "publicPublicationEnabled": False,
        }
        if args.write_test_sheet:
            result["sheets"] = write_test_sheet(normalized)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, CandidateImportError) as exc:
        print(json.dumps({"status": "failed", "errorCode": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
