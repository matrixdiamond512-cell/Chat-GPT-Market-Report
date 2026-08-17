#!/usr/bin/env python3
"""Fetch Tokyo pre-open breadth from public ranking pages.

This is intentionally a small, bounded snapshot collector.  It does not poll
225 constituents or treat a missing ranking row as neutral.  The output keeps
an unavailable ``current`` block when the source is missing or dated, while a
previous observation remains available only as ``lastGood`` for diagnostics.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from stock_freshness import current_block, envelope, last_good_from

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market" / "tokyo-preopen.json"
STOCKS = ROOT / "data" / "stocks.json"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0)"

TRADERS_WEB_URL = os.getenv(
    "TOKYO_PREOPEN_TRADERS_WEB_URL",
    "https://www.traders.co.jp/market_jp/stock_ranking/pre_open",
)
KABUTAN_URL = os.getenv(
    "TOKYO_PREOPEN_KABUTAN_URL",
    "https://kabutan.jp/warning/?mode=2_1",
)


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
        headers={"User-Agent": UA, "Accept-Language": "ja,en-US;q=0.7,en;q=0.5"},
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def source_date(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?\s*(\d{1,2}):?(\d{2})", text)
    if not match:
        return None, None
    year, month, day, hour, minute = (int(value) for value in match.groups())
    date = f"{year:04d}-{month:02d}-{day:02d}"
    return date, f"{date}T{hour:02d}:{minute:02d}:00+09:00"


def number(text: str) -> float | None:
    match = re.search(r"[-+−＋]?\d[\d,]*(?:\.\d+)?", text.replace("，", ","))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "").replace("−", "-").replace("＋", "+"))
    except ValueError:
        return None


def parse_rows(html: str, source_name: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    data_date, as_of = source_date(page_text)
    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        table_text = " ".join(list(table.stripped_strings)[:60])
        if not any(token in table_text for token in ("気配", "注文", "騰落率", "前日比")):
            continue
        for tr in table.find_all("tr"):
            cells = [" ".join(cell.stripped_strings).strip() for cell in tr.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            joined = " ".join(cells)
            code_match = re.search(r"(?<!\d)(\d{4})(?!\d)", joined)
            pct_match = re.search(r"([-+−＋]?\d+(?:\.\d+)?)\s*%", joined)
            if not code_match or not pct_match:
                continue
            name = next(
                (cell for cell in cells if not re.fullmatch(r"[\d,\. +%−＋-]+", cell) and not re.search(r"https?://", cell)),
                "",
            )
            if not name:
                continue
            pct = float(pct_match.group(1).replace("−", "-").replace("＋", "+"))
            price = number(cells[-2]) if len(cells) >= 3 else None
            side = "buy" if "買" in joined else "sell" if "売" in joined else ("buy" if pct > 0 else "sell" if pct < 0 else "")
            rows.append({
                "code": code_match.group(1),
                "name": name,
                "indicativePrice": price,
                "changePct": pct,
                "change": f"{pct:+.2f}%",
                "side": side,
                "source": source_name,
            })
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        unique[(row["code"], row["side"])] = row
    return list(unique.values()), data_date, as_of


def merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for row in group:
            unique[(row["code"], row.get("side") or "change")] = row
    return list(unique.values())


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gainers = [row for row in rows if row.get("changePct", 0) > 0]
    decliners = [row for row in rows if row.get("changePct", 0) < 0]
    if len(gainers) > len(decliners) * 1.25:
        tone = "buy"
    elif len(decliners) > len(gainers) * 1.25:
        tone = "sell"
    elif gainers or decliners:
        tone = "mixed"
    else:
        tone = "unknown"
    sectors = sorted({str(row.get("sector") or "") for row in rows if row.get("sector")})
    breadth = "broad" if len(sectors) >= 3 or (len(gainers) + len(decliners) >= 12 and min(len(gainers), len(decliners)) >= 3) else "narrow"
    return {
        "tone": tone,
        "breadth": breadth,
        "leadingSectors": sectors[:5],
        "themes": [],
        "comment": "非掲載銘柄は中立判定に含めていません。取得できたランキングだけを集計しています。",
    }


def build_current(expected_date: str, fetched_at: str) -> dict[str, Any]:
    sources = {"tradersWeb": {"name": "トレーダーズ・ウェブ", "url": TRADERS_WEB_URL}, "kabutan": {"name": "株探", "url": KABUTAN_URL}}
    traders, traders_date, traders_as_of = parse_rows(fetch_html(TRADERS_WEB_URL), "トレーダーズ・ウェブ")
    kabutan, kabutan_date, kabutan_as_of = parse_rows(fetch_html(KABUTAN_URL), "株探")
    dates = [date for date in (traders_date, kabutan_date) if date]
    if not dates or any(date != expected_date for date in dates):
        raise RuntimeError(f"pre-open source date mismatch: sources={dates}, expected={expected_date}")
    rows = merge_rows(traders, kabutan)
    if not rows:
        raise RuntimeError("no valid pre-open ranking rows were returned")
    gainers = sorted((row for row in rows if row.get("changePct", 0) > 0), key=lambda row: row["changePct"], reverse=True)[:10]
    decliners = sorted((row for row in rows if row.get("changePct", 0) < 0), key=lambda row: row["changePct"])[:10]
    buy_orders = sorted((row for row in rows if row.get("side") == "buy"), key=lambda row: row.get("orderValue", row.get("changePct", 0)), reverse=True)[:10]
    sell_orders = sorted((row for row in rows if row.get("side") == "sell"), key=lambda row: row.get("orderValue", row.get("changePct", 0)), reverse=True)[:10]
    as_of = max(filter(None, (traders_as_of, kabutan_as_of)), default=f"{expected_date}T08:53:00+09:00")
    return current_block(
        status="ok",
        data_date=expected_date,
        as_of=as_of,
        updated_at=fetched_at,
        source=sources,
        summary=summarize(rows),
        gainers=gainers,
        decliners=decliners,
        buyOrderLeaders=buy_orders,
        sellOrderLeaders=sell_orders,
    )


def main() -> int:
    stocks = load_json(STOCKS, {})
    previous = load_json(OUT, {})
    expected_date = os.getenv("TOKYO_PREOPEN_MARKET_DATE", "").strip()[:10] or now_jst().date().isoformat()
    fetched_at = now_jst().isoformat()
    try:
        current = build_current(expected_date, fetched_at)
    except Exception as error:  # noqa: BLE001
        current = current_block(
            status="unavailable",
            data_date=None,
            as_of=None,
            updated_at=fetched_at,
            source={"tradersWeb": {"name": "トレーダーズ・ウェブ", "url": TRADERS_WEB_URL}, "kabutan": {"name": "株探", "url": KABUTAN_URL}},
            error=f"当日の寄り前データを取得できませんでした: {error}",
            summary={}, gainers=[], decliners=[], buyOrderLeaders=[], sellOrderLeaders=[],
        )
    payload = envelope(current, previous)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stocks:
        old_component = stocks.get("preopen") or {}
        stocks["preopen"] = {**current, "lastGood": last_good_from(old_component)}
        STOCKS.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": current["status"], "dataDate": current.get("dataDate"), "updatedAt": fetched_at, "error": current.get("error")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

