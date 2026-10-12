"""Transcript-first source selection for time-slot report bodies.

This module consumes already retrieved candidates. It never queries Drive or
GitHub and deliberately has no market-snapshot fallback.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from typing import Any


SOURCE_ORDER = ("CHAT_TRANSCRIPT", "GOOGLE_DOCS", "CANONICAL_JSON")
WEEKDAYS_JA = ("月", "火", "水", "木", "金", "土", "日")
REQUIRED_0800_HEADINGS = (
    "今日の相場テーマ", "前営業日終値・主要市場データ", "昨夜のNY市場", "材料と値動きの整合性",
    "今日の主導市場", "金利・センチメント", "日経225バリュエーション", "需給・ポジション",
    "クロスアセット資金フロー", "重要ニュース・イベント", "主要6市場の短期見通し", "メインシナリオ",
    "代替シナリオ", "シナリオが崩れる条件", "12:00への引き継ぎ", "結論",
)


class ReportBodySourceError(ValueError):
    """No complete source candidate matched the requested report identity."""


def _expected_title(report_id: str) -> str:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_(08|12|16|21)-00", report_id)
    if not match:
        raise ReportBodySourceError("REPORT_ID_INVALID")
    iso_date, hour = match.groups()
    d = date.fromisoformat(iso_date)
    return f"マーケットレポート｜{d:%Y/%m/%d}（{WEEKDAYS_JA[d.weekday()]}）{hour}:00"


def _canonical_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _candidate_body(origin: str, value: Any) -> str:
    value = _canonical_payload(value) if origin == "CANONICAL_JSON" else value
    if isinstance(value, dict):
        if value.get("report_id") not in (None, "2026-10-09_08-00"):
            raise ReportBodySourceError("SOURCE_REPORT_ID_MISMATCH")
        value = value.get("full_text", value.get("body"))
    if not isinstance(value, str) or not value.strip():
        raise ReportBodySourceError("SOURCE_BODY_EMPTY")
    return value


def _validate_complete_body(body: str, report_id: str) -> None:
    expected_title = _expected_title(report_id)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or lines[0].lstrip("# ") != expected_title:
        raise ReportBodySourceError("SOURCE_TITLE_MISMATCH")
    if report_id != "2026-10-09_08-00":
        raise ReportBodySourceError("UNSUPPORTED_SLOT_COMPLETENESS_CONTRACT")
    heading_lines = [re.sub(r"^#+\s*", "", line) for line in lines]
    positions = []
    for number, heading in enumerate(REQUIRED_0800_HEADINGS, start=1):
        pattern = re.compile(rf"^{number}[.．、]\s*{re.escape(heading)}$")
        matches = [index for index, line in enumerate(heading_lines) if pattern.match(line)]
        if len(matches) != 1:
            raise ReportBodySourceError(f"SOURCE_REQUIRED_HEADING_INVALID:{number}:{heading}")
        positions.append(matches[0])
    if positions != sorted(positions):
        raise ReportBodySourceError("SOURCE_HEADING_ORDER_INVALID")
    if not any(re.fullmatch(r"(?:#+\s*)?クロスチェック結果", line) for line in lines):
        raise ReportBodySourceError("SOURCE_CROSSCHECK_SECTION_MISSING")


def resolve_report_body(
    report_id: str,
    *,
    chat_transcript: str | None = None,
    google_docs: str | None = None,
    canonical_json: dict | str | None = None,
) -> dict[str, Any]:
    """Select the first *complete identity-matched* body in the fixed order.

    Each input is the full body already read from its named source. The result
    preserves the body verbatim, including its boundary whitespace.
    Failed/incomplete candidates fall through to the next permitted source.
    """
    candidates = {
        "CHAT_TRANSCRIPT": chat_transcript,
        "GOOGLE_DOCS": google_docs,
        "CANONICAL_JSON": canonical_json,
    }
    attempts = []
    for origin in SOURCE_ORDER:
        candidate = candidates[origin]
        if candidate is None:
            attempts.append({"source": origin, "status": "NOT_AVAILABLE"})
            continue
        try:
            body = _candidate_body(origin, candidate)
            _validate_complete_body(body, report_id)
        except (ReportBodySourceError, TypeError) as exc:
            reason = str(exc) or "SOURCE_CANDIDATE_INVALID"
            attempts.append({"source": origin, "status": "REJECTED", "reason": reason})
            continue
        attempts.append({"source": origin, "status": "SELECTED"})
        return {
            "source": origin,
            "report_id": report_id,
            "title": _expected_title(report_id),
            "body": body,
            "body_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "attempts": attempts,
        }
    raise ReportBodySourceError("REPORT_BODY_NOT_FOUND:" + json.dumps(attempts, ensure_ascii=False))
