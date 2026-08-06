#!/usr/bin/env python3
"""Archive the stock-analysis page with independent U.S. and Japan data dates.

One calendar page may legitimately contain different market dates. For example,
a Tokyo-close update keeps the previous U.S. session, while the next morning's
U.S. update keeps the previous Tokyo session. The archive therefore stores both
market dates explicitly and never rewrites the untouched market with newer data.
"""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
HISTORY_DIR = ROOT / "data" / "history" / "stocks"
INDEX_PATH = HISTORY_DIR / "index.json"
JST = timezone(timedelta(hours=9))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKET_KEYS = ("us", "japan")
SECTION_KEYS = ("marketInternals", "movers", "sectors", "contributions")


def valid_date(value: Any) -> str:
    text = str(value or "").strip()[:10]
    return text if DATE_RE.fullmatch(text) else ""


def infer_market_date(stocks: dict[str, Any], key: str) -> str:
    dates = stocks.get("marketDates") or {}
    if key == "us":
        candidates = [
            dates.get("us"),
            ((stocks.get("marketInternals") or {}).get("us") or {}).get("dataDate"),
            (stocks.get("usBreadth") or {}).get("marketDate"),
        ]
    else:
        candidates = [
            dates.get("japan"),
            ((stocks.get("marketInternals") or {}).get("japan") or {}).get("dataDate"),
            stocks.get("nikkeiMetricsAsOf"),
        ]
    for candidate in candidates:
        date_text = valid_date(candidate)
        if date_text:
            return date_text
    return ""


def market_table(stocks: dict[str, Any], key: str) -> dict[str, Any]:
    return ((stocks.get("marketInternals") or {}).get(key) or {})


def validate_market(stocks: dict[str, Any], key: str, date_text: str) -> None:
    if not date_text:
        raise RuntimeError(f"{key}: market data date is missing")
    rows = market_table(stocks, key).get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"{key}: market table is empty")
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            raise RuntimeError(f"{key}: invalid market table row: {row!r}")


def preserve_newer_market(
    snapshot: dict[str, Any], existing: dict[str, Any], key: str
) -> None:
    new_date = valid_date((snapshot.get("marketDates") or {}).get(key))
    old_date = valid_date((existing.get("marketDates") or {}).get(key))
    if not old_date or not new_date or new_date >= old_date:
        return

    for section in SECTION_KEYS:
        old_section = existing.get(section) or {}
        if key in old_section:
            snapshot.setdefault(section, {})[key] = copy.deepcopy(old_section[key])
    snapshot.setdefault("marketDates", {})[key] = old_date
    old_updated = (existing.get("marketUpdatedAt") or {}).get(key)
    if old_updated:
        snapshot.setdefault("marketUpdatedAt", {})[key] = old_updated
    if key == "us" and existing.get("usBreadth"):
        snapshot["usBreadth"] = copy.deepcopy(existing["usBreadth"])


def update_index(snapshot_date: str, snapshot: dict[str, Any], saved_at: str) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if not isinstance(index, dict):
            index = {}
    except Exception:
        index = {}

    existing_entries = index.get("dates") or []
    entries: list[dict[str, Any]] = []
    for item in existing_entries:
        if isinstance(item, str):
            item = {"date": item}
        if isinstance(item, dict) and valid_date(item.get("date")) != snapshot_date:
            entries.append(item)

    market_dates = snapshot.get("marketDates") or {}
    entries.append({
        "date": snapshot_date,
        "savedAt": saved_at,
        "usDataDate": market_dates.get("us", ""),
        "japanDataDate": market_dates.get("japan", ""),
        "label": (
            f"米国 {market_dates.get('us', '取得不能')} / "
            f"東京 {market_dates.get('japan', '取得不能')}"
        ),
    })
    entries.sort(key=lambda item: str(item.get("date", "")), reverse=True)

    index.update({
        "schemaVersion": "2.0.0",
        "latestDate": entries[0]["date"] if entries else snapshot_date,
        "updatedAt": saved_at,
        "policy": "independent-market-session-dates",
        "dates": entries,
    })
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def archive_snapshot(
    stocks_path: Path = STOCKS_PATH,
    snapshot_date: str | None = None,
) -> Path:
    now = datetime.now(JST).replace(microsecond=0)
    saved_at = now.isoformat()
    page_date = valid_date(snapshot_date or os.getenv("STOCKS_SNAPSHOT_DATE") or now.date().isoformat())
    if not page_date:
        raise RuntimeError("snapshot date is invalid")

    stocks = json.loads(stocks_path.read_text(encoding="utf-8"))
    market_dates = {
        key: infer_market_date(stocks, key)
        for key in MARKET_KEYS
    }
    for key, date_text in market_dates.items():
        validate_market(stocks, key, date_text)

    snapshot = copy.deepcopy(stocks)
    snapshot["schemaVersion"] = "2.0.0"
    snapshot["snapshotDate"] = page_date
    snapshot["savedAt"] = saved_at
    snapshot["marketDates"] = market_dates
    snapshot.setdefault("marketUpdatedAt", {})
    snapshot["snapshotPolicy"] = {
        "type": "independent-market-session-dates",
        "description": (
            "米国市場と東京市場は、それぞれの取引終了後に独立更新。"
            "未更新側は直前の確定データを保持する。"
        ),
    }

    for key in MARKET_KEYS:
        panel = snapshot.setdefault("marketInternals", {}).setdefault(key, {})
        panel["dataDate"] = market_dates[key]

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    output_path = HISTORY_DIR / f"{page_date}.json"
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                for key in MARKET_KEYS:
                    preserve_newer_market(snapshot, existing, key)
        except Exception:
            pass

    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    update_index(page_date, snapshot, saved_at)
    return output_path


def main() -> int:
    path = archive_snapshot()
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
