#!/usr/bin/env python3
"""Create stock-analysis history without mixing U.S. and Tokyo session dates."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from archive_stocks_snapshot import archive_snapshot, infer_market_date

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
SECTOR_PATH = ROOT / "data" / "sector-performance.json"
NIKKEI_PATH = ROOT / "data" / "nikkei-metrics.json"

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


def sector_date(market: dict[str, Any]) -> str:
    return str(market.get("dataAsOf") or market.get("asOf") or "")[:10]


def merge_matching_sectors(stocks: dict[str, Any], sector_payload: dict[str, Any]) -> None:
    markets = sector_payload.get("markets") or {}
    sectors = stocks.setdefault("sectors", {})
    for key in ("us", "japan"):
        market = markets.get(key) or {}
        expected_date = infer_market_date(stocks, key)
        if not market or sector_date(market) != expected_date:
            continue
        current = dict(sectors.get(key) or {})
        current.update({
            "title": market.get("title") or current.get("title") or "セクター・業種",
            "flag": market.get("flag") or current.get("flag") or ("US" if key == "us" else "JP"),
            "gainers": market.get("gainers") or [],
            "losers": market.get("losers") or [],
            "rows": market.get("gainers") or [],
            "dataAsOf": expected_date,
            "sourceLabel": market.get("sourceLabel") or "",
            "status": market.get("status") or "",
        })
        sectors[key] = current


def metric_row(name: str, payload: dict[str, Any]) -> list[str]:
    item = (payload.get("metrics") or {}).get(name) or {}
    date_text = str(payload.get("dataAsOf") or "")[:10]
    evaluation = str(item.get("evaluation") or "").strip()
    if date_text and date_text not in evaluation:
        evaluation = (evaluation + " " if evaluation else "") + f"基準日 {date_text}。"
    return [
        name,
        str(item.get("display") or item.get("raw") or "取得不能"),
        str(item.get("change") or "—"),
        evaluation or f"基準日 {date_text or '取得不能'}。",
    ]


def merge_matching_nikkei(stocks: dict[str, Any], payload: dict[str, Any]) -> None:
    data_date = str(payload.get("dataAsOf") or "")[:10]
    if not payload.get("metrics") or data_date != infer_market_date(stocks, "japan"):
        return
    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    rows = [
        row for row in (japan.get("rows") or [])
        if not (isinstance(row, list) and row and str(row[0]).strip() in METRIC_NAMES)
    ]
    vi_at = next(
        (i + 1 for i, row in enumerate(rows)
         if isinstance(row, list) and row and str(row[0]).strip() == "グロース250"),
        min(3, len(rows)),
    )
    rows.insert(vi_at, metric_row("日経VI", payload))
    valuation = [metric_row(name, payload) for name in METRIC_NAMES[1:]]
    valuation_at = next(
        (i + 1 for i, row in enumerate(rows)
         if isinstance(row, list) and row and str(row[0]).strip() == "騰落レシオ（25日）"),
        len(rows),
    )
    japan["rows"] = rows[:valuation_at] + valuation + rows[valuation_at:]
    stocks["nikkeiMetricsAsOf"] = data_date


def main() -> int:
    stocks = load_json(STOCKS_PATH, {})
    if not stocks:
        raise SystemExit("data/stocks.json is missing or invalid")

    merge_matching_sectors(stocks, load_json(SECTOR_PATH, {}))
    merge_matching_nikkei(stocks, load_json(NIKKEI_PATH, {}))

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        temp_path = Path(handle.name)
        json.dump(stocks, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        output = archive_snapshot(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    print(json.dumps({
        "snapshot": str(output.relative_to(ROOT)),
        "marketDates": stocks.get("marketDates") or {},
        "policy": "independent-market-session-dates",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
