#!/usr/bin/env python3
"""Fetch and validate Tokyo Prime top gainers/losers, then sync stocks.json.

Source:
- Traders Web domestic stock ranking, Tokyo Prime, daily change

Safety rules:
- the source date must equal stocks.json's verified Tokyo market date;
- source time must be 15:00 JST or later so intraday rankings are not saved as close data;
- require five Tokyo Prime rows on both gainers and losers pages;
- never reuse a previous day's ranking under a new basis date;
- if the same verified ranking is already stored, do not churn generated files.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from stock_freshness import current_block, envelope, last_good_from

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
OUTPUT_PATH = ROOT / "data" / "market" / "japan-stock-movers.json"
JST = timezone(timedelta(hours=9))

UP_URL = "https://www.traders.co.jp/market_jp/stock_ranking/price_up/day/tp/all"
DOWN_URL = "https://www.traders.co.jp/market_jp/stock_ranking/price_down/day/tp/all"
SOURCE_NAME = "トレーダーズ・ウェブ 国内市場ランキング（東証プライム・前日比）"
USER_AGENT = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en-US;q=0.7,en;q=0.5"},
        timeout=40,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def source_timestamp(text: str) -> tuple[str, str]:
    match = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if not match:
        raise RuntimeError("Traders Web ranking timestamp was not found")
    year, month, day, hour, minute = (int(x) for x in match.groups())
    market_date = f"{year:04d}-{month:02d}-{day:02d}"
    source_at = f"{market_date}T{hour:02d}:{minute:02d}:00+09:00"
    if hour < 15:
        raise RuntimeError(f"Traders Web ranking is still intraday: {source_at}")
    return market_date, source_at


def parse_signed(value: str) -> str:
    text = value.replace("−", "-").replace("＋", "+").strip()
    match = re.search(r"[-+±]?\s*[\d,.]+(?:\.\d+)?", text)
    if not match:
        return "—"
    result = match.group(0).replace(" ", "")
    if result.startswith("±"):
        return "±0"
    return result


def parse_percent(value: str) -> float:
    text = value.replace("−", "-").replace("＋", "+").replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?\s*%", text)
    if not match:
        raise ValueError(f"percentage not found: {value!r}")
    return float(match.group(0).replace("%", "").strip())


def find_ranking_table(soup: BeautifulSoup) -> Any:
    for table in soup.find_all("table"):
        header = " ".join(list(table.stripped_strings)[:40])
        if "順位" in header and "銘柄名" in header and "騰落率" in header:
            return table
    raise RuntimeError("Traders Web ranking table was not found")


def parse_page(url: str, positive: bool) -> tuple[list[dict[str, Any]], str, str]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)
    market_date, source_at = source_timestamp(full_text)
    table = find_ranking_table(soup)

    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        rank_text = " ".join(cells[0].stripped_strings).strip()
        if not rank_text.isdigit():
            continue
        name_cell = " ".join(cells[1].stripped_strings).strip()
        code_match = re.search(r"\((\d{4}|\d{3}[A-Z])/([^\)]+)\)", name_cell, flags=re.I)
        if not code_match:
            continue
        code = code_match.group(1).upper()
        market = code_match.group(2).strip()
        if "東P" not in market:
            continue
        name = name_cell[: code_match.start()].strip()
        if not name:
            continue

        price_change_text = " ".join(cells[2].stripped_strings).strip()
        price_numbers = re.findall(r"[-+−＋±]?\d[\d,]*(?:\.\d+)?", price_change_text)
        if not price_numbers:
            continue
        close = price_numbers[0].replace("−", "-").replace("＋", "+")
        day_change = price_numbers[1].replace("−", "-").replace("＋", "+") if len(price_numbers) > 1 else "—"
        try:
            change_pct = parse_percent(" ".join(cells[3].stripped_strings))
        except ValueError:
            continue
        if positive and change_pct <= 0:
            continue
        if not positive and change_pct >= 0:
            continue

        rows.append({
            "rank": len(rows) + 1,
            "code": code,
            "name": name,
            "displayName": f"{name}（{code}）",
            "close": close,
            "dayChange": day_change,
            "changePct": change_pct,
        })
        if len(rows) >= 5:
            break

    if len(rows) != 5:
        raise RuntimeError(f"Traders Web ranking did not produce five rows: {len(rows)}")
    return rows, market_date, source_at


def public_row(row: dict[str, Any], market_date: str) -> dict[str, Any]:
    return {
        "rank": row["rank"],
        "code": row["code"],
        "name": row["displayName"],
        "close": row["close"],
        "change": f'{float(row["changePct"]):+.2f}%',
        "dayChange": row["dayChange"],
        "reason": f"東証プライム前日比騰落率ランキング。基準日 {market_date}。材料要因は別途ニュース確認。",
    }


def same_rankings(old: dict[str, Any], new: dict[str, Any]) -> bool:
    if old.get("dataDate") != new.get("dataDate"):
        return False
    for key in ("gainers", "losers"):
        old_rows = old.get(key) or []
        new_rows = new.get(key) or []
        old_sig = [(r.get("code"), r.get("close"), r.get("change")) for r in old_rows]
        new_sig = [(r.get("code"), r.get("close"), r.get("change")) for r in new_rows]
        if old_sig != new_sig:
            return False
    return True


def merge_into_stocks(stocks: dict[str, Any], payload: dict[str, Any]) -> None:
    current = payload.get("current") or payload
    market_date = current["dataDate"]
    current_date = str((stocks.get("marketDates") or {}).get("japan") or "")[:10]
    if current_date and current_date > market_date:
        raise RuntimeError(f"refusing stale Tokyo mover update: {market_date} < {current_date}")
    previous = (stocks.get("movers") or {}).get("japan") or {}
    previous_good = last_good_from(previous)
    stocks.setdefault("movers", {})["japan"] = {
        "title": "日本市場の大幅上昇・下落銘柄（東証プライム）",
        "flag": "JP",
        **current,
        "lastGood": previous_good,
    }


def merge_unavailable_into_stocks(stocks: dict[str, Any], error: str, updated_at: str) -> None:
    previous = (stocks.get("movers") or {}).get("japan") or {}
    current = current_block(
        status="unavailable",
        data_date=None,
        as_of=None,
        updated_at=updated_at,
        source={"name": SOURCE_NAME, "gainersUrl": UP_URL, "losersUrl": DOWN_URL},
        error=error,
        title="日本市場の大幅上昇・下落銘柄（東証プライム）",
        flag="JP",
        gainers=[],
        losers=[],
    )
    stocks.setdefault("movers", {})["japan"] = {**current, "lastGood": last_good_from(previous)}


def sync_stock_analysis_json(stocks: dict[str, Any]) -> None:
    spreadsheet_id = os.getenv("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_raw:
        print("Stock_Analysis_JSON sync skipped: Google credentials not configured")
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    client = SheetsClient(create_authorized_session(load_service_account_info(credentials_raw)), spreadsheet_id)
    values = client.get_values("Stock_Analysis_JSON", "A1:B2")
    if len(values) < 2:
        print("Stock_Analysis_JSON sync skipped: B2 payload not found")
        return
    raw = str(values[1][1] if len(values[1]) > 1 else "").strip()
    if not raw:
        print("Stock_Analysis_JSON sync skipped: B2 payload is empty")
        return
    sheet_payload = json.loads(raw)
    sheet_payload.setdefault("movers", {})["japan"] = stocks["movers"]["japan"]
    client.update("Stock_Analysis_JSON", "B2", [[json.dumps(sheet_payload, ensure_ascii=False)]])


def main() -> int:
    stocks = load_json(STOCKS_PATH, {})
    if not stocks:
        raise SystemExit("data/stocks.json is unavailable")
    expected_date = str((stocks.get("marketDates") or {}).get("japan") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expected_date):
        raise SystemExit("verified Tokyo market date is unavailable")

    old = load_json(OUTPUT_PATH, {})
    fetched_at = now_jst().isoformat()
    try:
        gainers, up_date, up_at = parse_page(UP_URL, True)
        losers, down_date, down_at = parse_page(DOWN_URL, False)
    except Exception as error:  # noqa: BLE001
        message = f"当日の東証プライムランキングを取得できませんでした: {error}"
        current = current_block(
            status="unavailable",
            data_date=None,
            as_of=None,
            updated_at=fetched_at,
            source={"name": SOURCE_NAME, "gainersUrl": UP_URL, "losersUrl": DOWN_URL},
            error=message,
            gainers=[],
            losers=[],
        )
        unavailable = envelope(current, old)
        merge_unavailable_into_stocks(stocks, message, fetched_at)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(unavailable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "unavailable", "error": message}, ensure_ascii=False))
        return 0
    if up_date != down_date:
        raise SystemExit(f"Traders Web up/down basis dates disagree: {up_date} / {down_date}")
    if up_date != expected_date:
        raise SystemExit(f"Traders Web ranking is not current: source={up_date}, expected={expected_date}")

    source_at = {"gainers": up_at, "losers": down_at}
    current = current_block(
        status="verified",
        data_date=expected_date,
        as_of=max(up_at, down_at),
        updated_at=fetched_at,
        source={"name": SOURCE_NAME, "gainersUrl": UP_URL, "losersUrl": DOWN_URL},
        sourceAt=source_at,
        gainers=[public_row(row, expected_date) for row in gainers],
        losers=[public_row(row, expected_date) for row in losers],
    )
    payload = envelope(current, old)
    if same_rankings(old, payload):
        print(json.dumps({"status": "already-current", "marketDate": expected_date}, ensure_ascii=False))
        return 0

    merge_into_stocks(stocks, payload)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_stock_analysis_json(stocks)
    print(json.dumps({
        "status": "verified",
        "marketDate": expected_date,
        "topGainer": payload["gainers"][0]["name"],
        "topLoser": payload["losers"][0]["name"],
        "sourceAt": payload["sourceAt"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

