#!/usr/bin/env python3
"""Audit dated rows of 終値一覧 without inventing prices or overwriting data.

Blank, source-unavailable and market-closed are *different* statuses.
This read-only audit never changes the closing-price worksheet.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from write_market_data_to_sheets import (
        SheetsClient, create_authorized_session, load_service_account_info,
    )
except ModuleNotFoundError:
    from scripts.write_market_data_to_sheets import (
        SheetsClient, create_authorized_session, load_service_account_info,
    )

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "market" / "close-missing-audit.json"
SHEET = "終値一覧"
EXPECTED_COLUMNS = 186
CORE_COLUMNS = 65
JST = dt.timezone(dt.timedelta(hours=9))
UNAVAILABLE = ("取得不能", "未取得", "公表待ち", "確認中", "未確認", "取得待ち", "未公表", "#REF!", "#N/A")
NOT_APPLICABLE = {"休場", "対象外", "該当なし"}


def state(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "blank"
    if text in NOT_APPLICABLE:
        return "not_applicable"
    if text.startswith(UNAVAILABLE):
        return "unavailable"
    return "filled"  # Not a claim that the value or its source was verified.


def audit_rows(values: list[list[Any]]) -> dict[str, Any]:
    if not values:
        raise ValueError("終値一覧: no rows returned")
    headers = list(map(str, values[0]))
    if len(headers) < EXPECTED_COLUMNS:
        raise ValueError(f"Expected {EXPECTED_COLUMNS} headers, received {len(headers)}")
    if headers[0] != "日付":
        raise ValueError(f"Unexpected first column {headers[0]!r}")

    per_column = [Counter() for _ in range(EXPECTED_COLUMNS)]
    daily: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row_number, row in enumerate(values[1:], start=2):
        date = str(row[0]).strip().replace("-", "/") if row else ""
        if not date:
            continue
        try:
            dt.datetime.strptime(date, "%Y/%m/%d")
        except ValueError as exc:
            raise ValueError(f"Invalid report date at row {row_number}: {date!r}") from exc
        if date in seen:
            raise ValueError(f"Duplicate report date {date}: rows {seen[date]} and {row_number}")
        seen[date] = row_number
        statuses = Counter()
        for j in range(EXPECTED_COLUMNS):
            s = state(row[j] if j < len(row) else None)
            per_column[j][s] += 1
            statuses["core_" + s if j < CORE_COLUMNS else "extra_" + s] += 1
        daily.append({
            "row": row_number, "date": date,
            "coreBlank": statuses["core_blank"],
            "extraBlank": statuses["extra_blank"],
            "coreUnavailable": statuses["core_unavailable"],
            "extraUnavailable": statuses["extra_unavailable"],
            "coreClosed": statuses["core_not_applicable"],
            "extraClosed": statuses["extra_not_applicable"],
        })

    by_column = [{
        "column": j + 1, "name": headers[j],
        "blank": entry["blank"],
        "unavailable": entry["unavailable"],
        "notApplicable": entry["not_applicable"],
        "filled": entry["filled"],
    } for j, entry in enumerate(per_column)]
    return {
        "status": "AUDITED",
        "sheet": SHEET,
        "rows": len(daily),
        "columns": EXPECTED_COLUMNS,
        "coreBlank": sum(x["blank"] for x in by_column[:CORE_COLUMNS]),
        "extraBlank": sum(x["blank"] for x in by_column[CORE_COLUMNS:]),
        "coreUnavailable": sum(x["unavailable"] for x in by_column[:CORE_COLUMNS]),
        "extraUnavailable": sum(x["unavailable"] for x in by_column[CORE_COLUMNS:]),
        "unverifiedValueWarning": "Filled means non-empty, NOT source-verified.",
        "missingByColumn": sorted(
            [x for x in by_column if x["blank"]],
            key=lambda x: (-x["blank"], x["column"]),
        ),
        "missingByDate": sorted(daily, key=lambda x: x["date"], reverse=True),
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    checked_at = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    sheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    secret = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sheet_id or not secret:
        result: dict[str, Any] = {
            "status": "BLOCKED", "checkedAt": checked_at,
            "reason": "MARKET_DATA_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON missing",
            "coreBlank": None, "extraBlank": None,
        }
    else:
        try:
            session = create_authorized_session(load_service_account_info(secret))
            client = SheetsClient(session, sheet_id)
            # Bounded, non-destructive read. Sheet holds < 250 dated rows today.
            cells = client.get_values(SHEET, "A1:GD250")
            result = audit_rows(cells)
            result["checkedAt"] = checked_at
            result["spreadsheetId"] = sheet_id
        except Exception as exc:  # noqa: BLE001
            reason = str(exc).splitlines()[0][:240]
            result = {
                "status": "BLOCKED", "checkedAt": checked_at,
                "reason": reason,
                "coreBlank": None, "extraBlank": None,
            }

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        key: result.get(key)
        for key in ("status", "checkedAt", "rows", "coreBlank", "extraBlank", "reason")
    }, ensure_ascii=False))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
