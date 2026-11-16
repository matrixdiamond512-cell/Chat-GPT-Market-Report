#!/usr/bin/env python3
"""Render a private report draft from the same normalized payload used by Sheets.

This module performs no acquisition and never touches the production close list.
With --write-test-sheet it appends one immutable report version to a dedicated
private test-sheet tab and verifies the readback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_INPUT = ROOT / "data" / "market" / "chatgpt-input.json"
DEFAULT_OUTPUT = ROOT / "data" / "market" / "personal-market-report.md"
JST = dt.timezone(dt.timedelta(hours=9))
REPORT_TAB = "Personal_Market_Report"
HEADERS = [
    "Snapshot ID", "生成日時", "データ基準日", "スナップショット状態",
    "検証済み件数", "参考値件数", "未取得件数", "レポート本文", "本文SHA256",
]


class PersonalReportError(ValueError):
    pass


try:
    from scripts.build_chatgpt_report_input import ITEMS
except ModuleNotFoundError:
    from build_chatgpt_report_input import ITEMS


def validate_sheet_target_ids(test_id: str, production_id: str) -> None:
    if not test_id or not production_id:
        raise PersonalReportError("both private test-sheet and production spreadsheet IDs are required")
    if test_id == production_id:
        raise PersonalReportError("test spreadsheet matches production spreadsheet")


def load_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PersonalReportError("market input could not be read") from exc
    if not isinstance(value, dict) or not isinstance(value.get("markets"), dict):
        raise PersonalReportError("market input must contain a markets object")
    return value


def report_value(market: dict[str, Any]) -> str:
    status = str(market.get("verificationStatus") or "unavailable")
    raw = market.get("displayValue")
    if raw in (None, "", "—", "–"):
        raw = market.get("value")
    if raw in (None, "", "—", "–"):
        return "—"
    market_type = str(market.get("marketType") or "")
    derivative = market_type in {"continuous_futures", "futures_cme", "futures_ose"}
    settlement_confirmed = str(market.get("priceType") or market.get("valueDefinition") or "").lower() in {
        "settlement", "official_settlement", "exchange_settlement", "清算値", "公式清算値",
    }
    if status == "verified" and (not derivative or settlement_confirmed):
        return str(raw)
    if status == "fallback" or market.get("fallbackUsed") or derivative or status == "reference_only" or market.get("referenceOnly"):
        return f"参考値: {raw}"
    return "—"


def status_label(market: dict[str, Any]) -> str:
    status = str(market.get("verificationStatus") or "unavailable")
    market_type = str(market.get("marketType") or "")
    derivative = market_type in {"continuous_futures", "futures_cme", "futures_ose"}
    settlement_confirmed = str(market.get("priceType") or market.get("valueDefinition") or "").lower() in {
        "settlement", "official_settlement", "exchange_settlement", "清算値", "公式清算値",
    }
    if derivative and not settlement_confirmed and market.get("value") not in (None, ""):
        return "参考値（清算値未確認）"
    if status == "verified":
        return "検証済み"
    if status == "fallback" or market.get("fallbackUsed"):
        return "参考値"
    if market.get("value") not in (None, "") and market.get("referenceOnly"):
        return "参考値（検証未完了）"
    return "未取得"


def report_counts(payload: dict[str, Any]) -> tuple[int, int, int]:
    markets = payload.get("markets") or {}
    verified = reference = 0
    for _, symbol, _, _, _ in ITEMS:
        market = markets.get(symbol)
        if not isinstance(market, dict) or market.get("value") in (None, ""):
            continue
        label = status_label(market)
        if label == "検証済み":
            verified += 1
        elif label.startswith("参考値"):
            reference += 1
    return verified, reference, len(ITEMS) - verified - reference


def _numeric(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _comparable_change(market: dict[str, Any]) -> float | None:
    """Accept only the change metric attached to this verified source observation."""
    if market.get("verificationStatus") != "verified" or status_label(market) != "検証済み" or not market.get("asOf"):
        return None
    explicit = _numeric(market.get("changePercent"))
    if explicit is not None:
        return explicit
    value = _numeric(market.get("value"))
    previous = _numeric(market.get("previousClose"))
    current_date = str(market.get("asOf") or "")[:10]
    previous_date = str(market.get("previousCloseAsOf") or "")[:10]
    current_source = str(market.get("sourceId") or "")
    previous_source = str(market.get("previousCloseSourceId") or current_source)
    if value is None or previous in (None, 0) or not previous_date or previous_date >= current_date:
        return None
    if current_source and previous_source != current_source:
        return None
    # Calculated changes require an explicitly dated prior observation from the
    # same source; a naked previousClose is insufficient evidence.
    return (value - previous) / abs(previous) * 100


def _observed_line(label: str, market: dict[str, Any]) -> str:
    date = market.get("asOf") or "基準日不明"
    value = report_value(market)
    unit = market.get("unit") or ""
    status = status_label(market)
    change = _comparable_change(market)
    movement = f"、前日比 {change:+.2f}%" if change is not None else "、方向比較データなし"
    return f"{label}: {value} {unit}（{date}{movement}、{status}）"


TIMELINE_PERIODS = [
    ("寄り付き前", "08:00-08:59 JST"),
    ("寄り付き", "09:00-09:15 JST"),
    ("前場序盤", "09:15-10:30 JST"),
    ("前場中盤", "10:30-11:30 JST"),
    ("前引け", "11:30-12:30 JST"),
    ("後場序盤", "12:30-13:30 JST"),
    ("後場中盤", "13:30-15:25 JST"),
    ("大引け", "15:25-15:30 JST（クロージング・オークションを含む）"),
    ("欧州への引き継ぎ", "15:30-16:00 JST"),
]
TIMELINE_FIELDS = (
    "時間帯", "JST時間範囲／観測制約", "出来事・確認可能な市場状態",
    "市場・業種・銘柄の反応", "相場上の意味・主導要因",
    "時刻・出典・観測制約", "次の時間帯への引き継ぎ",
)


def render_timeline_lines(payload: dict[str, Any]) -> list[str]:
    """Render source-backed periods; missing periods are explicitly unobserved."""
    provided = {
        str(row.get("時間帯") or row.get("period") or ""): row
        for row in payload.get("timelineEvidence") or [] if isinstance(row, dict)
    }
    lines = [
        "### 東京市場の時系列（16:00履歴再構成）", "",
        "| " + " | ".join(TIMELINE_FIELDS) + " |",
        "|---|---|---|---|---|---|---|",
    ]
    for period, time_range in TIMELINE_PERIODS:
        row = provided.get(period)
        if row and all(str(row.get(field) or "").strip() for field in TIMELINE_FIELDS):
            cells = [str(row[field]).replace("|", "\\|").replace("\n", " ") for field in TIMELINE_FIELDS]
        else:
            cells = [
                period,
                f"{time_range}。当該時間帯の保存済み観測記録なし",
                "価格推移・ニュース・出来事の時点証拠を確認できません。",
                "反応は未確認。終値から値動きを逆算しません。",
                "主導要因は判定不能。因果関係を付与しません。",
                "observedAt／出典URL／原本ハッシュを確認できず、観測制約あり。",
                "確認済みの引き継ぎ材料は未取得。変化なしとは判定しません。",
            ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def render_snapshot_analysis(payload: dict[str, Any]) -> list[str]:
    """Build every analytical section only from this snapshot and its evidence."""
    markets = payload.get("markets") or {}
    if not isinstance(markets, dict):
        markets = {}
    usable = {key: value for key, value in markets.items() if isinstance(value, dict)}
    changes = {
        key: change for key, market in usable.items()
        if (change := _comparable_change(market)) is not None
    }
    equity_keys = ("dow", "nasdaq", "sp500", "russell2000", "nikkei225_cash")
    cohorts: dict[tuple[str, str], list[str]] = {}
    for key in equity_keys:
        market = usable.get(key) or {}
        if key in changes:
            cohorts.setdefault((str(market.get("asOf") or ""), str(market.get("session") or "")), []).append(key)
    cohort_key, cohort_symbols = max(cohorts.items(), key=lambda item: len(item[1]), default=(None, []))
    equity_moves = [changes[key] for key in cohort_symbols]
    up = sum(value > 0 for value in equity_moves)
    down = sum(value < 0 for value in equity_moves)
    cohort_date = cohort_key[0] if cohort_key else ""
    vix_change = changes.get("vix") if (usable.get("vix") or {}).get("asOf") == cohort_date else None
    leading = max(cohort_symbols, key=lambda key: abs(changes[key]), default=None)
    names = {symbol: label for label, symbol, *_ in ITEMS}

    if equity_moves:
        theme = f"同じ市場日・セッション（{cohort_date} / {cohort_key[1] or 'session不明'}）で比較できる株価指数は上昇 {up}・下落 {down}。対象は {len(equity_moves)} 件です。"
    else:
        theme = "比較可能な前日比を同じ取得記録から確認できないため、相場の方向をテーマとして断定しません。以下は基準日時点の観測値に限った整理です。"
    movement_lines = [f"- {_observed_line(names.get(key, key), usable[key])}" for key in sorted(usable) if usable[key].get("value") not in (None, "")]
    if not movement_lines:
        movement_lines = ["- 数値を確認できる市場データはありません。"]
    consistency = (
        (f"{cohort_date} / {cohort_key[1] or 'session不明'} の株価指数前日比は上昇 {up}・下落 {down}。"
         if equity_moves else "同一市場日・セッションにそろう比較可能な株価指数の前日比はありません。")
        + (f" VIXの前日比は {vix_change:+.2f}%です。" if vix_change is not None else " VIXの比較可能な前日比はありません。")
        + "市場ごとの基準日は項目別一覧を参照してください。"
    )
    if leading:
        leader_text = f"{cohort_date} / {cohort_key[1] or 'session不明'} の株価指数群で絶対変化率が最大なのは {names.get(leading, leading)}（{changes[leading]:+.2f}%）。"
    else:
        leader_text = "同じスナップショットに比較可能な前日比がないため、主導市場は判定保留です。"

    news_items = payload.get("news") or []
    news_lines = []
    for article in news_items:
        if not isinstance(article, dict):
            continue
        title = str(article.get("title") or "").replace("|", "\\|").replace("\n", " ").strip()
        provider = str(article.get("provider") or "出典不明").replace("|", "\\|").strip()
        published = str(article.get("publishedAt") or "時刻不明")
        url = str(article.get("url") or "")
        source = f"[{provider}]({url})" if url.startswith("https://") else provider
        if title:
            news_lines.append(f"- {published} {source}: {title}")
    news_text = (
        "このスナップショット生成時に取得した見出しです。記事本文の閲覧権限は含まず、見出しから先の事実は推定していません。\n\n"
        + "\n".join(news_lines)
        if news_lines else "同一スナップショットに、時刻と出典を検証できるニュース記事は含まれていません。ニュース材料は未取得です。"
    )

    verified_count, reference_count, unavailable_count = report_counts(payload)
    lines = ["## 同一スナップショットに基づく詳細分析", "",
             "> 各文は下記の市場データと同じスナップショットから生成しています。取得記録にないニュース・資金流・建玉は推測していません。", "",
             "### データ取得・クロスチェック", "",
             f"対象28項目のうち検証済み {verified_count}、参考値 {reference_count}、証拠不足で未取得 {unavailable_count}。取得記録にない数値は推定せず、異なる市場日や系列を横並びにしていません。", "",
             "### 全体テーマ", "", theme, "",
             "### 主な変化", "", *movement_lines, "",
             *render_timeline_lines(payload),
             "### 市場間の整合性", "", consistency, "",
             "### 主導市場", "", leader_text, "",
             "### ニュース", "", news_text, "",
             "### クロスアセット資金フロー", "", "価格の同時変化は上表の範囲で比較できますが、資金流そのものを示すフロー統計は未取得です。値動きだけから資金移動を断定しません。", "",
             "### 需給・ポジション", "", "出来高・建玉・投資家ポジションの検証済み系列がないため、ポジションの偏りや清算規模は判定しません。", "",
             "### セクター", "", "同一時点のセクター別データがないため、強弱順位は未取得です。", "",
             "### 注目イベント", "", "イベントカレンダーがこのスナップショットに含まれていないため、日程は未取得です。", ""]

    if equity_moves:
        base_scenario = f"{cohort_date} / {cohort_key[1] or 'session不明'} の検証済み指数で観測した上昇・下落数（{up} 対 {down}）と同方向の広がりが、次の同市場セッションでも続く場合に限り、株式地合いの維持を確認します。"
        alternative = "次回の同一系列比較で下落数が上昇数を上回る場合は、地合い悪化の代替シナリオへ切り替えます。"
        invalidation = "次回の対象市場日で検証済み指数の上昇・下落優勢が逆転した時点で、現在の条件付きシナリオを無効とします。"
    else:
        base_scenario = "比較可能な方向データが不足しているため、価格目標を置くシナリオは作成しません。検証済み同一系列の次回終値取得後に更新します。"
        alternative = "次回値が取得できた場合に限り、上昇・下落の観測方向を別シナリオとして提示します。現時点で反対方向を予測しません。"
        invalidation = "現在は方向を伴うベースシナリオがないため、無効化水準も設定しません。"
    lines.extend(["### メインシナリオ", "", base_scenario, "",
                  "### 上振れシナリオ", "",
                  ("同一市場日・同一系列で上昇を確認できる証拠がないため、上振れ条件は設定しません。"
                   if not equity_moves else alternative), "",
                  "### 下振れシナリオ", "",
                  ("同一市場日・同一系列で下落を確認できる証拠がないため、下振れ条件は設定しません。"
                   if not equity_moves else alternative), "",
                  "### 代替シナリオ", "", alternative, "",
                  "### シナリオの崩れ条件", "", invalidation, "",
                  "### リスク管理", "", "検証済みの現物・公式系列と参考値を分けて判断し、連続先物足は清算値として扱いません。基準日の異なる市場を同じ日付の同時観測とみなしません。", "",
                  "### 欧州時間・NY時間への引き継ぎ", "",
                  "対象時点後に発生した値動きやニュースを含む証拠は除外しました。欧州・NY時間に渡す当時の確認済み材料は未取得です。", "",
                  "### 次の市場への引き継ぎ", "", "次回は各市場の営業日・締め時刻に沿った同一系列の新しい観測を取得し、前日比・金利・市場 breadth を更新します。", "",
                  "### 主要6市場の見通し", ""])
    six = (("金", "gold"), ("WTI原油", "wti"), ("日経225先物（大阪取引所）", "nikkei225_futures_ose"),
           ("USD/JPY", "usdjpy"), ("EUR/USD", "eurusd"), ("BTC/USD", "btcusd"))
    for label, key in six:
        market = usable.get(key)
        if not market or market.get("value") in (None, ""):
            lines.append(f"- **{label}** — 未取得。方向・見通しは提示しません。")
            continue
        line = _observed_line(label, market)
        if status_label(market).startswith("参考値"):
            line += "。参考終値のため、正式清算値に基づく見通しではありません。"
        elif _comparable_change(market) is None:
            line += "。比較可能な前日比がないため方向判断は保留です。"
        else:
            line += "。記載した前日比の観測継続を次回確認条件とします。"
        lines.append(f"- **{label}** — {line}")
    lines.append("")
    return lines


def render_report(payload: dict[str, Any]) -> str:
    markets = payload.get("markets") or {}
    retrieved = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("reportDate") or payload.get("previousCloseDate") or "")
    report_slot = str(payload.get("reportSlot") or "")
    report_symbols = [item[1] for item in ITEMS]
    verified, reference, unavailable = report_counts(payload)
    historical = bool(payload.get("historicalSnapshot")) or payload.get("overallStatus") == "historical_only"
    lines = [
        f"# {'履歴再構成・個人用マーケットレポート' if historical else '個人用マーケットレポート草案'} {report_date} {report_slot}".strip(),
        "",
        f"生成日時: {retrieved or '不明'}",
        f"対象データ期間: {payload.get('dataDateRange') or report_date or '不明'}",
        f"状態: {payload.get('overallStatus') or 'unknown'} / 検証済み {verified}項目 / 参考値 {reference}項目 / 未取得 {unavailable}項目 / 対象28項目",
        "",
    ]
    if historical:
        lines.extend([
            "> 履歴データからの再構成です。生成日時点の最新相場ではなく、現在の投資判断用スナップショットとして使用しないでください。",
            "",
        ])
    lines.extend([
        "各市場の営業日と日次締めは項目ごとに記録しています。参考値は清算値などの確定値と混同しません。",
        "",
    ])
    if payload.get("snapshotFreshness") == "latest_available_confirmed_per_market":
        lines.extend([
            "各項目はレポート生成時点で確認できた最新の市場別データです。休場日や検証未完了の新しい候補がある場合、基準日は市場ごとに異なります。",
            "",
        ])
    lines.extend(render_snapshot_analysis(payload))
    validation_notes = [str(note).strip().replace("\n", " ") for note in payload.get("validationNotes") or [] if str(note).strip()]
    if validation_notes:
        lines.extend(["### 取得・検証上の留意点", "", *[f"- {note}" for note in validation_notes], ""])
    yield_rows = []
    for key, label in (("us10y", "米10年債"), ("jp10y", "日本10年国債")):
        market = markets.get(key)
        if isinstance(market, dict) and market.get("value") not in (None, ""):
            yield_rows.append(f"{label}: {report_value(market)} {market.get('unit') or '%'}（基準日 {market.get('asOf') or '不明'}、{market.get('sourceName') or market.get('sourceId') or '取得元不明'}）")
        else:
            yield_rows.append(f"{label}: 未取得")
    lines.extend(["### 金利・金融環境（今回のスナップショット）", "", *[f"- {row}" for row in yield_rows], ""])
    lines.extend([
        "## 市場データスナップショット（項目別の取得記録）",
        "",
        "| 市場データ | 値 | 単位 | 基準日 | 取得日時 | 取得元 | 状態 | 定義・検証根拠 |",
        "|---|---:|---|---|---|---|---|---|",
    ])
    for label, symbol, item_unit, _, _ in ITEMS:
        market = markets.get(symbol)
        if not isinstance(market, dict):
            market = {"verificationStatus": "unavailable"}
        label = str(market.get("displayName") or label).replace("|", "\\|")
        value = report_value(market).replace("|", "\\|")
        unit = str(market.get("unit") or item_unit).replace("|", "\\|")
        as_of = str(market.get("asOf") or "—").replace("|", "\\|")
        source = str(market.get("sourceName") or market.get("sourceId") or "—").replace("|", "\\|")
        status = status_label(market)
        retrieved_at = str(market.get("fetchedAt") or market.get("retrievedAt") or "—").replace("|", "\\|")
        evidence = market.get("verificationBasis") or market.get("note") or market.get("valueDefinition") or ""
        anchor = market.get("barAnchorUTC")
        if anchor:
            evidence = f"{evidence}; anchor={anchor}" if evidence else f"anchor={anchor}"
        evidence = str(evidence or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {label} | {value} | {unit} | {as_of} | {retrieved_at} | {source} | {status} | {evidence} |")
    lines.extend([
        "", "未取得欄は推測で補っていません。", "",
        "## 最終まとめ", "",
        "対象日時の市場方向・ニュース反応・資金フローは、保存済みの時点証拠がないため判定できません。これは市場変動がなかったという意味ではありません。", "",
        "## 出典・取得不能事項", "",
        "項目別の取得元、証拠URL、証拠ハッシュ、採否理由は同梱の evidence.json を参照してください。市場日・観測時刻・確定時刻・公表時刻の独立証拠が不足する項目は未取得としています。", "",
    ])
    return "\n".join(lines)


def report_sheet_row(payload: dict[str, Any], body: str) -> list[Any]:
    generated = str(payload.get("generatedAt") or "")
    report_date = str(payload.get("dataDateRange") or payload.get("reportDate") or payload.get("previousCloseDate") or "")
    markets = payload.get("markets") or {}
    market_identity = payload.get("snapshotId")
    if not market_identity:
        identity_rows = [
            [symbol, market.get("value"), market.get("asOf"), market.get("sourceId"),
             market.get("sourceName"), market.get("unit"), market.get("verificationStatus"),
             market.get("fetchedAt")]
            for symbol, market in sorted(markets.items()) if isinstance(market, dict)
        ]
        canonical = json.dumps(identity_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        market_identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    identity = hashlib.sha256(f"{market_identity}|{report_date}|{body_hash}".encode("utf-8")).hexdigest()[:24]
    key = f"personal-report-{identity}"
    verified, reference, unavailable = report_counts(payload)
    return [
        key, generated, report_date, str(payload.get("overallStatus") or "unknown"),
        verified, reference, unavailable, body, body_hash,
    ]


def write_test_sheet(row: list[Any]) -> dict[str, Any]:
    test_id = os.environ.get("MARKET_DATA_TEST_SPREADSHEET_ID", "").strip()
    production_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not test_id or not account_json:
        raise PersonalReportError("private test-sheet ID or service-account credential is missing")
    validate_sheet_target_ids(test_id, production_id)
    try:
        from scripts.import_tradingview_mcp_candidates import append_idempotent_sheet_rows
        from scripts.write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    except ModuleNotFoundError:
        from import_tradingview_mcp_candidates import append_idempotent_sheet_rows
        from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
    info = load_service_account_info(account_json)
    client = SheetsClient(create_authorized_session(info), test_id)
    result = append_idempotent_sheet_rows(client, REPORT_TAB, HEADERS, [row], "H")
    return {"tab": REPORT_TAB, **result, "productionSpreadsheetWritten": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-test-sheet", action="store_true")
    args = parser.parse_args()
    try:
        payload = load_payload(args.input)
        body = render_report(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        result: dict[str, Any] = {
            "reportDate": payload.get("reportDate") or payload.get("previousCloseDate"),
            "marketCount": len(payload.get("markets") or {}),
            "verifiedCount": report_counts(payload)[0],
            "referenceCount": report_counts(payload)[1],
            "unavailableCount": report_counts(payload)[2],
            "output": str(args.output),
        }
        if args.write_test_sheet:
            result["sheets"] = write_test_sheet(report_sheet_row(payload, body))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, PersonalReportError) as exc:
        print(json.dumps({"status": "failed", "errorCode": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
