#!/usr/bin/env python3
"""Backfill missing US sector ranking history from 11 actual ETF daily closes.

Only dates with 11 independently sourced ETF returns may be reconstructed.
No assumptions about missing market days, no forward fill, no rank mixing and
no overwrite of already-populated rows or formulas. Requires Sheets editor.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import sys
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_sector_performance import US_SECTORS, request_bytes, request_json  # noqa: E402
from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info  # noqa: E402

SHEET = "終値一覧"
OUT = ROOT / "data" / "market" / "us-sector-history-backfill.json"
JST = dt.timezone(dt.timedelta(hours=9))
NEW_YORK = ZoneInfo("America/New_York")


def yahoo_closes(symbol: str) -> tuple[dict[str, float], str]:
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol)
           + "?range=6mo&interval=1d&events=history&includeAdjustedClose=true")
    result = request_json(url)["chart"]["result"][0]
    times = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    adjusted = ((indicators.get("adjclose") or [{}])[0].get("adjclose") or [])
    quotes = ((indicators.get("quote") or [{}])[0].get("close") or [])
    selected = adjusted if adjusted and len(adjusted) == len(times) else quotes
    values: dict[str, float] = {}
    for ts, price in zip(times, selected):
        if price is None or not math.isfinite(float(price)) or float(price) <= 0:
            continue
        date = dt.datetime.fromtimestamp(int(ts), NEW_YORK).date()
        if date.weekday() >= 5:
            continue
        values[date.isoformat()] = float(price)
    if len(values) < 10:
        raise ValueError(f"{symbol}: fewer than 10 daily closes")
    return values, url


def stooq_closes(symbol: str) -> tuple[dict[str, float], str]:
    end = dt.datetime.now(dt.timezone.utc).date()
    start = end - dt.timedelta(days=195)
    url = (f"https://stooq.com/q/d/l/?s={symbol.lower()}.us"
           f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")
    text = request_bytes(url).decode("utf-8-sig")
    values: dict[str, float] = {}
    for item in csv.DictReader(io.StringIO(text)):
        try:
            date = dt.date.fromisoformat(item["Date"])
            close = float(item["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if date.weekday() < 5 and math.isfinite(close) and close > 0:
            values[date.isoformat()] = close
    if len(values) < 10:
        raise ValueError(f"{symbol}: Stooq fewer than 10 daily closes")
    return values, url


def returns_from_closes(prices: dict[str, float]) -> dict[str, float]:
    days = sorted(prices)
    result = {}
    for previous, current in zip(days, days[1:]):
        gap = (dt.date.fromisoformat(current) - dt.date.fromisoformat(previous)).days
        if gap > 7 or prices[previous] <= 0:
            continue
        result[current] = round(prices[current] / prices[previous] - 1.0, 9)
    return result


def complete_market_days(series: dict[str, dict[str, float]]) -> dict[str, list[tuple[str, float]]]:
    if set(series) != set(US_SECTORS):
        return {}
    all_dates = set.intersection(*(set(s) for s in series.values()))
    days = {}
    for date in sorted(all_dates):
        if dt.date.fromisoformat(date).weekday() >= 5:
            continue
        items = [(symbol, series[symbol][date]) for symbol in US_SECTORS]
        if len(items) != 11 or not all(math.isfinite(v) and abs(v) < 0.4 for _, v in items):
            continue
        days[date] = sorted(items, key=lambda x: (-x[1], x[0]))
    return days


def make_plan(values: list[list[object]], markets: dict[str, list[tuple[str, float]]]) -> list[dict]:
    if not values or not values[0] or values[0][0] != "日付":
        raise ValueError("終値一覧の日付ヘッダーが見つかりません")
    headers = {str(v): j for j, v in enumerate(values[0])}
    names = [f"米国セクター{direction}{index}{suffix}"
             for direction in ("上昇", "下落")
             for index in range(1, 6)
             for suffix in ("業種", "騰落率")]
    if any(name not in headers for name in names):
        raise ValueError("米国セクター列が不足しています")
    result = []
    seen = set()
    for row_number, row in enumerate(values[1:], start=2):
        date = str(row[0] if row else "").replace("/", "-")[:10]
        if date in seen:
            raise ValueError("終値一覧の日付が重複: " + date)
        seen.add(date)
        ranked = markets.get(date)
        if ranked is None:
            continue
        old = [str(row[headers[name]]) if len(row) > headers[name] else "" for name in names]
        # All 20 empty: safe. Partially filled: do not merge different ranks.
        if any(old):
            continue
        winning = ranked[:5]
        losing = list(reversed(ranked[-5:]))
        pairs = []
        for direction, items in (("上昇", winning), ("下落", losing)):
            for i, (symbol, change) in enumerate(items, 1):
                prefix = f"米国セクター{direction}{i}"
                pairs += [
                    (prefix + "業種", f"{US_SECTORS[symbol]}（{symbol}）"),
                    (prefix + "騰落率", change),
                ]
        for name, val in pairs:
            result.append({"row": row_number, "column": headers[name] + 1, "date": date, "header": name, "value": val})
        # Other market's common metadata is preserved. US-specific provenance
        # is safe to write only when it has not already been populated.
        source_name = "米国セクター取得元"
        idx = headers.get(source_name)
        if idx is not None and (len(row) <= idx or not str(row[idx])):
            result.append({"row": row_number, "column": idx + 1, "date": date,
                           "header": source_name, "value": "Yahoo Finance/ Stooq 11 US Sector ETFs (daily close)"})
    return result


def column_letter(n: int) -> str:
    word = ""
    while n:
        n, r = divmod(n - 1, 26)
        word = chr(65 + r) + word
    return word


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write blanks after validation (default: dry-run)")
    args = parser.parse_args()
    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    receipt = {"status": "SOURCE_UNAVAILABLE", "checkedAt": now, "sourceSymbols": 0,
               "candidateDates": 0, "planned": 0, "written": 0, "readBack": 0}
    try:
        series = {}
        sources = {}
        errors = {}
        for symbol in US_SECTORS:
            try:
                prices, url = yahoo_closes(symbol)
            except Exception as e:
                try:
                    prices, url = stooq_closes(symbol)
                except Exception as other:
                    errors[symbol] = f"Yahoo {str(e)[:130]}; Stooq {str(other)[:130]}"
                    continue
            series[symbol] = returns_from_closes(prices)
            sources[symbol] = url
        receipt["sourceSymbols"] = len(series)
        receipt["sources"] = sources
        receipt["errors"] = errors
        days = complete_market_days(series)
        receipt["candidateDates"] = len(days)
        if not days:
            raise ValueError("11銘柄の日付一致・有効な過去騰落率を取得できません")
        account = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        spreadsheet_id = os.environ["MARKET_DATA_SPREADSHEET_ID"]
        client = SheetsClient(create_authorized_session(load_service_account_info(account)), spreadsheet_id)
        endpoint = client.base_url + "/values/" + client._range(SHEET, "A1:GD250") + "?valueRenderOption=FORMULA"
        sheet = client._request("GET", endpoint).get("values") or []
        plan = make_plan(sheet, days)
        receipt["planned"] = len(plan)
        receipt["matchedDays"] = len({p["date"] for p in plan})
        receipt["status"] = "DRY_RUN"
        if args.apply and plan:
            for start in range(0, len(plan), 80):
                batch = plan[start:start + 80]
                payload = {"valueInputOption": "RAW", "data": [
                    {"range": f"'{SHEET}'!{column_letter(item['column'])}{item['row']}",
                     "values": [[item["value"]]]} for item in batch]}
                response = client._request("POST", client.base_url + "/values:batchUpdate", json=payload)
                actual = int(response.get("totalUpdatedCells") or 0)
                if actual != len(batch):
                    raise RuntimeError(f"Partial Sheet update {actual}/{len(batch)}")
                receipt["written"] += actual
            # Force percentage format on only the newly populated numeric cells.
            meta = client.sheet_map()
            formatting = [
                {"repeatCell": {
                    "range": {"sheetId": meta[SHEET],
                              "startRowIndex": item["row"] - 1,
                              "endRowIndex": item["row"],
                              "startColumnIndex": item["column"] - 1,
                              "endColumnIndex": item["column"]},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "+0.00%;-0.00%;0.00%"}}},
                    "fields": "userEnteredFormat.numberFormat"}}
                for item in plan if item["header"].endswith("騰落率")
            ]
            for start in range(0, len(formatting), 80):
                client._request("POST", client.base_url + ":batchUpdate", json={"requests": formatting[start:start + 80]})
            verified = client._request("GET", endpoint).get("values") or []
            for item in plan:
                row, col = item["row"] - 1, item["column"] - 1
                value = verified[row][col] if len(verified) > row and len(verified[row]) > col else None
                if isinstance(item["value"], float):
                    if not isinstance(value, (float, int)) or abs(float(value) - item["value"]) > 1e-7:
                        raise RuntimeError(f"Readback mismatch for {item['date']} {item['header']}")
                elif str(value) != str(item["value"]):
                    raise RuntimeError(f"Readback mismatch for {item['date']} {item['header']}")
            receipt["readBack"] = len(plan)
            receipt["status"] = "APPLIED"
        elif args.apply:
            receipt["status"] = "NO_NEW_DATA"
    except Exception as err:
        receipt["status"] = "BLOCKED"
        receipt["reason"] = str(err).splitlines()[0][:300]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt.get(k) for k in ("status", "sourceSymbols", "candidateDates", "planned", "written", "readBack", "reason")}, ensure_ascii=False))
    return 2 if receipt["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
