#!/usr/bin/env python3
"""Persist verified market data to Google Sheets for ChatGPT report creation.

The dashboard JSON remains the machine source of record.  This script creates a
small, explicit Sheets contract so ChatGPT does not need to infer numbers from
free-form report text or from a legacy "closing prices" tab.
"""

from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_SHEET = "ChatGPT_Market_Input"
DEFAULT_HISTORY_SHEET = "Market_Data_Verified"
DEFAULT_RULES_SHEET = "ChatGPT_Market_Rules"
MARKET_ORDER = [
    "gold",
    "wti",
    "nikkei225_futures_ose",
    "usdjpy",
    "eurusd",
    "btcusd",
    "vix",
    "nikkei_vi",
    "fear_greed",
    "crypto_fear_greed",
]

SHEET_HEADERS = [
    "スナップショットID",
    "更新日時",
    "対象レポート時刻",
    "全体状態",
    "銘柄ID",
    "データ名",
    "利用判定",
    "現在値",
    "表示値",
    "単位",
    "前回値",
    "前回比",
    "前回比率(%)",
    "前回比表示",
    "対象時刻",
    "取得時刻",
    "検証状態",
    "鮮度",
    "前回確認値利用",
    "最終確認時刻",
    "取得元",
    "取得元URL",
    "市場区分",
    "セッション",
    "判定区分",
    "注記",
    "エラー",
]

RULES_ROWS = [
    ["優先順位", "ルール"],
    [1, "マーケットレポートの価格は ChatGPT_Market_Input を正本として使用する。"],
    [2, "利用判定が「使用可」の値だけを確認済みの最新値として使用する。"],
    [3, "利用判定が「前回確認値（要注記）」の場合は、前回値であることと最終確認時刻を本文に明記する。"],
    [4, "利用判定が「使用不可」の値は推測で補わず、取得不能と理由を記載する。"],
    [5, "単位、市場区分、セッションを変えない。XAU/USDとCOMEX金先物、OSE先物とCME・CFDを混同しない。"],
    [6, "異なる対象時刻の数値を同じ基準時点の値として比較しない。"],
    [7, "価格を記載するときは、対象時刻・取得元・検証状態を確認する。"],
    [8, "価格変化だけからニュース、中央銀行会合、介入などの出来事を推測しない。出来事は別の確認済み情報源で照合する。"],
    [9, "対象レポート時刻に一致する行がChatGPT_Market_Inputにない場合、取得不能と断定する前にGitHubのdata/market/latest.jsonとdata/market/chatgpt_input.csvを確認する。"],
    [10, "GitHub側に当日・対象レポート時刻の検証済み値がある場合は、その値を代替正本として使用し、Google Sheets同期遅延として扱う。『取得不能』とは書かない。"],
    [11, "レポート作成前にdata/market/report_readiness.jsonのready=trueを確認する。ready=falseの場合はデータ不足理由を示し、古い対象時刻の行を新しいレポート時刻の値として扱わない。"],
    [12, "対象レポート時刻の不一致は『データ未取得』ではなく『連携・時刻タグ不一致』として区別する。同日の検証済み値が存在する場合は時刻と取得元を明記して利用可否を判断する。"],
]


class SheetsSyncError(RuntimeError):
    """Raised when configured Google Sheets persistence fails."""


def safe_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return ""
        rounded = round(float(value), 10)
        return int(rounded) if rounded.is_integer() else rounded
    return str(value)


def use_policy(market: dict[str, Any]) -> str:
    status = market.get("verificationStatus")
    if status == "verified" and not market.get("fallbackUsed"):
        return "使用可"
    if status == "fallback" or market.get("fallbackUsed"):
        return "前回確認値（要注記）"
    return "使用不可"


