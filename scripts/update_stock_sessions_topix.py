#!/usr/bin/env python3
"""Run stock-session analysis with a reliable TOPIX source.

Yahoo's global chart endpoint does not reliably return current TOPIX intraday
points, and Yahoo Japan's 998405.T symbol is not accepted by that endpoint.
Google Finance exposes TOPIX directly with current value, daily change and open.
Convert those values into the chart-shaped structure expected by the existing
Tokyo-open analysis so no approximate ETF proxy is used.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, time as dtime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

import update_stock_sessions as stock_sessions


TOPIX_SYMBOL = "TOPIX:INDEXTOPIX"
TOPIX_URL = "https://www.google.com/finance/quote/TOPIX:INDEXTOPIX?hl=en&gl=jp"
_ORIGINAL_SAFE_FETCH = stock_sessions.safe_fetch
_ORIGINAL_TOKYO_SNAPSHOT = stock_sessions.tokyo_snapshot
_NUMBER = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")
_CHANGE = re.compile(r"^\(([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\)")
_PERCENT = re.compile(r"^([+-]?\d+(?:\.\d+)?)%$")


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


def _find_current(tokens: list[str]) -> tuple[float | None, int]:
    for idx, token in enumerate(tokens):
        if token != TOPIX_SYMBOL:
            continue
        for offset, candidate in enumerate(tokens[idx + 1 : idx + 16], start=idx + 1):
            value = _number(candidate)
            if value is not None:
                return value, offset
    return None, -1


def _find_change(tokens: list[str], start: int) -> tuple[float | None, float | None]:
    absolute = None
    percent = None
    if start < 0:
        start = 0
    for token in tokens[start : start + 24]:
        match = _CHANGE.match(token)
        if match:
            try:
                absolute = float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        match = _PERCENT.match(token)
        if match:
            try:
                percent = float(match.group(1))
            except ValueError:
                pass
    return absolute, percent


def _fetch_topix_quote() -> dict[str, object]:
    req = Request(
        TOPIX_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.7",
        },
    )
    with urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = _TextCollector()
    parser.feed(html)
    tokens = parser.tokens

    current, current_idx = _find_current(tokens)
    opening = _find_numeric_after(tokens, "Open")
    absolute_change, percent_change = _find_change(tokens, current_idx)

    previous = None
    if current is not None and absolute_change is not None:
        previous = current - absolute_change
    elif current is not None and percent_change is not None and percent_change > -100:
        previous = current / (1.0 + percent_change / 100.0)

    if current is None or previous is None or opening is None:
        sample = " | ".join(tokens[:160])
        raise RuntimeError(
            "Google Finance TOPIX parse failed "
            f"current={current} previous={previous} open={opening} "
            f"absoluteChange={absolute_change} percentChange={percent_change}; "
            f"sample={sample[:1600]}"
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
        # Preserve the prior Yahoo global symbol only as a fallback. Do not use
        # a TOPIX ETF as a substitute for the index itself.
        fallback, fallback_error = _ORIGINAL_SAFE_FETCH("^TOPX")
        if fallback:
            return fallback, f"Google Finance TOPIX source failed: {exc}"
        return None, f"Google Finance TOPIX source failed: {exc}; ^TOPX fallback: {fallback_error}"


def _tokyo_snapshot(existing):
    result = _ORIGINAL_TOKYO_SNAPSHOT(existing)
    result["source"] = "Yahoo Finance chart API（日経225・FX・CME参考先物） / Google Finance（TOPIX）"
    return result


stock_sessions.TOKYO_SYMBOLS["topix"] = (TOPIX_SYMBOL, "TOPIX")
stock_sessions.safe_fetch = _safe_fetch
stock_sessions.tokyo_snapshot = _tokyo_snapshot


if __name__ == "__main__":
    sys.exit(stock_sessions.main())
