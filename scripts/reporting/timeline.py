"""Fail-closed quality checks for the narrative timeline in each report slot."""
from __future__ import annotations

import re


TIMELINE_PERIODS = {
    "08:00": (
        ("開場前", ("開場前", "寄り付き前")),
        ("寄り付き", ("寄り付き", "開場")),
        ("序盤", ("序盤",)),
        ("中盤", ("中盤",)),
        ("終盤", ("終盤",)),
        ("東京への引き継ぎ", ("東京への引き継ぎ", "東京時間への引き継ぎ")),
    ),
    "12:00": (
        ("寄り付き前", ("寄り付き前", "前場寄り前")),
        ("寄り付き", ("寄り付き",)),
        ("前場序盤", ("前場序盤",)),
        ("前場中盤", ("前場中盤",)),
        ("前引け", ("前引け",)),
    ),
    "16:00": (
        ("寄り付き前", ("寄り付き前", "前場寄り前")),
        ("寄り付き", ("寄り付き",)),
        ("前場序盤", ("前場序盤",)),
        ("前場中盤", ("前場中盤",)),
        ("前引け", ("前引け",)),
        ("後場序盤", ("後場序盤",)),
        ("後場中盤", ("後場中盤",)),
        ("大引け", ("大引け",)),
        ("欧州への引き継ぎ", ("欧州への引き継ぎ", "欧州時間への引き継ぎ")),
    ),
    "21:00": (
        ("欧州開場前", ("欧州開場前", "欧州寄り前")),
        ("欧州寄り付き", ("欧州寄り付き", "欧州寄り")),
        ("欧州序盤", ("欧州序盤",)),
        ("欧州中盤", ("欧州中盤",)),
        ("NY開場前", ("NY開場前", "NY寄り前")),
    ),
}

TIMELINE_COLUMNS = (
    "時間帯",
    "JST時間範囲/観測制約",
    "出来事・確認可能な市場状態",
    "市場・業種・銘柄の反応",
    "相場上の意味・主導要因",
    "時刻・出典・観測制約",
    "次の時間帯への引き継ぎ",
)

_TIME_RE = re.compile(r"(?:[01]?\d|2[0-3]):[0-5]\d")
_CELL_SIGNALS = {
    2: re.compile(r"確認|観測|報道|発表|材料|売買|続|転換|反転|急落|急騰|上昇|下落|横ばい|動|取引|休場|発生|形成|警戒"),
    3: re.compile(r"上昇|下落|反応|買い|売り|円高|円安|低下|上昇|広が|優勢|軟調|堅調|反発|急落|急騰|横ばい|縮小|拡大"),
    4: re.compile(r"ため|背景|示|意味|主導|重要|波及|影響|転換|続|反映|焦点|リスク|注目|警戒|評価|受け止|整合|乖離|局面|見極め|待ち"),
    5: re.compile(r"出典|根拠|観測|制約|報道|発表|未確認|確認できず|確認不能|fact[-_ ]?\w+", re.I),
    6: re.compile(r"引き継|次|注目|確認|継続|監視"),
}


def _cells(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in line[1:-1].split("|")]


def _section(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    starts = [
        i for i, line in enumerate(lines)
        if "時系列" in line and re.match(r"^\s*(?:\d{1,2}[．.、)）]|[■◆◇●▶])", line)
    ]
    if len(starts) != 1:
        return ""
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^\s*\d{1,2}[．.、)）]\s*\S", lines[i]):
            end = i
            break
    return "\n".join(lines[start + 1:end])


def validate_timeline(text: str, slot: str) -> list[str]:
    """Return structural/content-contract violations for a slot's time series.

    The checker validates explicit rows and required explanatory fields. It does
    not infer event causes or treat a news timestamp as a market observation.
    """
    if slot not in TIMELINE_PERIODS:
        return [f"unsupported report slot: {slot}"]
    section = _section(text)
    if not section:
        return ["時系列セクションが一意に見つかりません"]

    lines = section.splitlines()
    header_index = next((i for i, line in enumerate(lines) if _cells(line)), None)
    if header_index is None:
        return ["時系列テーブルがありません"]
    header = [re.sub(r"\s+", "", cell) for cell in _cells(lines[header_index])]
    expected_header = [re.sub(r"\s+", "", cell) for cell in TIMELINE_COLUMNS]
    if header != expected_header:
        return ["時系列テーブルの列が共通契約と一致しません"]

    expected = {key: aliases for key, aliases in TIMELINE_PERIODS[slot]}
    found: dict[str, list[str]] = {}
    errors: list[str] = []
    for line in lines[header_index + 1:]:
        cells = _cells(line)
        if not cells or all(re.fullmatch(r"[-: ]+", cell or "-") for cell in cells):
            continue
        if len(cells) != len(TIMELINE_COLUMNS):
            errors.append("時系列の行に必須列の欠落があります")
            continue
        period = cells[0]
        canonical = next((key for key, aliases in expected.items() if period in aliases), None)
        if canonical is None:
            errors.append(f"対象時間帯ではない行があります: {period}")
            continue
        if canonical in found:
            errors.append(f"時間帯が重複しています: {canonical}")
        found[canonical] = cells

        for index, label in ((2, "出来事・市場状態"), (3, "市場反応"), (4, "相場上の意味"), (5, "時刻・出典"), (6, "次時間帯への引き継ぎ")):
            value = cells[index]
            if not value or not _CELL_SIGNALS[index].search(value):
                errors.append(f"{canonical}: {label}が説明文になっていません")
        if not (re.search(r"\d{1,2}:\d{2}", cells[1]) or "観測制約" in cells[1]):
            errors.append(f"{canonical}: JST時間範囲または観測制約がありません")

        # Any clock time in event/response cells must say what the time means.
        # This keeps report publication time distinct from market observation.
        timed_text = " ".join(cells[2:4])
        if _TIME_RE.search(timed_text) and not re.search(r"(?:発生|発表|報道|市場観測|観測)時刻", cells[5]):
            errors.append(f"{canonical}: 出来事/市場反応時刻と根拠欄の時刻区分が不明です")

        # A 21:00 report may name future releases as planned, but must not mark
        # events after the report cutoff as already observed.
        if slot == "21:00":
            for match in _TIME_RE.finditer(" ".join(cells[2:4])):
                hour, minute = map(int, match.group().split(":"))
                context = " ".join(cells[2:4])[max(0, match.start() - 22):match.end() + 28]
                explicitly_scheduled = bool(re.search(r"予定|予想|未発表|今後|これから|控え|待機|見込み|翌日|明日", context))
                explicitly_historical = bool(re.search(r"前日|昨日|昨夜|先週|過去", context))
                # In a 21:00 report an unqualified 22:30 event cannot be
                # stated as observed. Earlier-day references and clearly
                # scheduled future releases remain permissible.
                if hour * 60 + minute > 21 * 60 and not (explicitly_scheduled or explicitly_historical):
                    errors.append("21:00時点より後の出来事を発生済みとして記載しています")

    missing = [period for period, _ in TIMELINE_PERIODS[slot] if period not in found]
    if missing:
        errors.append("必須時間帯が不足しています: " + ", ".join(missing))
    return errors
