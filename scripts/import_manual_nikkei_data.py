#!/usr/bin/env python3
"""Validate manually supplied Nikkei official values and derive 25/200-session deviation.

No network source is contacted. Optional Sheets output is append-only and restricted
to the separately configured private test spreadsheet.
"""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    "nikkei225_per": ("倍", "manual_official_nikkei225_index_forecast_per"),
    "nikkei225_pbr": ("倍", "manual_official_nikkei225_index_pbr"),
    "nikkei225_eps": ("円", "manual_nikkei225_index_forecast_eps_derived"),
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

    rows: list[dict[str, Any]] = []
    values: dict[str, tuple[float, str]] = {}
    cash: float | None = None
    if payload.get("nikkei225Close") not in (None, ""):
        cash = _number(payload["nikkei225Close"], "nikkei225Close")
        if cash <= 0:
            raise ManualImportError("nikkei225Close must be positive")
        values["nikkei225_cash"] = (cash, "official Nikkei 225 cash close supplied manually")
    if payload.get("nikkeiViClose") not in (None, ""):
        vi = _number(payload["nikkeiViClose"], "nikkeiViClose")
        if not 0 <= vi <= 100:
            raise ManualImportError("nikkeiViClose is outside plausible validation bounds")
        values["nikkei_vi"] = (vi, "official Nikkei VI close supplied manually")

    history_present = payload.get("dailyCloseHistory") not in (None, "")
    if history_present:
        raw_history = payload["dailyCloseHistory"]
        if not isinstance(raw_history, list):
            raise ManualImportError("dailyCloseHistory must be an array")
        history_source_name = str(payload.get("dailyCloseHistorySourceName") or source_name).strip()
        history_source_url = _source_url(payload.get("dailyCloseHistorySourceUrl") or source_url, "dailyCloseHistorySourceUrl")
        if not history_source_name:
            raise ManualImportError("dailyCloseHistorySourceName is required when dailyCloseHistory is supplied")
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
        if len(history) < 200:
            raise ManualImportError("at least 200 dated closes are required to calculate both deviations")
        # The technical indicators belong to their own homogeneous daily-close
        # series. A different, higher precision official cash close may coexist
        # on the same date; it must not be silently substituted into this series.
        history_verified_with_cash = cash is not None and history[-1][1] == cash
        for window, symbol in ((25, "nikkei225_dev25"), (200, "nikkei225_dev200")):
            closes = [close for _, close in history[-window:]]
            sma = sum(closes) / window
            values[symbol] = ((history[-1][1] / sma - 1.0) * 100.0,
                              f"history close / SMA{window} - 1; {window} latest dated sessions including marketDate; history source={history_source_name}; final close cross-check={'matches' if history_verified_with_cash else 'differs from official close or is not supplied'}")

    valuation_keys = ("nikkei225ForecastPER", "nikkei225IndexPBR")
    valuation_present = [payload.get(key) not in (None, "") for key in valuation_keys]
    if any(valuation_present) and not all(valuation_present):
        raise ManualImportError("index-based PER and PBR must be supplied together")
    basis = str(payload.get("nikkei225ValuationBasis") or "")
    if all(valuation_present):
        if basis != "index_based":
            raise ManualImportError("nikkei225ValuationBasis must be index_based; weighted-average metrics are not interchangeable")
        if cash is None:
            raise ManualImportError("nikkei225Close is required to derive index-based forecast EPS")
        per = _number(payload[valuation_keys[0]], valuation_keys[0])
        pbr = _number(payload[valuation_keys[1]], valuation_keys[1])
        if per <= 0 or pbr <= 0:
            raise ManualImportError("index-based PER and PBR must be positive")
        try:
            close_decimal = Decimal(str(payload["nikkei225Close"]).replace(",", ""))
            per_decimal = Decimal(str(payload[valuation_keys[0]]).replace(",", ""))
            reported_eps_raw = payload.get("nikkei225ReportedForecastEPS")
            reported_eps_decimal = (
                Decimal(str(reported_eps_raw).replace(",", ""))
                if reported_eps_raw not in (None, "") else None
            )
        except (InvalidOperation, ValueError) as exc:
            raise ManualImportError("valuation inputs must be decimal numbers") from exc
        if reported_eps_decimal is not None and (not reported_eps_decimal.is_finite() or reported_eps_decimal <= 0):
            raise ManualImportError("source-reported forecast EPS must be finite and positive")
        implied_eps = close_decimal / per_decimal
        if reported_eps_decimal is not None:
            decimal_places = max(0, -reported_eps_decimal.as_tuple().exponent)
            quantum = Decimal(1).scaleb(-decimal_places)
            if implied_eps.quantize(quantum, rounding=ROUND_HALF_UP) != reported_eps_decimal.quantize(quantum, rounding=ROUND_HALF_UP):
                raise ManualImportError("close / index-based PER does not match source-reported forecast EPS at its published precision")
            eps_definition = f"derived from same-date official index close / index-based forecast PER; matches source-reported EPS at {decimal_places} decimal places"
        else:
            eps_definition = "derived from same-date official index close / index-based forecast PER; source does not separately publish comparable EPS"
        values["nikkei225_per"] = (per, "index-based forecast PER supplied manually")
        values["nikkei225_pbr"] = (pbr, "index-based PBR supplied manually")
        values["nikkei225_eps"] = (float(implied_eps), eps_definition)

    if not values:
        raise ManualImportError("at least one official Nikkei value or a complete daily history is required")

    for symbol, (value, definition) in values.items():
        unit, evidence = FIELDS[symbol]
        is_history_metric = symbol in {"nikkei225_dev25", "nikkei225_dev200"}
        if is_history_metric:
            item_source_name = str(payload.get("dailyCloseHistorySourceName") or source_name).strip()
            item_source_url = _source_url(payload.get("dailyCloseHistorySourceUrl") or source_url, "dailyCloseHistorySourceUrl")
        elif symbol == "nikkei_vi":
            item_source_name = str(payload.get("nikkeiViSourceName") or source_name).strip()
            item_source_url = _source_url(payload.get("nikkeiViSourceUrl") or source_url, "nikkeiViSourceUrl")
        else:
            item_source_name, item_source_url = source_name, source_url
        history_source_matches_official = (
            str(payload.get("dailyCloseHistorySourceName") or source_name).strip() == source_name
            and str(payload.get("dailyCloseHistorySourceUrl") or source_url).strip() == source_url
        )
        rows.append({
            "id": symbol,
            "value": value,
            "unit": unit,
            "marketDate": market_date.isoformat(),
            "sourceName": item_source_name,
            "sourceUrl": item_source_url,
            "sourceCapturedAt": captured_at.isoformat(),
            "evidenceStatus": "MANUAL_REVIEW",
            "evidenceType": evidence,
            "seriesDefinition": definition,
            "verificationEligibility": "manual_verified" if not is_history_metric or history_source_matches_official else "reference_only",
            "snapshotId": f"manual-nikkei-{symbol}-{market_date.isoformat()}",
        })
    return {"schemaVersion": "manual-nikkei-report-input-v1", "marketDate": market_date.isoformat(), "items": rows}


