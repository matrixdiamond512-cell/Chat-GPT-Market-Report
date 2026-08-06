#!/usr/bin/env python3
"""Sync Nikkei 225 valuation and moving-average deviation metrics.

Reads the latest complete row from the Google Sheets ``終値一覧`` tab, then:
- adds PER, EPS, 25-day deviation, and 200-day deviation rows to data/stocks.json;
- writes data/nikkei-metrics.json for audit/debugging;
- merges the same rows into the Stock_Analysis_JSON sheet so later GAS syncs keep them.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STOCKS_PATH = ROOT / "data" / "stocks.json"
OUTPUT_PATH = ROOT / "data" / "nikkei-metrics.json"
JST = dt.timezone(dt.timedelta(hours=9))

METRIC_HEADERS = {
    "日経225予想PER": "日経225予想PER",
    "日経225予想EPS": "日経225予想EPS",
    "日経225 25日乖離率": "日経225_25日乖離率",
    "日経225 200日乖離率": "日経225_200日乖離率",
}

METRIC_NAMES = set(METRIC_HEADERS)


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def parse_date(value: str) -> dt.date | None:
    text = str(value or "").strip().replace("-", "/")
    try:
        return dt.datetime.strptime(text, "%Y/%m/%d").date()
    except ValueError:
        return None


def usable(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and not re.search(r"取得不能|対象外|未確認|未取得|入力待ち", text))


def numeric(value: Any) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group(0)) if match else None


def format_number(value: Any, digits: int = 2) -> str:
    number = numeric(value)
    if number is None:
        return str(value or "")
    return f"{number:,.{digits}f}"


def format_percent(value: Any) -> str:
    number = numeric(value)
    if number is None:
        return str(value or "")
    return f"{number:+.2f}%"


def evaluation(metric: str, raw_value: Any, as_of: str) -> str:
    value = numeric(raw_value)
    suffix = f"基準日 {as_of}。"
    if metric == "日経225予想PER":
        return "予想利益に対する株価水準。EPSと指数水準を合わせて確認。" + suffix
    if metric == "日経225予想EPS":
        return "日経225構成銘柄の予想利益水準。PERの分母として確認。" + suffix
    if metric == "日経225 25日乖離率":
        if value is None:
            text = "短期の過熱・売られ過ぎを確認。"
        elif value >= 8:
            text = "短期過熱が強い。+8%以上は高警戒。"
        elif value >= 7:
            text = "短期過熱に注意。+7%以上は警戒域。"
        elif value <= -7:
            text = "短期的な売られ過ぎに注意。反発と下落継続を見極める。"
        else:
            text = "25日線からの乖離は警戒域外。短期の過熱感は限定的。"
        return text + suffix
    if metric == "日経225 200日乖離率":
        if value is None:
            text = "長期トレンドからの乖離を確認。"
        elif value >= 30:
            text = "長期トレンドから大幅上方乖離。+30%以上は過熱警戒。"
        elif value >= 0:
            text = "200日線を上回り長期上昇基調。+30%以上は過熱警戒。"
        else:
            text = "200日線を下回る。長期トレンドの弱化を確認。"
        return text + suffix
    return suffix


def display_value(metric: str, raw_value: Any) -> str:
    if metric == "日経225予想PER":
        return format_number(raw_value) + "倍"
    if metric == "日経225予想EPS":
        return format_number(raw_value) + "円"
    return format_percent(raw_value)


def metric_rows(values: dict[str, Any], as_of: str) -> list[list[str]]:
    return [
        [metric, display_value(metric, values[metric]), "—", evaluation(metric, values[metric], as_of)]
        for metric in (
            "日経225予想PER",
            "日経225予想EPS",
            "日経225 25日乖離率",
            "日経225 200日乖離率",
        )
    ]


def merge_rows(data: dict[str, Any], rows_to_add: list[list[str]]) -> dict[str, Any]:
    japan = data.setdefault("marketInternals", {}).setdefault("japan", {})
    rows = [
        row for row in (japan.get("rows") or [])
        if not (isinstance(row, list) and row and str(row[0]).strip() in METRIC_NAMES)
    ]
    insert_at = next(
        (index + 1 for index, row in enumerate(rows) if isinstance(row, list) and row and str(row[0]).strip() == "騰落レシオ（25日）"),
        len(rows),
    )
    japan["rows"] = rows[:insert_at] + rows_to_add + rows[insert_at:]
    return data


def read_stock_analysis_json(worksheet: Any) -> dict[str, Any] | None:
    table = worksheet.get_all_values()
    if len(table) < 2:
        return None
    headers = [str(value or "").strip().lower() for value in table[0]]
    json_index = headers.index("json") if "json" in headers else 1
    parts = [str(row[json_index]) for row in table[1:] if len(row) > json_index and str(row[json_index]).strip()]
    if not parts:
        return None
    return json.loads("".join(parts))


def write_stock_analysis_json(worksheet: Any, data: dict[str, Any]) -> None:
    text = json.dumps(data, ensure_ascii=False)
    worksheet.update("B2", [[text]], value_input_option="RAW")
    if worksheet.row_count >= 3:
        worksheet.batch_clear([f"B3:B{worksheet.row_count}"])


def load_latest_metrics(workbook: Any) -> tuple[dict[str, Any], str, int]:
    worksheet = workbook.worksheet("終値一覧")
    table = worksheet.get_all_values()
    if not table:
        raise RuntimeError("終値一覧 sheet is empty")
    headers = [str(value or "").strip() for value in table[0]]
    required_headers = ["日付", *METRIC_HEADERS.values()]
    missing = [header for header in required_headers if header not in headers]
    if missing:
        raise RuntimeError("終値一覧に必要な列がありません: " + ", ".join(missing))

    indexes = {header: headers.index(header) for header in required_headers}
    candidates: list[tuple[dt.date, int, list[str]]] = []
    for row_number, row in enumerate(table[1:], start=2):
        date_value = row[indexes["日付"]] if len(row) > indexes["日付"] else ""
        parsed = parse_date(date_value)
        if not parsed:
            continue
        if all(len(row) > indexes[header] and usable(row[indexes[header]]) for header in METRIC_HEADERS.values()):
            candidates.append((parsed, row_number, row))
    if not candidates:
        raise RuntimeError("4指標がすべてそろった日付行がありません")

    parsed_date, row_number, row = max(candidates, key=lambda item: item[0])
    values = {
        metric: row[indexes[header]]
        for metric, header in METRIC_HEADERS.items()
    }
    return values, parsed_date.isoformat(), row_number


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_json:
        raise SystemExit("Google Sheets credentials are not configured")

    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore

    credentials = Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    workbook = gspread.authorize(credentials).open_by_key(spreadsheet_id)
    values, as_of, source_row = load_latest_metrics(workbook)
    rows_to_add = metric_rows(values, as_of)

    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    merge_rows(stocks, rows_to_add)
    timestamp = now_jst().isoformat()
    stocks["updatedAt"] = timestamp
    stocks["sourceStatus"] = "Google Sheetsから更新＋日経バリュエーション自動連携"
    stocks["nikkeiMetricsAsOf"] = as_of
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stock_sheet = workbook.worksheet("Stock_Analysis_JSON")
    stock_sheet_data = read_stock_analysis_json(stock_sheet)
    if stock_sheet_data is not None:
        merge_rows(stock_sheet_data, rows_to_add)
        stock_sheet_data["updatedAt"] = now_jst().strftime("%Y/%m/%d %H:%M")
        stock_sheet_data["sourceStatus"] = "Google Sheetsから更新＋日経バリュエーション自動連携"
        stock_sheet_data["nikkeiMetricsAsOf"] = as_of
        write_stock_analysis_json(stock_sheet, stock_sheet_data)

    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": timestamp,
        "dataAsOf": as_of,
        "sourceSheet": "終値一覧",
        "sourceRow": source_row,
        "metrics": {
            metric: {
                "raw": str(values[metric]),
                "display": display_value(metric, values[metric]),
                "evaluation": evaluation(metric, values[metric], as_of),
            }
            for metric in METRIC_HEADERS
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
