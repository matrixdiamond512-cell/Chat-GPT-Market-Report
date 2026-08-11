import unittest

from lib.jpx_arbitrage import component_from_positions, parse_position_text


FIXTURE = """
2026年8月10日
裁定取引に係る現物ポジション（8月6日現在）
株 数 1,234 39,322 4,567 8,901 625,909
"""


class JpxArbitrageParserTest(unittest.TestCase):
    def test_current_jpx_position_line(self):
        parsed = parse_position_text(FIXTURE, "https://example.test/260806.pdf")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.asOfDate, "2026-08-06")
        self.assertEqual(parsed.sellBalance, 39322)
        self.assertEqual(parsed.buyBalance, 625909)

    def test_component_change_uses_previous_publication(self):
        current = parse_position_text(FIXTURE)
        older = parse_position_text(FIXTURE.replace("8月6日", "8月5日").replace("39,322", "40,269").replace("625,909", "630,611"))
        component = component_from_positions([current, older])
        self.assertEqual(component["sellChange"], -947)
        self.assertEqual(component["buyChange"], -4702)
        self.assertEqual(component["status"], "verified")


if __name__ == "__main__":
    unittest.main()
