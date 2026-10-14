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
import json
import math
import os
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

try:
    from scripts.verify_tradingview_close import verify_close_evidence
except ModuleNotFoundError:
    from verify_tradingview_close import verify_close_evidence

ROOT = Path(__file__).resolve().parents[1]
TEST_SHEET = "TradingView_MCP_Candidates"
REPORT_READY_SHEET = "Personal_Report_Ready"
REFERENCE_SHEET = "Personal_Reference_Values"
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
    "Source Market Date",
    "Source",
    "Review Status",
]
REPORT_READY_HEADERS = [
    "Snapshot ID",
    "Report Field",
    "Observed Value",
    "Unit",
    "Market Type",
    "Market Session",
    "Source Market Date",
    "Bar Anchor (UTC)",
    "Source",
    "Review Basis",
    "Status",
    "Retrieved At (UTC)",
]
REFERENCE_HEADERS = [
    "Snapshot ID", "Report Field", "Observed Value", "Unit", "TradingView Symbol",
    "Reference Type", "Market Session", "Source Market Date", "Bar Anchor (UTC)",
    "Source", "Use Status", "Settlement Evidence", "Retrieved At (UTC)",
]
FUTURES_REFERENCE_FIELDS = {
    "gold", "wti", "nikkei225_futures_ose", "cme_nikkei225_jpy", "cme_nikkei225_usd"
}

