#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "market" / "us-stock-breadth-history.json"
OUTPUT = ROOT / "data" / "market" / "us-stock-breadth-history.csv"
HEADERS = [
    "日付", "NYSE値上がり銘柄数", "NYSE値下がり銘柄数",
    "NYSE52週高値銘柄数", "NYSE52週安値銘柄数", "NYSE Advance/Decline比率",
    "NYSE前日比", "NYSE20営業日平均比", "NASDAQ値上がり銘柄数",
    "NASDAQ値下がり銘柄数", "NASDAQ52週高値銘柄数", "NASDAQ52週安値銘柄数",
    "NASDAQ Advance/Decline比率", "NASDAQ前日比", "NASDAQ20営業日平均比",
    "米国株合算値上がり比率", "市場内部判定", "データ取得元", "取得日時", "注記"
]


def val(obj, key):
    value = obj.get(key)
    return "" if value is None else value


def main() -> int:
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    rows = []
    for item in sorted(history, key=lambda x: x.get("marketDate", "")):
        nyse = item.get("exchanges", {}).get("NYSE", {})
        nasdaq = item.get("exchanges", {}).get("NASDAQ", {})
        rows.append([
            item.get("marketDate", ""), val(nyse, "advancers"), val(nyse, "decliners"),
            val(nyse, "newHigh52Week"), val(nyse, "newLow52Week"), val(nyse, "advanceDeclineRatio"),
            val(nyse, "previousDayChange"), val(nyse, "versus20DayAveragePercent"),
            val(nasdaq, "advancers"), val(nasdaq, "decliners"),
            val(nasdaq, "newHigh52Week"), val(nasdaq, "newLow52Week"), val(nasdaq, "advanceDeclineRatio"),
            val(nasdaq, "previousDayChange"), val(nasdaq, "versus20DayAveragePercent"),
            val(item, "combinedAdvanceRate"), item.get("judgement", ""),
            item.get("source", {}).get("name", ""), item.get("fetchedAt", ""), item.get("note", ""),
        ])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} US breadth history rows to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
