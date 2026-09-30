#!/usr/bin/env python3
"""Idempotently persist verified prior-session values to 終値一覧.

This runs after the market snapshot and its CSV exports have been pushed to
GitHub. It verifies the two IMPORTDATA-backed tabs, upserts one date row using
the live header names, reads the row back, and appends an audit entry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from write_market_data_to_sheets import (  # noqa: E402
    SheetsClient,
    SheetsSyncError,
    create_authorized_session,
    load_service_account_info,
)

ROOT = SCRIPT_DIR.parent
JST = dt.timezone(dt.timedelta(hours=9))
DEFAULT_SPREADSHEET_ID = "1n2ACInX4pmK0TdijC8xaur2RIiNZyVa6GFTZAyofcuE"
VALUE_RETRY_DELAYS = (5, 15)
IMPORT_RETRY_DELAYS = (5, 15)
MAX_STALE_DAYS = 10
PRICE_FIELDS: dict[str, tuple[str, str, str]] = {
    "dow": ("Dow終値", "Dow前日比", "Dow騰落率"),
    "nasdaq": ("Nasdaq終値", "Nasdaq前日比", "Nasdaq騰落率"),
    "sp500": ("S&P500終値", "S&P500前日比", "S&P500騰落率"),
    "russell2000": ("Russell 2000終値", "Russell 2000前日比", "Russell 2000騰落率"),
    "nikkei225": ("日経225終値", "日経225前日比", "日経225騰落率"),
    "nikkei225_futures_ose": ("日経225先物大阪終値", "日経225先物大阪前日比", "日経225先物大阪騰落率"),
    "usdjpy": ("USDJPY終値", "USDJPY前日比", "USDJPY騰落率"),
    "eurusd": ("EURUSD終値", "EURUSD前日比", "EURUSD騰落率"),
    "gold": ("ゴールド終値", "ゴールド前日比", "ゴールド騰落率"),
    "wti": ("WTI原油終値", "WTI原油前日比", "WTI原油騰落率"),
    "btcusd": ("BTCUSD終値", "BTCUSD前日比", "BTCUSD騰落率"),
    "vix": ("VIX終値", "VIX前日比", "VIX騰落率"),
    "nikkei_vi": ("日経VI終値", "日経VI前日比", "日経VI騰落率"),
    "fear_greed": ("FearGreed終値", "FearGreed前日比", ""),
}
REQUIRED_CLOSE_HEADERS = (
    "Dow終値", "Nasdaq終値", "S&P500終値", "Russell 2000終値", "日経225終値",
    "日経225先物大阪終値", "USDJPY終値", "EURUSD終値", "ゴールド終値",
    "WTI原油終値", "BTCUSD終値", "VIX終値", "日経VI終値", "FearGreed終値",
    "米10年債利回り", "日本10年債利回り", "日経225予想EPS", "日経225予想PER",
)
INPUT_HEADERS = ("スナップショットID", "更新日時", "対象レポート時刻", "全体状態", "銘柄ID", "データ名", "利用判定", "現在値")
LOG_HEADERS = ("updated_at", "sheet_name", "action", "data_as_of", "records", "status", "source", "note")


class CloseSyncError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(str(value).strip().replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_datetime(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def parse_sheet_date(value: Any) -> dt.date | None:
    if isinstance(value, (int, float)):
        # Google Sheets serial dates use 1899-12-30 as day zero.
        return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(value))).date()
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d %H:%M"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def resolve_target_date(payload: dict[str, Any], now: dt.datetime) -> dt.date:
    markets = payload.get("markets") or {}
    anchor_dates: list[dt.date] = []
    for symbol in ("vix", "nikkei_vi"):
        market = markets.get(symbol) or {}
        if market.get("verificationStatus") not in {"verified", "fallback"}:
            continue
        observed = parse_datetime(market.get("asOf"))
        if observed:
            anchor_dates.append(observed.date())
    if not anchor_dates:
        raise CloseSyncError("VALIDATE", "No verified VIX or Nikkei VI session date is available.")

    target = max(anchor_dates)
    today = now.astimezone(JST).date()
    if target >= today:
        raise CloseSyncError("VALIDATE", f"Market close date {target.isoformat()} is not before today {today.isoformat()}.")
    if (today - target).days > MAX_STALE_DAYS:
        raise CloseSyncError("VALIDATE", f"Market close date {target.isoformat()} is more than {MAX_STALE_DAYS} days old.")
    return target


def letter_for_column(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def is_transient_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("429", "500", "502", "503", "504", "timeout", "timed out", "connection", "temporarily unavailable"))


def retry(operation: Callable[[], Any], sleep: Callable[[float], None] = time.sleep) -> Any:
    for delay in (0, *VALUE_RETRY_DELAYS):
        if delay:
            sleep(delay)
        try:
            return operation()
        except Exception as exc:
            if delay == VALUE_RETRY_DELAYS[-1] or not is_transient_error(exc):
                raise
    raise AssertionError("unreachable")


def read_values(client: SheetsClient, sheet: str, cells: str, option: str = "FORMATTED_VALUE") -> list[list[Any]]:
    url = client.base_url + "/values/" + client._range(sheet, cells) + "?" + urlencode({"valueRenderOption": option})
    return retry(lambda: client._request("GET", url).get("values") or [])


def read_many_columns(client: SheetsClient, sheet: str, headers: list[str], header_indices: dict[str, int]) -> dict[str, list[Any]]:
    wanted = ["日付"] + [name for name in headers if name in header_indices]
    ranges = [client._range(sheet, f"{letter_for_column(header_indices[name])}:{letter_for_column(header_indices[name])}") for name in wanted]
    query: list[tuple[str, str]] = [("valueRenderOption", "FORMATTED_VALUE")]
    query.extend(("ranges", value) for value in ranges)
    response = retry(lambda: client._request("GET", client.base_url + "/values:batchGet?" + urlencode(query)))
    result: dict[str, list[Any]] = {}
    for name, item in zip(wanted, response.get("valueRanges") or []):
        result[name] = [row[0] if row else "" for row in (item.get("values") or [])]
    return result


def close_value_for_market(market: dict[str, Any], target: dt.date) -> tuple[float | None, str, str]:
    status = str(market.get("verificationStatus") or "")
    if status not in {"verified", "fallback"}:
        return None, "", f"status={status or 'missing'}"
    observed = parse_datetime(market.get("asOf"))
    if not observed:
        return None, "", "asOf missing or invalid"
    value = number(market.get("value"))
    previous = number(market.get("previousClose"))
    if value is None:
        return None, observed.date().isoformat(), "value is not numeric"
    if observed.date() == target:
        return value, observed.date().isoformat(), "fallback" if status == "fallback" else ""
    if observed.date() == target + dt.timedelta(days=1) and previous is not None:
        # At 06:30 JST a continuous/overnight quote may already have rolled to
        # the next market date. In that case previousClose is the target date.
        return previous, observed.date().isoformat(), ""
    return None, observed.date().isoformat(), f"asOf date {observed.date().isoformat()} does not match {target.isoformat()}"


def prior_numeric_value(column_values: list[Any], dates: list[Any], target: dt.date) -> float | None:
    candidates: list[tuple[dt.date, int]] = []
    for row_index, raw_date in enumerate(dates[1:], start=2):
        parsed = parse_sheet_date(raw_date)
        if parsed and parsed < target:
            candidates.append((parsed, row_index))
    if not candidates:
        return None
    _, row_number = max(candidates, key=lambda item: item[0])
    if row_number - 1 >= len(column_values):
        return None
    return number(column_values[row_number - 1])


def validate_change(market: dict[str, Any], close_value: float) -> tuple[float | None, float | None, str]:
    previous = number(market.get("previousClose"))
    if previous is None or previous == 0:
        return None, None, "previous close missing"
    computed_change = close_value - previous
    supplied_change = number(market.get("change"))
    if supplied_change is not None and abs(supplied_change - computed_change) > max(0.02, abs(computed_change) * 0.01):
        return None, None, "difference_detected: change does not match close minus previousClose"
    computed_percent_points = computed_change / previous * 100
    supplied_percent = number(market.get("changePercent"))
    if supplied_percent is not None and abs(supplied_percent - computed_percent_points) > 0.1:
        return None, None, "difference_detected: changePercent does not match calculation"
    return computed_change, computed_percent_points / 100, ""


def batch_write_values(client: SheetsClient, sheet: str, row: int, updates: dict[int, Any], sleep: Callable[[float], None] = time.sleep) -> None:
    data = []
    for col_index, value in sorted(updates.items()):
        col = letter_for_column(col_index)
        data.append({"range": client._range(sheet, f"{col}{row}"), "values": [[value]]})
    if not data:
        return
    retry(lambda: client._request(
        "POST",
        client.base_url + "/values:batchUpdate",
        json={"valueInputOption": "USER_ENTERED", "data": data},
    ), sleep)


def insert_formatted_row(client: SheetsClient, sheet_id: int, row: int, column_count: int, sheet: str, sleep: Callable[[float], None] = time.sleep) -> set[int]:
    # Insert within the chronological table. Copy the adjacent row's formats,
    # then copy only its formula cells so literal price columns stay untouched.
    source_row = 3 if row == 2 else row - 1
    requests = [{"insertDimension": {
        "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": row - 1, "endIndex": row},
        "inheritFromBefore": False,
    }}]
    source_start = source_row - 1
    destination_start = row - 1
    requests.append({"copyPaste": {
        "source": {"sheetId": sheet_id, "startRowIndex": source_start, "endRowIndex": source_start + 1, "startColumnIndex": 0, "endColumnIndex": column_count},
        "destination": {"sheetId": sheet_id, "startRowIndex": destination_start, "endRowIndex": destination_start + 1, "startColumnIndex": 0, "endColumnIndex": column_count},
        "pasteType": "PASTE_FORMAT", "pasteOrientation": "NORMAL",
    }})
    formula_row = read_values(client, sheet, f"A{source_row}:{letter_for_column(column_count - 1)}{source_row}", "FORMULA")
    formulas = formula_row[0] if formula_row else []
    formula_columns = {i for i, value in enumerate(formulas) if isinstance(value, str) and value.startswith("=")}
    start: int | None = None
    for i in range(column_count + 1):
        if i < column_count and i in formula_columns:
            if start is None:
                start = i
            continue
        if start is not None:
            requests.append({"copyPaste": {
                "source": {"sheetId": sheet_id, "startRowIndex": source_start, "endRowIndex": source_start + 1, "startColumnIndex": start, "endColumnIndex": i},
                "destination": {"sheetId": sheet_id, "startRowIndex": destination_start, "endRowIndex": destination_start + 1, "startColumnIndex": start, "endColumnIndex": i},
                "pasteType": "PASTE_FORMULA", "pasteOrientation": "NORMAL",
            }})
            start = None
    retry(lambda: client._request("POST", client.base_url + ":batchUpdate", json={"requests": requests}), sleep)
    return formula_columns


def find_target_row(date_values: list[Any], target: dt.date) -> tuple[int | None, int]:
    matches: list[int] = []
    rows: list[tuple[int, dt.date]] = []
    for row, value in enumerate(date_values[1:], start=2):
        parsed = parse_sheet_date(value)
        if not parsed:
            continue
        rows.append((row, parsed))
        if parsed == target:
            matches.append(row)
    if len(matches) > 1:
        raise CloseSyncError("VALIDATE", f"Duplicate date rows already exist for {target.isoformat()}: {matches}")
    if matches:
        return matches[0], max((r for r, _ in rows), default=1)
    older_rows = [row for row, parsed in rows if parsed < target]
    if older_rows:
        return None, min(older_rows)
    last_row = max((row for row, _ in rows), default=1)
    return None, last_row + 1


def normalized_value(value: Any) -> float | str | None:
    parsed = number(value)
    return parsed if parsed is not None else (str(value).strip() if value is not None else None)


def close_row_sync(
    client: SheetsClient,
    payload: dict[str, Any],
    now: dt.datetime,
    *,
    scheduled_time: str = "06:30",
    run_key: str = "manual",
    sleep: Callable[[float], None] = time.sleep,
    verify_import_tabs: bool = True,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "FAILED", "generatedAt": payload.get("generatedAt"), "targetDate": None,
        "row": None, "inserted": False, "failedStage": "FETCH",
        "stages": {"FETCH": "PENDING", "VALIDATE": "PENDING", "GITHUB_SAVE": "SUCCESS", "SHEETS_IMPORT": "PENDING", "CHATGPT_INPUT": "PENDING", "CLOSE_DATA_WRITE": "PENDING", "READBACK_VERIFY": "PENDING", "LOG": "PENDING"},
        "missingRequiredFields": [], "updatedFields": [], "sources": [], "marketData": [], "errors": [],
    }
    try:
        generated = parse_datetime(payload.get("generatedAt"))
        now_jst = now.astimezone(JST)
        if payload.get("reportSlot") != "08:00":
            raise CloseSyncError("VALIDATE", "Only the 08:00 morning acquisition can update the prior-close table.")
        if not generated or generated.date() != now_jst.date() or (now_jst - generated).total_seconds() > 3 * 60 * 60:
            raise CloseSyncError("VALIDATE", "Market snapshot is missing, from another JST date, or older than three hours.")
        target = resolve_target_date(payload, now_jst)
        summary["generatedAt"] = generated.isoformat()
        summary["targetDate"] = target.isoformat()
        summary["stages"]["FETCH"] = "SUCCESS"
        summary["stages"]["VALIDATE"] = "SUCCESS"

        sheet_map = retry(client.sheet_map)
        for required_sheet in ("終値一覧", "GitHub_Market_Import", "ChatGPT_Market_Input", "WEB_Data_Update_Log"):
            if required_sheet not in sheet_map:
                raise CloseSyncError("VALIDATE", f"Required sheet is missing: {required_sheet}")

        import_errors: list[str] = []
        if verify_import_tabs:
            for sheet_name, stage in (("GitHub_Market_Import", "SHEETS_IMPORT"), ("ChatGPT_Market_Input", "CHATGPT_INPUT")):
                ok = False
                last_error = "snapshot rows do not match"
                for attempt, delay in enumerate((0, *IMPORT_RETRY_DELAYS)):
                    if delay:
                        sleep(delay)
                    try:
                        rows = read_values(client, sheet_name, "A1:H100", "UNFORMATTED_VALUE")
                        ok, last_error = verify_input_rows(rows, payload)
                    except Exception as exc:
                        last_error = str(exc)
                        ok = False
                    if ok:
                        break
                summary["stages"][stage] = "SUCCESS" if ok else "FAILED"
                if not ok:
                    import_errors.append(f"{sheet_name}: {last_error}")
        else:
            summary["stages"]["SHEETS_IMPORT"] = "SKIPPED"
            summary["stages"]["CHATGPT_INPUT"] = "SKIPPED"

        sheet_name = "終値一覧"
        header_rows = read_values(client, sheet_name, "A1:GF1", "FORMATTED_VALUE")
        headers = [str(value or "").strip() for value in (header_rows[0] if header_rows else [])]
        if not headers or "日付" not in headers:
            raise CloseSyncError("VALIDATE", "終値一覧 header row or 日付 header is missing.")
        header_indices = {name: i for i, name in enumerate(headers) if name}
        column_values = read_many_columns(client, sheet_name, list({h for trio in PRICE_FIELDS.values() for h in trio if h} | {"日付"}), header_indices)
        date_values = column_values.get("日付", [])
        target_row, insert_row = find_target_row(date_values, target)
        duplicate_count = sum(1 for value in date_values[1:] if parse_sheet_date(value) == target)
        if duplicate_count > 1:
            raise CloseSyncError("VALIDATE", f"Duplicate date rows already exist for {target.isoformat()}.")
        inserting = target_row is None
        if inserting:
            target_row = insert_row

        # Resolve previous close from the most recent earlier date already in
        # the master sheet. This is needed when an overnight feed has rolled
        # into the next JST date and exposes the target close as previousClose.
        writes: dict[str, Any] = {"日付": target.strftime("%Y/%m/%d")}
        source_ids: list[str] = []
        field_warnings: list[str] = []
        statuses = []
        markets = payload.get("markets") or {}
        for symbol, (close_header, change_header, percent_header) in PRICE_FIELDS.items():
            market = markets.get(symbol)
            if not isinstance(market, dict):
                continue
            close_value, source_date, warning = close_value_for_market(market, target)
            if close_value is None:
                if warning:
                    field_warnings.append(f"{symbol}: {warning}")
                continue
            if warning:
                field_warnings.append(f"{symbol}: {warning}")
            source_ids.append(str(market.get("sourceId") or symbol))
            writes[close_header] = close_value
            observed = parse_datetime(market.get("asOf"))
            summary["marketData"].append({
                "symbol": symbol,
                "sourceId": market.get("sourceId"),
                "sourceName": market.get("sourceName"),
                "asOf": market.get("asOf"),
                "fetchedAt": market.get("fetchedAt"),
                "verifiedAt": market.get("verifiedAt") or market.get("verifiedAtUtc") or "",
                "verificationStatus": market.get("verificationStatus"),
                "valueSource": "value" if observed and observed.date() == target else "previousClose",
                "closeValue": close_value,
            })
            if change_header:
                change_value: float | None = None
                percent_value: float | None = None
                if source_date == target.isoformat():
                    change_value, percent_value, warning = validate_change(market, close_value)
                else:
                    previous = prior_numeric_value(column_values.get(close_header, []), date_values, target)
                    if previous is not None and previous != 0:
                        change_value = close_value - previous
                        percent_value = change_value / previous
                    else:
                        warning = "prior table close unavailable for change calculation"
                if warning:
                    field_warnings.append(f"{symbol}: {warning}")
                if change_value is not None:
                    writes[change_header] = change_value
                if percent_header and percent_value is not None:
                    writes[percent_header] = percent_value
            if symbol == "fear_greed" and source_date == target.isoformat() and str(market.get("classification") or "").strip():
                writes["FearGreed判定"] = str(market.get("classification")).strip()

        # Existing rows from another trusted updater are retained. Missing
        # new data never overwrites a same-date verified value with a guess.
        registration = now_jst.strftime("%Y/%m/%d %H:%M JST") + f" ({scheduled_time} scheduled)"
        if "登録日時" in header_indices:
            writes["登録日時"] = registration
        for header, value in (("USDJPY価格取得元", (markets.get("usdjpy") or {}).get("sourceName") or (markets.get("usdjpy") or {}).get("sourceId")),
                              ("USDJPY価格取得日時", (markets.get("usdjpy") or {}).get("asOf"))):
            if header in header_indices and value:
                writes[header] = str(value)

        if inserting:
            formula_columns = insert_formatted_row(client, sheet_map[sheet_name], target_row, len(headers), sheet_name, sleep)
        else:
            formulas = read_values(client, sheet_name, f"A{target_row}:{letter_for_column(len(headers)-1)}{target_row}", "FORMULA")
            formula_columns = {i for i, value in enumerate(formulas[0] if formulas else []) if isinstance(value, str) and value.startswith("=")}

        updates = {header_indices[name]: value for name, value in writes.items() if name in header_indices and header_indices[name] not in formula_columns}
        batch_write_values(client, sheet_name, target_row, updates, sleep)
        summary["stages"]["CLOSE_DATA_WRITE"] = "SUCCESS"
        summary["row"] = target_row
        summary["inserted"] = inserting
        summary["updatedFields"] = [name for name in writes if name in header_indices and header_indices[name] not in formula_columns]
        summary["sources"] = sorted(set(source_ids))

        readback = read_values(client, sheet_name, f"A{target_row}:{letter_for_column(len(headers)-1)}{target_row}", "UNFORMATTED_VALUE")
        actual_row = readback[0] if readback else []
        actual_date = parse_sheet_date(actual_row[header_indices["日付"]] if len(actual_row) > header_indices["日付"] else "")
        if actual_date != target:
            raise CloseSyncError("READBACK_VERIFY", f"Date readback mismatch: expected {target}, got {actual_date}.")
        mismatches = []
        for name, expected in writes.items():
            if name not in header_indices or header_indices[name] in formula_columns:
                continue
            index = header_indices[name]
            actual = actual_row[index] if index < len(actual_row) else ""
            expected_number = number(expected)
            actual_number = number(actual)
            if expected_number is not None:
                if actual_number is None or not math.isclose(expected_number, actual_number, rel_tol=1e-8, abs_tol=1e-8):
                    mismatches.append(f"{name}: expected {expected_number}, read {actual!r}")
            elif str(actual).strip() != str(expected).strip():
                mismatches.append(f"{name}: expected {expected!r}, read {actual!r}")
        if mismatches:
            raise CloseSyncError("READBACK_VERIFY", "; ".join(mismatches[:10]))
        summary["stages"]["READBACK_VERIFY"] = "SUCCESS"

        # Re-evaluate required cells after the upsert. A same-day prior verified
        # value counts; an empty cell stays explicitly listed as incomplete.
        readback_missing = []
        for header in REQUIRED_CLOSE_HEADERS:
            if header not in header_indices:
                readback_missing.append(header)
                continue
            index = header_indices[header]
            value = actual_row[index] if index < len(actual_row) else ""
            normalized = normalized_value(value)
            if normalized in (None, "") or (isinstance(normalized, str) and normalized.startswith("取得不能")):
                readback_missing.append(header)
        summary["missingRequiredFields"] = readback_missing

        if import_errors:
            summary["errors"].extend(import_errors)
        if field_warnings:
            summary["errors"].extend(field_warnings)
        complete = (
            payload.get("overallStatus") == "verified"
            and not payload.get("missingRequired")
            and all(summary["stages"].get(stage) == "SUCCESS" for stage in ("SHEETS_IMPORT", "CHATGPT_INPUT", "CLOSE_DATA_WRITE", "READBACK_VERIFY"))
            and not summary["missingRequiredFields"]
            and not field_warnings
        )
        summary["status"] = "SUCCESS" if complete else "PARTIAL"
        validation_partial = bool(
            payload.get("overallStatus") != "verified"
            or payload.get("missingRequired")
            or summary["missingRequiredFields"]
            or field_warnings
        )
        if validation_partial:
            summary["stages"]["VALIDATE"] = "PARTIAL"
        summary["failedStage"] = "" if complete else ("SHEETS_IMPORT" if import_errors else "VALIDATE" if validation_partial else "")
    except Exception as exc:
        stage = exc.stage if isinstance(exc, CloseSyncError) else "CLOSE_DATA_WRITE"
        summary["failedStage"] = stage
        summary["errors"].append(str(exc))
        summary["stages"][stage] = "FAILED"
        summary["status"] = "FAILED"

    # Always persist the status in the live audit sheet when the API is
    # available, including partial or readback failures.
    try:
        append_update_log(client, summary, now, run_key, scheduled_time, sleep)
        summary["stages"]["LOG"] = "SUCCESS"
    except Exception as exc:
        summary["stages"]["LOG"] = "FAILED"
        summary["errors"].append(f"WEB_Data_Update_Log: {exc}")
        summary["failedStage"] = "LOG"
        summary["status"] = "FAILED"
    return summary


def verify_input_rows(rows: list[list[Any]], payload: dict[str, Any]) -> tuple[bool, str]:
    if not rows:
        return False, "no rows"
    headers = [str(value or "").strip() for value in rows[0]]
    missing = [name for name in INPUT_HEADERS if name not in headers]
    if missing:
        return False, "missing headers: " + ", ".join(missing)
    indices = {name: headers.index(name) for name in INPUT_HEADERS}
    expected_at = str(payload.get("generatedAt") or "")
    markets = payload.get("markets") or {}
    by_id: dict[str, list[Any]] = {}
    for row in rows[1:]:
        if len(row) <= indices["銘柄ID"]:
            continue
        symbol = str(row[indices["銘柄ID"]] or "")
        if symbol:
            by_id[symbol] = row
    for symbol, market in markets.items():
        row = by_id.get(str(symbol))
        if row is None:
            return False, f"missing symbol {symbol}"
        snapshot = str(row[indices["スナップショットID"]] or "")
        updated = str(row[indices["更新日時"]] or "")
        if snapshot != f"{expected_at}|{symbol}" or updated != expected_at:
            return False, f"stale snapshot for {symbol}"
        wanted = number(market.get("value"))
        actual = number(row[indices["現在値"]])
        if wanted is None:
            if actual is not None:
                return False, f"unexpected numeric value for {symbol}"
        elif actual is None or not math.isclose(wanted, actual, rel_tol=1e-8, abs_tol=1e-8):
            return False, f"value mismatch for {symbol}: expected {wanted}, got {actual}"
    return True, "snapshot ids and current values match"


def append_update_log(client: SheetsClient, summary: dict[str, Any], now: dt.datetime, run_key: str, scheduled_time: str, sleep: Callable[[float], None]) -> None:
    sheet = "WEB_Data_Update_Log"
    existing = read_values(client, sheet, "A1:H100", "FORMATTED_VALUE")
    headers = tuple(str(value or "").strip() for value in (existing[0] if existing else []))
    if headers != LOG_HEADERS:
        raise SheetsSyncError(f"Unexpected WEB_Data_Update_Log headers: {headers}")
    timestamp = now.astimezone(JST).strftime("%Y/%m/%d %H:%M JST")
    target = str(summary.get("targetDate") or "")
    status_label = {"SUCCESS": "完了", "PARTIAL": "部分完了", "FAILED": "失敗"}.get(summary.get("status"), "失敗")
    action = f"{target}行更新・再読込確認 ({summary.get('status')})" if summary.get("row") else f"{target or '対象日未確定'}行更新 ({summary.get('status')})"
    source = ", ".join(summary.get("sources") or []) or "GitHub verified market data"
    note = json.dumps({
        "runKey": run_key,
        "scheduledTime": scheduled_time,
        "failedStage": summary.get("failedStage") or "",
        "stages": summary.get("stages") or {},
        "missingRequiredFields": summary.get("missingRequiredFields") or [],
        "marketData": summary.get("marketData") or [],
        "errors": summary.get("errors") or [],
    }, ensure_ascii=False, separators=(",", ":"))
    row = [timestamp, "終値一覧", action, target, 1 if summary.get("stages", {}).get("READBACK_VERIFY") == "SUCCESS" else 0, status_label, source, note]
    retry(lambda: client.append(sheet, "A:H", [row]), sleep)


def write_status_file(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", default=str(ROOT / "data" / "market" / "latest.json"))
    parser.add_argument("--status-output", default=str(ROOT / "data" / "market" / "close_data_sync_status.json"))
    parser.add_argument("--scheduled-time", default=os.environ.get("ACQUISITION_SCHEDULED_TIME", "06:30"))
    parser.add_argument("--run-key", default=os.environ.get("GITHUB_RUN_ID", "manual") + ":" + os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--skip-import-check", action="store_true", help="Only for local unit/integration tests.")
    args = parser.parse_args()

    now = dt.datetime.now(JST).replace(microsecond=0)
    summary: dict[str, Any]
    client: SheetsClient | None = None
    try:
        payload = json.loads(Path(args.latest).read_text(encoding="utf-8"))
        spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID).strip()
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if not service_account_json:
            raise CloseSyncError("VALIDATE", "GOOGLE_SERVICE_ACCOUNT_JSON is required for close-row persistence.")
        client = SheetsClient(create_authorized_session(load_service_account_info(service_account_json)), spreadsheet_id)
        summary = close_row_sync(
            client, payload, now, scheduled_time=args.scheduled_time,
            run_key=args.run_key, verify_import_tabs=not args.skip_import_check,
        )
    except Exception as exc:
        summary = {
            "status": "FAILED", "generatedAt": "", "targetDate": None, "row": None,
            "inserted": False, "failedStage": getattr(exc, "stage", "FETCH"),
            "stages": {"FETCH": "FAILED", "VALIDATE": "PENDING", "GITHUB_SAVE": "SUCCESS", "SHEETS_IMPORT": "PENDING", "CHATGPT_INPUT": "PENDING", "CLOSE_DATA_WRITE": "PENDING", "READBACK_VERIFY": "PENDING", "LOG": "PENDING"},
            "missingRequiredFields": list(REQUIRED_CLOSE_HEADERS), "updatedFields": [], "sources": [], "marketData": [], "errors": [str(exc)],
        }
    write_status_file(Path(args.status_output), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("status") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

