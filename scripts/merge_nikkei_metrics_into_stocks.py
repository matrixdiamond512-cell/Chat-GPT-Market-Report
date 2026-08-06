#!/usr/bin/env python3
"""Merge Nikkei VI and valuation metrics directly into data/stocks.json.

This script has no external dependencies and does not require Google credentials.
It makes the Japan market table self-contained so the public page does not rely on
post-render JavaScript overlays.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

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
    return [
        name,
        str(item.get("display") or item.get("raw") or "取得不能"),
        str(item.get("change") or "—"),
        str(item.get("evaluation") or f"基準日 {payload.get('dataAsOf') or '取得不能'}。"),
    ]


def main() -> int:
    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    missing = [name for name in ORDER if name not in (metrics.get("metrics") or {})]
    if missing:
        raise SystemExit("nikkei-metrics.json is missing: " + ", ".join(missing))

    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    rows = [
        row for row in (japan.get("rows") or [])
        if not (isinstance(row, list) and row and str(row[0]).strip() in ORDER)
    ]

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
    stocks["updatedAt"] = now.isoformat()
    stocks["nikkeiMetricsAsOf"] = metrics.get("dataAsOf") or ""
    stocks["sourceStatus"] = "Google Sheetsから更新＋日経VI・日経バリュエーション直接反映"

    STOCKS_PATH.write_text(
        json.dumps(stocks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    names = [row[0] for row in japan["rows"] if isinstance(row, list) and row]
    remaining = [name for name in ORDER if name not in names]
    if remaining:
        raise SystemExit("data/stocks.json merge failed: " + ", ".join(remaining))

    print("Merged Japan market metrics:", ", ".join(ORDER))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
