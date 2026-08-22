#!/usr/bin/env python3
"""Build the stock-page judgement cards from stock-market data.

The stock page has its own structured data in ``data/stocks.json``. Do not
copy narrative fields from ``data/latest-report.json`` here: that report is a
macro dashboard and may contain rates, commodities, FX, or crypto commentary
that is not a stock-market analysis.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
LATEST_PATH = ROOT / "data" / "latest-report.json"
JST = timezone(timedelta(hours=9))


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def compact(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def rows_by_label(section: Any) -> dict[str, list[Any]]:
    rows = section.get("rows", []) if isinstance(section, dict) else []
    return {
        str(row[0]): row
        for row in rows
        if isinstance(row, list) and row and str(row[0]).strip()
    }


def row_value(rows: dict[str, list[Any]], label: str, index: int = 1) -> str:
    row = rows.get(label, [])
    return compact(row[index] if len(row) > index else "—", 80) or "—"


def row_change(rows: dict[str, list[Any]], label: str) -> str:
    return row_value(rows, label, 2)


def section_rows(stocks: dict[str, Any], market: str) -> dict[str, list[Any]]:
    section = stocks.get("marketInternals", {}).get(market, {})
    return rows_by_label(section)


def mover_line(mover: Any) -> str:
    if not isinstance(mover, dict):
        return ""
    name = compact(mover.get("name"), 50)
    change = compact(mover.get("change"), 30)
    return f"{name} {change}".strip()


def top_movers(stocks: dict[str, Any], market: str, side: str, limit: int = 3) -> list[str]:
    section = stocks.get("movers", {}).get(market, {})
    values = section.get(side, []) if isinstance(section, dict) else []
    return [line for line in (mover_line(item) for item in values[:limit]) if line]


def top_sectors(stocks: dict[str, Any], market: str, limit: int = 3) -> list[str]:
    section = stocks.get("sectors", {}).get(market, {})
    values = section.get("rows", []) if isinstance(section, dict) else []
    output: list[str] = []
    for item in values[:limit]:
        if not isinstance(item, dict):
            continue
        name = compact(item.get("name"), 40)
        change = compact(item.get("change"), 30)
        if name:
            output.append(f"{name} {change}".strip())
    return output


def session_metric(stocks: dict[str, Any], session: str, label: str) -> str:
    block = stocks.get("sessionAnalysis", {}).get(session, {})
    for metric in block.get("metrics", []) if isinstance(block, dict) else []:
        if isinstance(metric, dict) and metric.get("label") == label:
            value = compact(metric.get("value"), 50)
            change = compact(metric.get("change"), 30)
            return f"{label} {value} {change}".strip()
    return ""


def build_judgement(stocks: dict[str, Any]) -> dict[str, Any]:
    jp = section_rows(stocks, "japan")
    us = section_rows(stocks, "us")
    jp_gainers = top_movers(stocks, "japan", "gainers", 2)
    jp_losers = top_movers(stocks, "japan", "losers", 2)
    jp_sectors = top_sectors(stocks, "japan", 2)

    conclusion_main = (
        "米国主要指数は下落、日本はTOPIXが小幅高だがグロース250は下落。"
        "大型株・半導体を軸に強弱が分かれる株式市場。"
    )
    conclusion_sub = (
        f"日経225 {row_value(jp, '日経225')} / TOPIX {row_value(jp, 'TOPIX')} "
        f"/ S&P500 {row_value(us, 'S&P500')} / Nasdaq {row_value(us, 'Nasdaq（総合）')}。"
    )

    reason = [
        f"日本：TOPIX {row_change(jp, 'TOPIX')}、値上がり/値下がり {row_value(jp, '値上がり銘柄 / 値下がり銘柄')}。",
        f"米国：SOX {row_change(us, 'SOX（半導体指数）')}に対し、S&P500 {row_change(us, 'S&P500')}、Nasdaq {row_change(us, 'Nasdaq（総合）')}。",
        f"日本の強いセクター：{'、'.join(jp_sectors)}。個別では{'、'.join(jp_gainers)}。",
    ]
    risk = [
        f"米国はVIX {row_change(us, 'VIX（恐怖指数）')}、NYSE値上がり/値下がり {row_value(us, 'NYSE 値上がり / 値下がり')}で内部下落が優勢。",
        f"日本はグロース250 {row_change(jp, 'グロース250')}で、TOPIXとの乖離に注意。",
        f"日本の下落率上位：{'、'.join(jp_losers)}。",
    ]
    watch = [
        f"S&P500 {row_change(us, 'S&P500')}・Nasdaq {row_change(us, 'Nasdaq（総合）')}の下落が続くか、SOX {row_change(us, 'SOX（半導体指数）')}が下支えを維持するか。",
        f"日経225 / TOPIX / グロース250の方向と、値上がり・値下がり {row_value(jp, '値上がり銘柄 / 値下がり銘柄')}の広がり。",
        f"次回寄り付き：{session_metric(stocks, 'tokyoOpen', 'TOPIX')}、{session_metric(stocks, 'tokyoOpen', '日経225先物（CME参考）')}。",
    ]

    return {
        "conclusion": {
            "title": "今日の結論",
            "main": compact(conclusion_main),
            "sub": compact(conclusion_sub),
        },
        "reason": {"title": "なぜ買われたか／売られたか", "items": [compact(item) for item in reason]},
        "risk": {"title": "リスク", "items": [compact(item) for item in risk]},
        "watch": {"title": "次の注目点", "items": [compact(item) for item in watch]},
    }


def build_analysis_cards(stocks: dict[str, Any]) -> list[dict[str, Any]]:
    jp = section_rows(stocks, "japan")
    us = section_rows(stocks, "us")
    jp_gainers = top_movers(stocks, "japan", "gainers", 3)
    jp_losers = top_movers(stocks, "japan", "losers", 3)
    jp_sectors = top_sectors(stocks, "japan", 3)
    us_sectors = top_sectors(stocks, "us", 3)

    overseas = row_value(jp, "海外投資家動向（現物）")
    cards = [
        {
            "title": "需給・ポジション",
            "items": [
                f"日本：値上がり/値下がり {row_value(jp, '値上がり銘柄 / 値下がり銘柄')}、東証プライム売買代金 {row_value(jp, '東証プライム売買代金')}。",
                f"海外投資家動向（週次）：{overseas}。",
                f"米国：NYSE {row_value(us, 'NYSE 値上がり / 値下がり')}、NASDAQ {row_value(us, 'NASDAQ 値上がり / 値下がり')}で下落優勢。",
            ],
        },
        {
            "title": "フロー判断",
            "items": [
                f"日本：TOPIX {row_change(jp, 'TOPIX')}に対し、グロース250 {row_change(jp, 'グロース250')}。指数間の強弱が残る。",
                f"日本の上位セクター：{'、'.join(jp_sectors)}。米国の上位セクター：{'、'.join(us_sectors)}。",
                f"米国：SOX {row_change(us, 'SOX（半導体指数）')}、Russell2000 {row_change(us, 'Russell2000（小型株）')}。資金の広がりは未確認。",
            ],
        },
        {
            "title": "メインシナリオ",
            "items": [
                f"TOPIX {row_change(jp, 'TOPIX')}の相対優位が続くか、グロース250 {row_change(jp, 'グロース250')}の下落が縮小するかを確認。",
                f"米国はSOX {row_change(us, 'SOX（半導体指数）')}の底堅さが、S&P500 {row_change(us, 'S&P500')}・Nasdaq {row_change(us, 'Nasdaq（総合）')}の下落を吸収できるかが分岐。",
                f"寄り付き確認：{session_metric(stocks, 'tokyoOpen', 'TOPIX')}。",
            ],
        },
        {
            "title": "崩れる条件",
            "items": [
                f"米国でS&P500/Nasdaqの下落とVIX {row_change(us, 'VIX（恐怖指数）')}の上昇が同時に続く場合。",
                f"日本でTOPIXの上昇が広がりを伴わず、グロース250 {row_change(jp, 'グロース250')}の下落が拡大する場合。",
                f"個別株の下落が拡大：{'、'.join(jp_losers)}。",
            ],
        },
        {
            "title": "監視ポイント",
            "items": [
                f"日本の上昇率上位：{'、'.join(jp_gainers)}。",
                f"日本の下落率上位：{'、'.join(jp_losers)}。",
                f"米国の主要指数：S&P500 {row_change(us, 'S&P500')}、Nasdaq {row_change(us, 'Nasdaq（総合）')}、SOX {row_change(us, 'SOX（半導体指数）')}。",
            ],
        },
    ]
    return [{"title": card["title"], "items": [compact(item) for item in card["items"]]} for card in cards]


def report_from(payload: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("latestReport") or payload.get("report") or payload
    return report if isinstance(report, dict) else {}


def main() -> int:
    latest_payload = load(LATEST_PATH)
    latest_report = report_from(latest_payload)
    stocks = load(STOCKS_PATH)
    report_key = stocks.get("judgementReportKey") or (
        f"{latest_report.get('date')} {latest_report.get('time')}"
        if latest_report.get("date") and latest_report.get("time")
        else "stock-market-data"
    )
    previous_key = stocks.get("judgementReportKey")
    judgement_updated_at = (
        stocks.get("judgementUpdatedAt")
        or latest_payload.get("generatedAt")
        or datetime.now(JST).replace(microsecond=0).isoformat()
    )

    stocks["judgement"] = build_judgement(stocks)
    stocks["analysisCards"] = build_analysis_cards(stocks)
    stocks["judgementReportKey"] = report_key
    stocks["judgementUpdatedAt"] = judgement_updated_at
    stocks["judgementSource"] = (
        "data/stocks.json（指数・市場内部・セクター・上昇下落銘柄・セッション分析）"
    )
    if isinstance(judgement_updated_at, str) and judgement_updated_at > str(stocks.get("updatedAt") or ""):
        stocks["updatedAt"] = judgement_updated_at

    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "reportKey": report_key, "previousKey": previous_key}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

