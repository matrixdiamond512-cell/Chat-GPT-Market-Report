#!/usr/bin/env python3
"""Build the 12-column Gold_Demand CSV consumed directly by Google Sheets."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from write_gold_supply_demand_to_sheets import GOLD_JSON, MARKET_JSON, HEADERS, build_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "gold-supply-demand-sheet.csv"

STATUS_JA = {
    "verified": "確認済み",
    "stale": "前回確認値",
    "unavailable": "取得待ち",
    "calculated": "計算値",
    "fallback": "前回確認値",
}


def main() -> int:
    gold = json.loads(Path(GOLD_JSON).read_text(encoding="utf-8"))
    market = json.loads(Path(MARKET_JSON).read_text(encoding="utf-8"))
    rows = build_rows(gold, market)

    normalized = []
    for raw in rows:
        row = list(raw)
        # Column I (zero-based 8) is the visible status field.
        if len(row) > 8:
            row[8] = STATUS_JA.get(str(row[8]), row[8])
        # A blank China/India premium is not a prior confirmed numeric value.
        if len(row) > 8 and row[0] == "中国・インド現物需要" and row[2] in (None, ""):
            row[8] = "取得待ち"
        # Keep the central-bank reference as a month label, not a Sheets date serial.
        if len(row) > 5 and row[0] == "中央銀行":
            period = str(row[5] or "")
            if len(period) == 7 and period[4] == "-":
                row[5] = f"{period[:4]}年{int(period[5:7])}月"
        normalized.append(row)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(HEADERS)
        writer.writerows(normalized)

    print(json.dumps({
        "output": str(OUT.relative_to(ROOT)),
        "rows": len(normalized),
        "columns": len(HEADERS),
        "generatedAt": gold.get("generatedAt"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
