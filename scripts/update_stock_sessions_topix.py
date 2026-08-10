#!/usr/bin/env python3
"""Run stock-session analysis with a working TOPIX intraday source.

Yahoo's global chart endpoint does not reliably return current TOPIX intraday
points. Yahoo Japan exposes TOPIX as 998405.T on its quote page, including the
current value, previous close and opening value. Convert those values into the
same chart-shaped structure used by update_stock_sessions.py so the existing
Tokyo-open analysis can remain unchanged.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, time as dtime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

import update_stock_sessions as stock_sessions


TOPIX_SYMBOL = "998405.T"
TOPIX_URL = "https://finance.yahoo.co.jp/quote/998405.T"
_ORIGINAL_SAFE_FETCH = stock_sessions.safe_fetch
_NUMBER = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data or "").split())
        if text:
            self.tokens.append(text)


def _number(token: str) -> float | None:
    text = str(token or "").strip()
    if not _NUMBER.match(text):
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _find_numeric_after(tokens: list[str], label: str, *, limit: int = 12) -> float | None:
    for idx, token in enumerate(tokens):
        if token != label:
            continue
        for candidate in tokens[idx + 1 : idx + 1 + limit]:
            value = _number(candidate)
            if value is not None:
                return value
    return None


def _find_current_before_change(tokens: list[str]) -> float | None:
    for idx, token in enumerate(tokens):
        if token != "前日比":
            continue
        start = max(0, idx - 12)
        for candidate in reversed(tokens[start:idx]):
            value = _number(candidate)
            if value is not None:
                return value
    return None


def _fetch_topix_quote() -> dict[str, object]:
    req = Request(
        TOPIX_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = _TextCollector()
    parser.feed(html)
    tokens = parser.tokens

    current = _find_current_before_change(tokens)
    previous = _find_numeric_after(tokens, "前日終値")
    opening = _find_numeric_after(tokens, "始値")
    if current is None or previous is None or opening is None:
        sample = " | ".join(tokens[:120])
        raise RuntimeError(
            f"Yahoo Japan TOPIX parse failed current={current} previous={previous} open={opening}; sample={sample[:1200]}"
        )

    now = stock_sessions.now_jst()
    open_dt = datetime.combine(now.date(), dtime(9, 0), tzinfo=stock_sessions.JST)
    now_ts = int(now.timestamp())
    open_ts = int(open_dt.timestamp())
    if now_ts <= open_ts:
        now_ts = open_ts + 60

    return {
        "symbol": TOPIX_SYMBOL,
        "currency": "JPY",
        "exchangeTimezoneName": "Asia/Tokyo",
        "regularMarketPrice": current,
        "previousClose": previous,
        "last": current,
        "points": [
            {"ts": open_ts, "open": opening, "close": opening, "volume": None},
            {"ts": now_ts, "open": current, "close": current, "volume": None},
        ],
    }


def _safe_fetch(symbol: str):
    if symbol != TOPIX_SYMBOL:
        return _ORIGINAL_SAFE_FETCH(symbol)
    try:
        return _fetch_topix_quote(), None
    except Exception as exc:
        # Keep the old global Yahoo source as a last-resort fallback. It may not
        # contain today's one-minute bars, but retaining it is preferable to
        # silently fabricating TOPIX values.
        fallback, fallback_error = _ORIGINAL_SAFE_FETCH("^TOPX")
        if fallback:
            return fallback, f"Yahoo Japan TOPIX source failed: {exc}"
        return None, f"Yahoo Japan TOPIX source failed: {exc}; ^TOPX fallback: {fallback_error}"


stock_sessions.TOKYO_SYMBOLS["topix"] = (TOPIX_SYMBOL, "TOPIX")
stock_sessions.safe_fetch = _safe_fetch


if __name__ == "__main__":
    sys.exit(stock_sessions.main())
