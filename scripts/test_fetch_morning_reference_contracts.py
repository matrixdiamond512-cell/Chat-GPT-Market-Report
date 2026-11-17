from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_morning_reference as fetch


class ContractExpiryTests(unittest.TestCase):
    def test_expiry_sequence_moves_forward_from_current_month(self):
        self.assertEqual(
            [entry[2] for entry in fetch._active_month_codes(2026, 11)[:3]],
            ["26年12月限", "27年03月限", "27年06月限"],
        )

    def test_front_contract_rolls_before_delivery_month(self):
        self.assertEqual(fetch._quarterly_contract_for_date(2026, 11)[2], "26年12月限")
        self.assertEqual(fetch._quarterly_contract_for_date(2026, 12)[2], "27年03月限")

    def test_cme_uses_current_contract_not_stale_hardcoded_contract(self):
        text = "CME￥ 27年03月限 52,000 +100 51,900 52,100 52,010 07:45"
        result = fetch.parse_cme(text, "yen", dt.date(2026, 11, 16))
        self.assertEqual(result["contract"], "27年03月限")
        self.assertEqual(result["value"], "52,000")

    def test_cme_labels_next_quarter_contract_without_claiming_front_status(self):
        result = fetch.parse_cme("CME￥ 27年03月限 52,000 +100 51,900 52,100 52,010 07:45", "yen", dt.date(2026, 11, 16))
        self.assertFalse(result["contractIsFront"])

    def test_ose_uses_current_contract(self):
        text = "大証ラージ 26年12月限 52,000 +100 51,900 52,100 51,950 52,010 07:45"
        result = fetch.parse_ose(text, dt.date(2026, 11, 16))
        self.assertEqual(result["contract"], "26年12月限")
        self.assertEqual(result["value"], "52,000円")

    def test_cme_and_ose_timestamped_values_are_not_claimed_before_cutoff_when_late(self):
        parsed = fetch.parse_cme("CME￥ 26年12月限 52,000 +100 51,900 52,100 52,010 08:06", "yen", dt.date(2026, 11, 16))
        as_of = fetch.cme_as_of(dt.date(2026, 11, 16), parsed)
        self.assertEqual(as_of, "2026-11-16T08:06:00+09:00")
        self.assertEqual(fetch.reference_status(as_of, dt.date(2026, 11, 16), "08:00"), "reference_after_report")

    def test_expired_contract_not_treated_as_current(self):
        text = "CME￥ 26年09月限 52,000 +100 51,900 52,100 52,010 07:45"
        self.assertIsNone(fetch.parse_cme(text, "yen", dt.date(2026, 11, 16)))

    def test_fallback_contract_is_explicitly_not_front(self):
        text = "CME￥ 27年03月限 52,000 +100 51,900 52,100 52,010 07:45"
        result = fetch.parse_cme(text, "yen", dt.date(2026, 11, 16))
        self.assertEqual(result["contract"], "27年03月限")
        self.assertFalse(result["contractIsFront"])


if __name__ == "__main__":
    unittest.main()
