#!/usr/bin/env python3
"""Fetch US and Tokyo sector performance, preserve verified data, and sync Google Sheets.

US: the 11 Select Sector SPDR ETFs via Yahoo Finance chart data, with Stooq CSV fallback.
Japan: the 33 TSE industry index pages (codes 0251-0283) on the mobile Kabutan site.

The output is consumed by assets/js/stock-sector-decliners.js. When Google Sheets
credentials are configured, the same Top 5 gainers/decliners are written to the
latest matching date row in the 終値一覧 sheet and merged into Stock_Analysis_JSON.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from stock_freshness import current_block, last_good_from

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "sector-performance.json"
MARKET_OUTPUT_PATH = ROOT / "data" / "market" / "sector-performance.json"
STOCKS_PATH = ROOT / "data" / "stocks.json"
JST = dt.timezone(dt.timedelta(hours=9))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
TRADERS_WEB_SECTOR_URL = os.getenv(
    "TRADERS_WEB_SECTOR_URL",
    "https://www.traders.co.jp/market_jp/sector_ranking/day",
)

US_SECTORS = {
    "XLC": "コミュニケーション・サービス",
    "XLY": "一般消費財・サービス",
    "XLP": "生活必需品",
    "XLE": "エネルギー",
    "XLF": "金融",
    "XLV": "ヘルスケア",
    "XLI": "資本財・サービス",
    "XLB": "素材",
    "XLRE": "不動産",
    "XLK": "情報技術",
    "XLU": "公益事業",
}

JP_SECTORS = {
    "0251": "水産・農林業",
    "0252": "鉱業",
    "0253": "建設業",
    "0254": "食料品",
    "0255": "繊維製品",
    "0256": "パルプ・紙",
    "0257": "化学",
    "0258": "医薬品",
    "0259": "石油・石炭製品",
    "0260": "ゴム製品",
    "0261": "ガラス・土石製品",
    "0262": "鉄鋼",
    "0263": "非鉄金属",
    "0264": "金属製品",
    "0265": "機械",
    "0266": "電気機器",
    "0267": "輸送用機器",
    "0268": "精密機器",
    "0269": "その他製品",
    "0270": "電気・ガス業",
    "0271": "陸運業",
    "0272": "海運業",
    "0273": "空運業",
    "0274": "倉庫・運輸関連業",
    "0275": "情報・通信業",
    "0276": "卸売業",
    "0277": "小売業",
    "0278": "銀行業",
    "0279": "証券・商品先物取引業",
    "0280": "保険業",
    "0281": "その他金融業",
    "0282": "不動産業",
    "0283": "サービス業",
}

TRADERS_WEB_SECTOR_ALIASES = {
    "倉庫・運輸関連": "倉庫・運輸関連業",
    "証券・商品先物取引": "証券・商品先物取引業",
}

SHEET_HEADERS = [
    *[item for i in range(1, 6) for item in (f"米国セクター上昇{i}業種", f"米国セクター上昇{i}騰落率")],
    *[item for i in range(1, 6) for item in (f"米国セクター下落{i}業種", f"米国セクター下落{i}騰落率")],
    *[item for i in range(1, 6) for item in (f"東京業種上昇{i}業種", f"東京業種上昇{i}騰落率")],
    *[item for i in range(1, 6) for item in (f"東京業種下落{i}業種", f"東京業種下落{i}騰落率")],
    "セクター取得基準日",
    "セクター取得日時",
    "米国セクター取得元",
    "東京業種取得元",
]


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def request_bytes(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,text/csv,*/*",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def request_json(url: str) -> Any:
    return json.loads(request_bytes(url).decode("utf-8"))


def format_pct(value: float) -> str:
    return f"{value:+.2f}%"


def sector_row(name: str, code: str, change_pct: float, as_of: str, note: str) -> dict[str, Any]:
    return {
        "name": name,
        "code": code,
        "changePct": round(change_pct, 6),
        "change": format_pct(change_pct),
        "asOf": as_of,
        "note": note,
    }


def fetch_us_yahoo(ticker: str, name: str) -> dict[str, Any]:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(ticker)
        + "?range=10d&interval=1d&events=history&includeAdjustedClose=true"
    )
    payload = request_json(url)
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    adjusted = ((indicators.get("adjclose") or [{}])[0].get("adjclose") or [])
    closes = adjusted or ((indicators.get("quote") or [{}])[0].get("close") or [])
    valid = [(int(ts), float(close)) for ts, close in zip(timestamps, closes) if close is not None]
    if len(valid) < 2:
        raise ValueError(f"{ticker}: two daily closes were not returned")
    previous, latest = valid[-2], valid[-1]
    if previous[1] == 0:
        raise ValueError(f"{ticker}: previous close is zero")
    change_pct = (latest[1] / previous[1] - 1.0) * 100.0
    as_of = dt.datetime.fromtimestamp(latest[0], dt.timezone.utc).date().isoformat()
    return sector_row(name, ticker, change_pct, as_of, f"{ticker}調整後終値の前営業日比")


def fetch_us_stooq(ticker: str, name: str) -> dict[str, Any]:
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=20)
    url = (
        "https://stooq.com/q/d/l/?s="
        + urllib.parse.quote(ticker.lower() + ".us")
        + "&d1="
        + start.strftime("%Y%m%d")
        + "&d2="
        + today.strftime("%Y%m%d")
        + "&i=d"
    )
    text = request_bytes(url).decode("utf-8-sig")
    records = [row for row in csv.DictReader(io.StringIO(text)) if row.get("Close")]
    if len(records) < 2:
        raise ValueError(f"{ticker}: Stooq did not return two closes")
    previous, latest = records[-2], records[-1]
    prev_close = float(previous["Close"])
    close = float(latest["Close"])
    change_pct = (close / prev_close - 1.0) * 100.0
    return sector_row(name, ticker, change_pct, latest["Date"], f"{ticker}終値の前営業日比（予備取得）")


def accept_source_date(row: dict[str, Any], expected_date: str | None, label: str) -> dict[str, Any]:
    """Accept same-day or newer public data, but never silently publish older data."""
    actual_date = str(row.get("asOf") or "")[:10]
    if expected_date and (not actual_date or actual_date < expected_date):
        raise ValueError(
            f"{label}: public source returned {actual_date or 'no date'}; "
            f"expected at least {expected_date}"
        )
    return row


def fetch_us_market(expected_date: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    errors: list[str] = []
    for ticker, name in US_SECTORS.items():
        try:
            result.append(accept_source_date(fetch_us_yahoo(ticker, name), expected_date, f"{ticker} Yahoo"))
        except Exception as first_error:  # noqa: BLE001
            try:
                result.append(accept_source_date(fetch_us_stooq(ticker, name), expected_date, f"{ticker} Stooq"))
            except Exception as second_error:  # noqa: BLE001
                errors.append(f"{ticker}: Yahoo={first_error}; Stooq={second_error}")
    return result, errors


def html_to_text_lines(html: str) -> list[str]:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def fetch_japan_sector(code: str, name: str) -> dict[str, Any]:
    url = f"https://s.kabutan.jp/stocks/{code}/"
    html = request_bytes(url).decode("utf-8", errors="replace")
    lines = html_to_text_lines(html)
    title_index = next(
        (index for index, line in enumerate(lines) if name in line and "株価・基本情報" in line),
        -1,
    )
    search_lines = lines[title_index + 1 : title_index + 45] if title_index >= 0 else lines[:160]
    pct_pattern = re.compile(r"^[+−-]?\d+(?:\.\d+)?%$")
    pct_text = next((line for line in search_lines if pct_pattern.fullmatch(line)), "")
    if not pct_text:
        # Fallback: locate a percentage near the current-value time marker.
        for index, line in enumerate(lines):
            if line in {"(15:30)", "(15:00)"}:
                nearby = lines[max(0, index - 12) : index]
                pct_text = next((item for item in reversed(nearby) if pct_pattern.fullmatch(item)), "")
                if pct_text:
                    break
    if not pct_text:
        raise ValueError("daily percentage change was not found")
    change_pct = float(pct_text.replace("−", "-").replace("%", ""))
    date_match = re.search(r"株価情報\s*\((\d{1,2})/(\d{1,2})時点\)", " ".join(lines))
    now = now_jst()
    if date_match:
        month, day = map(int, date_match.groups())
        year = now.year - (1 if month > now.month + 1 else 0)
        as_of = dt.date(year, month, day).isoformat()
    else:
        as_of = now.date().isoformat()
    return sector_row(name, code, change_pct, as_of, "東証33業種指数の前営業日比")


def fetch_japan_market() -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    errors: list[str] = []
    for code, name in JP_SECTORS.items():
        try:
            result.append(fetch_japan_sector(code, name))
        except Exception as error:  # noqa: BLE001
            errors.append(f"{code} {name}: {error}")
        time.sleep(0.12)
    return result, errors


def parse_japan_traders_web_html(html: str, expected_date: str | None = None) -> list[dict[str, Any]]:
    """Parse the one-page Traders Web 33-sector ranking."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    date_match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s+\d{1,2}:\d{2}", text)
    source_date = None
    if date_match:
        source_date = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    if expected_date and (not source_date or source_date < expected_date):
        raise ValueError(
            f"Traders Web sector date is older than the target: "
            f"source={source_date or 'missing'}, expected at least {expected_date}"
        )
    table = next(
        (
            candidate
            for candidate in soup.find_all("table")
            if "騰落率" in " ".join(list(candidate.stripped_strings)[:40])
            and ("業種" in " ".join(list(candidate.stripped_strings)[:40]) or "セクター" in " ".join(list(candidate.stripped_strings)[:40]))
        ),
        None,
    )
    if table is None:
        raise ValueError("Traders Web sector ranking table was not found")
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in table.find_all("tr"):
        cells = [" ".join(cell.stripped_strings).strip() for cell in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        name = ""
        for cell in cells:
            normalized = re.sub(r"[（(]東証[）)]", "", cell).strip()
            normalized = TRADERS_WEB_SECTOR_ALIASES.get(normalized, normalized)
            if normalized in JP_SECTORS.values():
                name = normalized
                break
        pct_cell = next((cell for cell in cells if re.search(r"[+−-]?\d+(?:\.\d+)?\s*%", cell)), "")
        if not name or not pct_cell or name in seen:
            continue
        match = re.search(r"[+−-]?\d+(?:\.\d+)?", pct_cell)
        if not match:
            continue
        seen.add(name)
        values.append(sector_row(name, "", float(match.group(0).replace("−", "-")), source_date or expected_date or "", "トレーダーズ・ウェブ業種別ランキング"))
    if len(values) < len(JP_SECTORS):
        raise ValueError(f"Traders Web sector ranking returned only {len(values)} sectors")
    return values


def fetch_japan_traders_web(expected_date: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch the preferred one-page Traders Web 33-sector ranking."""
    try:
        html = request_bytes(TRADERS_WEB_SECTOR_URL).decode("utf-8", errors="replace")
        return parse_japan_traders_web_html(html, expected_date), []
    except Exception as error:  # noqa: BLE001
        return [], [f"Traders Web: {error}"]


def load_existing() -> dict[str, Any]:
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_stocks() -> dict[str, Any]:
    try:
        return json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def top_groups(values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(values, key=lambda item: float(item["changePct"]), reverse=True)
    return ordered[:5], list(reversed(ordered[-5:]))


def build_market(
    key: str,
    values: list[dict[str, Any]],
    existing: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    previous = ((existing.get("markets") or {}).get(key) or {})
    minimum = 11 if key == "us" else 30
    if len(values) < minimum:
        current = current_block(
            status="unavailable",
            data_date=None,
            as_of=None,
            updated_at=now_jst().isoformat(),
            source={"name": "Yahoo Finance / Stooq" if key == "us" else "Traders Web / 株探"},
            error="; ".join(errors[-20:]) or "当日の業種データを取得できませんでした",
            title="米国市場のセクター・業種" if key == "us" else "東京市場のセクター・業種",
            flag="US" if key == "us" else "JP",
            gainers=[], losers=[], all=[], lastErrors=errors[-20:],
        )
        return {**current, "lastGood": last_good_from(previous)}
    gainers, losers = top_groups(values)
    as_of = max((item.get("asOf") or "" for item in values), default="")
    current = current_block(
        status="verified",
        data_date=as_of,
        as_of=as_of,
        updated_at=now_jst().isoformat(),
        source={"name": "Select Sector SPDR ETF" if key == "us" else "Traders Web / 株探"},
        title="米国市場のセクター・業種" if key == "us" else "東京市場のセクター・業種",
        flag="US" if key == "us" else "JP",
        sourceLabel="Select Sector SPDR ETF" if key == "us" else "東証33業種指数",
        gainers=gainers,
        losers=losers,
        all=sorted(values, key=lambda item: float(item["changePct"]), reverse=True),
        lastErrors=errors[-20:],
    )
    return {**current, "lastGood": last_good_from(previous)}


def build_payload() -> dict[str, Any]:
    existing = load_existing()
    stocks = load_stocks()
    expected_us_date = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    expected_japan_date = str((stocks.get("marketDates") or {}).get("japan") or "")[:10]
    us_values, us_errors = fetch_us_market(expected_us_date or None)
    japan_values, japan_errors = fetch_japan_traders_web(expected_japan_date or None)
    if len(japan_values) < 30:
        fallback_values, fallback_errors = fetch_japan_market()
        japan_values, japan_errors = fallback_values, japan_errors + fallback_errors
    generated = now_jst()
    us = build_market("us", us_values, existing, us_errors)
    japan = build_market("japan", japan_values, existing, japan_errors)
    statuses = {us.get("status"), japan.get("status")}
    status = "ok" if statuses == {"verified"} else "degraded"
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": generated.isoformat(),
        "status": status,
        "markets": {"us": us, "japan": japan},
        "errors": {"us": us_errors, "japan": japan_errors},
        "sources": [
            {
                "id": "US_SELECT_SECTOR_ETF",
                "name": "Yahoo Finance Chart API / Stooq fallback",
                "url": "https://query1.finance.yahoo.com/v8/finance/chart/",
            },
            {
                "id": "JP_33_SECTOR_TRADERS_WEB_KABUTAN",
                "name": "トレーダーズ・ウェブ業種別ランキング / 株探 東証33業種指数ページ",
                "url": TRADERS_WEB_SECTOR_URL,
            },
        ],
    }


def write_output(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MARKET_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKET_OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def column_letter(index: int) -> str:
    value = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def row_value_map(payload: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    groups = [
        ("米国セクター上昇", payload["markets"]["us"].get("gainers") or []),
        ("米国セクター下落", payload["markets"]["us"].get("losers") or []),
        ("東京業種上昇", payload["markets"]["japan"].get("gainers") or []),
        ("東京業種下落", payload["markets"]["japan"].get("losers") or []),
    ]
    for prefix, items in groups:
        for index in range(1, 6):
            item = items[index - 1] if index <= len(items) else {}
            values[f"{prefix}{index}業種"] = str(item.get("name") or "")
            values[f"{prefix}{index}騰落率"] = str(item.get("change") or "")
    dates = [
        str((payload["markets"].get(key) or {}).get("asOf") or "")
        for key in ("us", "japan")
    ]
    values["セクター取得基準日"] = max(dates)
    values["セクター取得日時"] = str(payload.get("generatedAt") or "")
    values["米国セクター取得元"] = "Yahoo Finance Chart API（Select Sector SPDR ETF、Stooq予備）"
    values["東京業種取得元"] = "株探 東証33業種指数ページ（JPX指数系列）"
    return values


def merge_stock_analysis_json(workbook: Any, payload: dict[str, Any]) -> None:
    try:
        worksheet = workbook.worksheet("Stock_Analysis_JSON")
        raw = str(worksheet.acell("B2").value or "").strip()
        if not raw:
            return
        data = json.loads(raw)
        data.setdefault("sectors", {})
        for key in ("us", "japan"):
            market = payload["markets"][key]
            current = dict(data["sectors"].get(key) or {})
            current["title"] = market["title"]
            current["flag"] = market["flag"]
            current["gainers"] = market.get("gainers") or []
            current["losers"] = market.get("losers") or []
            current["rows"] = market.get("gainers") or []  # backward compatibility
            current["dataAsOf"] = market.get("asOf") or ""
            current["sourceLabel"] = market.get("sourceLabel") or ""
            data["sectors"][key] = current
        data["updatedAt"] = now_jst().strftime("%Y/%m/%d %H:%M")
        data["sourceStatus"] = "Google Sheets＋セクター自動取得"
        worksheet.update("B2", [[json.dumps(data, ensure_ascii=False)]], value_input_option="RAW")
    except Exception as error:  # noqa: BLE001
        print(f"Stock_Analysis_JSON merge warning: {error}")


def sync_google_sheets(payload: dict[str, Any]) -> None:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_json:
        print("Google Sheets sync skipped: credentials are not configured.")
        return

    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore

    info = json.loads(credentials_json)
    credentials = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(credentials)
    workbook = client.open_by_key(spreadsheet_id)
    worksheet = workbook.worksheet("終値一覧")
    table = worksheet.get_all_values()
    if not table:
        raise RuntimeError("終値一覧 sheet is empty")
    headers = list(table[0])
    missing = [header for header in SHEET_HEADERS if header not in headers]
    if missing:
        headers.extend(missing)
        worksheet.update(
            f"A1:{column_letter(len(headers))}1",
            [headers],
            value_input_option="RAW",
        )
        table[0] = headers

    values = row_value_map(payload)
    target_date = values["セクター取得基準日"].replace("-", "/")
    date_column = headers.index("日付")
    row_number = next(
        (
            index + 1
            for index, row in enumerate(table[1:], start=1)
            if len(row) > date_column and str(row[date_column]).strip().replace("-", "/") == target_date
        ),
        0,
    )
    if not row_number:
        row_number = len(table) + 1
        row = [""] * len(headers)
        row[date_column] = target_date
    else:
        existing_row = table[row_number - 1]
        row = existing_row + [""] * (len(headers) - len(existing_row))

    for header, value in values.items():
        row[headers.index(header)] = value
    worksheet.update(
        f"A{row_number}:{column_letter(len(headers))}{row_number}",
        [row],
        value_input_option="RAW",
    )
    merge_stock_analysis_json(workbook, payload)
    print(f"Google Sheets sync succeeded: 終値一覧 row {row_number}, date {target_date}")


def main() -> int:
    payload = build_payload()
    write_output(payload)
    sync_google_sheets(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "generatedAt": payload["generatedAt"],
                "us": {
                    "status": payload["markets"]["us"].get("status"),
                    "asOf": payload["markets"]["us"].get("asOf"),
                    "count": len(payload["markets"]["us"].get("all") or []),
                },
                "japan": {
                    "status": payload["markets"]["japan"].get("status"),
                    "asOf": payload["markets"]["japan"].get("asOf"),
                    "count": len(payload["markets"]["japan"].get("all") or []),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
