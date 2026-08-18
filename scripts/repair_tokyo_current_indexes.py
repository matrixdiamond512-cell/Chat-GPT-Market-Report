#!/usr/bin/env python3
"""Fill current Tokyo index rows when exact-date history has not published yet.

The dashboard's target date is the latest completed Tokyo session. Historical
pages can lag the closing quote. For the current calendar session only, this
script accepts explicitly dated closing quotes from Traders Web first, then
Google Finance / Kabutan fallbacks. It never applies a current quote to an older
target date.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136 Safari/537.36"
TOPIX_SYMBOL = "TOPIX:INDEXTOPIX"
TOPIX_URL = "https://www.google.com/finance/quote/TOPIX:INDEXTOPIX?hl=en&gl=jp"
TRADERS_MARKET_URL = "https://www.traders.co.jp/market_jp/"
_NUMBER = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")
_CHANGE = re.compile(r"^\(([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\)")
_PERCENT = re.compile(r"^([+-]?\d+(?:\.\d+)?)%$")


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(str(data or "").split())
        if value:
            self.tokens.append(value)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_html(url: str, *, language: str = "ja,en-US;q=0.8,en;q=0.7") -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": language,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="replace")


def clean_text(source: str) -> str:
    source = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", source)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", source))).strip()


def numeric(token: str) -> float | None:
    token = str(token or "").strip()
    if not _NUMBER.fullmatch(token):
        return None
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def signed_number(value: str) -> float:
    return float(value.replace(",", "").replace("＋", "+").replace("−", "-"))


def traders_current_indexes(target: dt.date) -> dict[str, tuple[float, float, float]]:
    """Parse the dated post-close market table from Traders Web.

    The table is accepted only when the page explicitly contains the target
    date and a 15:00-or-later timestamp. This avoids turning cached prior-day
    market data into today's values.
    """
    text = clean_text(fetch_html(TRADERS_MARKET_URL))
    date_token = f"{target.year:04d}/{target.month:02d}/{target.day:02d}"
    timestamp = re.compile(rf"{re.escape(date_token)}\s+(1[5-9]|2[0-3]):([0-5]\d)")
    starts = [match.end() for match in timestamp.finditer(text)]
    if not starts:
        return {}

    label_patterns = {
        "TOPIX": r"TOPIX",
        "グロース250": r"グロース250",
    }
    result: dict[str, tuple[float, float, float]] = {}
    for start in starts:
        segment = text[start : start + 2600]
        if "日経平均" not in segment or "TOPIX" not in segment or "グロース250" not in segment:
            continue
        for label, label_pattern in label_patterns.items():
            if label in result:
                continue
            match = re.search(
                label_pattern
                + r"\s+([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s+"
                + r"([+＋\-−][0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s+"
                + r"([+＋\-−][0-9]+(?:\.[0-9]+)?)%",
                segment,
            )
            if not match:
                continue
            result[label] = (
                float(match.group(1).replace(",", "")),
                signed_number(match.group(2)),
                signed_number(match.group(3)),
            )
        if len(result) == len(label_patterns):
            break
    return result


def google_topix() -> tuple[float, float, float] | None:
    source = fetch_html(TOPIX_URL, language="en-US,en;q=0.9,ja;q=0.7")
    parser = TextCollector()
    parser.feed(source)
    tokens = parser.tokens

    current = None
    current_idx = -1
    for idx, token in enumerate(tokens):
        if token != TOPIX_SYMBOL:
            continue
        for pos, candidate in enumerate(tokens[idx + 1 : idx + 16], start=idx + 1):
            value = numeric(candidate)
            if value is not None:
                current = value
                current_idx = pos
                break
        if current is not None:
            break
    if current is None:
        return None

    absolute = None
    percent = None
    for token in tokens[current_idx : current_idx + 24]:
        match = _CHANGE.match(token)
        if match:
            try:
                absolute = float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        match = _PERCENT.fullmatch(token)
        if match:
            try:
                percent = float(match.group(1))
            except ValueError:
                pass
    if absolute is None and percent is not None and percent > -100:
        previous = current / (1.0 + percent / 100.0)
        absolute = current - previous
    if absolute is None:
        return None
    if percent is None:
        previous = current - absolute
        percent = absolute / previous * 100.0 if previous else 0.0
    return current, absolute, percent


def kabutan_current(target: dt.date, code: str, heading: str) -> tuple[float, float, float] | None:
    url = f"https://s.kabutan.jp/stocks/{code}/"
    text = clean_text(fetch_html(url))
    date_markers = (
        f"({target.month}/{target.day}時点)",
        f"{target.month}/{target.day}時点",
        f"({target.month}/{target.day})",
    )
    if not any(marker in text for marker in date_markers):
        return None

    start = text.find(heading)
    if start < 0:
        return None
    segment = text[start : start + 1200]
    match = re.search(
        r"\s([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s+"
        r"([+\-][0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s+"
        r"([+\-][0-9]+(?:\.[0-9]+)?)%",
        segment,
    )
    if not match:
        return None
    return (
        float(match.group(1).replace(",", "")),
        float(match.group(2).replace(",", "")),
        float(match.group(3)),
    )


def current_calendar_session_allowed(target: dt.date) -> bool:
    today = dt.datetime.now(JST).date()
    return target == today and today.weekday() < 5


def patch_row(rows: list[Any], label: str, quote: tuple[float, float, float], evaluation: str) -> None:
    current, change, percent = quote
    replacement = [
        label,
        f"{current:,.2f}",
        f"{change:+,.2f}（{percent:+.2f}%）",
        evaluation,
    ]
    for idx, row in enumerate(rows):
        if isinstance(row, list) and row and row[0] == label:
            rows[idx] = replacement
            return
    rows.append(replacement)


def main() -> int:
    stocks = load_json(STOCKS_PATH)
    japan = ((stocks.get("marketInternals") or {}).get("japan") or {})
    rows = japan.get("rows") or []
    target_text = str((stocks.get("marketDates") or {}).get("japan") or japan.get("dataDate") or "")[:10]
    try:
        target = dt.date.fromisoformat(target_text)
    except ValueError:
        raise SystemExit("invalid Tokyo target date")
    if not isinstance(rows, list):
        raise SystemExit("Tokyo rows missing")
    if not current_calendar_session_allowed(target):
        print(json.dumps({"targetDate": target_text, "status": "skip-current-quote-fallback"}, ensure_ascii=False))
        return 0

    diagnostics: dict[str, str] = {}
    try:
        traders = traders_current_indexes(target)
    except Exception as exc:
        traders = {}
        diagnostics["TradersWeb-indexes"] = f"{type(exc).__name__}: {exc}"

    quote = traders.get("TOPIX")
    topix_source = "トレーダーズ・ウェブ 国内市場"
    if quote is None:
        try:
            quote = google_topix()
            topix_source = "Google Finance"
        except Exception as exc:
            quote = None
            diagnostics["TOPIX-google"] = f"{type(exc).__name__}: {exc}"
    if quote is None:
        try:
            quote = kabutan_current(target, "0010", "ＴＯＰＩＸ 株価・基本情報")
            topix_source = "株探"
        except Exception as exc:
            quote = None
            diagnostics["TOPIX-kabutan"] = f"{type(exc).__name__}: {exc}"
    if quote is not None:
        patch_row(rows, "TOPIX", quote, f"{topix_source}の当日終値確認。基準日 {target_text}。")
        diagnostics["TOPIX"] = f"repaired from {topix_source} current-session close"
    else:
        diagnostics.setdefault("TOPIX", "current-session quote unavailable")

    growth = traders.get("グロース250")
    growth_source = "トレーダーズ・ウェブ 国内市場"
    if growth is None:
        try:
            growth = kabutan_current(target, "0012", "東証グロース市場250指数 株価・基本情報")
            growth_source = "株探"
        except Exception as exc:
            growth = None
            diagnostics["グロース250-kabutan"] = f"{type(exc).__name__}: {exc}"
    if growth is not None:
        patch_row(rows, "グロース250", growth, f"{growth_source}の当日終値確認。基準日 {target_text}。")
        diagnostics["グロース250"] = f"repaired from {growth_source} dated current-session close"
    else:
        diagnostics.setdefault("グロース250", "dated current-session quote unavailable")

    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    japan["rows"] = rows
    japan["updatedAt"] = now
    source = japan.get("source") if isinstance(japan.get("source"), dict) else {}
    prior = source.get("repairDiagnostics") if isinstance(source.get("repairDiagnostics"), dict) else {}
    prior.update(diagnostics)
    source["repairDiagnostics"] = prior
    japan["source"] = source
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now
    save_json(STOCKS_PATH, stocks)
    print(json.dumps({"targetDate": target_text, "diagnostics": diagnostics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())