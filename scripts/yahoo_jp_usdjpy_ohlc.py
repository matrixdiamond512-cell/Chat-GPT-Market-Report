"""Retrieve USD/JPY calendar-day OHLC from the public Yahoo Japan history table.

Use when the global Yahoo Finance chart endpoint rate limits CI (HTTP 429).
The historical page labels its symbol USDJPY=X; its daily quote is not a
Bank of Japan Tokyo-session 9:00/17:00 price. Do not confuse time bases.
"""
from __future__ import annotations

import math
import re
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

SOURCE_URL = "https://finance.yahoo.co.jp/quote/USDJPY=X/history"
FIELDS = ("open", "high", "low", "close")


class HistoryTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.in_cell = False
        self.cell_depth = 0
        self.cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.current_row = []
        elif tag in ("td", "th") and self.current_row is not None:
            self.in_cell = True
            self.cell_depth = 0
            self.cell_parts = []
        elif self.in_cell:
            self.cell_depth += 1

    def handle_data(self, value: str) -> None:
        if self.in_cell:
            self.cell_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.in_cell:
            self.current_row.append("".join(self.cell_parts).strip())
            self.in_cell = False
            self.cell_parts = []
        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None


def parse_history(html: str) -> dict[str, dict]:
    parser = HistoryTableParser()
    parser.feed(html)
    result: dict[str, dict] = {}
    for cells in parser.rows:
        if len(cells) < 5:
            continue
        match = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", cells[0])
        if not match:
            continue
        try:
            day = date(*(int(part) for part in match.groups())).isoformat()
            values = {field: round(float(re.sub(r"[,\s]", "", cells[idx])), 4)
                      for idx, field in enumerate(FIELDS, start=1)}
        except (ValueError, IndexError):
            continue
        if not all(math.isfinite(v) and 50 <= v <= 300 for v in values.values()):
            continue
        if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]):
            continue
        result[day] = {"date": day, **values}
    return result


def fetch_history(target_dates: set[str] | None = None) -> dict[str, dict]:
    """Fetch enough history pages to cover all targeted BOJ spot-volume dates."""
    result: dict[str, dict] = {}
    for page in range(1, 7):
        url = SOURCE_URL + ("?" + urllib.parse.urlencode({"page": page}) if page > 1 else "")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=24) as response:
            html = response.read().decode("utf-8", "replace")
        found = parse_history(html)
        if not found:
            raise RuntimeError(f"Yahoo Japan history page {page} yielded no valid USDJPY daily OHLC rows")
        before = len(result)
        result.update(found)
        print(f"YahooJP USDJPY history page {page}: {len(found)} rows / {min(found)}..{max(found)}")
        if target_dates is not None and target_dates.issubset(result):
            break
        if len(result) == before:
            break
    return result
