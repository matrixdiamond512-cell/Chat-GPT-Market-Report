#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "market" / "us-stock-breadth.json"
HISTORY = ROOT / "data" / "market" / "us-stock-breadth-history.json"
STOCKS = ROOT / "data" / "stocks.json"
URL = "https://scanner.tradingview.com/america/scan"


def scan(exchange: str) -> tuple[int, int]:
    payload = {
        "filter": [
            {"left": "exchange", "operation": "equal", "right": exchange},
            {"left": "type", "operation": "equal", "right": "stock"},
        ],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "high", "low", "High.52W", "Low.52W"],
        "range": [0, 10000],
    }
    body = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            req = Request(URL, data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 MarketReportBreadth/1.0"}, method="POST")
            with urlopen(req, timeout=40) as response:
                data = json.loads(response.read().decode("utf-8"))
            highs = lows = 0
            for row in data.get("data") or []:
                values = row.get("d") or []
                if len(values) < 5:
                    continue
                day_high, day_low, high52, low52 = values[1], values[2], values[3], values[4]
                if isinstance(day_high, (int, float)) and isinstance(high52, (int, float)) and high52:
                    if float(day_high) >= float(high52) * (1 - 1e-7):
                        highs += 1
                if isinstance(day_low, (int, float)) and isinstance(low52, (int, float)) and low52:
                    if float(day_low) <= float(low52) * (1 + 1e-7):
                        lows += 1
            return highs, lows
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{exchange} 52-week scan failed: {last_error}")


def update_stocks(stocks: dict[str, Any], payload: dict[str, Any]) -> None:
    rows = stocks.setdefault("marketInternals", {}).setdefault("us", {}).setdefault("rows", [])
    labels = {
        "NYSE 52週高値 / 安値": payload["exchanges"]["NYSE"],
        "NASDAQ 52週高値 / 安値": payload["exchanges"]["NASDAQ"],
    }
    for label, values in labels.items():
        display = f'{values["newHigh52Week"]:,} / {values["newLow52Week"]:,}'
        row = next((r for r in rows if isinstance(r, list) and r and r[0] == label), None)
        if row:
            while len(row) < 4:
                row.append("")
            row[1] = display
            row[2] = "-"
            row[3] = f'基準日 {payload["marketDate"]}'
        else:
            rows.append([label, display, "-", f'基準日 {payload["marketDate"]}'])
    stocks["usBreadth"] = payload


def main() -> int:
    payload = json.loads(LATEST.read_text(encoding="utf-8"))
    current = payload.get("current") if isinstance(payload.get("current"), dict) else payload
    if current.get("status") == "unavailable":
        print("US breadth is unavailable; 52-week correction skipped")
        return 0
    for exchange in ("NYSE", "NASDAQ"):
        highs, lows = scan(exchange)
        current["exchanges"][exchange]["newHigh52Week"] = highs
        current["exchanges"][exchange]["newLow52Week"] = lows
    current["note"] = "値上がり・値下がりは前日比change、52週高値・安値は当日高安と52週高安の一致で集計。"
    if isinstance(payload.get("current"), dict):
        payload["exchanges"] = current["exchanges"]
        payload["note"] = current["note"]
    else:
        payload = current
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    history = [payload if item.get("marketDate") == payload.get("marketDate") else item for item in history]
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if STOCKS.exists():
        stocks = json.loads(STOCKS.read_text(encoding="utf-8"))
        update_stocks(stocks, payload)
        STOCKS.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {"highs": payload["exchanges"][k]["newHigh52Week"], "lows": payload["exchanges"][k]["newLow52Week"]} for k in ("NYSE", "NASDAQ")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

