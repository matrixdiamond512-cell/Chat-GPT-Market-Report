"""Update visible dashboard labels to match verified OHLC provenance.

Only the price descriptions change. The existing spot-volume chart,
period selector, metrics, and layout are not altered.
"""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "usdjpy-volume.html"

REPLACEMENTS = {
    "日本銀行「外国為替市況（日次）」のPDFから、USD/JPYのスポット出来高だけを抽出し、Investing.comのUSD/JPY日足OHLCと照合しています。":
        "日本銀行「外国為替市況（日次）」のUSD/JPYスポット出来高と、対象日ごとのドル円日足OHLCを照合しています。価格は既存のInvesting.comデータと、欠損を補完したYahoo!ファイナンス日本版データを使用しています。",
    "<td id=\"priceRange\">Investing.com USD/JPY日足OHLC</td>":
        "<td id=\"priceRange\">価格の出典・対象期間を取得中...</td>",
    "※ 出来高はUSD/JPYスポット出来高のみです。価格データはInvesting.comのUSD/JPY日足OHLCです。":
        "※ 出来高は日本銀行公表のUSD/JPYスポット出来高のみです。価格は2026/08/26以前がInvesting.com、2026/08/27以降の欠損補完分がYahoo!ファイナンス日本版の日足OHLCです。東京市場の出来高と日足OHLCは集計時間帯が異なるため、同一時間帯の約定出来高と値動きの厳密な対応ではありません。",
}


def main() -> None:
    original = PAGE.read_text(encoding="utf-8")
    updated = original
    for old, new in REPLACEMENTS.items():
        if old in updated:
            updated = updated.replace(old, new, 1)
        elif new not in updated:
            raise SystemExit("Dashboard price attribution marker absent: " + old[:65])
    if updated != original:
        PAGE.write_text(updated, encoding="utf-8")
        print("Updated the live USDJPY dashboard price-source labels")
    else:
        print("USDJPY dashboard price-source labels were already accurate")


if __name__ == "__main__":
    main()
