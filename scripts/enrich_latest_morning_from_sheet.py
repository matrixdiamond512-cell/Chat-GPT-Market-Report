#!/usr/bin/env python3
"""Populate the 08:00 market table from the canonical 終値一覧 previous-close row.

The 08:00 report is a previous-close report. Therefore every mapped market row must
use the latest valid row in 終値一覧 whose date is before the report date.

Most importantly, a missing/unusable previous close must NEVER leave a pre-existing
08:00 live quote in the previous-close table. Such a row is explicitly replaced by a
reasoned unavailable marker so that later date-matched repair steps may fill it. This
also protects the row from the historical "original published value" recovery step,
which must not be allowed to re-introduce an intraday quote into the previous-close
table.

The time at which a valid close is retrieved is not the market-data timestamp: a
verified close for the correct prior session may be retrieved later and is still a
previous-session close.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest-report.json"
JST = dt.timezone(dt.timedelta(hours=9))

MAP: dict[str, dict[str, str]] = {
    "NYダウ": {"value":"Dow終値","change":"Dow前日比","rate":"Dow騰落率"},
    "NASDAQ総合": {"value":"Nasdaq終値","change":"Nasdaq前日比","rate":"Nasdaq騰落率"},
    "S&P500": {"value":"S&P500終値","change":"S&P500前日比","rate":"S&P500騰落率"},
    "Russell 2000": {"value":"Russell 2000終値","change":"Russell 2000前日比","rate":"Russell 2000騰落率"},
    "日経225現物": {"value":"日経225終値","change":"日経225前日比","rate":"日経225騰落率"},
    "日経225先物（大阪取引所）": {"value":"日経225先物大阪終値","change":"日経225先物大阪前日比","rate":"日経225先物大阪騰落率"},
    "USD/JPY": {"value":"USDJPY終値","change":"USDJPY前日比","rate":"USDJPY騰落率"},
    "EUR/USD": {"value":"EURUSD終値","change":"EURUSD前日比","rate":"EURUSD騰落率"},
    "COMEX金先物": {"value":"ゴールド終値","change":"ゴールド前日比","rate":"ゴールド騰落率"},
    "WTI原油": {"value":"WTI原油終値","change":"WTI原油前日比","rate":"WTI原油騰落率"},
    "BTCUSD": {"value":"BTCUSD終値","change":"BTCUSD前日比","rate":"BTCUSD騰落率"},
    "VIX": {"value":"VIX終値","change":"VIX前日比","rate":"VIX騰落率"},
    "日経VI": {"value":"日経VI終値","change":"日経VI前日比","rate":"日経VI騰落率"},
    "Fear & Greed Index": {"value":"FearGreed終値","change":"FearGreed前日比","classification":"FearGreed判定"},
    "米10年債利回り": {"value":"米10年債利回り","change":"米10年債前日比"},
    "日本10年国債利回り": {"value":"日本10年債利回り","change":"日本10年債前日比"},
    "日経225予想PER": {"value":"日経225予想PER"},
    "日経225 PBR": {"value":"日経225予想PBR"},
    "日経225予想EPS": {"value":"日経225予想EPS"},
    "日経225 25日移動平均乖離率": {"value":"日経225_25日乖離率"},
    "日経225 200日移動平均乖離率": {"value":"日経225_200日乖離率"},
    "東証プライム売買代金": {"value":"東証プライム売買代金"},
    "東証プライム売買高": {"value":"東証プライム売買高"},
    "東証プライム値上がり銘柄数": {"value":"東証プライム値上がり銘柄数"},
    "東証プライム値下がり銘柄数": {"value":"東証プライム値下がり銘柄数"},
    "東証プライム25日騰落レシオ": {"value":"東証プライム騰落レシオ"},
}

UNAVAILABLE_RE = re.compile(r"取得不能|未取得|未公表|入力に値なし|入力待ち|取得継続|休場")
REASONED_UNAVAILABLE_RE = re.compile(r"^(取得不能|未公表)（.+）$")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_date(value: str) -> dt.date | None:
    text = str(value or "").strip().replace("-", "/")
    try:
        return dt.datetime.strptime(text, "%Y/%m/%d").date()
    except ValueError:
        return None


def usable(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and not UNAVAILABLE_RE.search(text))


def numeric(value: Any) -> float | None:
    m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", str(value or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def signed_direction(change: Any, rate: Any, label: str, value: Any, classification: str = "") -> str:
    if label == "Fear & Greed Index":
        return classification or "センチメント指標"
    if "乖離率" in label:
        n = numeric(value)
        if n is None:
            return "基準値"
        return "上方乖離" if n > 0 else "下方乖離" if n < 0 else "乖離なし"
    n = numeric(change)
    if n is None:
        n = numeric(rate)
    if n is None:
        return "確定値"
    return "上昇" if n > 0 else "下落" if n < 0 else "横ばい"


def fmt(label: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    if label in {"日経225予想PER", "日経225 PBR"} and not text.endswith("倍"):
        return text + "倍"
    if label == "日経225予想EPS" and not text.endswith("円"):
        return text + "円"
    if label == "東証プライム売買代金":
        n = numeric(text)
        return f"{n:g}兆円" if n is not None else text
    return text


def reasoned_unavailable(sheet_value: Any, sheet_date: str, label: str) -> str:
    text = str(sheet_value or "").strip()
    if REASONED_UNAVAILABLE_RE.match(text):
        return text
    if text:
        return f"取得不能（{sheet_date}の{label}前営業日終値を終値一覧で利用できず：{text}）"
    return f"取得不能（{sheet_date}の{label}前営業日終値が終値一覧で空欄）"


def latest_prior_row(table: list[list[str]], report_date: dt.date) -> tuple[dict[str, str], str]:
    headers = [str(x or "").strip() for x in table[0]]
    date_index = headers.index("日付")
    candidates: list[tuple[dt.date, list[str]]] = []
    for row in table[1:]:
        if len(row) <= date_index:
            continue
        d = parse_date(row[date_index])
        if d and d < report_date:
            candidates.append((d, row))
    if not candidates:
        raise RuntimeError("終値一覧にレポート日前の行がありません")
    date_value, row = max(candidates, key=lambda item: item[0])
    return {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}, date_value.isoformat()


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_json:
        print("Google Sheets enrichment skipped: GitHub Actions Sheets credentials are not configured")
        return 0

    payload = load_json(LATEST)
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict) or report.get("time") != "08:00":
        print("Latest report is not 08:00; enrichment skipped")
        return 0

    report_date = dt.date.fromisoformat(str(report["date"]))
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
    credentials = Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.readonly"],
    )
    workbook = gspread.authorize(credentials).open_by_key(spreadsheet_id)
    table = workbook.worksheet("終値一覧").get_all_values()
    sheet_row, sheet_date = latest_prior_row(table, report_date)

    market_table = report.setdefault("marketDataTable", {})
    rows = market_table.get("rows") or []
    if not isinstance(rows, list) or len(rows) != 28:
        raise SystemExit(f"08:00 table must already have 28 rows; got {len(rows) if isinstance(rows,list) else 'invalid'}")

    market_table["columns"] = ["項目", "終値・値", "前日比", "騰落率", "方向感"]
    market_table["semantics"] = "previous_close"
    market_table["dataDate"] = sheet_date

    by_label = {
        str(row.get("label") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("label") or "").strip()
    }

    updated: list[str] = []
    unavailable: list[str] = []
    for label, spec in MAP.items():
        row = by_label.get(label)
        if not isinstance(row, dict):
            continue

        sheet_value = sheet_row.get(spec["value"], "")
        # Every mapped row is marked as canonical-processed, even when unavailable.
        # This prevents the later historical recovery step from restoring the old
        # intraday 08:00 quote into a previous-close cell.
        updated.append(label)

        if not usable(sheet_value):
            row["value"] = reasoned_unavailable(sheet_value, sheet_date, label)
            row["change"] = "—"
            row["rate"] = "—"
            row["direction"] = "取得不能"
            unavailable.append(label)
            continue

        change = sheet_row.get(spec.get("change", ""), "") if spec.get("change") else ""
        rate = sheet_row.get(spec.get("rate", ""), "") if spec.get("rate") else ""
        classification = sheet_row.get(spec.get("classification", ""), "") if spec.get("classification") else ""
        row["value"] = fmt(label, sheet_value)
        row["change"] = str(change or "—")
        row["rate"] = str(rate or "—")
        row["direction"] = signed_direction(change, rate, label, sheet_value, classification)

    report.setdefault("dataProvenance", {})["closeSheet"] = {
        "sheet": "終値一覧",
        "dataDate": sheet_date,
        "syncedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "updatedLabels": updated,
        "unavailableLabels": unavailable,
        "semantics": "previous_close",
        "rule": "08:00 previous-close table never retains a same-day live quote when the canonical prior close is missing",
    }
    dump_json(LATEST, payload)
    print(json.dumps({"sheetDate": sheet_date, "updated": updated, "unavailable": unavailable}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
