#!/usr/bin/env python3
"""Update only the completed Tokyo-market session from the verified close sheet.

Before the Tokyo close, the expected date is the previous Tokyo business day.
After the close, the expected date is the current business day. The U.S. side is
never modified by this script.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from archive_stocks_snapshot import archive_snapshot
from write_market_data_to_sheets import (
    SheetsClient,
    create_authorized_session,
    load_service_account_info,
)

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
NIKKEI_METRICS_PATH = ROOT / "data" / "nikkei-metrics.json"
JST = timezone(timedelta(hours=9))
DEFAULT_SPREADSHEET_ID = "1n2ACInX4pmK0TdijC8xaur2RIiNZyVa6GFTZAyofcuE"
SHEET_NAME = "終値一覧"
DATE_RE = re.compile(r"^(\d{4})[/-](\d{2})[/-](\d{2})")


def normalize_date(value: Any) -> str:
    match = DATE_RE.match(str(value or "").strip())
    return "-".join(match.groups()) if match else ""


def previous_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def expected_tokyo_date(now: datetime) -> str:
    override = os.getenv("TOKYO_MARKET_DATE", "").strip()
    if override:
        normalized = normalize_date(override)
        if not normalized:
            raise RuntimeError("TOKYO_MARKET_DATE is invalid")
        return normalized
    current = now.date()
    if current.weekday() < 5 and now.time() >= time(16, 0):
        return current.isoformat()
    return previous_weekday(current).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def numeric(value: Any) -> str:
    raw = text(value)
    return raw if raw else "取得不能（終値一覧に対象日の値なし）"


def percent(value: Any) -> str:
    raw = text(value)
    if not raw:
        return "取得不能（終値一覧に対象日の値なし）"
    if raw.endswith("%"):
        return raw
    try:
        number = float(raw.replace(",", ""))
        return f"{number:+.2f}%"
    except ValueError:
        return raw


def signed_number(value: Any) -> str:
    raw = text(value)
    if not raw:
        return "取得不能（終値一覧に対象日の値なし）"
    try:
        number = float(raw.replace(",", ""))
        return f"{number:+,.2f}"
    except ValueError:
        return raw


def row_map(headers: list[Any], values: list[Any]) -> dict[str, Any]:
    return {
        str(header).strip(): values[index] if index < len(values) else ""
        for index, header in enumerate(headers)
        if str(header).strip()
    }


def evaluation(label: str, data_date: str, available: bool = True) -> str:
    if available:
        return f"終値一覧の確定値。基準日 {data_date}。"
    return f"取得不能（終値一覧に対象日の値なし）。基準日 {data_date}。"


def metric_item(display: str, change: str, label: str, data_date: str) -> dict[str, str]:
    available = not display.startswith("取得不能")
    return {
        "raw": display,
        "display": display,
        "change": change,
        "evaluation": evaluation(label, data_date, available),
    }


def find_existing_row(rows: list[Any], label: str, current_date: str, target_date: str) -> list[str] | None:
    if current_date != target_date:
        return None
    for row in rows:
        if isinstance(row, list) and row and str(row[0]).strip() == label:
            return [str(item) for item in row]
    return None


def unavailable_row(label: str, data_date: str) -> list[str]:
    return [
        label,
        "取得不能（終値一覧に対象日の値なし）",
        "—",
        evaluation(label, data_date, False),
    ]


def main() -> int:
    now = datetime.now(JST).replace(microsecond=0)
    target_date = expected_tokyo_date(now)
    spreadsheet_id = os.getenv("MARKET_DATA_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID).strip()
    credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not credentials_raw:
        raise SystemExit("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")

    client = SheetsClient(
        create_authorized_session(load_service_account_info(credentials_raw)),
        spreadsheet_id,
    )
    values = client.get_values(SHEET_NAME, "A:EZ")
    if len(values) < 2:
        raise SystemExit("終値一覧にデータ行がありません")
    headers = values[0]
    selected: dict[str, Any] | None = None
    for raw_row in values[1:]:
        mapped = row_map(headers, raw_row)
        if normalize_date(mapped.get("日付")) == target_date:
            selected = mapped
            break
    if selected is None:
        raise SystemExit(f"終値一覧に東京市場の対象日 {target_date} がありません")

    nikkei_close = numeric(selected.get("日経225終値"))
    nikkei_change = signed_number(selected.get("日経225前日比"))
    nikkei_pct = percent(selected.get("日経225騰落率"))
    if nikkei_close.startswith("取得不能"):
        raise SystemExit(f"{target_date} の日経225終値がありません")

    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    old_rows = japan.get("rows") or []
    old_date = str((stocks.get("marketDates") or {}).get("japan") or japan.get("dataDate") or "")[:10]

    rows: list[list[str]] = [
        [
            "日経225",
            nikkei_close,
            f"{nikkei_change}（{nikkei_pct}）",
            f"終値一覧の確定値。基準日 {target_date}。",
        ]
    ]
    for label in ("TOPIX", "グロース250"):
        rows.append(find_existing_row(old_rows, label, old_date, target_date) or unavailable_row(label, target_date))

    nikkei_vi = numeric(selected.get("日経VI終値"))
    nikkei_vi_change = signed_number(selected.get("日経VI前日比"))
    nikkei_vi_pct = percent(selected.get("日経VI騰落率"))
    rows.append([
        "日経VI",
        nikkei_vi,
        f"{nikkei_vi_change}（{nikkei_vi_pct}）" if not nikkei_vi.startswith("取得不能") else "—",
        evaluation("日経VI", target_date, not nikkei_vi.startswith("取得不能")),
    ])

    adv = numeric(selected.get("東証プライム値上がり銘柄数"))
    dec = numeric(selected.get("東証プライム値下がり銘柄数"))
    breadth_available = not adv.startswith("取得不能") and not dec.startswith("取得不能")
    rows.append([
        "値上がり銘柄 / 値下がり銘柄",
        f"{adv} / {dec}" if breadth_available else "取得不能（終値一覧に対象日の値なし）",
        "—",
        evaluation("東証プライム騰落銘柄数", target_date, breadth_available),
    ])

    trading_value = numeric(selected.get("東証プライム売買代金"))
    if not trading_value.startswith("取得不能") and "兆" not in trading_value:
        trading_value += " 兆円"
    rows.append([
        "東証プライム売買代金",
        trading_value,
        "—",
        evaluation("東証プライム売買代金", target_date, not trading_value.startswith("取得不能")),
    ])

    ratio = numeric(selected.get("東証プライム騰落レシオ"))
    rows.append([
        "騰落レシオ（25日）",
        ratio,
        "—",
        evaluation("東証プライム騰落レシオ", target_date, not ratio.startswith("取得不能")),
    ])

    eps = numeric(selected.get("日経225予想EPS"))
    per = numeric(selected.get("日経225予想PER"))
    dev25 = percent(selected.get("日経225_25日乖離率"))
    dev200 = percent(selected.get("日経225_200日乖離率"))
    rows.extend([
        ["日経225予想PER", per, "—", evaluation("日経225予想PER", target_date, not per.startswith("取得不能"))],
        ["日経225予想EPS", eps, "—", evaluation("日経225予想EPS", target_date, not eps.startswith("取得不能"))],
        ["日経225 25日乖離率", dev25, "—", evaluation("日経225 25日乖離率", target_date, not dev25.startswith("取得不能"))],
        ["日経225 200日乖離率", dev200, "—", evaluation("日経225 200日乖離率", target_date, not dev200.startswith("取得不能"))],
    ])

    overseas = find_existing_row(old_rows, "海外投資家動向（現物）", old_date, target_date)
    rows.append(overseas or unavailable_row("海外投資家動向（現物）", target_date))

    japan.update({
        "title": "主要指数と市場内部（日本）",
        "flag": "JP",
        "columns": ["指標名", "終値", "前日比", "評価・概況"],
        "rows": rows,
        "dataDate": target_date,
        "updatedAt": now.isoformat(),
    })
    stocks.setdefault("marketDates", {})["japan"] = target_date
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now.isoformat()
    stocks["updatedAt"] = now.isoformat()
    stocks["nikkeiMetricsAsOf"] = target_date
    stocks["sourceStatus"] = "米国市場と東京市場を独立更新・市場別基準日を明示"
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics_payload = {
        "schemaVersion": "2.0.0",
        "generatedAt": now.isoformat(),
        "dataAsOf": target_date,
        "sourceSheet": SHEET_NAME,
        "metrics": {
            "日経VI": metric_item(nikkei_vi, f"{nikkei_vi_change}（{nikkei_vi_pct}）" if not nikkei_vi.startswith("取得不能") else "—", "日経VI", target_date),
            "日経225予想PER": metric_item(per, "—", "日経225予想PER", target_date),
            "日経225予想EPS": metric_item(eps, "—", "日経225予想EPS", target_date),
            "日経225 25日乖離率": metric_item(dev25, "—", "日経225 25日乖離率", target_date),
            "日経225 200日乖離率": metric_item(dev200, "—", "日経225 200日乖離率", target_date),
        },
    }
    NIKKEI_METRICS_PATH.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    snapshot = archive_snapshot(STOCKS_PATH)
    print(json.dumps({
        "tokyoMarketDate": target_date,
        "usMarketDateRetained": (stocks.get("marketDates") or {}).get("us"),
        "snapshot": str(snapshot.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
