"""Fill historical BOJ volume dates from real Dukascopy USDJPY daily BID OHLC.

The Dukascopy d1 bars are UTC-session bid candles, not Tokyo BOJ volume
quotes or Yahoo day-boundary prices. No interpolation; never replace a
complete daily OHLC record. Keep per-day source IDs for provenance.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import update_usdjpy_volume_prices as core

SOURCE_ID = "DUKASCOPY_USDJPY_D1_UTC_BID"
SOURCE_URL = "https://www.dukascopy-node.app/instrument/usdjpy"
FIELDS = ("open", "high", "low", "close")


def read_candles(paths: list[Path]) -> dict[str, dict]:
    candles: dict[str, dict] = {}
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            if not rows.fieldnames or not set(("timestamp", *FIELDS)).issubset(rows.fieldnames):
                continue
            for raw in rows:
                try:
                    day = datetime.fromtimestamp(int(raw["timestamp"]) / 1000, timezone.utc).date().isoformat()
                    candle = {k: round(float(raw[k]), 4) for k in FIELDS}
                except (ValueError, TypeError, OverflowError, OSError):
                    continue
                if (not all(math.isfinite(v) and 50 <= v <= 300 for v in candle.values())
                    or candle["high"] < max(candle["open"], candle["close"])
                    or candle["low"] > min(candle["open"], candle["close"])):
                    continue
                candles[day] = {"date": day, **candle}
    return candles


def fill(data: dict, candles: dict[str, dict]) -> tuple[int, list[str]]:
    records = data["records"]
    ordered = sorted(candles)
    changes = {
        day: round((candles[day]["close"] / candles[ordered[i - 1]]["close"] - 1) * 100, 2)
        for i, day in enumerate(ordered) if i > 0 and candles[ordered[i - 1]]["close"]
    }
    filled = 0
    for row in records:
        day = row["targetDate"]
        candle = candles.get(day)
        if not candle or any(row.get(field) is not None for field in FIELDS):
            continue
        for field in FIELDS:
            row[field] = candle[field]
        row["priceChangePct"] = changes.get(day)
        row["priceSourceId"] = SOURCE_ID
        filled += 1
    prices = {r["date"]: r for r in data.get("priceRecords", []) if r.get("date")}
    for row in records:
        if all(row.get(k) is not None for k in FIELDS):
            day = row["targetDate"]
            prices[day] = {"date": day, **{k: row.get(k) for k in (*FIELDS, "priceChangePct", "priceSourceId")}}
    data["priceRecords"] = sorted(prices.values(), key=lambda p: p["date"], reverse=True)
    valid = sorted(r["targetDate"] for r in records if all(r.get(k) is not None for k in FIELDS))
    data["priceRange"] = {
        "startDate": valid[0] if valid else None,
        "endDate": valid[-1] if valid else None,
        "count": len(valid),
    }
    return filled, valid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--json-path", type=Path, default=core.PATH)
    args = parser.parse_args()
    paths = sorted(args.csv_dir.glob("*.csv"))
    if not paths:
        raise SystemExit("Dukascopy historical USDJPY CSV file was not found")
    candles = read_candles(paths)
    if not candles:
        raise SystemExit("Dukascopy CSV returned no validated USDJPY daily OHLC bars")
    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    data = payload["data"]
    before = {r["targetDate"]: r.get("close") for r in data["records"]}
    filled, valid = fill(data, candles)
    records = data["records"]
    if any(r.get("close") != prior for r in records if (prior := before[r["targetDate"]]) is not None):
        raise SystemExit("Existing USDJPY daily close was altered; refuse to publish")
    still_missing = sorted(r["targetDate"] for r in records if any(r.get(k) is None for k in FIELDS))
    pct_missing = sorted(r["targetDate"] for r in records if r.get("priceChangePct") is None)
    acquisition = data.setdefault("priceAcquisition", {})
    acquisition["checkedAtDukascopy"] = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    acquisition["filledMissingDates"] = int(acquisition.get("filledMissingDates") or 0) + filled
    provider_counts = acquisition.setdefault("filledByProvider", {})
    provider_counts[SOURCE_ID] = filled
    acquisition["missingAllDates"] = still_missing
    acquisition["missingPriceChangePctDates"] = pct_missing
    acquisition["missingLast20Dates"] = [r["targetDate"] for r in records[:20]
                                        if any(r.get(k) is None for k in FIELDS)]
    acquisition["note"] = "Dukascopy UTC日足BID価格と、Yahoo日足・日銀出来高は時刻区切りが異なる。各日付に出典を記録。"
    component = payload.setdefault("components", {}).setdefault("usdjpyOhlc", {})
    component["status"] = "ok" if not still_missing else "partial"
    component["missingHistoricalDates"] = still_missing
    component["missingLast20Dates"] = acquisition["missingLast20Dates"]
    component["latestDate"] = valid[-1] if valid else None
    if filled:
        data["priceSourceName"] = (str(data.get("priceSourceName") or "") +
                                   "／Dukascopy USDJPY UTC日足BID（古い欠損日の補完）")
    sources = payload.setdefault("sources", [])
    sources[:] = [s for s in sources if s.get("id") != SOURCE_ID]
    if any(r.get("priceSourceId") == SOURCE_ID for r in records):
        sourced_dates = sorted(r["targetDate"] for r in records if r.get("priceSourceId") == SOURCE_ID)
        sources.append({
            "id": SOURCE_ID, "name": "Dukascopy USDJPY d1 bid OHLC (UTC)",
            "url": SOURCE_URL, "asOf": sourced_dates[-1], "status": "ok",
            "fields": [*FIELDS, "priceChangePct"],
            "note": "価格はUTC基準のBID日足。日銀東京市場出来高・Yahoo等の時間帯とは異なる。"
        })
    args.json_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "dukaCandles": len(candles), "filledDukascopy": filled,
        "totalBOJRecords": len(records), "completeOHLC": len(valid),
        "stillMissingOHLC": still_missing, "missingPct": pct_missing,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
