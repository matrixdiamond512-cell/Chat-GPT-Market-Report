#!/usr/bin/env python3
"""Reconstruct blank Tokyo 33-sector ranked history from Kabutan daily index closes.

Fail closed: 33 independent dated sector index histories, consecutive-session
returns, no forward fill, no date reassignment, no writes to partially filled
or existing rankings, and a readback receipt for every cell written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_sector_performance import JP_SECTORS, request_bytes  # noqa: E402
from sheet_date_utils import parse_sheet_market_date  # noqa: E402
from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info  # noqa: E402

OUT = ROOT / "data" / "market" / "jp-sector-history-backfill.json"
SHEET = "終値一覧"
JST = dt.timezone(dt.timedelta(hours=9))
BASE_URL = "https://s.kabutan.jp/stocks/{code}/historical_prices/daily/?page={page}"
MAX_PAGES = 4


def parse_kabutan_daily(html: str, *, reference_date: dt.date) -> dict[str, float]:
    """Parse daily close rows only. Never treat a headline live quote as a close."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    records: dict[str, float] = {}
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).replace(" ", "") for th in table.find_all("th")]
        if not ("日付" in headers and "終値" in headers):
            continue
        for tr in table.find_all("tr"):
            cells = [z.get_text(" ", strip=True) for z in tr.find_all(["th", "td"])]
            if len(cells) < 7:
                continue
            match = re.fullmatch(r"(\d{1,4})/(\d{1,2})(?:/(\d{1,2}))?", cells[0].strip())
            if not match:
                continue
            if match.group(3):
                year, month, day = map(int, match.groups())
            else:
                month, day = int(match.group(1)), int(match.group(2))
                year = reference_date.year - (1 if month > reference_date.month + 1 else 0)
            try:
                market_date = dt.date(year, month, day)
                close = float(cells[4].replace(",", ""))
            except (ValueError, TypeError):
                continue
            if market_date > reference_date or market_date.weekday() >= 5:
                continue
            if not math.isfinite(close) or close <= 0:
                continue
            date = market_date.isoformat()
            if date in records and abs(records[date] - close) > 1e-6:
                raise ValueError(f"Conflicting closes for {date}")
            records[date] = close
    if not records:
        raise ValueError("No dated daily-index closing-price rows parsed")
    return records


def fetch_kabutan_sector_history(
    code: str, reference_date: dt.date, pages: int = MAX_PAGES,
    *, sleep_seconds: float = .20,
) -> tuple[dict[str, float], list[str]]:
    all_prices: dict[str, float] = {}
    urls = []
    for page in range(1, pages + 1):
        url = BASE_URL.format(code=code, page=page)
        html = request_bytes(url).decode("utf-8", errors="replace")
        records = parse_kabutan_daily(html, reference_date=reference_date)
        for day, close in records.items():
            if day in all_prices and abs(all_prices[day] - close) > 1e-6:
                raise ValueError(f"{code}: inconsistent page close on {day}")
            all_prices[day] = close
        urls.append(url)
        time.sleep(sleep_seconds)
    if len(all_prices) < 30:
        raise ValueError(f"{code}: only {len(all_prices)} dated daily closes")
    return all_prices, urls


def daily_returns(prices: dict[str, float]) -> dict[str, float]:
    ordered = sorted(prices)
    out = {}
    for before, after in zip(ordered, ordered[1:]):
        gap = (dt.date.fromisoformat(after) - dt.date.fromisoformat(before)).days
        if 1 <= gap <= 7 and prices[before] > 0:
            out[after] = round(prices[after] / prices[before] - 1, 9)
    return out


def complete_33_sector_rankings(data: dict[str, dict[str, float]]) -> dict[str, list[tuple[str, float]]]:
    if set(data) != set(JP_SECTORS):
        return {}
    common = set.intersection(*(set(series) for series in data.values()))
    rankings = {}
    for date in sorted(common):
        if dt.date.fromisoformat(date).weekday() >= 5:
            continue
        items = [(code, data[code][date]) for code in JP_SECTORS]
        if len(items) == 33 and all(math.isfinite(value) and abs(value) < .30 for _, value in items):
            rankings[date] = sorted(items, key=lambda x: (-x[1], x[0]))
    return rankings


def plan_blank_days(
    sheet: list[list[Any]], rankings: dict[str, list[tuple[str, float]]]
) -> list[dict[str, Any]]:
    if not sheet or not sheet[0] or sheet[0][0] != "日付":
        raise ValueError("Sheet header 日付 missing")
    headers = {str(h): i for i, h in enumerate(sheet[0]) if h}
    names = [
        f"東京業種{side}{i}{suffix}"
        for side in ("上昇", "下落")
        for i in range(1, 6)
        for suffix in ("業種", "騰落率")
    ]
    if any(x not in headers for x in names):
        raise ValueError("Missing Tokyo sector ranking columns")
    planned: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for row_num, row in enumerate(sheet[1:], start=2):
        date = parse_sheet_market_date(row[0]) if row else None
        if not date:
            continue
        if date in seen_dates:
            raise ValueError("Duplicate target Sheet date " + date)
        seen_dates.add(date)
        ranking = rankings.get(date)
        if ranking is None:
            continue
        # Mixing rankings from multiple calculation sources violates integrity:
        # apply only when the complete 20-cell group is blank.
        if any(len(row) > headers[h] and str(row[headers[h]]).strip() for h in names):
            continue
        winners, losers = ranking[:5], list(reversed(ranking[-5:]))
        for side, ranked in (("上昇", winners), ("下落", losers)):
            for i, (code, change) in enumerate(ranked, start=1):
                label = f"東京業種{side}{i}"
                for suffix, value in (("業種", JP_SECTORS[code]), ("騰落率", change)):
                    header = label + suffix
                    planned.append({
                        "row": row_num, "column": headers[header] + 1,
                        "date": date, "header": header, "value": value,
                    })
        meta = "東京業種取得元"
        idx = headers.get(meta)
        if idx is not None and (len(row) <= idx or not str(row[idx]).strip()):
            planned.append({
                "row": row_num, "column": idx + 1, "date": date, "header": meta,
                "value": "株探 東証33業種別指数 日次時系列終値 0251-0283（計算）",
            })
    return planned


