#!/usr/bin/env python3
"""Export the Tokyo main table with current and permanent snapshot payloads."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
OUTPUT_PATH = ROOT / "data" / "market" / "tokyo-stock-table.json"
HISTORY_DIR = ROOT / "data" / "history" / "stocks"
INDEX_PATH = HISTORY_DIR / "index.json"
JST = timezone(timedelta(hours=9))


def main() -> int:
    now = datetime.now(JST).replace(microsecond=0)
    snapshot_date = now.date().isoformat()
    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    table = ((stocks.get("marketInternals") or {}).get("japan") or {})
    dates = stocks.get("marketDates") or {}
    data_date = str(dates.get("japan") or table.get("dataDate") or "")[:10]
    us_date = str(dates.get("us") or ((stocks.get("marketInternals") or {}).get("us") or {}).get("dataDate") or "")[:10]
    if len(data_date) != 10 or not table.get("rows"):
        raise SystemExit("Tokyo table or data date is missing")
    if len(us_date) != 10:
        raise SystemExit("U.S. market date is missing")

    payload = {
        "schemaVersion": "1.0.0",
        "market": "japan",
        "snapshotDate": snapshot_date,
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

    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")

    overlay_path = HISTORY_DIR / "overlays" / f"{snapshot_date}-japan.json"
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(content, encoding="utf-8")

    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if not isinstance(index, dict):
            index = {}
    except Exception:
        index = {}
    entries = index.get("dates") or []
    entries = [item if isinstance(item, dict) else {"date": item} for item in entries]
    entry = next((item for item in entries if item.get("date") == snapshot_date), None)
    if entry is None:
        entry = {"date": snapshot_date}
        entries.append(entry)
    entry.update({
        "savedAt": now.isoformat(),
        "usDataDate": us_date,
        "japanDataDate": data_date,
        "label": f"米国 {us_date} / 東京 {data_date}",
        "japanOverlay": f"data/history/stocks/overlays/{snapshot_date}-japan.json",
    })
    entries.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    index.update({
        "schemaVersion": "2.0.0",
        "latestDate": entries[0]["date"],
        "updatedAt": now.isoformat(),
        "policy": "independent-market-session-dates",
        "dates": entries,
    })
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(OUTPUT_PATH.relative_to(ROOT))
    print(overlay_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
