"""Validate saved source material without generating missing report content."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
NAME = re.compile(r"^マーケットレポート_(\d{4}-\d{2}-\d{2})_(08|12|16|21)-00(?:\.(png|jpg|jpeg|webp))?$")
HEADING_REGISTRY = json.loads((Path(__file__).resolve().parents[1] / "config/report_heading_registry.json").read_text(encoding="utf-8"))
HEADING_ALIASES = {alias: canonical for canonical, aliases in HEADING_REGISTRY["sections"].items() for alias in aliases}
PLAIN_HEADING = re.compile(
    r"^(?:総括|結論|最終判断|今日の相場テーマ|主導市場|今日の主導市場|金利|"
    r"材料と値動きの整合性|重要ニュース(?:・金利)?|主要市場(?:データ|の確認値|まとめ)|"
    r"クロスアセット資金フロー|金利・為替・クロスアセット資金フロー|需給・ポジション|6市場の(?:個別)?見通し|"
    r"個別市場見通し|今後の(?:重要)?イベント|メインシナリオ|代替シナリオ|"
    r"(?:シナリオが)?崩れる条件|クロスチェック結果|"
    r"(?:前回|\d{2}:00)(?:から|→)(?:\d{2}:00)?の(?:主な)?変化|"
    r"(?:\d{2}:00|次の時間帯|翌東京時間|東京時間|欧州時間|NY時間)への引き継ぎ(?:・リスク管理)?)$"
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


def section_bodies(text: str) -> dict[str, str]:
    """Return content under registry headings; incidental prose is never a heading."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in str(text or "").replace("\r", "").split("\n"):
        label = heading(line)
        canonical = HEADING_ALIASES.get(label)
        if label:
            current = canonical
            if canonical:
                sections.setdefault(canonical, [])
        elif current:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def validate_key_section_bodies(text: str, slot: str = "") -> None:
    """Keep causal-flow and outlook sections substantive after heading recognition."""
    sections = section_bodies(text)
    causal = sections.get("クロスアセット資金フロー", "")
    if len(causal) < 20 or len(re.findall(r"[。！？]", causal)) < 1:
        raise ValueError("incomplete saved report section: クロスアセット資金フロー body is missing or insubstantial")

    if slot == "21:00":
        handover = sections.get("引き継ぎ", "")
        if len(handover) < 20 or len(re.findall(r"[。！？]", handover)) < 1:
            raise ValueError("incomplete saved report section: 引き継ぎ body is missing or insubstantial")

    outlook = sections.get("個別市場見通し", "")
    market_patterns = (
        r"^[ \t]*(?:金|ゴールド)(?:先物)?[ \t]*[：:]",
        r"^[ \t]*(?:WTI原油|原油)[ \t]*[：:]",
        r"^[ \t]*日経225先物[^\n：:]*[ \t]*[：:]",
        r"^[ \t]*(?:USD/JPY|ドル円)[ \t]*[：:]",
        r"^[ \t]*(?:EUR/USD|ユーロドル)[ \t]*[：:]",
        r"^[ \t]*(?:BTCUSD|BTC/USD|ビットコイン)[ \t]*[：:]",
    )
    positions = []
    missing_markets = 0
    for pattern in market_patterns:
        match = re.search(pattern, outlook, re.I | re.M)
        if match is None:
            missing_markets += 1
        else:
            positions.append(match.start())
    positions.sort()
    for index, start in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(outlook)
        if len(outlook[start:end].strip()) < 20:
            missing_markets += 1
    if len(outlook) < 180 or missing_markets:
        raise ValueError(f"incomplete saved report section: 個別市場見通し requires substantive outlooks for six markets (chars={len(outlook)}, missing={missing_markets})")


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
