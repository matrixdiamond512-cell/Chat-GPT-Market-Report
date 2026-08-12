import unittest

from enrich_usdjpy_tradersweb_levels import parse_rows, select_levels


class TradersWebLevelsTest(unittest.TestCase):
    def test_current_markup_without_literal_separator(self) -> None:
        text = (
        "2026/08/11 06:26 更新 "
        "160.50円 売り小さめ "
        "159.29円 8/11 06:00現在（高値159.36円 - 安値157.54円） "
        "158.80円 買い小さめ・割り込むとストップロス売り小さめ "
        "158.00円 買い小さめ、OP14日NYカット大きめ "
        "プレミアム会員サービス"
    )

        rows = parse_rows(text)
        levels = select_levels(rows)

        self.assertEqual(len(rows), 4)
        self.assertEqual(levels["referenceSpot"], "159.29")
        self.assertEqual(levels["sellOrders"][0]["price"], "160.50")
        self.assertEqual(levels["buyOrders"][0]["price"], "158.80")
        self.assertEqual(levels["stops"][0]["price"], "158.80")
        self.assertEqual(levels["nyCutOptions"][0]["price"], "158.00")
        self.assertEqual(levels["optionAnalysis"]["nearestDistancePips"], 129)
        self.assertIn("下側NYカット", levels["optionAnalysis"]["headline"])

    def test_option_analysis_detects_range_and_order_overlap(self) -> None:
        text = ("160.00円 売り小さめ、OP13日NYカット " "159.29円 8/11 06:00現在 " "159.00円 OP12・13日NYカット大きめ " "158.00円 買い小さめ、OP14日NYカット大きめ " "プレミアム会員サービス")
        levels = select_levels(parse_rows(text))
        self.assertIn("挟まれ", levels["optionAnalysis"]["headline"])
        self.assertTrue(any("売り注文" in point for point in levels["optionAnalysis"]["points"]))


    def test_legacy_literal_separator_remains_supported(self) -> None:
        text = "160.00円 | 売り小さめ 159.50円 | 9:00現在 プレミアム会員サービス"

        rows = parse_rows(text)

        self.assertEqual([row["price"] for row in rows], ["160.00", "159.50"])


if __name__ == "__main__":
    unittest.main()
