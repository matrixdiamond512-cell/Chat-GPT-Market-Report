#!/usr/bin/env python3
"""Replace the Gold_Demand sheet with the page-aligned current snapshot.

The sheet is deliberately long-form.  It stores only data actually used by the
Gold supply-demand page, with each metric's own as-of date and source.  Legacy
columns for estimated IAU flows, regional ETF flows, options strikes/IV, etc.
are not retained.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from write_market_data_to_sheets import (
    SheetsClient,
    SheetsSyncError,
    create_authorized_session,
    load_service_account_info,
    safe_cell,
)

ROOT = Path(__file__).resolve().parents[1]
GOLD_JSON = ROOT / "data" / "gold-supply-demand.json"
MARKET_JSON = ROOT / "data" / "market" / "latest.json"
SHEET = "Gold_Demand"
SOURCE_SHEET = "Gold_Demand_SourceMap"

HEADERS = ["セクション", "項目", "値", "単位", "変化", "基準日", "更新頻度", "判定・見方", "状態", "出典", "URL", "更新日時"]
SOURCE_HEADERS = ["セクション", "データ", "優先取得先", "更新頻度", "自動化", "備考"]

SOURCE_ROWS = [
    ["価格", "金価格（COMEX先物）", "検証済み市場データ基盤（GC=F）", "随時", "自動", "ページ上段の現在価格。COMEX建玉の基準日とは分離する。"],
    ["COMEX先物需給", "出来高・建玉（OI）", "CME Group Daily Bulletin PG02B", "日次", "自動", "GC COMEX GOLD FUTURES行の総出来高、総建玉、建玉前日比を使用。"],
    ["CFTC投機筋", "Managed Money Long / Short / Net", "CFTC Disaggregated COT - Futures Only", "週次", "自動", "GOLD、CFTC Contract Market Code 088691。基準日は火曜日。"],
    ["ETF", "GLD金保有量", "SPDR Gold Shares Historical Archive", "日次", "自動", "Gold Holdings / Tonnes。公式更新が止まった場合は前回確認値をstale表示。"],
    ["ETF", "IAU金保有量", "iShares Gold Trust公式", "日次", "自動", "Tonnes in Trustを使用。発行済口数・AUM・推定フローは使用しない。"],
    ["ETF", "世界金ETF", "World Gold Council Gold ETFs holdings and flows", "週次・月次", "半自動", "公開値を取得できる場合だけ更新。地域別フローはページ正本から除外。"],
    ["中国・インド現物需要", "現物プレミアム/ディスカウント", "World Gold Council Local gold price premium/discount", "週次", "半自動", "5日移動平均の方向性指標。ログイン等で取得不能なら推測しない。"],
    ["先物カーブ", "Contango / Flat / Backwardation", "CME / World Gold Council", "日次〜週次", "取得経路確認中", "安定した無料公開データを確認するまで数値を作らない。"],
    ["中央銀行", "世界中央銀行純購入量", "World Gold Council Central bank gold statistics", "月次", "半自動", "短期シグナルと混ぜず構造的需給として使用。"],
    ["価格環境", "米10年実質金利", "FRED DFII10", "毎営業日", "自動", "低下は一般に金価格の支援要因。"],
    ["価格環境", "米ドル実効指数（Broad）", "FRED DTWEXBGS", "毎営業日", "自動", "DXYと誤表記しない。公開データとしてBroad Dollarを使用。"],
    ["価格環境", "USD/JPY", "検証済み市場データ基盤", "随時", "自動", "円建て金価格・ドル環境確認用。"],
    ["総合判定", "短期需給・構造的需給・スコア", "上記確認済みデータから計算", "更新時", "自動計算", "確認済み項目が不足する場合はスコアを出さない。"],
]


def n(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def row(section: str, item: str, value: Any, unit: str = "", change: Any = "", asof: str = "", freq: str = "", view: str = "", status: str = "", source: str = "", url: str = "", updated: str = "") -> list[Any]:
    return [section, item, safe_cell(value), unit, safe_cell(change), asof or "", freq, view, status, source, url, updated]


def source_of(x: dict[str, Any]) -> tuple[str, str]:
    return str(x.get("sourceName") or ""), str(x.get("sourceUrl") or "")


def build_rows(gold: dict[str, Any], market: dict[str, Any]) -> list[list[Any]]:
    updated = str(gold.get("generatedAt") or "")
    rows: list[list[Any]] = []
    markets = market.get("markets") or {}
    mg = markets.get("gold") or {}
    usd = markets.get("usdjpy") or {}

    if mg:
        rows.append(row("価格", "金価格（COMEX先物）", mg.get("value"), mg.get("unit") or "USD/oz", mg.get("change"), mg.get("asOf") or "", "随時", mg.get("changeText") or "", mg.get("verificationStatus") or "", mg.get("sourceName") or "", mg.get("sourceUrl") or "", updated))
        rows.append(row("価格", "金価格前日比（%）", mg.get("changePercent"), "%", "", mg.get("asOf") or "", "随時", "", mg.get("verificationStatus") or "", mg.get("sourceName") or "", mg.get("sourceUrl") or "", updated))

    c = gold.get("comex") or {}
    sn, su = source_of(c)
    rows += [
        row("COMEX先物需給", "COMEX出来高", c.get("volume"), "枚", "", c.get("asOfDate") or "", "日次", c.get("interpretation") or "", c.get("status") or "", sn, su, updated),
        row("COMEX先物需給", "COMEX建玉（OI）", c.get("openInterest"), "枚", c.get("openInterestChange"), c.get("asOfDate") or "", "日次", c.get("interpretation") or "", c.get("status") or "", sn, su, updated),
        row("COMEX先物需給", "価格×建玉判定", c.get("interpretation"), "", "", c.get("asOfDate") or "", "日次", "価格と建玉の基準日を揃えられた場合のみ判定", c.get("status") or "", sn, su, updated),
    ]

    c = gold.get("cftc") or {}
    sn, su = source_of(c)
    rows += [
        row("CFTC投機筋", "Managed Money Long", c.get("managedMoneyLong"), "枚", "", c.get("asOfDate") or "", "週次", c.get("judgement") or "", c.get("status") or "", sn, su, updated),
        row("CFTC投機筋", "Managed Money Short", c.get("managedMoneyShort"), "枚", "", c.get("asOfDate") or "", "週次", c.get("judgement") or "", c.get("status") or "", sn, su, updated),
        row("CFTC投機筋", "Managed Money Net", c.get("managedMoneyNet"), "枚", c.get("managedMoneyNetChange"), c.get("asOfDate") or "", "週次", c.get("judgement") or "", c.get("status") or "", sn, su, updated),
    ]

    etf = gold.get("etf") or {}
    for label, key in (("GLD金保有量", "gld"), ("IAU金保有量", "iau"), ("世界金ETF保有量", "global")):
        x = etf.get(key) or {}
        sn, su = source_of(x)
        rows.append(row("ETF資金フロー", label, x.get("tonnes"), "t", x.get("changeTonnes"), x.get("asOfDate") or "", "日次" if key in {"gld", "iau"} else "週次・月次", "増加=金ETFへの需要流入の目安", x.get("status") or "", sn, su, updated))

    p = gold.get("physical") or {}
    sn, su = source_of(p)
    for label, key in (("中国プレミアム", "china"), ("インドプレミアム", "india")):
        x = p.get(key) or {}
        rows.append(row("中国・インド現物需要", label, x.get("premiumUsdOz"), "$/oz", x.get("change"), x.get("asOfDate") or p.get("asOfDate") or "", "週次", "プラス方向は現地需要の強さを示す目安", x.get("status") or p.get("status") or "", sn, su, updated))

    curve = gold.get("curve") or {}
    sn, su = source_of(curve)
    rows.append(row("先物カーブ", "カーブ状態", curve.get("state"), "", curve.get("spreadUsdOz"), curve.get("asOfDate") or "", "日次〜週次", "Contango / Flat / Backwardation", curve.get("status") or "", sn, su, updated))

    cb = gold.get("centralBank") or {}
    sn, su = source_of(cb)
    rows.append(row("中央銀行", "中央銀行純購入量", cb.get("netPurchasesTonnes"), "t", "", cb.get("period") or "", "月次", "構造的需要として評価", cb.get("status") or "", sn, su, updated))

    env = gold.get("environment") or {}
    for label, key, unit in (("米10年実質金利", "realYield10y", "%"), ("米ドル実効指数（Broad）", "dollarBroad", "指数")):
        x = env.get(key) or {}
        sn, su = source_of(x)
        rows.append(row("価格環境", label, x.get("value"), unit, x.get("change"), x.get("asOfDate") or "", "毎営業日", "価格ドライバー。需給そのものとは分離", x.get("status") or "", sn, su, updated))
    u = env.get("usdjpy") or {}
    sn, su = source_of(u)
    rows.append(row("価格環境", "USD/JPY", u.get("value") if u else usd.get("value"), "円", u.get("change") if u else usd.get("change"), u.get("asOfDateTime") or usd.get("asOf") or "", "随時", "円建て金価格・ドル環境確認用", u.get("status") or usd.get("verificationStatus") or "", sn or usd.get("sourceName") or "", su or usd.get("sourceUrl") or "", updated))

    a = gold.get("assessment") or {}
    ds = gold.get("dataStatus") or {}
    rows += [
        row("総合判定", "短期需給", a.get("shortTerm"), "", "", updated, "更新時", "COMEX・CFTC・ETF・実質金利・ドルから判定", "calculated", "内部計算", "", updated),
        row("総合判定", "構造的需給", a.get("structural"), "", "", updated, "更新時", "中央銀行・中国/インド等から判定", "calculated", "内部計算", "", updated),
        row("総合判定", "総合需給スコア", a.get("score"), "/100", "", updated, "更新時", "確認済み短期項目が3つ未満なら空欄", "calculated" if a.get("score") is not None else "unavailable", "内部計算", "", updated),
        row("総合判定", "データ状態", f"{ds.get('connected', 0)}/{ds.get('total', 7)}", "", "", updated, "更新時", "7系統中の連携数", "calculated", "内部計算", "", updated),
    ]
    for i, text in enumerate(gold.get("aiSummary") or [], 1):
        rows.append(row("AI総合解説", f"要点{i}", text, "", "", updated, "更新時", "事実と判定を分離した要約", "calculated", "内部計算", "", updated))
    return rows


def main() -> int:
    spreadsheet_id = os.environ.get("MARKET_DATA_SPREADSHEET_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not spreadsheet_id or not service_account_json:
        print("Gold Google Sheets sync skipped: MARKET_DATA_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
        return 0
    gold = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    market = json.loads(MARKET_JSON.read_text(encoding="utf-8"))
    rows = build_rows(gold, market)
    info = load_service_account_info(service_account_json)
    client = SheetsClient(create_authorized_session(info), spreadsheet_id)
    sheets = client.ensure_sheets([SHEET, SOURCE_SHEET])
    client.clear(SHEET, "A:AZ")
    client.update(SHEET, "A1", [HEADERS] + rows)
    client.clear(SOURCE_SHEET, "A:AZ")
    client.update(SOURCE_SHEET, "A1", [SOURCE_HEADERS] + SOURCE_ROWS)
    client.format_table(sheets[SHEET], len(HEADERS), len(rows) + 1)
    client.format_table(sheets[SOURCE_SHEET], len(SOURCE_HEADERS), len(SOURCE_ROWS) + 1)
    print(json.dumps({"sheet": SHEET, "rows": len(rows), "sourceRows": len(SOURCE_ROWS), "generatedAt": gold.get("generatedAt")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
