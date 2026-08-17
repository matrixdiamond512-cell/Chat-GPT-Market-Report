#!/usr/bin/env python3
"""Fetch Tokyo pre-open observations from Traders Web and Kabutan.

Traders Web publishes the pre-open item as a Market Flash article, while
Kabutan publishes the order-value rankings inside a news article. The
collector discovers the current article from each site's news index and never
falls back to change percentage when an order amount is unavailable.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover - GitHub Actions installs requests
    requests = None
from bs4 import BeautifulSoup

from stock_freshness import current_block, envelope, last_good_from

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market" / "tokyo-preopen.json"
STOCKS = ROOT / "data" / "stocks.json"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0)"

TRADERS_WEB_URL = os.getenv(
    "TOKYO_PREOPEN_TRADERS_WEB_URL",
    "https://www.traders.co.jp/market_jp/wadai",
)
KABUTAN_URL = os.getenv(
    "TOKYO_PREOPEN_KABUTAN_URL",
    "https://s.kabutan.jp/news/",
)

DATE_RE = re.compile(
    r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?(?:\([^)]*\)|（[^）]*）)?\s*(\d{1,2})(?:時|:)?(\d{2})(?:分)?"
)
PERCENT_RE = re.compile(r"[-+−＋]?\d+(?:\.\d+)?\s*%")
CODE_RE = re.compile(r"[<＜〈]\s*(\d{3,4}[A-Z]?)(?:\.T)?\s*[>＞〉]")
ORDER_ROW_RE = re.compile(
    r"(?P<name>[\w\u3040-\u30ff\u3400-\u9fffＡ-Ｚａ-ｚー・]{1,30})"
    r"\s*[<＜〈]\s*(?P<code>\d{3,4}[A-Z]?)(?:\.T)?\s*[>＞〉]"
    r"\s*(?P<price>[\d,]+(?:\.\d+)?)"
    r"\s+(?P<absolute>[-+−＋]?\s*[\d,]+(?:\.\d+)?)"
    r"\s*\(\s*(?P<pct>[-+−＋]?\d+(?:\.\d+)?)\s*%\s*\)"
    r"\s*(?P<sell_shares>[\d,]+)\s*\(\s*(?P<sell_value>[\d,]+)\s*\)"
    r"\s*(?P<buy_shares>[\d,]+)\s*\(\s*(?P<buy_value>[\d,]+)\s*\)"
)


def now_jst() -> datetime:
    return datetime.now(JST).replace(microsecond=0)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch_html(url: str) -> str:
    if requests is None:
        raise RuntimeError("requests is not installed; run pip install requests")
    response = requests.get(
        url,
        headers={"User-Agent": UA, "Accept-Language": "ja,en-US;q=0.7,en;q=0.5"},
        timeout=15,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def source_date(text: str) -> tuple[str | None, str | None]:
    match = DATE_RE.search(html_lib.unescape(text))
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


def clean_name(value: str) -> str:
    return value.strip(" \t\r\n、,，。:：;；()（）[]【】")


def article_candidates(index_url: str, html: str, pattern: re.Pattern[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        label = " ".join(link.stripped_strings)
        href = urljoin(index_url, str(link["href"]))
        if pattern.search(label) and href not in seen:
            seen.add(href)
            candidates.append(href)
    return candidates


def fetch_current_article(
    index_url: str,
    title_pattern: re.Pattern[str],
    expected_date: str,
) -> tuple[str, str, str, str]:
    """Return article URL, HTML, source date, and source timestamp."""
    if "/article/" in index_url or "/news/n" in index_url:
        candidates = [index_url]
    else:
        candidates = article_candidates(index_url, fetch_html(index_url), title_pattern)
    for url in candidates[:12]:
        article_html = fetch_html(url)
        data_date, as_of = source_date(BeautifulSoup(article_html, "html.parser").get_text(" ", strip=True))
        if data_date == expected_date and as_of:
            return url, article_html, data_date, as_of
    raise RuntimeError(f"当日の記事が見つかりません: index={index_url}, expected={expected_date}")


def parse_traders_web_article(
    html: str,
    expected_date: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None, list[dict[str, Any]]]:
    """Parse Market Flash prose, including code/percentage mentions and highlights."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    data_date, as_of = source_date(text)
    if expected_date and data_date != expected_date:
        raise ValueError(f"Traders Web article date mismatch: source={data_date}, expected={expected_date}")

    rows: list[dict[str, Any]] = []
    for code_match in CODE_RE.finditer(text):
        before = text[max(0, code_match.start() - 32) : code_match.start()]
        name_match = re.search(r"([^\s、。,:：;()（）]{1,24})\s*$", before)
        after = text[code_match.end() : code_match.end() + 100]
        pct_match = PERCENT_RE.search(after)
        if not name_match or not pct_match:
            continue
        pct = number(pct_match.group(0))
        if pct is None:
            continue
        rows.append(
            {
                "code": code_match.group(1),
                "name": clean_name(name_match.group(1)),
                "indicativePrice": None,
                "changePct": pct,
                "change": f"{pct:+.2f}%",
                "side": "buy" if pct > 0 else "sell" if pct < 0 else "",
                "source": "トレーダーズ・ウェブ",
            }
        )

    highlights: list[dict[str, Any]] = []
    phrase = re.search(r"寄り前気配(?:では|は)(.{1,180}?)(?:が|は)(高|安)い気配値", text)
    if phrase:
        names = re.split(r"[、,，]", phrase.group(1))
        signal = "up" if phrase.group(2) == "高" else "down"
        highlights = [
            {"name": clean_name(name), "signal": signal, "source": "トレーダーズ・ウェブ"}
            for name in names
            if clean_name(name)
        ]
    if not rows and not highlights:
        raise ValueError("Traders Web Market Flashから銘柄情報を抽出できません")
    return rows, data_date, as_of, highlights


