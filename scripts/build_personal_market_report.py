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
    "Snapshot ID", "生成日時", "データ基準日", "スナップショット状態",
    "検証済み件数", "参考値件数", "未取得件数", "レポート本文", "本文SHA256",
]


class PersonalReportError(ValueError):
    pass


try:
    from scripts.build_chatgpt_report_input import ITEMS
except ModuleNotFoundError:
    from build_chatgpt_report_input import ITEMS


def validate_sheet_target_ids(test_id: str, production_id: str) -> None:
    if not test_id or not production_id:
        raise PersonalReportError("both private test-sheet and production spreadsheet IDs are required")
    if test_id == production_id:
        raise PersonalReportError("test spreadsheet matches production spreadsheet")


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
    market_type = str(market.get("marketType") or "")
    derivative = market_type in {"continuous_futures", "futures_cme", "futures_ose"}
    settlement_confirmed = str(market.get("priceType") or market.get("valueDefinition") or "").lower() in {
        "settlement", "official_settlement", "exchange_settlement", "清算値", "公式清算値",
    }
    if derivative and not settlement_confirmed and market.get("value") not in (None, ""):
        return "参考値（清算値未確認）"
    if status == "verified":
        return "検証済み"
    if status == "fallback" or market.get("fallbackUsed"):
        return "参考値"
    if market.get("value") not in (None, "") and market.get("referenceOnly"):
        return "参考値（検証未完了）"
    return "未取得"


def report_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    markets = payload.get("markets") or {}
    verified = reference = 0
    for _, symbol, _, _, _ in ITEMS:
        market = markets.get(symbol)
        if not isinstance(market, dict) or market.get("value") in (None, ""):
            continue
        label = status_label(market)
        if label == "検証済み":
            verified += 1
        elif label.startswith("参考値"):
            reference += 1
    return verified, reference, len(ITEMS) - verified - reference


