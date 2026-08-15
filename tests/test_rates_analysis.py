import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_rates_bonds_json as builder


def stat(value, daily, weekly=0, day=date(2026, 8, 14)):
    return {"value": value, "changeBp": daily, "weekChangeBp": weekly, "date": day}


class RatesAnalysisTests(unittest.TestCase):
    def test_us_bull_steepening(self):
        result = builder.curve_analysis(stat(4.1, -10), stat(4.6, -5), {"shape": "順イールド"}, "米国")
        self.assertEqual(result["type"], "ブル・スティープニング")

    def test_weekly_breaks_daily_tie(self):
        result = builder.curve_analysis(stat(4.1, -5, -10), stat(4.6, -5, -6), {"shape": "順イールド"}, "米国")
        self.assertEqual(result["type"], "ブル・スティープニング")
        self.assertIn("週間", result["interpretation"])

    def test_long_led_bear_steepening(self):
        result = builder.curve_analysis(stat(4.1, 3), stat(5.0, 12), {"shape": "順イールド"}, "米国")
        self.assertEqual(result["type"], "ベア・スティープニング")

    def test_japan_bear_steepening(self):
        result = builder.curve_analysis(stat(1.6, 2), stat(4.0, 10), {"shape": "順イールド"}, "日本")
        self.assertEqual(result["type"], "ベア・スティープニング")

    def test_cross_asset_consistency_and_confidence(self):
        market = {"markets": {
            "usdjpy": {"changePercent": .2, "asOf": "2026-08-15"},
            "gold": {"changePercent": .4, "asOf": "2026-08-14"},
            "btcusd": {"changePercent": -.5, "asOf": "2026-08-14"},
        }}
        analysis = builder.build_analysis(
            {"2年": stat(4.1, -5), "10年": stat(4.6, -4)},
            {"2年": stat(1.6, 2), "10年": stat(2.8, 7), "30年": stat(4.0, 10)},
            {"us": {"shape": "順イールド"}, "jp": {"shape": "順イールド"}}, stat(2.3, -3), market)
        by_market = {row["market"]: row for row in analysis["crossAssetAnalysis"]}
        self.assertEqual(by_market["USD/JPY"]["verdict"], "逆行")
        self.assertEqual(by_market["USD/JPY"]["confidence"], "中")
        self.assertEqual(by_market["金"]["verdict"], "整合")
        self.assertEqual(by_market["BTCUSD"]["verdict"], "逆行")

    def test_missing_data_does_not_invent(self):
        result = builder.rates_block([("2年", None)], {"type": "判定保留", "interpretation": "不足"}, "米国債")
        self.assertEqual(result["direction"], "判定保留")


if __name__ == "__main__":
    unittest.main()
