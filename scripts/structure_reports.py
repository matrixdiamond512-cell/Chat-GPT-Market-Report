#!/usr/bin/env python3
"""Convert imported market-report full text into the structured reports.json schema.

No external API is required. Existing structured values are preserved; only empty or
placeholder fields are filled. The script is idempotent and safe to run repeatedly.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MARKETS: list[tuple[str, re.Pattern[str]]] = [
    ("金", re.compile(r"(?:金|ゴールド|Gold)", re.I)),
    ("原油", re.compile(r"(?:WTI|原油|ブレント|Brent)", re.I)),
    ("日経225先物", re.compile(r"(?:日経225先物|日経先物)", re.I)),
    ("USD/JPY", re.compile(r"(?:USD\s*/?\s*JPY|ドル円)", re.I)),
    ("EUR/USD", re.compile(r"(?:EUR\s*/?\s*USD|ユーロドル)", re.I)),
    ("BTCUSD", re.compile(r"(?:BTC\s*/?\s*USD|BTCUSD|ビットコイン)", re.I)),
]

PLACEHOLDERS = {
    "", "本文参照", "旧形式のため原文参照", "取得不能", "記載なし",
    "旧形式のため自動抽出できません。",
}

SECTION_RULES: dict[str, re.Pattern[str]] = {
    "theme": re.compile(r"相場テーマ|今日のテーマ"),
    "changes": re.compile(r"前回から|からの変化|時間からの変化"),
    "consistency": re.compile(r"整合性|材料と値動き"),
    "leadingMarket": re.compile(r"主導市場|相場を主導"),
    "positioning": re.compile(r"需給|ポジション|建玉|フローの偏り"),
    "news": re.compile(r"重要ニュース|相場に影響|ニュース|重要材料"),
    "crossAssetFlow": re.compile(r"クロスアセット|資金フロー|何が買われ|何が売られ"),
    "sectors": re.compile(r"セクター|業種|買われた|売られた"),
    "events": re.compile(r"イベント|今後の予定|経済指標"),
    "handover": re.compile(r"引き継ぎ|次の時間帯|欧州時間|NY時間"),
    "scenario": re.compile(r"全体シナリオ|メインシナリオ|代替シナリオ"),
    "riskManagement": re.compile(r"リスク管理|主なリスク|リスク要因"),
}

HEADING_RE = re.compile(
    r"^\s*(?:(?:第?\d+|[一二三四五六七八九十]+)\s*[．.、:：)）]|【([^】]+)】|[■◆◇●])\s*(.+?)\s*$"
)


def clean(value: Any) -> str:
    return str(value or "").replace("\r", "").strip()


def sparse(value: Any) -> bool:
    if value is None or value == []:
        return True
    return clean(value) in PLACEHOLDERS


def paragraphs(text: str) -> list[str]:
    result: list[str] = []
    for block in re.split(r"\n\s*\n", clean(text)):
        block = re.sub(r"\s*\n\s*", " ", block).strip()
        block = re.sub(r"^[・●■◆◇]\s*", "", block)
        if block:
            result.append(block)
    return result


def split_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    heading = "冒頭"
    body: list[str] = []
    for raw in clean(text).splitlines():
        line = raw.strip()
        match = HEADING_RE.match(line)
        # Also accept plain, short headings commonly used in the reports.
        plain_heading = (
            2 <= len(line) <= 55
            and any(rule.search(line) for rule in SECTION_RULES.values())
            and not line.endswith("。")
        )
        if match or plain_heading:
            if any(x.strip() for x in body):
                sections.append({"heading": heading, "text": clean("\n".join(body))})
            heading = clean((match.group(1) or match.group(2)) if match else line)
            body = []
        else:
            body.append(raw)
    if any(x.strip() for x in body):
        sections.append({"heading": heading, "text": clean("\n".join(body))})
    return sections


def section_text(sections: list[dict[str, str]], pattern: re.Pattern[str]) -> str:
    return "\n\n".join(s["text"] for s in sections if pattern.search(s["heading"]) and s["text"])


def first_meaningful(text: str) -> str:
    for paragraph in paragraphs(text):
        if len(paragraph) > 12 and not re.search(r"作成日時|対象：|基準時刻", paragraph):
            return paragraph
    return ""


def sentences(text: str) -> list[str]:
    rows: list[str] = []
    for paragraph in paragraphs(text):
        pieces = re.split(r"(?<=[。！？])\s+|\n", paragraph)
        rows.extend(p.strip() for p in pieces if len(p.strip()) >= 12)
    return rows


def infer_direction(text: str) -> str:
    down = len(re.findall(r"急落|下落|弱含み|売り優勢|上値重い|反落|軟調|弱気", text))
    up = len(re.findall(r"急騰|上昇|強含み|買い優勢|反発|堅調|強気", text))
    if down > up:
        return "下落・弱気"
    if up > down:
        return "上昇・強気"
    if re.search(r"横ばい|レンジ|拮抗|中立|方向感", text):
        return "中立・レンジ"
    return "本文参照"


def market_block(full_text: str, sections: list[dict[str, str]], pattern: re.Pattern[str]) -> str:
    matched = [f'{s["heading"]}\n{s["text"]}' for s in sections if pattern.search(s["heading"])]
    if matched:
        return "\n\n".join(matched)
    lines = clean(full_text).splitlines()
    chunks: list[str] = []
    for i, line in enumerate(lines):
        if pattern.search(line):
            chunks.extend(lines[max(0, i - 1): min(len(lines), i + 5)])
    return clean("\n".join(dict.fromkeys(chunks)))


def pick(rows: list[str], pattern: str) -> str:
    regex = re.compile(pattern)
    return next((row for row in rows if regex.search(row)), "")


def structure_market(report: dict[str, Any], name: str, pattern: re.Pattern[str], sections: list[dict[str, str]], full_text: str) -> dict[str, Any]:
    existing = next((m for m in report.get("markets", []) if m.get("name") == name), {})
    text = market_block(full_text, sections, pattern)
    rows = paragraphs(text)
    line_rows = [x.strip() for x in text.splitlines() if x.strip()]
    price = next((x for x in line_rows if re.search(r"\d", x) and re.search(r"円|ドル|%|％|前後|台|ポイント", x)), "")
    material = first_meaningful(text)
    result = dict(existing)
    result["name"] = name
    if sparse(result.get("direction")):
        result["direction"] = infer_direction(text)
    if sparse(result.get("price")):
        result["price"] = price[:180]
    if sparse(result.get("material")):
        result["material"] = material or "本文参照"
    fields = {
        "positioning": r"需給|ポジション|買い戻し|ショート|ロング|建玉|フロー|レバレッジ",
        "levels": r"注目水準|サポート|レジスタンス|上抜|下抜|割れ|超え",
        "mainScenario": r"メインシナリオ|基本シナリオ|中心シナリオ",
        "alternativeScenario": r"代替シナリオ|別シナリオ|反対シナリオ",
        "breakCondition": r"崩れる条件|見方を変える|無効|否定",
        "risk": r"リスク|注意|警戒",
    }
    for field, regex in fields.items():
        if sparse(result.get(field)):
            result[field] = pick(rows, regex)
    if sparse(result.get("breakCondition")):
        result["breakCondition"] = "本文参照"
    return result


def structure_report(report: dict[str, Any]) -> dict[str, Any]:
    full_text = clean(report.get("fullText"))
    if not full_text:
        return report
    sections = split_sections(full_text)
    extracted = {key: section_text(sections, rule) for key, rule in SECTION_RULES.items()}
    result = dict(report)

    theme = first_meaningful(extracted["theme"])
    if sparse(result.get("theme")) or re.search(r"作成日時|基準時刻", clean(result.get("theme"))):
        result["theme"] = theme or first_meaningful(full_text)
    if sparse(result.get("leadingMarket")):
        result["leadingMarket"] = first_meaningful(extracted["leadingMarket"]) or "本文参照"

    array_fields = ["changes", "consistency", "positioning", "news", "crossAssetFlow", "sectors", "events", "handover", "riskManagement"]
    for field in array_fields:
        if sparse(result.get(field)):
            result[field] = paragraphs(extracted[field])

    scenario_rows = paragraphs(extracted["scenario"])
    if sparse(result.get("mainScenario")):
        result["mainScenario"] = pick(scenario_rows, r"メイン|基本|中心") or (scenario_rows[0] if scenario_rows else "")
    if sparse(result.get("alternativeScenario")):
        result["alternativeScenario"] = pick(scenario_rows, r"代替|別|反対") or (scenario_rows[1] if len(scenario_rows) > 1 else "")
    if sparse(result.get("breakConditions")):
        result["breakConditions"] = pick(scenario_rows, r"崩れる|無効|否定|見方を変える")

    # Targeted fallbacks prevent empty cards even when old reports used unusual headings.
    all_sentences = sentences(full_text)
    fallbacks: dict[str, str] = {
        "news": r"発表|報道|ニュース|合意|協議|政策|FOMC|日銀|ECB|FRB",
        "positioning": r"需給|ポジション|建玉|買い戻し|ショート|ロング|ETF|オプション|SQ|レバレッジ",
        "crossAssetFlow": r"資金|流入|流出|買われ|売られ|株式から|債券へ|安全資産",
        "events": r"予定|発表|会合|指標|決算|入札|会見",
        "handover": r"欧州時間|NY時間|次の時間帯|引き継ぎ|今夜|今後",
        "riskManagement": r"リスク|警戒|注意|急変|損切り|ポジションサイズ",
    }
    for field, regex in fallbacks.items():
        if not result.get(field):
            result[field] = [s for s in all_sentences if re.search(regex, s)][:5]

    result["markets"] = [structure_market(result, name, pattern, sections, full_text) for name, pattern in MARKETS]
    result["structuredFromFullText"] = True
    result["structureVersion"] = 2
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="reports.json")
    parser.add_argument("--check", action="store_true", help="Exit 1 when the file would change")
    args = parser.parse_args()
    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("reports.json must contain an array")
    structured = [structure_report(item) for item in data]
    output = json.dumps(structured, ensure_ascii=False, indent=2) + "\n"
    original = path.read_text(encoding="utf-8")
    changed = output != original
    if args.check:
        return 1 if changed else 0
    if changed:
        path.write_text(output, encoding="utf-8")
        print(f"Structured {len(structured)} reports: {path}")
    else:
        print(f"Already structured: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
