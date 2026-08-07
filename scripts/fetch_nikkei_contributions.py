#!/usr/bin/env python3
"""Fetch and validate Nikkei 225 contribution rankings, then sync WEB/Sheets data.

Source:
- Kabutan Nikkei 225 contribution ranking (descending / ascending contribution)

Safety rules:
- never keep sample/fixed contribution rows as if they were live data;
- require 5 positive and 5 negative contributors;
- require code/name/contribution for every row;
- reject duplicate stock codes across positive/negative groups;
- reject source-date mismatch between positive and negative pages;
- on failure, keep the previous verified contribution payload and mark the attempt failed.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
STOCKS_PATH = ROOT / "data" / "stocks.json"
OUTPUT_PATH = ROOT / "data" / "nikkei-contributions.json"
JST = dt.timezone(dt.timedelta(hours=9))

DESC_URL = "https://s.kabutan.jp/warnings/nk225_contrib/?direction=desc&market=all&order=contrib_price"
ASC_URL = "https://s.kabutan.jp/warnings/nk225_contrib/?direction=asc&market=all&order=contrib_price"
USER_AGENT = "Mozilla/5.0 (compatible; Chat-GPT-Market-Report/1.0; +https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report)"


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en-US;q=0.8,en;q=0.6"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def source_timestamp(text: str) -> tuple[str, str]:
    match = re.search(r"株価[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})現在", text)
    if not match:
        raise ValueError("株探ページから株価基準日時を取得できません")
    year, month, day, hour, minute = (int(x) for x in match.groups())
    date = dt.date(year, month, day).isoformat()
    stamp = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00+09:00"
    return date, stamp


def normalise_code(text: str) -> str:
    text = text.strip().upper()
    if re.fullmatch(r"\d{4}", text) or re.fullmatch(r"\d{3}[A-Z]", text):
        return text
    return ""


def extract_code(cell: Any) -> str:
    # Prefer an explicit code embedded in the stock link URL.
    for anchor in cell.find_all("a"):
        href = str(anchor.get("href") or "")
        for pattern in (r"(?:code=|/stocks?/)(\d{4}|\d{3}[A-Z])", r"/(\d{4}|\d{3}[A-Z])(?:/|\?|$)"):
            match = re.search(pattern, href, flags=re.I)
            if match:
                code = normalise_code(match.group(1))
                if code:
                    return code

    # Fallback to visible text, choosing the last code-like token before market suffixes.
    text = " ".join(cell.stripped_strings)
    candidates = re.findall(r"(?<![0-9A-Z])(\d{4}|\d{3}[A-Z])(?![0-9A-Z])", text, flags=re.I)
    for candidate in reversed(candidates):
        code = normalise_code(candidate)
        if code:
            return code
    return ""


def extract_name(cell: Any, code: str) -> str:
    text = " ".join(cell.stripped_strings)
    text = re.sub(r"\s+", " ", text).strip()
    if code:
        text = re.sub(rf"\s*{re.escape(code)}\b.*$", "", text, flags=re.I).strip()
    text = re.sub(r"\s+(東P|東S|東G|東Ｅ|東EN|東Ｒ|東IF)\b.*$", "", text).strip()
    return text


def contribution_value(text: str) -> float:
    match = re.search(r"[-+−]?\d+(?:\.\d+)?", text.replace(",", "").replace("−", "-"))
    if not match:
        raise ValueError(f"寄与度を数値化できません: {text!r}")
    return float(match.group(0))


def find_ranking_table(soup: BeautifulSoup) -> Any:
    for table in soup.find_all("table"):
        header_text = " ".join(table.stripped_strings[:20]) if hasattr(table.stripped_strings, "__getitem__") else " ".join(list(table.stripped_strings)[:20])
        if "寄与度" in header_text and "銘柄" in header_text:
            return table
    # Some parsers do not support slicing generator-like stripped_strings.
    for table in soup.find_all("table"):
        head = " ".join(list(table.stripped_strings)[:30])
        if "寄与度" in head and "銘柄" in head:
            return table
    raise ValueError("日経平均寄与度ランキング表を取得できません")


def parse_page(url: str) -> tuple[list[dict[str, Any]], str, str]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)
    as_of, source_at = source_timestamp(full_text)
    table = find_ranking_table(soup)

    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        first_text = " ".join(cells[0].stripped_strings)
        if "銘柄" in first_text or "コード" in first_text:
            continue
        code = extract_code(cells[0])
        name = extract_name(cells[0], code)
        if not code or not name:
            continue
        contribution_text = " ".join(cells[2].stripped_strings).strip()
        try:
            contribution = contribution_value(contribution_text)
        except ValueError:
            continue
        close_text = " ".join(cells[1].stripped_strings).strip()
        rows.append({
            "code": code,
            "name": name,
            "displayName": f"{name}（{code}）",
            "close": close_text,
            "contributionValue": contribution,
            "contribution": f"{contribution:+.2f}",
        })
    if not rows:
        raise ValueError("寄与度ランキングの銘柄行を取得できません")
    return rows, as_of, source_at


def select_top(rows: list[dict[str, Any]], positive: bool) -> list[dict[str, Any]]:
    filtered = [row for row in rows if (row["contributionValue"] > 0 if positive else row["contributionValue"] < 0)]
    filtered.sort(key=lambda row: row["contributionValue"], reverse=positive)
    selected = filtered[:5]
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank
    return selected


def validate(top: list[dict[str, Any]], bottom: list[dict[str, Any]], top_date: str, bottom_date: str) -> None:
    if top_date != bottom_date:
        raise ValueError(f"上位と下位の基準日が不一致: {top_date} / {bottom_date}")
    if len(top) != 5 or len(bottom) != 5:
        raise ValueError(f"寄与度ランキングが5件ずつそろっていません: top={len(top)}, bottom={len(bottom)}")

    top_codes = {row["code"] for row in top}
    bottom_codes = {row["code"] for row in bottom}
    duplicates = sorted(top_codes & bottom_codes)
    if duplicates:
        raise ValueError("同一銘柄コードが寄与度上位・下位に重複: " + ", ".join(duplicates))

    for row in top:
        if row["contributionValue"] <= 0:
            raise ValueError(f"寄与度上位に非プラス値: {row}")
    for row in bottom:
        if row["contributionValue"] >= 0:
            raise ValueError(f"寄与度下位に非マイナス値: {row}")

    parsed = dt.date.fromisoformat(top_date)
    if (now_jst().date() - parsed).days > 7:
        raise ValueError(f"寄与度データが古すぎます: {top_date}")


def clean_for_public(row: dict[str, Any], as_of: str) -> dict[str, Any]:
    return {
        "rank": row["rank"],
        "code": row["code"],
        "name": row["displayName"],
        "shortName": row["name"],
        "close": row["close"],
        "contribution": row["contribution"],
        "reason": f"株探 日経平均寄与度ランキング・基準日 {as_of}",
    }


def build_payload() -> dict[str, Any]:
    desc_rows, desc_date, desc_at = parse_page(DESC_URL)
    asc_rows, asc_date, asc_at = parse_page(ASC_URL)
    top = select_top(desc_rows, True)
    bottom = select_top(asc_rows, False)
    validate(top, bottom, desc_date, asc_date)

    generated = now_jst().isoformat()
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": generated,
        "status": "verified",
        "asOf": desc_date,
        "sourceAt": {"top": desc_at, "bottom": asc_at},
        "source": {
            "name": "株探 日経平均の寄与度ランキング",
            "topUrl": DESC_URL,
            "bottomUrl": ASC_URL,
        },
        "top": [clean_for_public(row, desc_date) for row in top],
        "bottom": [clean_for_public(row, desc_date) for row in bottom],
    }


def merge_into_stocks(payload: dict[str, Any]) -> None:
    stocks = load_json(STOCKS_PATH, {})
    if not stocks:
        raise RuntimeError("data/stocks.json がありません")
    contributions = stocks.setdefault("contributions", {})
    contributions["japan"] = {
        "title": "日本市場（日経225寄与度 上位・下位）",
        "flag": "JP",
        "status": "verified",
        "asOf": payload["asOf"],
        "source": payload["source"]["name"],
        "top": payload["top"],
        "bottom": payload["bottom"],
    }
    stocks["updatedAt"] = now_jst().isoformat()
    stocks["sourceStatus"] = "Google Sheets＋日経225寄与度検証済みデータ"
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def sheet_value_map(payload: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for label, items in (("日経225寄与度上位", payload["top"]), ("日経225寄与度下位", payload["bottom"])):
        for index, item in enumerate(items, start=1):
            values[f"{label}{index}コード"] = str(item["code"])
            values[f"{label}{index}銘柄"] = str(item["shortName"])
            values[f"{label}{index}寄与度"] = str(item["contribution"])
    values["日経225寄与度基準日"] = payload["asOf"]
    values["日経225寄与度取得日時"] = payload["generatedAt"]
    values["日経225寄与度取得元"] = payload["source"]["name"]
    return values


def merge_stock_analysis_json(workbook: Any, payload: dict[str, Any]) -> None:
    worksheet = workbook.worksheet("Stock_Analysis_JSON")
    raw = str(worksheet.acell("B2").value or "").strip()
    if not raw:
        return
    data = json.loads(raw)
    data.setdefault("contributions", {})["japan"] = {
        "title": "日本市場（日経225寄与度 上位・下位）",
        "flag": "JP",
        "status": "verified",
        "asOf": payload["asOf"],
        "source": payload["source"]["name"],
        "top": payload["top"],
        "bottom": payload["bottom"],
    }
    data["updatedAt"] = now_jst().strftime("%Y/%m/%d %H:%M")
    data["sourceStatus"] = "Google Sheets＋日経225寄与度検証済みデータ"
    worksheet.update("B2", [[json.dumps(data, ensure_ascii=False)]], value_input_option="RAW")


def sync_google_sheets(payload: dict[str, Any]) -> None:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not credentials_json:
        print("Google Sheets sync skipped: credentials are not configured")
        return

    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore

    credentials = Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    workbook = gspread.authorize(credentials).open_by_key(spreadsheet_id)
    worksheet = workbook.worksheet("終値一覧")
    table = worksheet.get_all_values()
    if not table:
        raise RuntimeError("終値一覧 sheet is empty")

    headers = list(table[0])
    values = sheet_value_map(payload)
    missing = [header for header in values if header not in headers]
    if missing:
        headers.extend(missing)
        worksheet.update(f"A1:{column_letter(len(headers))}1", [headers], value_input_option="RAW")
        table[0] = headers

    target_date = payload["asOf"].replace("-", "/")
    date_col = headers.index("日付")
    row_number = next((i + 2 for i, row in enumerate(table[1:]) if len(row) > date_col and str(row[date_col]).strip().replace("-", "/") == target_date), 0)
    if not row_number:
        row_number = len(table) + 1
        row = [""] * len(headers)
        row[date_col] = target_date
    else:
        existing = table[row_number - 1]
        row = existing + [""] * (len(headers) - len(existing))

    for header, value in values.items():
        row[headers.index(header)] = value
    worksheet.update(f"A{row_number}:{column_letter(len(headers))}{row_number}", [row], value_input_option="RAW")
    merge_stock_analysis_json(workbook, payload)
    print(f"Google Sheets sync succeeded: row={row_number}, date={target_date}")


def main() -> int:
    previous = load_json(OUTPUT_PATH, {})
    try:
        payload = build_payload()
        OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        merge_into_stocks(payload)
        sync_google_sheets(payload)
        print(json.dumps({
            "status": "verified",
            "asOf": payload["asOf"],
            "top": [(x["code"], x["contribution"]) for x in payload["top"]],
            "bottom": [(x["code"], x["contribution"]) for x in payload["bottom"]],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001
        failed = {
            "schemaVersion": "1.0.0",
            "generatedAt": now_jst().isoformat(),
            "status": "fetch_failed",
            "error": str(error),
            "previousVerifiedAsOf": previous.get("asOf") if previous.get("status") == "verified" else "",
        }
        OUTPUT_PATH.write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
