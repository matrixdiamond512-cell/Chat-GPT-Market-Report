#!/usr/bin/env python3
"""Validate reports.json before publication.

This script never invents or repairs market data. It fails loudly when required
fields, schedules, instruments, titles, or duplicate report keys are wrong.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
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


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def expected_slots(date_text: str) -> set[str]:
    day = datetime.strptime(date_text, "%Y-%m-%d").weekday()  # Mon=0
    if day == 6:
        return set()
    if day == 5:
        return {"07:00", "09:00"}
    return {"07:00", "12:00", "16:00", "21:00"}


def validate(path: Path, require_current_slot: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        reports = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSONを読み込めません: {exc}"]

    if not isinstance(reports, list):
        return ["reports.json のルートは配列である必要があります"]

    seen: set[tuple[str, str]] = set()
    available: set[tuple[str, str]] = set()

    for i, report in enumerate(reports):
        prefix = f"reports[{i}]"
        if not isinstance(report, dict):
            fail(errors, f"{prefix}: オブジェクトではありません")
            continue

        missing = sorted(REQUIRED_REPORT_FIELDS - report.keys())
        if missing:
            fail(errors, f"{prefix}: 必須項目不足: {', '.join(missing)}")

        date_text = str(report.get("date", ""))
        time_text = str(report.get("time", ""))
        title = str(report.get("title", ""))

        if not DATE_RE.fullmatch(date_text):
            fail(errors, f"{prefix}: date形式不正: {date_text!r}")
        if not TIME_RE.fullmatch(time_text):
            fail(errors, f"{prefix}: time形式不正: {time_text!r}")

        key = (date_text, time_text)
        if key in seen:
            fail(errors, f"{prefix}: 重複レポート: {date_text} {time_text}")
        seen.add(key)
        available.add(key)

        match = TITLE_RE.fullmatch(title)
        if not match:
            fail(errors, f"{prefix}: タイトル形式不正: {title!r}")
        elif f"{match.group(1)}-{match.group(2)}-{match.group(3)}" != date_text or f"{match.group(4)}:{match.group(5)}" != time_text:
            fail(errors, f"{prefix}: title と date/time が不一致")

        if DATE_RE.fullmatch(date_text) and time_text not in expected_slots(date_text):
            fail(errors, f"{prefix}: 運用対象外スロット: {date_text} {time_text}")

        markets = report.get("markets")
        if not isinstance(markets, list):
            fail(errors, f"{prefix}: markets は配列である必要があります")
            continue

        names = {str(m.get("name", "")) for m in markets if isinstance(m, dict)}
        missing_markets = sorted(REQUIRED_MARKETS - names)
        if missing_markets:
            fail(errors, f"{prefix}: 必須市場不足: {', '.join(missing_markets)}")

        for j, market in enumerate(markets):
            mp = f"{prefix}.markets[{j}]"
            if not isinstance(market, dict):
                fail(errors, f"{mp}: オブジェクトではありません")
                continue
            mm = sorted(REQUIRED_MARKET_FIELDS - market.keys())
            if mm:
                fail(errors, f"{mp}: 必須項目不足: {', '.join(mm)}")
            for field in REQUIRED_MARKET_FIELDS:
                if field in market and not str(market[field]).strip():
                    fail(errors, f"{mp}: {field} が空です")

    if require_current_slot:
        now = datetime.now(JST)
        today = now.strftime("%Y-%m-%d")
        due = sorted(s for s in expected_slots(today) if s <= now.strftime("%H:%M"))
        if due:
            latest_due = due[-1]
            if (today, latest_due) not in available:
                fail(errors, f"発行期限超過: {today} {latest_due} のレポートがありません")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="reports.json")
    parser.add_argument("--require-current-slot", action="store_true")
    args = parser.parse_args()

    errors = validate(Path(args.file), args.require_current_slot)
    if errors:
        print("MARKET REPORT VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("MARKET REPORT VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
