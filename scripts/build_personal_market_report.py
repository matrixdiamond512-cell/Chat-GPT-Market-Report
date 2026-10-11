#!/usr/bin/env python3
"""Render a private report draft from the same normalized payload used by Sheets.

This module performs no acquisition and never touches the production close list.
With --write-test-sheet it appends one immutable report version to a dedicated
private test-sheet tab and verifies the readback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_INPUT = ROOT / "data" / "market" / "chatgpt-input.json"
DEFAULT_OUTPUT = ROOT / "data" / "market" / "personal-market-report.md"
JST = dt.timezone(dt.timedelta(hours=9))
REPORT_TAB = "Personal_Market_Report"
HEADERS = [
    "Snapshot ID", "生成日時", "レポート日", "レポート時刻", "状態",
    "取得項目数", "28項目本文", "本文SHA256",
]


class PersonalReportError(ValueError):
    pass


try:
    from scripts.build_chatgpt_report_input import ITEMS
except ModuleNotFoundError:
    from build_chatgpt_report_input import ITEMS


def load_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PersonalReportError("market input could not be read") from exc
    if not isinstance(value, dict) or not isinstance(value.get("markets"), dict):
        raise PersonalReportError("market input must contain a markets object")
    return value


def report_value(market: dict[str, Any]) -> str:
    status = str(market.get("verificationStatus") or "unavailable")
    raw = market.get("displayValue")
    if raw in (None, ""):
        raw = market.get("value")
    if raw in (None, ""):
        return "—"
    market_type = str(market.get("marketType") or "")
    derivative = market_type in {"continuous_futures", "futures_cme", "futures_ose"}
    settlement_confirmed = str(market.get("priceType") or market.get("valueDefinition") or "").lower() in {
        "settlement", "official_settlement", "exchange_settlement", "清算値", "公式清算値",
    }
    if status == "verified" and (not derivative or settlement_confirmed):
        return str(raw)
    if status == "fallback" or market.get("fallbackUsed") or derivative:
        return f"参考値: {raw}"
    return "—"


def status_label(market: dict[str, Any]) -> str:
    status = str(market.get("verificationStatus") or "unavailable")
    if status == "verified":
        market_type = str(market.get("marketType") or "")
        if market_type in {"continuous_futures", "futures_cme", "futures_ose"} and str(market.get("priceType") or market.get("valueDefinition") or "").lower() not in {
            "settlement", "official_settlement", "exchange_settlement", "清算値", "公式清算値",
        }:
            return "参考値（清算値未確認）"
        return "検証済み"
    if status == "fallback" or market.get("fallbackUsed"):
        return "参考値"
    return "未取得"


def render_report(payload: dict[str, Any]) -> str:
    markets = payload.get("markets") or {}
    retrieved = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("reportDate") or payload.get("previousCloseDate") or "")
    report_slot = str(payload.get("reportSlot") or "")
    report_symbols = [item[1] for item in ITEMS]
    verified = sum(1 for symbol in report_symbols if isinstance(markets.get(symbol), dict) and markets[symbol].get("verificationStatus") == "verified")
    fallback = sum(1 for symbol in report_symbols if isinstance(markets.get(symbol), dict) and (markets[symbol].get("verificationStatus") == "fallback" or markets[symbol].get("fallbackUsed")))
    lines = [
        f"# 個人用マーケットレポート草案 {report_date} {report_slot}".strip(),
        "",
        f"生成日時: {retrieved or '不明'}",
        f"状態: {payload.get('overallStatus') or 'unknown'} / 検証済み {verified}項目 / 参考値 {fallback}項目 / 対象28項目",
        "",
        "各市場の営業日と日次締めは項目ごとに記録しています。参考値は清算値などの確定値と混同しません。",
        "",
        "| 市場データ | 値 | 単位 | 基準日 | 取得元 | 状態 |",
        "|---|---:|---|---|---|---|",
    ]
    for label, symbol, item_unit, _, _ in ITEMS:
        market = markets.get(symbol)
        if not isinstance(market, dict):
            market = {"verificationStatus": "unavailable"}
        label = str(market.get("displayName") or label).replace("|", "\\|")
        value = report_value(market).replace("|", "\\|")
        unit = str(market.get("unit") or item_unit).replace("|", "\\|")
        as_of = str(market.get("asOf") or "—").replace("|", "\\|")
        source = str(market.get("sourceName") or market.get("sourceId") or "—").replace("|", "\\|")
        status = status_label(market)
        note = str(market.get("note") or "")
        lines.append(f"| {label} | {value} | {unit} | {as_of} | {source} | {status} |")
    lines.extend(["", "この草案は取得スナップショットから生成しています。未取得欄は推測で埋めていません。", ""])
    return "\n".join(lines)


def report_sheet_row(payload: dict[str, Any], body: str) -> list[Any]:
    generated = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("reportDate") or payload.get("previousCloseDate") or "")
    slot = str(payload.get("reportSlot") or "")
    identity = hashlib.sha256(f"{generated}|{report_date}|{slot}".encode("utf-8")).hexdigest()[:24]
    key = f"personal-report-{identity}"
    return [
        key, generated, report_date, slot, str(payload.get("overallStatus") or "unknown"),
        len(ITEMS), body, hashlib.sha256(body.encode("utf-8")).hexdigest(),
    ]


def write_test_sheet(row: list[Any]) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not account_json:
        raise PersonalReportError("private test-sheet ID or service-account credential is missing")
    if production_id and test_id == production_id:
        raise PersonalReportError("test spreadsheet matches production spreadsheet")
    try:
        from scripts.import_tradingview_mcp_candidates import append_idempotent_sheet_rows
        from scripts.write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    except ModuleNotFoundError:
        from import_tradingview_mcp_candidates import append_idempotent_sheet_rows
        from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    info = load_service_account_info(account_json)
    client = SheetsClient(create_authorized_session(info), test_id)
    result = append_idempotent_sheet_rows(client, REPORT_TAB, HEADERS, [row], "H")
    return {"tab": REPORT_TAB, **result, "productionSpreadsheetWritten": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-test-sheet", action="store_true")
    args = parser.parse_args()
    try:
        payload = load_payload(args.input)
        body = render_report(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        result: dict[str, Any] = {
            "reportDate": payload.get("reportDate") or payload.get("previousCloseDate"),
            "marketCount": len(payload.get("markets") or {}),
            "verifiedCount": sum(1 for _, symbol, _, _, _ in ITEMS if isinstance(payload["markets"].get(symbol), dict) and payload["markets"][symbol].get("verificationStatus") == "verified"),
            "fallbackCount": sum(1 for _, symbol, _, _, _ in ITEMS if isinstance(payload["markets"].get(symbol), dict) and (payload["markets"][symbol].get("verificationStatus") == "fallback" or payload["markets"][symbol].get("fallbackUsed"))),
            "output": str(args.output),
        }
        if args.write_test_sheet:
            result["sheets"] = write_test_sheet(report_sheet_row(payload, body))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, PersonalReportError) as exc:
        print(json.dumps({"status": "failed", "errorCode": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