# The explicit symbol/unit/session contract prevents a plausible-looking but
# different instrument from being silently relabelled as a report field.
FIELD_CONTRACT: dict[str, dict[str, str]] = {
    "dow": {"symbol": "DJ:DJI", "unit": "pt", "marketType": "index", "session": "us_cash", "marketTimezone": "America/New_York"},
    "nasdaq": {"symbol": "NASDAQ:IXIC", "unit": "pt", "marketType": "index", "session": "us_cash", "marketTimezone": "America/New_York"},
    "sp500": {"symbol": "SP:SPX", "unit": "pt", "marketType": "index", "session": "us_cash", "marketTimezone": "America/New_York"},
    "russell2000": {"symbol": "CBOEFTSE:RUT", "unit": "pt", "marketType": "index", "session": "us_cash", "marketTimezone": "America/New_York"},
    "nikkei225_cash": {"symbol": "TVC:NI225", "unit": "円", "marketType": "index", "session": "japan_cash", "marketTimezone": "Asia/Tokyo"},
    "gold": {"symbol": "COMEX:GC1!", "unit": "USD/oz", "marketType": "continuous_futures", "session": "comex", "marketTimezone": "America/Chicago"},
    "wti": {"symbol": "NYMEX:CL1!", "unit": "USD/bbl", "marketType": "continuous_futures", "session": "nymex", "marketTimezone": "America/Chicago"},
    "nikkei225_futures_ose": {"symbol": "OSE:NK2251!", "unit": "円", "marketType": "futures_ose", "session": "ose", "marketTimezone": "Asia/Tokyo"},
    "cme_nikkei225_jpy": {"symbol": "CME:NIY1!", "unit": "円", "marketType": "futures_cme", "session": "cme", "marketTimezone": "America/Chicago"},
    "cme_nikkei225_usd": {"symbol": "CME:NKD1!", "unit": "USD", "marketType": "futures_cme", "session": "cme", "marketTimezone": "America/Chicago"},
    "usdjpy": {"symbol": "FX:USDJPY", "unit": "JPY per USD", "marketType": "spot", "session": "forex_daily", "marketTimezone": "America/New_York"},
    "eurusd": {"symbol": "FX:EURUSD", "unit": "USD per EUR", "marketType": "spot", "session": "forex_daily", "marketTimezone": "America/New_York"},
    "btcusd": {"symbol": "BITSTAMP:BTCUSD", "unit": "USD", "marketType": "spot", "session": "utc_daily", "marketTimezone": "UTC"},
    "vix": {"symbol": "CBOE:VIX", "unit": "pt", "marketType": "index", "session": "us_volatility", "marketTimezone": "America/New_York"},
    "nikkei_vi": {"symbol": "TOCOM:NVI", "unit": "pt", "marketType": "index", "session": "japan_cash", "marketTimezone": "Asia/Tokyo"},
    "jp10y": {"symbol": "TVC:JP10Y", "unit": "%", "marketType": "bond_yield", "session": "japan_yield", "marketTimezone": "Asia/Tokyo"},
    "us10y": {"symbol": "TVC:US10Y", "unit": "%", "marketType": "bond_yield", "session": "us_yield", "marketTimezone": "America/New_York"},
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
    parsed_anchor = parse_aware_datetime(anchor, "barAnchorUtc")
    return f"tv-mcp-{item_id}-{parsed_anchor.strftime('%Y%m%d%H%M%S')}"


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
        market_today = retrieved.astimezone(ZoneInfo(contract["marketTimezone"])).date()
        if market_date > market_today:
            raise CandidateImportError(f"{item_id} market date is later than retrieval date in its market timezone")
        value = finite_number(item.get("value"), f"{item_id}.value")
        candidate = {
            "id": item_id,
            "symbol": contract["symbol"],
            "value": value,
            "unit": contract["unit"],
            "marketType": contract["marketType"],
            "session": contract["session"],
            "marketTimezone": contract["marketTimezone"],
            "interval": "1D",
            "barAnchorUtc": anchor.isoformat().replace("+00:00", "Z"),
            "marketDate": market_date.isoformat(),
            "snapshotId": snapshot_id(item_id, contract["symbol"], anchor.isoformat()),
            "source": "TradingView official MCP",
        }
        review = verify_close_evidence(candidate, item.get("closeValidation"))
        candidate["reviewStatus"] = review["status"]
        candidate["reviewBasis"] = review["basis"]
        candidates.append(candidate)

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


def new_sheet_rows(rows: list[list[Any]], existing_ids: set[str]) -> list[list[Any]]:
    """Return only rows whose stable snapshot identity is not already stored."""
    return [row for row in rows if str(row[0]) not in existing_ids]


def verified_report_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Select only evidence-reviewed closes; other candidates never block these rows."""
    return [item for item in payload.get("candidates", []) if item.get("reviewStatus") == "VERIFIED"]


def report_ready_rows(payload: dict[str, Any]) -> list[list[Any]]:
    """Build a separate personal-report feed while retaining source and session lineage."""
    return [
        [
            item["snapshotId"], item["id"], item["value"], item["unit"],
            item["marketType"], item["session"], item["marketDate"],
            item["barAnchorUtc"], item["source"], item["reviewBasis"],
            "VERIFIED", payload["retrievedAt"],
        ]
        for item in verified_report_candidates(payload)
    ]


def reference_futures_rows(payload: dict[str, Any]) -> list[list[Any]]:
    """Expose continuous futures bars separately; never label them settlement prices."""
    rows = []
    for item in payload.get("candidates", []):
        if item.get("id") not in FUTURES_REFERENCE_FIELDS:
            continue
        market_type = item.get("marketType")
        if market_type == "continuous_futures":
            reference_type = "CONTINUOUS_FUTURES_BAR_CLOSE"
        elif market_type in {"futures_ose", "futures_cme"}:
            reference_type = "CONTINUOUS_FRONT_MONTH_BAR_CLOSE"
        else:
            continue
        rows.append([
            item["snapshotId"], item["id"], item["value"], item["unit"],
            item["symbol"], reference_type, item["session"], item["marketDate"],
            item["barAnchorUtc"], item["source"], "REFERENCE_ONLY",
            "NOT_CONFIRMED; daily bar close is not an exchange settlement", payload["retrievedAt"],
        ])
    return rows


def append_idempotent_sheet_rows(
    client: Any, sheet_name: str, headers: list[str], rows: list[list[Any]], width: str
) -> dict[str, Any]:
    """Append immutable snapshot rows to a dedicated tab and verify exact readback."""
    if not rows:
        return {"rowsRequested": 0, "rowsAppended": 0, "readback": "not_needed"}
    client.ensure_sheets([sheet_name])
    prior = client.get_values(sheet_name, f"A1:{width}1000")
    if not prior or not prior[0] or not prior[0][0]:
        client.update(sheet_name, "A1", [headers])
        prior = [headers]
    elif prior[0][:len(headers)] != headers:
        raise CandidateImportError(f"{sheet_name} tab has an unexpected header; refusing to alter it")

    existing_by_id = {str(row[0]): row for row in prior[1:] if row and row[0]}
    for expected in rows:
        key = str(expected[0])
        if key in existing_by_id:
            existing = list(existing_by_id[key][:len(headers)]) + [""] * max(0, len(headers) - len(existing_by_id[key]))
            if existing != expected:
                raise CandidateImportError(f"{sheet_name} snapshot identity already exists with different data")
    pending = new_sheet_rows(rows, set(existing_by_id))
    if pending:
        client.append(sheet_name, f"A:{width}", pending)

    readback = client.get_values(sheet_name, f"A1:{width}1000")
    actual_rows = [row for row in readback[1:] if row and row[0]] if readback else []
    counts: dict[str, int] = {}
    actual_by_id: dict[str, list[Any]] = {}
    for row in actual_rows:
        key = str(row[0])
        counts[key] = counts.get(key, 0) + 1
        actual_by_id[key] = row
    for expected in rows:
        key = str(expected[0])
        actual = actual_by_id.get(key, [])
        normalized = list(actual[:len(headers)]) + [""] * max(0, len(headers) - len(actual))
        if counts.get(key) != 1 or normalized != expected:
            raise CandidateImportError(f"{sheet_name} readback identity/value/duplicate check failed")
    return {"rowsRequested": len(rows), "rowsAppended": len(pending), "readback": "verified"}


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
    candidate_result = append_idempotent_sheet_rows(
        client, TEST_SHEET, HEADERS, sheet_rows(payload), "M"
    )
    verified_rows = report_ready_rows(payload)
    report_result = append_idempotent_sheet_rows(
        client, REPORT_READY_SHEET, REPORT_READY_HEADERS, verified_rows, "L"
    )
    reference_rows = reference_futures_rows(payload)
    reference_result = append_idempotent_sheet_rows(
        client, REFERENCE_SHEET, REFERENCE_HEADERS, reference_rows, "M"
    )
    return {
        "sheet": TEST_SHEET,
        "candidateRows": candidate_result["rowsRequested"],
        "candidateRowsAppended": candidate_result["rowsAppended"],
        "candidateReadback": candidate_result["readback"],
        "reportReadySheet": REPORT_READY_SHEET,
        "reportUsableRows": report_result["rowsRequested"],
        "reportRowsAppended": report_result["rowsAppended"],
        "reportReadback": report_result["readback"],
        "reportUsableFieldCount": len(verified_rows),
        "referenceValuesSheet": REFERENCE_SHEET,
        "referenceFuturesCount": len(reference_rows),
        "referenceRowsAppended": reference_result["rowsAppended"],
        "referenceReadback": reference_result["readback"],
        "duplicatePrevention": "verified",
        "productionSpreadsheetWritten": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON exported from the manual TradingView MCP read")
    parser.add_argument("--output", type=Path, help="normalized candidate JSON output")
    parser.add_argument("--report-output", type=Path, help="write only VERIFIED rows as a private report-ready JSON feed")
    parser.add_argument("--write-test-sheet", action="store_true", help="append to a dedicated private test tab; never writes production")
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
        normalized = normalize_snapshot(snapshot)
        if args.output:
            args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.report_output:
            ready = verified_report_candidates(normalized)
            feed = {
                "schemaVersion": "personal-market-report-input-v1",
                "generatedAt": normalized["retrievedAt"],
                "status": "PARTIAL_VERIFIED" if ready else "NO_VERIFIED_FIELDS",
                "verifiedFieldCount": len(ready),
                "items": ready,
                "automationEnabled": False,
                "publicPublicationEnabled": False,
            }
            args.report_output.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result: dict[str, Any] = {
            "candidateCount": normalized["candidateCount"],
            "verifiedReportFieldCount": len(verified_report_candidates(normalized)),
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
