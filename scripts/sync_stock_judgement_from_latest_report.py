#!/usr/bin/env python3
"""Refresh the stock-page judgement cards from the canonical latest report.

The stock page is updated by several independent collectors, while its four
judgement cards historically came from a manually written block in
``data/stocks.json``. That split made the cards remain on an old report even
when ``data/latest-report.json`` had advanced. This script keeps the cards
source-grounded in the same report publication used by the dashboard.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
LATEST_PATH = ROOT / "data" / "latest-report.json"
JST = timezone(timedelta(hours=9))


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def compact(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def first_items(*values: Any, limit: int = 3) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in as_list(value):
            item = compact(item)
            if not item or item in seen:
                continue
            if any(token in item for token in ("reportSlot=", "overallStatus=", "missingRequired=", "fallbackCount=")):
                continue
            seen.add(item)
            result.append(item)
            if len(result) >= limit:
                return result
    return result


def report_from(payload: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict):
        raise ValueError("latest-report.json does not contain a report object")
    if not report.get("date") or not report.get("time"):
        raise ValueError("latest report date/time is missing")
    return report


def build_judgement(report: dict[str, Any]) -> dict[str, Any]:
    theme = compact(report.get("theme"), 140)
    main_scenario = compact(report.get("mainScenario"), 180)
    conclusion_main = main_scenario or theme or "最新レポートの結論を確認してください。"
    supporting = first_items(report.get("changes"), report.get("consistency"), limit=1)
    conclusion_sub = compact(supporting[0] if supporting else report.get("leadingMarket"), 180)

    reason = first_items(report.get("changes"), report.get("consistency"), report.get("news"), limit=3)
    risk = first_items(report.get("breakConditions"), report.get("riskManagement"), limit=3)
    watch = first_items(report.get("events"), report.get("handover"), limit=3)

    return {
        "conclusion": {
            "title": "今日の結論",
            "main": conclusion_main,
            "sub": conclusion_sub or "構造化された補足コメントはありません。",
        },
        "reason": {
            "title": "なぜ買われたか／売られたか",
            "items": reason or ["理由データは最新レポートに未登録です。"],
        },
        "risk": {
            "title": "リスク",
            "items": risk or ["リスク条件は最新レポートに未登録です。"],
        },
        "watch": {
            "title": "次の注目点",
            "items": watch or ["注目点は最新レポートに未登録です。"],
        },
    }


def build_analysis_cards(report: dict[str, Any]) -> list[dict[str, Any]]:
    cards = [
        ("需給・ポジション", report.get("positioning")),
        ("フロー判断", report.get("crossAssetFlow")),
        ("メインシナリオ", report.get("mainScenario")),
        ("崩れる条件", report.get("breakConditions")),
        ("監視ポイント", report.get("handover") or report.get("events")),
    ]
    output: list[dict[str, Any]] = []
    for title, value in cards:
        items = first_items(value, limit=3)
        if items:
            output.append({"title": title, "items": items})
    return output


def main() -> int:
    latest_payload = load(LATEST_PATH)
    report = report_from(latest_payload)
    stocks = load(STOCKS_PATH)
    report_key = f"{report['date']} {report['time']}"
    previous_key = stocks.get("judgementReportKey")

    stocks["judgement"] = build_judgement(report)
    stocks["analysisCards"] = build_analysis_cards(report)
    stocks["judgementReportKey"] = report_key
    stocks["judgementUpdatedAt"] = latest_payload.get("generatedAt") or datetime.now(JST).replace(microsecond=0).isoformat()
    stocks["judgementSource"] = "data/latest-report.json（canonical report publication）"

    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "reportKey": report_key, "previousKey": previous_key}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