def market_rows(payload: dict[str, Any]) -> list[list[Any]]:
    generated_at = str(payload.get("generatedAt") or "")
    report_slot = str(payload.get("reportSlot") or "")
    overall_status = str(payload.get("overallStatus") or "unknown")
    markets = payload.get("markets") or {}
    ordered_ids = MARKET_ORDER + sorted(set(markets) - set(MARKET_ORDER))
    rows: list[list[Any]] = []

    for symbol_id in ordered_ids:
        market = markets.get(symbol_id)
        if not isinstance(market, dict):
            continue
        snapshot_id = f"{generated_at}|{symbol_id}"
        rows.append(
            [
                snapshot_id,
                generated_at,
                report_slot,
                overall_status,
                symbol_id,
                market.get("displayName", symbol_id),
                use_policy(market),
                safe_cell(market.get("value")),
                market.get("displayValue", ""),
                market.get("unit", ""),
                safe_cell(market.get("previousClose")),
                safe_cell(market.get("change")),
                safe_cell(market.get("changePercent")),
                market.get("changeText", ""),
                market.get("asOf", ""),
                market.get("fetchedAt", ""),
                market.get("verificationStatus", ""),
                market.get("freshnessStatus", ""),
                bool(market.get("fallbackUsed")),
                market.get("lastVerifiedAt", ""),
                market.get("sourceName", ""),
                market.get("sourceUrl", ""),
                market.get("marketType", ""),
                market.get("session", ""),
                market.get("classification", ""),
                market.get("note", ""),
                market.get("error", "") or "",
            ]
        )
    return rows


def load_service_account_info(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise SheetsSyncError("GOOGLE_SERVICE_ACCOUNT_JSON is empty")
    path = Path(raw)
    if not raw.startswith("{") and len(raw) < 240 and path.is_file():
        raw = path.read_text(encoding="utf-8")
    elif not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except Exception as exc:
            raise SheetsSyncError(
                "GOOGLE_SERVICE_ACCOUNT_JSON must be JSON, a JSON file path, or base64-encoded JSON"
            ) from exc
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SheetsSyncError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    if not info.get("client_email") or not info.get("private_key"):
        raise SheetsSyncError("service account JSON is missing client_email or private_key")
    return info


def create_authorized_session(info: dict[str, Any]):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:
        raise SheetsSyncError(
            "Google Sheets dependencies are missing. Install scripts/requirements-market-data.txt"
        ) from exc
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return AuthorizedSession(credentials)


class SheetsClient:
    def __init__(self, session: Any, spreadsheet_id: str):
        self.session = session
        self.spreadsheet_id = spreadsheet_id
        self.base_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"

    @staticmethod
    def _range(sheet_name: str, cells: str) -> str:
        escaped = sheet_name.replace("'", "''")
        return quote(f"'{escaped}'!{cells}", safe="!'")

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.request(method, url, timeout=30, **kwargs)
        if not getattr(response, "ok", False):
            detail = getattr(response, "text", "")[:500]
            raise SheetsSyncError(f"Google Sheets API {method} failed: {response.status_code} {detail}")
        if not getattr(response, "content", b""):
            return {}
        return response.json()

    def sheet_map(self) -> dict[str, int]:
        data = self._request(
            "GET",
            self.base_url + "?fields=sheets.properties(sheetId,title)",
        )
        return {
            str(item["properties"]["title"]): int(item["properties"]["sheetId"])
            for item in data.get("sheets", [])
        }

    def ensure_sheets(self, names: Iterable[str]) -> dict[str, int]:
        sheets = self.sheet_map()
        missing = [name for name in names if name not in sheets]
        if missing:
            self._request(
                "POST",
                self.base_url + ":batchUpdate",
                json={"requests": [{"addSheet": {"properties": {"title": name}}} for name in missing]},
            )
            sheets = self.sheet_map()
        return sheets

    def get_values(self, sheet_name: str, cells: str) -> list[list[Any]]:
        data = self._request("GET", self.base_url + "/values/" + self._range(sheet_name, cells))
        return data.get("values") or []

    def clear(self, sheet_name: str, cells: str = "A:AZ") -> None:
        self._request("POST", self.base_url + "/values/" + self._range(sheet_name, cells) + ":clear", json={})

    def update(self, sheet_name: str, cells: str, values: list[list[Any]]) -> None:
        self._request(
            "PUT",
            self.base_url + "/values/" + self._range(sheet_name, cells) + "?valueInputOption=RAW",
            json={"majorDimension": "ROWS", "values": values},
        )

    def append(self, sheet_name: str, cells: str, values: list[list[Any]]) -> None:
        if not values:
            return
        self._request(
            "POST",
            self.base_url
            + "/values/"
            + self._range(sheet_name, cells)
            + ":append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
            json={"majorDimension": "ROWS", "values": values},
        )

    def format_table(self, sheet_id: int, column_count: int, row_count: int) -> None:
        requests = [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": column_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.88, "green": 0.93, "blue": 1.0},
                            "textFormat": {"bold": True},
                            "wrapStrategy": "WRAP",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy)",
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": column_count,
                    }
                }
            },
        ]
        if row_count > 1:
            requests.append(
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": row_count,
                                "startColumnIndex": 0,
                                "endColumnIndex": column_count,
                            }
                        }
                    }
                }
            )
        self._request("POST", self.base_url + ":batchUpdate", json={"requests": requests})


