#!/usr/bin/env python3
"""Fixture tests for the Version 7.01 stock-source parsers."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fetch_sector_performance import JP_SECTORS, TRADERS_WEB_SECTOR_URL, parse_japan_traders_web_html
from fetch_tokyo_preopen import parse_kabutan_order_article, parse_traders_web_article
from fetch_us_premarket import aggregate_premarket_rows


TRADERS_ARTICLE = """
<html><h1>〔Market Flash〕寄り前気配は住友不、フジクラが高い気配値</h1>
<p>2026/08/18(火) 08:48</p>
<input id="body_text" value="主力株の寄り前気配では住友不動産&lt;8830&gt;+2.1%、フジクラ&lt;5803&gt;+1.8%が高い気配値。" />
</html>
"""

KABUTAN_ARTICLE = """
<html><h1>寄前〖板状況〗注文ランキング</h1>
<p>2026年7月31日 8時53分18秒現在</p>
<p>■ 買い注文金額ランキング 上位30銘柄</p>
<p>キオクシア &lt;285A&gt; 46,500 +7,000 (+17.7%) 627,100 (2,916,015) 4,972,900 (23,123,985)</p>
<p>東エレク &lt;8035&gt; 60,090 +7,850 (+15.0%) 348,500 (2,094,485) 342,200 (2,056,279)</p>
<p>■ 売り注文金額ランキング 上位20銘柄</p>
<p>ファストリ &lt;9983&gt; 74,850 -3,650 (-4.6%) 52,500 (392,962) 52,500 (392,962)</p>
<p>任天堂 &lt;7974&gt; 7,640 -505 (-6.2%) 495,800 (378,791) 495,800 (378,791)</p>
</html>
"""


class StockSourceParserTests(unittest.TestCase):
    def test_traders_web_market_flash_prose(self) -> None:
        rows, data_date, as_of, highlights = parse_traders_web_article(TRADERS_ARTICLE, "2026-08-18")
        self.assertEqual(data_date, "2026-08-18")
        self.assertEqual(as_of, "2026-08-18T08:48:00+09:00")
        self.assertEqual([(row["code"], row["changePct"]) for row in rows], [("8830", 2.1), ("5803", 1.8)])
        self.assertTrue(highlights)

    def test_kabutan_order_value_is_not_change_percentage(self) -> None:
        rows, data_date, as_of = parse_kabutan_order_article(KABUTAN_ARTICLE, "2026-07-31")
        self.assertEqual(data_date, "2026-07-31")
        self.assertEqual(as_of, "2026-07-31T08:53:00+09:00")
        buy = sorted((row for row in rows if row["side"] == "buy"), key=lambda row: row["orderValue"], reverse=True)
        sell = sorted((row for row in rows if row["side"] == "sell"), key=lambda row: row["orderValue"], reverse=True)
        self.assertEqual(buy[0]["code"], "285A")
        self.assertEqual(buy[0]["orderValue"], 23123985)
        self.assertEqual(sell[0]["code"], "9983")
        self.assertEqual(sell[0]["orderValue"], 392962)
        self.assertNotEqual(buy[0]["orderValue"], buy[0]["changePct"])

    def test_premarket_volume_is_cumulative(self) -> None:
        rows = [
            (datetime(2026, 8, 18, 4, 0, tzinfo=timezone.utc), 101.0, 100.0),
            (datetime(2026, 8, 18, 4, 1, tzinfo=timezone.utc), 102.0, 200.0),
            (datetime(2026, 8, 18, 4, 2, tzinfo=timezone.utc), 103.0, 300.0),
        ]
        item = aggregate_premarket_rows("TEST", rows, 100.0)
        self.assertEqual(item["volume"], 600)
        self.assertEqual(item["volumeWindow"], "04:00〜最新時刻のプレマーケット累計")
        self.assertEqual(item["price"], 103.0)

    def test_traders_web_sector_parser_uses_current_ranking_url(self) -> None:
        rows = "".join(
            f"<tr><td>{index}</td><td>{name}（東証）</td><td>1,000</td><td>+1.0</td><td>+{index / 100:.2f}%</td></tr>"
            for index, name in enumerate(JP_SECTORS.values(), start=1)
        )
        html = f"<html><p>2026/08/17 15:45</p><table><tr><th>順位</th><th>業種</th><th>現値</th><th>前日比</th><th>騰落率</th></tr>{rows}</table></html>"
        parsed = parse_japan_traders_web_html(html, "2026-08-17")
        self.assertEqual(len(parsed), 33)
        self.assertEqual(parsed[0]["name"], "水産・農林業")
        self.assertTrue(TRADERS_WEB_SECTOR_URL.endswith("/market_jp/sector_ranking/day"))


if __name__ == "__main__":
    unittest.main()

