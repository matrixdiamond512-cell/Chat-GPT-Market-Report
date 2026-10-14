"""Safety checks for BTC report-price parsing in comparison repair."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from repair_btc_24h_change import numeric


class BTCNumericSafetyTests(unittest.TestCase):
    def test_unavailable_reason_date_is_not_a_btc_price(self):
        self.assertIsNone(numeric("取得不能（2026-10-14のBTCUSD前営業日終値が空欄）"))
        self.assertIsNone(numeric("未公表（2026/10/14）"))
        self.assertIsNone(numeric("2026-10-14"))

    def test_real_numeric_prices_still_parse(self):
        self.assertEqual(numeric("約81,854ドル"), 81854.0)
        self.assertEqual(numeric("81,854.50 USD"), 81854.50)
        self.assertEqual(numeric(81854.5), 81854.5)


if __name__ == "__main__":
    unittest.main()
