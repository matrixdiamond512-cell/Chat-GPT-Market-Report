#!/usr/bin/env python3
"""Offline tests for 33 Japanese sector daily index historical backfill."""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backfill_jp_sector_history import (
    JP_SECTORS, complete_33_sector_rankings, daily_returns,
    parse_kabutan_daily, plan_blank_days,
)


class JapaneseIndustryHistoryTests(unittest.TestCase):
    def test_parse_realistic_kabutan_table(self):
        html = """
        <table><tr><th>日付</th><th>始値</th><th>高値</th><th>安値</th><th>終値</th><th>前日比</th><th>前日比%</th><th>売買高</th></tr>
        <tr><td>10/16</td><td>692.71</td><td>696.03</td><td>689.76</td><td>694.93</td><td>+3.70</td><td>+0.5%</td><td>1株</td></tr>
        <tr><td>10/15</td><td>689.13</td><td>692.49</td><td>684.42</td><td>691.23</td><td>+7.87</td><td>+1.2%</td><td>1株</td></tr>
        </table>
        """
        prices = parse_kabutan_daily(html, reference_date=dt.date(2026, 10, 18))
        self.assertEqual(prices, {"2026-10-16": 694.93, "2026-10-15": 691.23})
        changes = daily_returns(prices)
        self.assertAlmostEqual(changes["2026-10-16"], 694.93 / 691.23 - 1, places=8)

    def test_requires_all_33_matching_dates(self):
        series = {code: {"2026-09-24": (n - 16) / 10000}
                  for n, code in enumerate(JP_SECTORS)}
        ready = complete_33_sector_rankings(series)
        self.assertEqual(len(ready["2026-09-24"]), 33)
        self.assertEqual(len({i[0] for i in ready["2026-09-24"]}), 33)
        series["0251"].clear()
        self.assertNotIn("2026-09-24", complete_33_sector_rankings(series))

    def test_only_blank_numeric_date_rows_can_fill(self):
        series = {code: {"2026-09-24": (n - 16) / 10000}
                  for n, code in enumerate(JP_SECTORS)}
        rankings = complete_33_sector_rankings(series)
        headers = ["日付"] + [
            f"東京業種{side}{i}{suffix}"
            for side in ("上昇", "下落")
            for i in range(1, 6)
            for suffix in ("業種", "騰落率")
        ] + ["東京業種取得元"]
        serial = (dt.date(2026,9,24) - dt.date(1899,12,30)).days
        updates = plan_blank_days([headers, [serial]], rankings)
        self.assertEqual(len(updates), 21)
        self.assertEqual(len({x["date"] for x in updates}), 1)
        self.assertTrue(all(x["date"] == "2026-09-24" for x in updates))
        self.assertEqual(sum(x["header"].endswith("騰落率") for x in updates), 10)
        self.assertEqual(plan_blank_days([headers, [serial, "existing ranking"]], rankings), [])

    def test_no_other_dates_or_mixed_rankings(self):
        series = {code: {"2026-09-24": (n - 16) / 10000}
                  for n, code in enumerate(JP_SECTORS)}
        rankings = complete_33_sector_rankings(series)
        headers = ["日付"] + [
            f"東京業種{side}{i}{suffix}"
            for side in ("上昇", "下落")
            for i in range(1, 6)
            for suffix in ("業種", "騰落率")
        ]
        self.assertEqual(plan_blank_days([headers, ["2026/09/25"]], rankings), [])


if __name__ == "__main__":
    unittest.main()
