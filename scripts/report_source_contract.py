"""Validate saved source material without generating missing report content."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
NAME = re.compile(r"^マーケットレポート_(\d{4}-\d{2}-\d{2})_(08|12|16|21)-00(?:\.(png|jpg|jpeg|webp))?$")
PLAIN_HEADING = re.compile(
    r"^(?:総括|結論|最終判断|今日の相場テーマ|主導市場|今日の主導市場|金利|"
    r"材料と値動きの整合性|重要ニュース(?:・金利)?|主要市場(?:データ|の確認値|まとめ)|"
    r"クロスアセット資金フロー|需給・ポジション|6市場の(?:個別)?見通し|"
    r"個別市場見通し|今後の(?:重要)?イベント|メインシナリオ|代替シナリオ|"
    r"(?:シナリオが)?崩れる条件|クロスチェック結果|"
    r"(?:前回|\d{2}:00)(?:から|→)(?:\d{2}:00)?の(?:主な)?変化|"
    r"(?:\d{2}:00|次の時間帯|翌東京時間|東京時間|欧州時間|NY時間)への引き継ぎ)$"
)


def source_key(name: str) -> str:
    match = NAME.fullmatch(name)
    if not match:
        raise ValueError(f"unsupported source name: {name}")
    datetime.strptime(match[1], "%Y-%m-%d")
    return f"{match[1]}_{match[2]}-00"


def title_for(date: str, time: str) -> str:
    day = datetime.strptime(date, "%Y-%m-%d")
    return f"マーケットレポート｜{day:%Y/%m/%d}（{'月火水木金土日'[day.weekday()]}）{time}"


def body_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def heading(line: str) -> str:
    line = line.strip().strip("\ufeff")
    explicit = re.match(r"^(?:【(.+?)】|#{1,6}\s+(.+)|\d{1,2}[．.、)）]\s*(.+))$", line)
    if explicit:
        return next(value.strip() for value in explicit.groups() if value)
    return line if PLAIN_HEADING.fullmatch(line) else ""


def validate_saved_body(report: dict) -> None:
    """Accept complete plain-heading Docs as well as Markdown; reject saved stubs."""
    text = str(report.get("fullText") or "")
    if len(text.strip()) < 1200:
        raise ValueError(f"incomplete saved report: {len(text.strip())} characters")
    expected = title_for(report["date"], report["time"])
    # Cosmetic spacing is tolerated in the source, never a different date/slot.
    first = next((line.strip().lstrip("\ufeff") for line in text.splitlines() if line.strip()), "")
    if re.sub(r"\s", "", first) != expected:
        raise ValueError(f"source body title does not match slot: {first!r}")
    headings = [heading(line) for line in text.splitlines() if heading(line)]
    if len(headings) < 9 or not any(re.search(r"結論|最終判断|まとめ", h) for h in headings):
        raise ValueError("incomplete saved report: missing sections/conclusion")
    patterns = [r"金|ゴールド", r"WTI|原油", r"日経", r"USD/JPY|ドル円", r"EUR/USD|ユーロドル", r"BTC|ビットコイン"]
    if not all(re.search(pattern, text) for pattern in patterns):
        raise ValueError("incomplete saved report: six-market source text missing")
    expected_hash = report.get("bodyHash")
    if expected_hash and expected_hash != body_hash(text):
        raise ValueError("source body hash mismatch")


def validate_pair(report: dict, image: dict) -> None:
    key = f"{report['date']}_{report['time'].replace(':', '-')}"
    if source_key(image["name"]) != key or not image.get("mimeType", "").startswith("image/"):
        raise ValueError(f"image does not match report slot: {key}")