def sync_payload(client: SheetsClient, payload: dict[str, Any], input_sheet: str, history_sheet: str, rules_sheet: str) -> dict[str, Any]:
    rows = market_rows(payload)
    if not rows:
        raise SheetsSyncError("market data JSON contains no market rows")

    sheets = client.ensure_sheets([input_sheet, history_sheet, rules_sheet])

    client.clear(input_sheet)
    client.update(input_sheet, "A1", [SHEET_HEADERS] + rows)

    history_values = client.get_values(history_sheet, "A:A")
    existing_ids = {str(row[0]) for row in history_values[1:] if row}
    if not history_values:
        client.update(history_sheet, "A1", [SHEET_HEADERS])
    new_history_rows = [row for row in rows if str(row[0]) not in existing_ids]
    client.append(history_sheet, "A:AA", new_history_rows)

    client.clear(rules_sheet)
    client.update(rules_sheet, "A1", RULES_ROWS)

    client.format_table(sheets[input_sheet], len(SHEET_HEADERS), len(rows) + 1)
    client.format_table(
        sheets[history_sheet],
        len(SHEET_HEADERS),
        max(len(history_values), 1) + len(new_history_rows),
    )
    client.format_table(sheets[rules_sheet], 2, len(RULES_ROWS))

    return {
        "inputRows": len(rows),
        "historyRowsAdded": len(new_history_rows),
        "overallStatus": payload.get("overallStatus"),
        "generatedAt": payload.get("generatedAt"),
    }


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    latest_path = Path(os.environ.get("MARKET_DATA_JSON_PATH", str(ROOT / "data" / "market" / "latest.json")))
    if not spreadsheet_id or not service_account_json:
        print("Google Sheets persistence skipped: MARKET_DATA_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        return 0

    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    if payload.get("overallStatus") == "blocked":
        raise SheetsSyncError("market data status is blocked; refusing to replace ChatGPT input sheet")

    info = load_service_account_info(service_account_json)
    client = SheetsClient(create_authorized_session(info), spreadsheet_id)
    summary = sync_payload(
        client,
        payload,
        os.environ.get("MARKET_DATA_INPUT_SHEET", DEFAULT_INPUT_SHEET),
        os.environ.get("MARKET_DATA_HISTORY_SHEET", DEFAULT_HISTORY_SHEET),
        os.environ.get("MARKET_DATA_RULES_SHEET", DEFAULT_RULES_SHEET),
    )
    print("Google Sheets market data sync completed: " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
