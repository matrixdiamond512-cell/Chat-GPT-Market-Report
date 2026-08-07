#!/usr/bin/env python3
"""Export the Tokyo main table as a small independently dated payload."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
OUTPUT_PATH = ROOT / "data" / "market" / "tokyo-stock-table.json"
JST = timezone(timedelta(hours=9))


def main() -> int:
    now = datetime.now(JST).replace(microsecond=0)
    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    table = ((stocks.get("marketInternals") or {}).get("japan") or {})
    data_date = str((stocks.get("marketDates") or {}).get("japan") or table.get("dataDate") or "")[:10]
    if len(data_date) != 10 or not table.get("rows"):
        raise SystemExit("Tokyo table or data date is missing")
    payload = {
        "schemaVersion": "1.0.0",
        "market": "japan",
        "snapshotDate": now.date().isoformat(),
        "dataDate": data_date,
        "fetchedAt": str((stocks.get("marketUpdatedAt") or {}).get("japan") or table.get("updatedAt") or now.isoformat()),
        "status": "verified",
        "source": {
            "name": "マーケットレポート終値一覧2026",
            "sheet": "終値一覧",
            "rowDate": data_date.replace("-", "/"),
        },
        "table": table,
        "note": "東京市場だけを更新し、米国市場の確定済みデータと基準日は変更しない。",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