def column_letter(n: int) -> str:
    text = ""
    while n:
        n, rem = divmod(n - 1, 26)
        text = chr(65 + rem) + text
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write blanks only (default dry-run)")
    parser.add_argument("--pages", type=int, default=MAX_PAGES, choices=(2, 3, 4))
    args = parser.parse_args()
    now = dt.datetime.now(JST).replace(microsecond=0)
    receipt: dict[str, Any] = {
        "status": "SOURCE_UNAVAILABLE", "checkedAt": now.isoformat(),
        "indexCount": 0, "candidateDates": 0, "planned": 0,
        "written": 0, "readBack": 0,
    }
    try:
        source_dates = {}
        source_errors = {}
        all_returns = {}
        today = now.date()
        for code in JP_SECTORS:
            try:
                closes, _urls = fetch_kabutan_sector_history(code, today, args.pages)
                all_returns[code] = daily_returns(closes)
                source_dates[code] = {"first": min(closes), "last": max(closes), "count": len(closes)}
            except Exception as error:
                source_errors[code] = str(error)[:200]
        receipt["indexCount"] = len(all_returns)
        receipt["indexDateRanges"] = source_dates
        receipt["errors"] = source_errors
        rankings = complete_33_sector_rankings(all_returns)
        receipt["candidateDates"] = len(rankings)
        if rankings:
            receipt["earliestCompleteDate"] = min(rankings)
            receipt["latestCompleteDate"] = max(rankings)
        if not rankings:
            raise ValueError("33個の東証業種指数の日付一致履歴が取得できません")

        sheet_id = os.environ["MARKET_DATA_SPREADSHEET_ID"]
        secret = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        client = SheetsClient(create_authorized_session(load_service_account_info(secret)), sheet_id)
        endpoint = client.base_url + "/values/" + client._range(SHEET, "A1:GD250") + "?valueRenderOption=FORMULA"
        before = client._request("GET", endpoint).get("values") or []
        plan = plan_blank_days(before, rankings)
        receipt["planned"] = len(plan)
        receipt["matchedDays"] = len({x["date"] for x in plan})
        receipt["status"] = "DRY_RUN"
        if args.apply and plan:
            for start in range(0, len(plan), 80):
                part = plan[start:start+80]
                ranges = [{"range": f"'{SHEET}'!{column_letter(x['column'])}{x['row']}",
                           "values": [[x["value"]]]} for x in part]
                reply = client._request("POST", client.base_url + "/values:batchUpdate",
                                        json={"valueInputOption": "RAW", "data": ranges})
                n = int(reply.get("totalUpdatedCells") or 0)
                if n != len(part):
                    raise RuntimeError(f"Partial update: {n}/{len(part)}")
                receipt["written"] += n
            # Numeric underlying returns must display as percents, not decimals.
            numeric = [x for x in plan if x["header"].endswith("騰落率")]
            sid = client.sheet_map()[SHEET]
            for start in range(0, len(numeric), 80):
                format_ops = [
                    {"repeatCell": {
                        "range": {"sheetId": sid, "startRowIndex": x["row"]-1,
                                  "endRowIndex": x["row"], "startColumnIndex": x["column"]-1,
                                  "endColumnIndex": x["column"]},
                        "cell": {"userEnteredFormat": {"numberFormat": {
                            "type": "PERCENT", "pattern": "+0.00%;-0.00%;0.00%"}},
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }} for x in numeric[start:start+80]
                ]
                client._request("POST", client.base_url + ":batchUpdate", json={"requests": format_ops})
            after = client._request("GET", endpoint).get("values") or []
            for x in plan:
                ri, ci = x["row"] - 1, x["column"] - 1
                observed = after[ri][ci] if len(after)>ri and len(after[ri])>ci else None
                if isinstance(x["value"], float):
                    if not isinstance(observed, (int, float)) or abs(observed - x["value"]) > 1e-7:
                        raise RuntimeError(f"Readback mismatch {x['date']} {x['header']}")
                elif str(observed) != str(x["value"]):
                    raise RuntimeError(f"Readback mismatch {x['date']} {x['header']}")
            receipt["readBack"] = len(plan)
            receipt["status"] = "APPLIED"
        elif args.apply:
            receipt["status"] = "NO_NEW_DATA"
    except Exception as exc:
        receipt["status"] = "BLOCKED"
        receipt["reason"] = str(exc).splitlines()[0][:260]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt.get(k) for k in (
        "status", "indexCount", "candidateDates", "planned", "written", "readBack", "reason"
    )}, ensure_ascii=False))
    return 2 if receipt["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
