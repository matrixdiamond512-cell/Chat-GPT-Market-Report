#!/usr/bin/env python3
"""Create date-addressable stock-analysis snapshots for the WEB market report."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STOCKS_PATH = ROOT / "data" / "stocks.json"
SECTOR_PATH = ROOT / "data" / "sector-performance.json"
NIKKEI_PATH = ROOT / "data" / "nikkei-metrics.json"
HISTORY_DIR = ROOT / "data" / "history" / "stocks"
INDEX_PATH = HISTORY_DIR / "index.json"
JST = dt.timezone(dt.timedelta(hours=9))

METRIC_NAMES = [
    "日経VI",
    "日経225予想PER",
    "日経225予想EPS",
    "日経225 25日乖離率",
    "日経225 200日乖離率",
]


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def parse_snapshot_date(payload: dict[str, Any]) -> str:
    for value in (payload.get("updatedAt"), payload.get("generatedAt"), payload.get("dataAsOf")):
        match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", str(value or ""))
        if match:
            return "-".join(match.groups())
    return now_jst().date().isoformat()


def merge_sectors(stocks: dict[str, Any], sector_payload: dict[str, Any]) -> None:
    markets = sector_payload.get("markets") or {}
    sectors = stocks.setdefault("sectors", {})
    for key in ("us", "japan"):
        market = markets.get(key) or {}
        if not market:
            continue
        current = dict(sectors.get(key) or {})
        current.update({
            "title": market.get("title") or current.get("title") or "セクター・業種",
            "flag": market.get("flag") or current.get("flag") or ("US" if key == "us" else "JP"),
            "gainers": market.get("gainers") or [],
            "losers": market.get("losers") or [],
            "rows": market.get("gainers") or [],
            "dataAsOf": market.get("asOf") or "",
            "sourceLabel": market.get("sourceLabel") or "",
            "status": market.get("status") or "",
        })
        sectors[key] = current


def metric_row(name: str, nikkei_payload: dict[str, Any]) -> list[str]:
    item = (nikkei_payload.get("metrics") or {}).get(name) or {}
    return [
        name,
        str(item.get("display") or item.get("raw") or "取得不能"),
        str(item.get("change") or "—"),
        str(item.get("evaluation") or f"基準日 {nikkei_payload.get('dataAsOf') or '取得不能'}"),
    ]


def merge_nikkei_metrics(stocks: dict[str, Any], nikkei_payload: dict[str, Any]) -> None:
    if not (nikkei_payload.get("metrics") or {}):
        return
    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    rows = [
        row for row in (japan.get("rows") or [])
        if not (isinstance(row, list) and row and str(row[0]).strip() in METRIC_NAMES)
    ]

    vi_at = next(
        (index + 1 for index, row in enumerate(rows)
         if isinstance(row, list) and row and str(row[0]).strip() == "グロース250"),
        min(3, len(rows)),
    )
    rows.insert(vi_at, metric_row("日経VI", nikkei_payload))

    valuation = [metric_row(name, nikkei_payload) for name in METRIC_NAMES[1:]]
    valuation_at = next(
        (index + 1 for index, row in enumerate(rows)
         if isinstance(row, list) and row and str(row[0]).strip() == "騰落レシオ（25日）"),
        len(rows),
    )
    japan["rows"] = rows[:valuation_at] + valuation + rows[valuation_at:]
    stocks["nikkeiMetricsAsOf"] = nikkei_payload.get("dataAsOf") or ""


def write_index(snapshot_date: str, snapshot: dict[str, Any], generated_at: str) -> None:
    current = load_json(INDEX_PATH, {})
    entries = [item for item in (current.get("dates") or [])
               if isinstance(item, dict) and item.get("date") != snapshot_date]
    entries.append({
        "date": snapshot_date,
        "path": f"data/history/stocks/{snapshot_date}.json",
        "updatedAt": snapshot.get("updatedAt") or snapshot.get("generatedAt") or generated_at,
        "dataAsOf": snapshot.get("dataAsOf") or "",
    })
    entries.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    INDEX_PATH.write_text(json.dumps({
        "schemaVersion": "1.0.0",
        "generatedAt": generated_at,
        "latestDate": entries[0]["date"] if entries else snapshot_date,
        "dates": entries,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    stocks = load_json(STOCKS_PATH, {})
    if not stocks:
        raise SystemExit("data/stocks.json is missing or invalid")
    sector_payload = load_json(SECTOR_PATH, {})
    nikkei_payload = load_json(NIKKEI_PATH, {})
    merge_sectors(stocks, sector_payload)
    merge_nikkei_metrics(stocks, nikkei_payload)

    generated_at = now_jst().isoformat()
    snapshot_date = parse_snapshot_date(stocks)
    stocks["historyDate"] = snapshot_date
    stocks["historyGeneratedAt"] = generated_at
    stocks["isHistorySnapshot"] = True

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    output_path = HISTORY_DIR / f"{snapshot_date}.json"
    output_path.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(snapshot_date, stocks, generated_at)
    print(json.dumps({
        "snapshotDate": snapshot_date,
        "output": str(output_path.relative_to(ROOT)),
        "index": str(INDEX_PATH.relative_to(ROOT)),
        "sectorMarkets": sorted((sector_payload.get("markets") or {}).keys()),
        "nikkeiMetrics": sorted((nikkei_payload.get("metrics") or {}).keys()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