def parse_kabutan_order_article(
    html: str,
    expected_date: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Parse Kabutan's buy/sell order-value article rows."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    data_date, as_of = source_date(text)
    if expected_date and data_date != expected_date:
        raise ValueError(f"Kabutan article date mismatch: source={data_date}, expected={expected_date}")

    rows: list[dict[str, Any]] = []
    for match in ORDER_ROW_RE.finditer(text):
        prefix = text[max(0, match.start() - 240) : match.start()]
        buy_heading = prefix.rfind("買い注文金額ランキング")
        sell_heading = prefix.rfind("売り注文金額ランキング")
        if buy_heading < 0 and sell_heading < 0:
            continue
        side = "buy" if buy_heading > sell_heading else "sell"
        pct = number(match.group("pct"))
        if pct is None:
            continue
        order_value = int(match.group("buy_value" if side == "buy" else "sell_value").replace(",", ""))
        rows.append(
            {
                "code": match.group("code"),
                "name": clean_name(match.group("name")),
                "indicativePrice": number(match.group("price")),
                "changePct": pct,
                "change": f"{pct:+.2f}%",
                "side": side,
                "sellShares": int(match.group("sell_shares").replace(",", "")),
                "sellOrderValue": int(match.group("sell_value").replace(",", "")),
                "buyShares": int(match.group("buy_shares").replace(",", "")),
                "buyOrderValue": int(match.group("buy_value").replace(",", "")),
                "orderValue": order_value,
                "orderValueUnit": "万円",
                "source": "株探",
            }
        )
    if not rows:
        raise ValueError("株探の買い／売り注文金額ランキングを抽出できません")
    return rows, data_date, as_of


def fetch_traders(expected_date: str) -> tuple[list[dict[str, Any]], str, str, list[dict[str, Any]]]:
    url, html, _, as_of = fetch_current_article(TRADERS_WEB_URL, re.compile(r"寄り前気配|寄前"), expected_date)
    rows, _, _, highlights = parse_traders_web_article(html, expected_date)
    return rows, url, as_of, highlights


def fetch_kabutan(expected_date: str) -> tuple[list[dict[str, Any]], str, str]:
    url, html, _, as_of = fetch_current_article(KABUTAN_URL, re.compile(r"寄前|板状況|注文ランキング"), expected_date)
    rows, _, _ = parse_kabutan_order_article(html, expected_date)
    return rows, url, as_of


def merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for row in group:
            key = (row.get("code") or row.get("name") or "", row.get("side") or "change")
            old = unique.get(key)
            if old and old.get("orderValue") is not None and row.get("orderValue") is None:
                continue
            unique[key] = row
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
    breadth = "broad" if len(gainers) + len(decliners) >= 12 and min(len(gainers), len(decliners)) >= 3 else "narrow"
    return {
        "tone": tone,
        "breadth": breadth,
        "leadingSectors": [],
        "leadingSectorsStatus": "unavailable",
        "themes": [],
        "comment": "主導業種は銘柄コードと33業種の対応表がないため表示しません。取得できた気配ランキングだけを集計しています。",
    }


def build_current(expected_date: str, fetched_at: str) -> dict[str, Any]:
    traders_rows, traders_url, traders_as_of, traders_highlights = fetch_traders(expected_date)
    kabutan_rows, kabutan_url, kabutan_as_of = fetch_kabutan(expected_date)
    if not kabutan_rows:
        raise RuntimeError("Kabutan order-value rows are empty")
    rows = merge_rows(kabutan_rows, traders_rows)
    gainers = sorted((row for row in rows if row.get("changePct", 0) > 0), key=lambda row: row["changePct"], reverse=True)[:10]
    decliners = sorted((row for row in rows if row.get("changePct", 0) < 0), key=lambda row: row["changePct"])[:10]
    buy_orders = sorted(
        (row for row in rows if row.get("side") == "buy" and row.get("orderValue") is not None),
        key=lambda row: row["orderValue"], reverse=True,
    )[:10]
    sell_orders = sorted(
        (row for row in rows if row.get("side") == "sell" and row.get("orderValue") is not None),
        key=lambda row: row["orderValue"], reverse=True,
    )[:10]
    if not buy_orders or not sell_orders:
        raise RuntimeError("Kabutan buy/sell order-value rankings are incomplete")
    return current_block(
        status="ok",
        data_date=expected_date,
        as_of=max(traders_as_of, kabutan_as_of),
        updated_at=fetched_at,
        source={
            "tradersWeb": {"name": "トレーダーズ・ウェブ Market Flash", "url": traders_url},
            "kabutan": {"name": "株探 寄前板状況注文ランキング", "url": kabutan_url},
        },
        summary=summarize(rows),
        tradersWebHighlights=traders_highlights,
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
            source={"tradersWeb": {"name": "トレーダーズ・ウェブ Market Flash", "url": TRADERS_WEB_URL}, "kabutan": {"name": "株探 寄前板状況注文ランキング", "url": KABUTAN_URL}},
            error=f"当日の寄り前データを取得できませんでした: {error}",
            summary={}, tradersWebHighlights=[], gainers=[], decliners=[], buyOrderLeaders=[], sellOrderLeaders=[],
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

