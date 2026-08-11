"""Fetch and parse JPX arbitrage-position publications.

The public JPX PDF is the single source used by both the Nikkei 225
supply-demand page and the dedicated arbitrage page.
"""
from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

JST = timezone(timedelta(hours=9))
PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/program/"
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"


def now_iso() -> str:
    return datetime.now(JST).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ArbitragePosition:
    asOfDate: str
    sellBalance: int
    buyBalance: int
    sourceFileUrl: str

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_with_retry(
    url: str,
    *,
    timeouts: tuple[int, ...] = (20, 30, 45),
    session: requests.Session | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> requests.Response:
    client = session or requests.Session()
    last_error: Exception | None = None
    for attempt, timeout in enumerate(timeouts, start=1):
        try:
            response = client.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < len(timeouts):
                sleeper(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"JPX fetch failed after {len(timeouts)} attempts: {last_error}")


def pdf_links(page_url: str = PAGE_URL, *, session: requests.Session | None = None) -> list[str]:
    html = fetch_with_retry(page_url, session=session).text
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(page_url, anchor["href"])
        if re.search(r"\.pdf(?:\?|$)", url, re.I) and url not in links:
            links.append(url)
    return links


def parse_position_text(text: str, source_url: str = "fixture.pdf") -> ArbitragePosition | None:
    match = re.search(
        r"株\s*数\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)",
        text,
        re.S,
    )
    if not match:
        return None
    values = [int(value.replace(",", "")) for value in match.groups()]
    day_match = re.search(r"現物ポジション[（(](\d{1,2})月(\d{1,2})日現在[）)]", text)
    year_match = re.search(r"(20\d{2})年\d{1,2}月\d{1,2}日", text)
    if not day_match or not year_match:
        return None
    try:
        as_of = date(int(year_match.group(1)), int(day_match.group(1)), int(day_match.group(2))).isoformat()
    except ValueError:
        return None
    return ArbitragePosition(as_of, values[1], values[4], source_url)


def parse_position_pdf(content: bytes, source_url: str) -> ArbitragePosition | None:
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return parse_position_text(text, source_url)


def fetch_latest_positions(limit: int = 8, *, session: requests.Session | None = None) -> list[ArbitragePosition]:
    parsed: dict[str, ArbitragePosition] = {}
    errors: list[str] = []
    for url in pdf_links(session=session)[:limit]:
        try:
            response = fetch_with_retry(url, session=session)
            position = parse_position_pdf(response.content, url)
            if position:
                parsed[position.asOfDate] = position
        except Exception as exc:  # one broken historical PDF must not abort the latest update
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    rows = sorted(parsed.values(), key=lambda item: item.asOfDate, reverse=True)
    if not rows:
        detail = " / ".join(errors[:3]) or "position row not found"
        raise RuntimeError(f"JPX arbitrage parse failed: {detail}")
    return rows


def component_from_positions(rows: list[ArbitragePosition], previous: dict | None = None) -> dict:
    if not rows:
        raise ValueError("at least one JPX position is required")
    current = rows[0]
    older = rows[1] if len(rows) > 1 else None
    if older is None and previous and previous.get("asOfDate") != current.asOfDate:
        try:
            older = ArbitragePosition(
                str(previous["asOfDate"]).replace("/", "-"),
                int(previous["sellBalance"]),
                int(previous["buyBalance"]),
                str(previous.get("sourceFileUrl") or "previous"),
            )
        except (KeyError, TypeError, ValueError):
            older = None
    return {
        "sourceName": "JPX 裁定取引の状況",
        "sourceUrl": PAGE_URL,
        "comment": "裁定買い・売りポジションはJPXの全取引参加者報告合計。前々営業日データとして鮮度を分離表示。",
        **current.to_dict(),
        "sellChange": current.sellBalance - older.sellBalance if older else None,
        "buyChange": current.buyBalance - older.buyBalance if older else None,
        "status": "verified",
        "frequency": "daily",
        "lastAttemptAt": now_iso(),
        "lastSuccessAt": now_iso(),
        "fetchedAt": now_iso(),
        "error": None,
    }