def manual_report_ready_rows(normalized: dict[str, Any], source_review_attested: bool) -> list[list[Any]]:
    if not source_review_attested:
        return []
    rows = []
    for item in normalized["items"]:
        status = "VERIFIED_MANUAL" if item.get("verificationEligibility") == "manual_verified" else "REFERENCE_ONLY"
        rows.append([
            item["snapshotId"], item["id"], item["value"], item["unit"],
            "index" if item["id"] in {"nikkei225_cash", "nikkei_vi"} else
            "valuation" if item["id"] in {"nikkei225_per", "nikkei225_pbr", "nikkei225_eps"} else "technical",
            "japan_cash", item["marketDate"], "", item["sourceName"],
            "Operator attested source date/value review; calculation validation passed"
            if status == "VERIFIED_MANUAL" else "Calculated from separate dated history source; independent full-history confirmation pending",
            status, item["sourceCapturedAt"],
        ])
    return rows


def write_private_test_sheet(normalized: dict[str, Any], source_review_attested: bool = False) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not credentials:
        raise ManualImportError("test spreadsheet or service-account setting is missing")
    if test_id == production_id:
        raise ManualImportError("refusing production spreadsheet")
    try:
        from scripts.import_tradingview_mcp_candidates import REPORT_READY_HEADERS, append_idempotent_sheet_rows
        from scripts.write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    except ModuleNotFoundError:
        from import_tradingview_mcp_candidates import REPORT_READY_HEADERS, append_idempotent_sheet_rows
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
    report_rows = manual_report_ready_rows(normalized, source_review_attested)
    report_result = append_idempotent_sheet_rows(
        client, "Personal_Report_Ready", REPORT_READY_HEADERS, report_rows, "L"
    )
    return {
        "status": "PASS", "sheet": tab, "items": len(values), "rowsAppended": len(pending),
        "readback": "verified", "evidenceStatus": "MANUAL_REVIEW",
        "manuallyVerifiedRows": report_result["rowsRequested"],
        "reportReadback": report_result["readback"], "productionWritten": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="manually prepared JSON including official source and daily closes")
    parser.add_argument("--output", type=Path, help="normalized personal-report feed JSON")
    parser.add_argument("--write-test-sheet", action="store_true", help="append to Manual_Nikkei_Review in the private test spreadsheet")
    parser.add_argument("--attest-source-reviewed", action="store_true", help="after personally checking the source date and value, also append rows as VERIFIED_MANUAL to Personal_Report_Ready; requires --write-test-sheet")
    args = parser.parse_args()
    try:
        if args.attest_source_reviewed and not args.write_test_sheet:
            raise ManualImportError("--attest-source-reviewed requires --write-test-sheet")
        data = json.loads(args.input.read_text(encoding="utf-8"))
        normalized = normalize_manual_data(data)
        if args.output:
            args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {"status": "PASS", "marketDate": normalized["marketDate"], "items": len(normalized["items"]), "evidenceStatus": "MANUAL_REVIEW", "sheets": None}
        if args.write_test_sheet:
            result["sheets"] = write_private_test_sheet(normalized, args.attest_source_reviewed)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, ManualImportError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "errorCode": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
