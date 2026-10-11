#!/usr/bin/env python3
"""Validate manually supplied Nikkei official values and derive 25/200-session deviation.

No network source is contacted. Optional Sheets output is append-only and restricted
to the separately configured private test spreadsheet.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


class ManualImportError(ValueError):
    pass


HEADERS = [
    "Snapshot ID", "Report Field", "Observed Value", "Unit", "Market Date",
    "Source Name", "Source URL", "Source Captured At", "Evidence Status",
    "Calculation Window", "Series Definition",
]
FIELDS = {
    "nikkei225_cash": ("円", "manual_official_index_close"),
    "nikkei_vi": ("pt", "manual_official_index_close"),
    "nikkei225_dev25": ("%", "manual_daily_close_sma_deviation"),
    "nikkei225_dev200": ("%", "manual_daily_close_sma_deviation"),
}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ManualImportError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ManualImportError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ManualImportError(f"{name} must be a finite number")
    return result


def _date(value: Any, name: str) -> dt.date:
    try:
        result = dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ManualImportError(f"{name} must be YYYY-MM-DD") from exc
    if result.weekday() >= 5:
        raise ManualImportError(f"{name} must be a Japan market weekday")
    return result


def _source_url(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("https://"):
        raise ManualImportError(f"{name} must be an https source URL")
    return text


def normalize_manual_data(payload: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ManualImportError("input must be an object")
    market_date = _date(payload.get("marketDate"), "marketDate")
    today = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone(dt.timedelta(hours=9))).date()
    if market_date > today:
        raise ManualImportError("marketDate cannot be in the future")

    source_name = str(payload.get("sourceName") or "").strip()
    if not source_name:
        raise ManualImportError("sourceName is required")
    source_url = _source_url(payload.get("sourceUrl"), "sourceUrl")
    captured_text = str(payload.get("sourceCapturedAt") or "")
    try:
        captured_at = dt.datetime.fromisoformat(captured_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManualImportError("sourceCapturedAt must be ISO-8601 with timezone") from exc
    if captured_at.tzinfo is None or captured_at.astimezone(dt.timezone.utc) > (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ManualImportError("sourceCapturedAt must be an aware, nonfuture timestamp")

    cash = _number(payload.get("nikkei225Close"), "nikkei225Close")
    vi = _number(payload.get("nikkeiViClose"), "nikkeiViClose")
    if cash <= 0 or not 0 <= vi <= 100:
        raise ManualImportError("manual index values are outside plausible validation bounds")
    raw_history = payload.get("dailyCloseHistory")
    if not isinstance(raw_history, list):
        raise ManualImportError("dailyCloseHistory must be an array")
    history: list[tuple[dt.date, float]] = []
    for index, entry in enumerate(raw_history):
        if not isinstance(entry, dict):
            raise ManualImportError(f"dailyCloseHistory[{index}] must be an object")
        date = _date(entry.get("date"), f"dailyCloseHistory[{index}].date")
        close = _number(entry.get("close"), f"dailyCloseHistory[{index}].close")
        if close <= 0:
            raise ManualImportError("daily closes must be positive")
        history.append((date, close))
    if len({date for date, _ in history}) != len(history):
        raise ManualImportError("dailyCloseHistory contains duplicate dates")
    history.sort(key=lambda item: item[0])
    if not history or history[-1][0] != market_date:
        raise ManualImportError("dailyCloseHistory must end on marketDate")
    if history[-1][1] != cash:
        raise ManualImportError("dailyCloseHistory final close must exactly match nikkei225Close")
    if len(history) < 200:
        raise ManualImportError("at least 200 dated closes are required to calculate both deviations")

    rows: list[dict[str, Any]] = []
    values = {
        "nikkei225_cash": (cash, "official value supplied manually"),
        "nikkei_vi": (vi, "official value supplied manually"),
    }
    for window, symbol in ((25, "nikkei225_dev25"), (200, "nikkei225_dev200")):
        closes = [close for _, close in history[-window:]]
        sma = sum(closes) / window
        values[symbol] = ((cash / sma - 1.0) * 100.0, f"close / SMA{window} - 1; {window} latest dated sessions including marketDate")

    for symbol, (value, definition) in values.items():
        unit, evidence = FIELDS[symbol]
        rows.append({
            "id": symbol,
            "value": value,
            "unit": unit,
            "marketDate": market_date.isoformat(),
            "sourceName": source_name,
            "sourceUrl": source_url,
            "sourceCapturedAt": captured_at.isoformat(),
            "evidenceStatus": "MANUAL_REVIEW",
            "evidenceType": evidence,
            "seriesDefinition": definition,
            "snapshotId": f"manual-nikkei-{symbol}-{market_date.isoformat()}",
        })
    return {"schemaVersion": "manual-nikkei-report-input-v1", "marketDate": market_date.isoformat(), "items": rows}


def write_private_test_sheet(normalized: dict[str, Any]) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not credentials:
        raise ManualImportError("test spreadsheet or service-account setting is missing")
    if test_id == production_id:
        raise ManualImportError("refusing production spreadsheet")
    try:
        from scripts.write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    except ModuleNotFoundError:
        from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    client = SheetsClient(create_authorized_session(load_service_account_info(credentials)), test_id)
    tab = "Manual_Nikkei_Review"
    client.ensure_sheets([tab])
    prior = client.get_values(tab, "A1:K1000")
    if not prior or not prior[0] or not prior[0][0]:
        client.update(tab, "A1", [HEADERS])
        prior = [HEADERS]
    elif prior[0][:len(HEADERS)] != HEADERS:
        raise ManualImportError("manual Nikkei tab header mismatch; refusing to write")
    old = {str(row[0]): row for row in prior[1:] if row and row[0]}
    values = [[
        item["snapshotId"], item["id"], item["value"], item["unit"], item["marketDate"],
        item["sourceName"], item["sourceUrl"], item["sourceCapturedAt"], item["evidenceStatus"],
        item["seriesDefinition"].split(";")[0] if item["id"].endswith(("dev25", "dev200")) else "",
        item["seriesDefinition"],
    ] for item in normalized["items"]]
    pending = []
    for row in values:
        existing = old.get(str(row[0]))
        if existing:
            padded = list(existing[:len(HEADERS)]) + [""] * max(0, len(HEADERS)-len(existing))
            if padded != row:
                raise ManualImportError("manual snapshot already exists with different data")
        else:
            pending.append(row)
    if pending:
        client.append(tab, "A:K", pending)
    actual = client.get_values(tab, "A1:K1000")
    rows = [row for row in actual[1:] if row and row[0]] if actual else []
    for expected in values:
        matches = [row for row in rows if str(row[0]) == str(expected[0])]
        if len(matches) != 1 or list(matches[0][:len(HEADERS)]) + [""] * max(0, len(HEADERS)-len(matches[0])) != expected:
            raise ManualImportError("manual Nikkei readback or duplicate check failed")
    return {"status": "PASS", "sheet": tab, "items": len(values), "rowsAppended": len(pending), "readback": "verified", "evidenceStatus": "MANUAL_REVIEW", "productionWritten": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="manually prepared JSON including official source and daily closes")
    parser.add_argument("--output", type=Path, help="normalized personal-report feed JSON")
    parser.add_argument("--write-test-sheet", action="store_true", help="append to Manual_Nikkei_Review in the private test spreadsheet")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        normalized = normalize_manual_data(data)
        if args.output:
            args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {"status": "PASS", "marketDate": normalized["marketDate"], "items": 4, "evidenceStatus": "MANUAL_REVIEW", "sheets": None}
        if args.write_test_sheet:
            result["sheets"] = write_private_test_sheet(normalized)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, ManualImportError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "errorCode": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
