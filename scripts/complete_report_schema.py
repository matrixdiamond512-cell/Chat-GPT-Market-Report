#!/usr/bin/env python3
"""Complete required market-report fields without inventing market facts.

Empty market-level fields are filled from matching report-level text where possible.
When the source report does not contain the information, an explicit
"取得不能（理由）" value is written. No price, level, direction, or market fact is guessed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MARKET_PATTERNS: dict[str, re.Pattern[str]] = {
    "金": re.compile(r"(?:金|ゴールド|Gold|XAUUSD)", re.I),
    "原油": re.compile(r"(?:WTI|原油|ブレント|Brent)", re.I),
    "日経225先物": re.compile(r"(?:日経225先物|日経先物|大阪取引所)", re.I),
    "USD/JPY": re.compile(r"(?:USD\s*/?\s*JPY|ドル円)", re.I),
    "EUR/USD": re.compile(r"(?:EUR\s*/?\s*USD|ユーロドル)", re.I),
    "BTCUSD": re.compile(r"(?:BTC\s*/?\s*USD|BTCUSD|ビットコイン)", re.I),
}

EMPTY = {"", "本文参照", "旧形式のため原文参照", "記載なし", None}


def text(value: Any) -> str:
    return str(value or "").strip()


def is_empty(value: Any) -> bool:
    return value in EMPTY or text(value) in EMPTY


def as_rows(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text(v) for v in value if text(v)]
    if text(value):
        return [text(value)]
    return []


def first_matching(rows: list[str], pattern: re.Pattern[str]) -> str:
    return next((row for row in rows if pattern.search(row)), "")


def complete_market(report: dict[str, Any], market: dict[str, Any]) -> bool:
    changed = False
    name = text(market.get("name"))
    pattern = MARKET_PATTERNS.get(name, re.compile(re.escape(name), re.I))

    report_positioning = as_rows(report.get("positioning"))
    report_risks = as_rows(report.get("riskManagement"))
    report_break = text(report.get("breakConditions"))
    report_main = text(report.get("mainScenario"))
    report_alt = text(report.get("alternativeScenario"))

    fallbacks = {
        "price": "取得不能（構造化元本文に価格記載なし）",
        "positioning": first_matching(report_positioning, pattern)
            or "取得不能（構造化元本文に当該市場の需給・ポジション記載なし）",
        "levels": "取得不能（構造化元本文に注目水準記載なし）",
        "mainScenario": report_main
            or "取得不能（構造化元本文にメインシナリオ記載なし）",
        "alternativeScenario": report_alt
            or "取得不能（構造化元本文に代替シナリオ記載なし）",
        "breakCondition": report_break
            or "取得不能（構造化元本文にシナリオが崩れる条件の記載なし）",
        "risk": first_matching(report_risks, pattern)
            or (report_risks[0] if report_risks else "取得不能（構造化元本文にリスク記載なし）"),
    }

    for field, fallback in fallbacks.items():
        if is_empty(market.get(field)):
            market[field] = fallback
            changed = True

    return changed


def complete_report(report: dict[str, Any]) -> bool:
    changed = False
    markets = report.get("markets")
    if not isinstance(markets, list):
        return False

    for market in markets:
        if isinstance(market, dict):
            changed = complete_market(report, market) or changed

    if changed:
        report["schemaCompletion"] = {
            "version": 1,
            "policy": "source-derived-or-explicit-unavailable",
        }
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="reports.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("reports.json must contain an array")

    changed = any(complete_report(report) for report in data if isinstance(report, dict))
    if args.check:
        return 1 if changed else 0

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Completed empty schema fields without inventing market data.")
    else:
        print("No schema completion needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
