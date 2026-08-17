#!/usr/bin/env python3
"""Merge Tokyo-market metrics without advancing the U.S. market date.

The Tokyo side is updated from its completed-session data. U.S. rows and their
market date remain untouched. A full daily snapshot is then saved with both
market dates recorded independently.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from archive_stocks_snapshot import archive_snapshot

ROOT = Path(__file__).resolve().parent.parent
STOCKS_PATH = ROOT / "data" / "stocks.json"
METRICS_PATH = ROOT / "data" / "nikkei-metrics.json"
JST = dt.timezone(dt.timedelta(hours=9))

ORDER = [
    "日経VI",
    "日経225予想PER",
    "日経225予想EPS",
    "日経225 25日乖離率",
    "日経225 200日乖離率",
]


def metric_row(name: str, payload: dict[str, Any]) -> list[str]:
    item = (payload.get("metrics") or {}).get(name) or {}
    data_date = str(payload.get("dataAsOf") or "取得不能")[:10]
    evaluation = str(item.get("evaluation") or "").strip()
    if data_date not in evaluation:
        evaluation = (evaluation + " " if evaluation else "") + f"基準日 {data_date}。"
    return [
        name,
        str(item.get("display") or item.get("raw") or "取得不能"),
        str(item.get("change") or "—"),
        evaluation,
    ]


def main() -> int:
    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    data_date = str(metrics.get("dataAsOf") or "")[:10]
    if len(data_date) != 10:
        raise SystemExit("nikkei-metrics.json dataAsOf is missing or invalid")

    missing = [name for name in ORDER if name not in (metrics.get("metrics") or {})]
    if missing:
        raise SystemExit("nikkei-metrics.json is missing: " + ", ".join(missing))

    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    rows = [
        row for row in (japan.get("rows") or [])
        if not (isinstance(row, list) and row and str(row[0]).strip() in ORDER)
    ]
    if not rows:
        raise SystemExit("Japan market table is empty; refusing to archive")

    vi_index = next(
        (
            index + 1
            for index, row in enumerate(rows)
            if isinstance(row, list) and row and str(row[0]).strip() == "グロース250"
        ),
        min(3, len(rows)),
    )
    rows.insert(vi_index, metric_row("日経VI", metrics))

    valuation_rows = [metric_row(name, metrics) for name in ORDER[1:]]
    ratio_index = next(
        (
            index + 1
            for index, row in enumerate(rows)
            if isinstance(row, list) and row and str(row[0]).strip() == "騰落レシオ（25日）"
        ),
        len(rows),
    )
    japan["rows"] = rows[:ratio_index] + valuation_rows + rows[ratio_index:]

    now = dt.datetime.now(JST).replace(microsecond=0)
    japan["dataDate"] = data_date
    japan["updatedAt"] = now.isoformat()
    stocks.setdefault("marketDates", {})["japan"] = data_date
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now.isoformat()
    stocks["nikkeiMetricsAsOf"] = data_date
    stocks["sourceStatus"] = "米国市場と東京市場を独立更新・市場別基準日を明示"

    STOCKS_PATH.write_text(
        json.dumps(stocks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    names = [row[0] for row in japan["rows"] if isinstance(row, list) and row]
    remaining = [name for name in ORDER if name not in names]
    if remaining:
        raise SystemExit("data/stocks.json merge failed: " + ", ".join(remaining))

    snapshot_path = archive_snapshot(STOCKS_PATH)
    print(
        "Merged Tokyo metrics without changing the U.S. date:",
        ", ".join(ORDER),
        "snapshot=", snapshot_path.relative_to(ROOT),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

