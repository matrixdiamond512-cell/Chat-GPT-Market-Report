#!/usr/bin/env python3
"""Validate reports.json before publication.

Historical reports may use older schemas, so their content gaps are warnings.
The newest report and the latest due schedule slot are validated strictly.
From 2026-08-13 onward, 21:00 reports must also satisfy the portal/SOP
readability contract: mandatory sections, a parseable major-market block,
and no internal QA wording in public text.

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
# Publication must always know which market it is and the directional judgement.
# The deeper per-market fields remain strongly recommended, but older/current imports
# can legitimately carry them in the full-text sections instead of the market object.
REQUIRED_MARKET_FIELDS = {"name", "direction"}
RECOMMENDED_MARKET_FIELDS = {
    "price", "material", "positioning", "levels", "mainScenario",
    "alternativeScenario", "breakCondition", "risk"
}
TITLE_RE = re.compile(r"^マーケットレポート｜(\d{4})/(\d{2})/(\d{2})（.）(\d{2}):(\d{2})$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 07:00 is kept as a legacy-compatible slot while the current morning portal also
# contains 08:00 reports. Strict due-time checks use publication_slots() below.
TIME_RE = re.compile(r"^(07|08|09|12|16|21):00$")

MANUAL_21_ENFORCE_FROM = "2026-08-13"
REQUIRED_21_FIELDS = {
    "changes", "consistency", "news", "crossAssetFlow", "positioning", "events", "handover"
}
REQUIRED_21_SECTIONS: dict[str, re.Pattern[str]] = {
    "主要市場データ": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?主要市場データ(?:（.*）)?\s*$"),
    "今日の相場テーマ": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?今日の相場テーマ\s*$"),
    "16:00からの変化": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?(?:16:00|16時|前回)からの(?:主な)?変化\s*$"),
    "材料と値動きの整合性": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?材料と値動きの整合性\s*$"),
    "主導市場": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?(?:今日の)?主導市場\s*$"),
    "重要ニュース": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?重要ニュース\s*$"),
    "クロスアセット資金フロー": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?クロスアセット(?:資金フロー)?\s*$"),
    "需給・ポジション": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?需給・ポジション\s*$"),
    "重要イベント": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?(?:今後の)?重要イベント\s*$"),
    "6市場の見通し": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?6市場の(?:個別)?見通し\s*$"),
    "メインシナリオ": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?メインシナリオ\s*$"),
    "代替シナリオ": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?代替シナリオ\s*$"),
    "シナリオが崩れる条件": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?(?:シナリオが)?崩れる条件\s*$"),
    "引き継ぎ": re.compile(r"(?m)^\s*(?:\d+[．.]\s*)?(?:NY時間|次の時間帯|翌東京時間)への引き継ぎ\s*$"),
}
REQUIRED_21_MARKET_PATTERNS: dict[str, re.Pattern[str]] = {
    "金": re.compile(r"(?mi)^\s*\|?\s*(?:金|ゴールド|COMEX金先物)(?:[・（|：:].*)?$"),
    "原油": re.compile(r"(?mi)^\s*\|?\s*(?:WTI原油|原油)(?:[（|：:].*)?$"),
    "日経225先物": re.compile(r"(?mi)^\s*\|?\s*日経225先物(?:（大阪取引所）)?\s*[|：:].*$"),
    "USD/JPY": re.compile(r"(?mi)^\s*\|?\s*(?:USD/JPY|USDJPY|ドル円)\s*[|：:].*$"),
    "EUR/USD": re.compile(r"(?mi)^\s*\|?\s*(?:EUR/USD|EURUSD|ユーロドル)\s*[|：:].*$"),
    "BTCUSD": re.compile(r"(?mi)^\s*\|?\s*(?:BTCUSD|BTC/USD|ビットコイン)\s*[|：:].*$"),
}
PUBLIC_INTERNAL_PATTERNS = {
    "verified": re.compile(r"\bverified\b", re.I),
    "未確認": re.compile(r"未確認"),
}
LEAKED_HEADING_RE = re.compile(
    r"^(?:金利|6市場の(?:個別)?見通し|結論|シナリオが崩れる条件|翌東京時間への引き継ぎ)$"
)
EMBEDDED_HEADING_RE = re.compile(
    r"(?:^|[。\s])(?:シナリオが崩れる条件|翌東京時間への引き継ぎ|NY時間への引き継ぎ|結論)(?:\s|$)"
)


def expected_slots(date_text: str) -> set[str]:
    """Slots accepted in stored reports, including legacy morning variants."""
    day = datetime.strptime(date_text, "%Y-%m-%d").weekday()  # Mon=0
    if day == 6:
        return set()
    if day == 5:
        return {"07:00", "09:00"}
    return {"07:00", "08:00", "12:00", "16:00", "21:00"}


def publication_slots(date_text: str) -> set[str]:
    """Slots used for due-time checks; 08:00 is the current weekday morning slot."""
    day = datetime.strptime(date_text, "%Y-%m-%d").weekday()
    if day == 6:
        return set()
    if day == 5:
        return {"07:00", "09:00"}
    return {"08:00", "12:00", "16:00", "21:00"}


def report_key(report: dict) -> tuple[str, str]:
    return str(report.get("date", "")), str(report.get("time", ""))


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return not str(value).strip()


def public_full_text(report: dict) -> str:
    for key in ("fullText", "rawText", "body"):
        value = report.get(key)
        if isinstance(value, str) and value.strip():
            return value.replace("\r", "").strip()
    return ""


def validate_21_manual_contract(report: dict, prefix: str, target: list[str]) -> None:
    """Strict public/readability checks for 21:00 reports after the enforcement date."""
    missing_fields = sorted(field for field in REQUIRED_21_FIELDS if is_blank(report.get(field)))
    if missing_fields:
        target.append(f"{prefix}: 21:00 SOP必須項目不足/空欄: {', '.join(missing_fields)}")

    source = public_full_text(report)
    if not source:
        target.append(f"{prefix}: 21:00 SOPでは公開本文 fullText/rawText/body が必須です")
        return

    for label, pattern in PUBLIC_INTERNAL_PATTERNS.items():
        if pattern.search(source):
            target.append(f"{prefix}: 公開本文に内部確認用語 {label!r} が残っています")

    missing_sections = [name for name, pattern in REQUIRED_21_SECTIONS.items() if not pattern.search(source)]
    if missing_sections:
        target.append(f"{prefix}: 21:00 SOP必須セクション不足: {', '.join(missing_sections)}")

    missing_rows = [name for name, pattern in REQUIRED_21_MARKET_PATTERNS.items() if not pattern.search(source)]
    if missing_rows:
        target.append(f"{prefix}: 主要市場データで表変換可能な市場行が不足: {', '.join(missing_rows)}")

    for field in ("changes", "consistency", "news", "crossAssetFlow", "positioning", "events", "handover", "riskManagement"):
        value = report.get(field)
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = str(item or "").strip()
            if LEAKED_HEADING_RE.fullmatch(text):
                target.append(f"{prefix}.{field}: 見出しが本文項目へ混入しています: {text}")

    for field in ("mainScenario", "alternativeScenario", "breakConditions"):
        text = str(report.get(field, ""))
        if EMBEDDED_HEADING_RE.search(text):
            target.append(f"{prefix}.{field}: 複数セクションが1フィールドへ連結されています")


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

        missing_recommended = sorted(RECOMMENDED_MARKET_FIELDS - market.keys())
        if missing_recommended:
            warnings.append(f"{mp}: 推奨項目不足: {', '.join(missing_recommended)}")
        empty_recommended = [
            field for field in RECOMMENDED_MARKET_FIELDS
            if field in market and not str(market[field]).strip()
        ]
        if empty_recommended:
            warnings.append(f"{mp}: 推奨項目が空欄: {', '.join(sorted(empty_recommended))}")

    date_text = str(report.get("date", ""))
    time_text = str(report.get("time", ""))
    if time_text == "21:00" and date_text >= MANUAL_21_ENFORCE_FROM:
        validate_21_manual_contract(report, prefix, target)
    elif time_text == "21:00":
        source = public_full_text(report)
        if source and PUBLIC_INTERNAL_PATTERNS["verified"].search(source):
            warnings.append(f"{prefix}: 過去21:00本文に内部確認用語 'verified' があります（表示層で除去）")


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

        if DATE_RE.fullmatch(date_text) and TIME_RE.fullmatch(time_text) and time_text not in expected_slots(date_text):
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
        for slot in sorted(publication_slots(today)):
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