def _as_lines(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def render_detailed_analysis(report: dict[str, Any]) -> list[str]:
    """Render retained narrative analysis fields without replacing them with quotes."""
    if not isinstance(report, dict):
        return []
    sections: list[tuple[str, str]] = [
        ("全体テーマ", "theme"), ("主な変化", "changes"),
        ("市場間の整合性", "consistency"), ("主導市場", "leadingMarket"),
        ("ニュース", "news"), ("クロスアセット資金フロー", "crossAssetFlow"),
        ("需給・ポジション", "positioning"), ("セクター", "sectors"),
        ("注目イベント", "events"), ("メインシナリオ", "mainScenario"),
        ("代替シナリオ", "alternativeScenario"),
        ("シナリオの崩れ条件", "breakConditions"),
        ("リスク管理", "riskManagement"), ("次の市場への引き継ぎ", "handover"),
    ]
    original_date = f"{report.get('date') or '日付不明'} {report.get('time') or ''}".strip()
    lines = [
        "## 従来の詳細分析（保存済みレポート本文を保持）", "",
        f"> 原文のレポート日時: {original_date}。以下の分析文は当時の内容を保持し、今回の取得値から再計算していません。数値の採用判断は後段の項目別スナップショットを参照してください。",
        "",
    ]
    for heading, key in sections:
        values = _as_lines(report.get(key))
        if not values:
            continue
        lines.extend([f"### {heading}", ""])
        lines.extend([f"- {item}" for item in values] if isinstance(report.get(key), list) else values)
        lines.append("")
    markets = report.get("markets")
    if isinstance(markets, list) and markets:
        lines.extend(["### 主要6市場の見通し", ""])
        for market in markets:
            if not isinstance(market, dict):
                continue
            name = str(market.get("name") or "市場")
            fields = [
                ("価格", "price"), ("方向", "direction"), ("材料", "material"),
                ("需給", "positioning"), ("水準", "levels"),
                ("メイン", "mainScenario"), ("代替", "alternativeScenario"),
                ("崩れ条件", "breakCondition"), ("リスク", "risk"),
            ]
            details = [f"{label}: {market[key]}" for label, key in fields if market.get(key) not in (None, "")]
            lines.append(f"- **{name}** — " + "；".join(details))
        lines.append("")
    return lines if len(lines) > 2 else []


def render_report(payload: dict[str, Any]) -> str:
    markets = payload.get("markets") or {}
    retrieved = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("reportDate") or payload.get("previousCloseDate") or "")
    report_slot = str(payload.get("reportSlot") or "")
    report_symbols = [item[1] for item in ITEMS]
    verified, reference, unavailable = report_counts(payload)
    historical = bool(payload.get("historicalSnapshot")) or payload.get("overallStatus") == "historical_only"
    lines = [
        f"# {'履歴再構成・個人用マーケットレポート' if historical else '個人用マーケットレポート草案'} {report_date} {report_slot}".strip(),
        "",
        f"生成日時: {retrieved or '不明'}",
        f"対象データ期間: {payload.get('dataDateRange') or report_date or '不明'}",
        f"状態: {payload.get('overallStatus') or 'unknown'} / 検証済み {verified}項目 / 参考値 {reference}項目 / 未取得 {unavailable}項目 / 対象28項目",
        "",
    ]
    if historical:
        lines.extend([
            "> 履歴データからの再構成です。生成日時点の最新相場ではなく、現在の投資判断用スナップショットとして使用しないでください。",
            "",
        ])
    lines.extend([
        "各市場の営業日と日次締めは項目ごとに記録しています。参考値は清算値などの確定値と混同しません。",
        "",
    ])
    lines.extend(render_detailed_analysis(payload.get("detailedReport") or {}))
    yield_rows = []
    for key, label in (("us10y", "米10年債"), ("jp10y", "日本10年国債")):
        market = markets.get(key)
        if isinstance(market, dict) and market.get("value") not in (None, ""):
            yield_rows.append(f"{label}: {report_value(market)} {market.get('unit') or '%'}（基準日 {market.get('asOf') or '不明'}、{market.get('sourceName') or market.get('sourceId') or '取得元不明'}）")
        else:
            yield_rows.append(f"{label}: 未取得")
    lines.extend(["### 金利・金融環境（今回のスナップショット）", "", *[f"- {row}" for row in yield_rows], ""])
    lines.extend([
        "## 市場データスナップショット（項目別の取得記録）",
        "",
        "| 市場データ | 値 | 単位 | 基準日 | 取得日時 | 取得元 | 状態 | 定義・検証根拠 |",
        "|---|---:|---|---|---|---|---|---|",
    ])
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
        retrieved_at = str(market.get("fetchedAt") or market.get("retrievedAt") or "—").replace("|", "\\|")
        evidence = market.get("verificationBasis") or market.get("note") or market.get("valueDefinition") or ""
        anchor = market.get("barAnchorUTC")
        if anchor:
            evidence = f"{evidence}; anchor={anchor}" if evidence else f"anchor={anchor}"
        evidence = str(evidence or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {label} | {value} | {unit} | {as_of} | {retrieved_at} | {source} | {status} | {evidence} |")
    lines.extend(["", "未取得欄は推測で補っていません。", ""])
    return "\n".join(lines)


def report_sheet_row(payload: dict[str, Any], body: str) -> list[Any]:
    generated = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("dataDateRange") or payload.get("reportDate") or payload.get("previousCloseDate") or "")
    markets = payload.get("markets") or {}
    market_identity = payload.get("snapshotId")
    if not market_identity:
        identity_rows = [
            [symbol, market.get("value"), market.get("asOf"), market.get("sourceId"),
             market.get("sourceName"), market.get("unit"), market.get("verificationStatus"),
             market.get("fetchedAt")]
            for symbol, market in sorted(markets.items()) if isinstance(market, dict)
        ]
        canonical = json.dumps(identity_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        market_identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    identity = hashlib.sha256(f"{market_identity}|{report_date}|{body_hash}".encode("utf-8")).hexdigest()[:24]
    key = f"personal-report-{identity}"
    verified, reference, unavailable = report_counts(payload)
    return [
        key, generated, report_date, str(payload.get("overallStatus") or "unknown"),
        verified, reference, unavailable, body, body_hash,
    ]


def write_test_sheet(row: list[Any]) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not account_json:
        raise PersonalReportError("private test-sheet ID or service-account credential is missing")
    validate_sheet_target_ids(test_id, production_id)
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
    parser.add_argument("--detailed-report", type=Path, help="optional structured report JSON whose narrative sections are retained")
    parser.add_argument("--write-test-sheet", action="store_true")
    args = parser.parse_args()
    try:
        payload = load_payload(args.input)
        if args.detailed_report:
            try:
                detailed_source = json.loads(args.detailed_report.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PersonalReportError("detailed report input could not be read") from exc
            detailed = detailed_source.get("latestReport") or detailed_source.get("report") or detailed_source
            if not isinstance(detailed, dict):
                raise PersonalReportError("detailed report input has an invalid structure")
            payload["detailedReport"] = detailed
        body = render_report(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        result: dict[str, Any] = {
            "reportDate": payload.get("reportDate") or payload.get("previousCloseDate"),
            "marketCount": len(payload.get("markets") or {}),
            "verifiedCount": report_counts(payload)[0],
            "referenceCount": report_counts(payload)[1],
            "unavailableCount": report_counts(payload)[2],
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
