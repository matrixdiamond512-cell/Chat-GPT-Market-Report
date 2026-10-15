"""Narrative quality checks against frozen source prices, without any AI calls.

Conservative automated checks cannot establish economic causality. Passing
them never authorizes release; they only catch detectable contradictions.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import re
from .context import ReportContext
from .snapshot import MarketDataSnapshot

REQUIRED_PRACTICAL_SECTIONS = (
    "材料と値動きの整合性",
    "今日の主導市場",
    "シナリオが崩れる条件",
)
# These must be explicit for cross-session interpretation, including 21h.
HANDOFF_ALIASES = ("次の時間帯への引き継ぎ", "NY市場への引き継ぎ",
                   "欧州市場への引き継ぎ", "東京市場への引き継ぎ")
DIRECTION_NAMES = {
    "gold": ("金", "ゴールド", "gold"),
    "wti": ("原油", "WTI", "wti"),
    "nikkei225_futures_ose": ("日経225先物", "日経先物"),
    "usdjpy": ("ドル円", "USD/JPY", "usdjpy"),
    "eurusd": ("ユーロドル", "EUR/USD", "eurusd"),
    "btcusd": ("ビットコイン", "BTC", "btcusd"),
}
UP = ("上昇", "強含み", "堅調", "値上がり", "上げ", "反発", "高騰")
DOWN = ("下落", "弱含み", "軟調", "値下がり", "下げ", "反落", "急落")
NAME = r"(?:金(?!利)|ゴールド|原油|WTI|日経225先物|日経先物|ドル円|USD/JPY|ユーロドル|EUR/USD|ビットコイン|BTC)"


@dataclass(frozen=True)
class NarrativeQualityResult:
    status: str
    issues: tuple[str, ...]
    publishable: bool = False


def expected_title(context: ReportContext) -> str:
    day=date.fromisoformat(context.report_date)
    return f"マーケットレポート｜{day:%Y/%m/%d}（{'月火水木金土日'[day.weekday()]}）{context.report_time}"


def _observed_section(text: str, heading: str):
    """Read one anchored heading; do not interpret conditional future scenarios."""
    match = re.search(r"(?:^|\n)\s*(?:#{1,3}\s*)?"+re.escape(heading)+r"\s*\n",text)
    if not match:
        return ""
    chunk=text[match.end():]
    end=re.search(r"\n\s*(?:#{1,3}\s*)?(?:今日の相場テーマ|前回からの変化|主要市場データ|重要ニュース|クロスアセット資金フロー|需給・ポジション|重要イベント|個別市場見通し|シナリオ|リスク管理|結論|材料と値動きの整合性|今日の主導市場|シナリオが崩れる条件|次の時間帯への引き継ぎ)\s*(?:\n|$)",chunk)
    return chunk[:end.start()] if end else chunk


def _direction_assertions(section: str):
    """Parse explicit observed price descriptions, not hypothetical conditions."""
    results=[]
    for sentence in re.split(r"[。\n]",section):
        if not sentence.strip():
            continue
        if any(cue in sentence for cue in ("ならば","場合","条件","すれば","仮に","可能性","余地")):
            continue
        # Combined-asset phrase e.g. "金と原油の強含み" claims both assets up.
        together=re.search(r"("+NAME+r")と("+NAME+r")(?:の|は|が|も)\s*(強含み|弱含み|上昇|下落|堅調|軟調)",sentence)
        if together:
            sign="UP" if together.group(3) in UP else "DOWN"
            results.append((together.group(1),sign))
            results.append((together.group(2),sign))
        for m in re.finditer(r"("+NAME+r")(?:は|が|も|の値動きは)\s*([^\n。、]{0,12}?)\s*(上昇|下落|強含み|弱含み|堅調|軟調|反発|反落)",sentence):
            direction="UP" if m.group(3) in UP else "DOWN"
            results.append((m.group(1),direction))
    return results


def check_narrative_quality(context: ReportContext, snapshot: MarketDataSnapshot,
                            title: str, body: str, *, require_full_sop=True):
    issues=[]
    wanted=expected_title(context)
    if title!=wanted or not isinstance(body,str) or not body.splitlines() or body.splitlines()[0].strip()!=wanted:
        issues.append("EXACT_TITLE_OR_WEEKDAY_MISMATCH")
    if not isinstance(body,str) or len(body.strip())<1200:
        issues.append("BODY_TOO_SHORT")
    if not isinstance(body,str):
        return NarrativeQualityResult("BLOCKED",tuple(issues))
    if require_full_sop:
        for section in REQUIRED_PRACTICAL_SECTIONS:
            if not re.search(r"(?:^|\n)\s*(?:#{1,3}\s*)?"+re.escape(section)+r"\s*(?:\n|$)",body):
                issues.append("REQUIRED_USER_SOP_SECTION_MISSING:"+section)
        if not any(re.search(r"(?:^|\n)\s*(?:#{1,3}\s*)?"+re.escape(x)+r"\s*(?:\n|$)",body)
                   for x in HANDOFF_ALIASES):
            issues.append("SESSION_HANDOFF_MISSING")
    direction={}
    for m in snapshot.markets:
        for name in DIRECTION_NAMES.get(m.instrument,()):
            direction[name]=m.direction
    for section_name in ("今日の相場テーマ","前回からの変化","結論"):
        for name,observed in _direction_assertions(_observed_section(body,section_name)):
            true=direction.get(name)
            if true and true in ("UP","DOWN") and observed != true:
                issues.append(f"OBSERVED_DIRECTION_CONTRADICTION:{section_name}:{name}:{true}!={observed}")
    return NarrativeQualityResult("PASS" if not issues else "BLOCKED",tuple(issues))
