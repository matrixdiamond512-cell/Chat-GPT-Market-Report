#!/usr/bin/env python3
"""Validate reports.json before publication.

Historical reports may use older schemas, so their content gaps are warnings.
The newest report and the latest due schedule slot are validated strictly.
This script never invents or repairs market data.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
REQUIRED_MARKETS = {"金", "原油", "日経225先物", "USD/JPY", "EUR/USD", "BTCUSD"}
REQUIRED_REPORT_FIELDS = {
    "date", "time", "title", "theme", "leadingMarket", "markets",
    "mainScenario", "alternativeScenario", "breakConditions", "riskManagement"
}
REQUIRED_MARKET_FIELDS = {
    "name", "direction", "price", "material", "positioning", "levels",
    "mainScenario", "alternativeScenario", "breakCondition", "risk"
}
TITLE_RE = re.compile(r"^マーケットレポート｜(\d{4})/(\d{2})/(\d{2})（.）(\d{2}):(\d{2})$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(07|09|12|16|21):00$")


def expected_slots(date_text: str) -> set[str]:
    day = datetime.strptime(date_text, "%Y-%m-%d").weekday()  # Mon=0
    if day == 6:
        return set()
    if day == 5:
        return {"07:00", "09:00"}
    return {"07:00", "12:00", "16:00", "21:00"}


def report_key(report: dict) -> tuple[str, str]:
    return str(report.get("date", "")), str(report.get("time", ""))


def validate_report_content(report: dict, prefix: str, strict: bool, errors: list[str], warnings: list[str]) -> None:
    target = errors if strict else warnings
    missing = sorted(REQUIRED_REPORT_FIELDS - report.keys())
    if missing:
        target.append(f"{prefix}: 必須項目不足: {', '.join(missing)}")

    markets = report.get("markets")
    if not isinstance(markets, list):
        target.append(f"{prefix}: markets は配列である必要があります")
        return

    names = {str(m.get("name", "")) for m in markets if isinstance(m, dict)}
    missing_markets = sorted(REQUIRED_MARKETS - names)
    if missing_markets:
        target.append(f"{prefix}: 必須市場不足: {', '.join(missing_markets)}")

    for j, market in enumerate(markets):
        mp = f"{prefix}.markets[{j}]"
        if not isinstance(market, dict):
            target.append(f"{mp}: オブジェクトではありません")
            continue
        missing_fields = sorted(REQUIRED_MARKET_FIELDS - market.keys())
        if missing_fields:
            target.append(f"{mp}: 必須項目不足: {', '.join(missing_fields)}")
        empty_fields = [
            field for field in REQUIRED_MARKET_FIELDS
            if field in market and not str(market[field]).strip()
        ]
        if empty_fields:
            target.append(f"{mp}: 空欄項目: {', '.join(sorted(empty_fields))}")


def validate(path: Path, require_current_slot: bool = False, grace_minutes: int = 45) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        reports = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSONを読み込めません: {exc}"], warnings

    if not isinstance(reports, list):
        return ["reports.json のルートは配列である必要があります"], warnings

    seen: set[tuple[str, str]] = set()
    available: dict[tuple[str, str], tuple[int, dict]] = {}

    for i, report in enumerate(reports):
        prefix = f"reports[{i}]"
        if not isinstance(report, dict):
            errors.append(f"{prefix}: オブジェクトではありません")
            continue

        date_text, time_text = report_key(report)
        title = str(report.get("title", ""))

        if not DATE_RE.fullmatch(date_text):
            errors.append(f"{prefix}: date形式不正: {date_text!r}")
        if not TIME_RE.fullmatch(time_text):
            errors.append(f"{prefix}: time形式不正: {time_text!r}")

        key = (date_text, time_text)
        if key in seen:
            errors.append(f"{prefix}: 重複レポート: {date_text} {time_text}")
        seen.add(key)
        available[key] = (i, report)

        match = TITLE_RE.fullmatch(title)
        if not match:
            errors.append(f"{prefix}: タイトル形式不正: {title!r}")
        elif (
            f"{match.group(1)}-{match.group(2)}-{match.group(3)}" != date_text
            or f"{match.group(4)}:{match.group(5)}" != time_text
        ):
            errors.append(f"{prefix}: title と date/time が不一致")

        if DATE_RE.fullmatch(date_text) and time_text not in expected_slots(date_text):
            errors.append(f"{prefix}: 運用対象外スロット: {date_text} {time_text}")

    valid_keys = sorted(k for k in available if DATE_RE.fullmatch(k[0]) and TIME_RE.fullmatch(k[1]))
    latest_key = valid_keys[-1] if valid_keys else None

    for key, (index, report) in available.items():
        validate_report_content(
            report,
            f"reports[{index}]",
            strict=(key == latest_key),
            errors=errors,
            warnings=warnings,
        )

    if require_current_slot:
        now = datetime.now(JST)
        today = now.strftime("%Y-%m-%d")
        due: list[str] = []
        for slot in sorted(expected_slots(today)):
            slot_dt = datetime.strptime(f"{today} {slot}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
            if now >= slot_dt + timedelta(minutes=grace_minutes):
                due.append(slot)

        if due:
            latest_due = due[-1]
            due_key = (today, latest_due)
            if due_key not in available:
                errors.append(
                    f"発行期限超過: {today} {latest_due} のレポートがありません"
                    f"（猶予 {grace_minutes} 分）"
                )
            else:
                index, report = available[due_key]
                validate_report_content(
                    report,
                    f"reports[{index}]",
                    strict=True,
                    errors=errors,
                    warnings=warnings,
                )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="reports.json")
    parser.add_argument("--require-current-slot", action="store_true")
    parser.add_argument("--grace-minutes", type=int, default=45)
    args = parser.parse_args()

    errors, warnings = validate(
        Path(args.file),
        require_current_slot=args.require_current_slot,
        grace_minutes=args.grace_minutes,
    )

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print("MARKET REPORT VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"MARKET REPORT VALIDATION PASSED (warnings={len(warnings)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
