import datetime as dt
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_tokyo_stock_table_from_sheet import expected_tokyo_date

JST = dt.timezone(dt.timedelta(hours=9))

class TokyoStockHolidayDateTests(unittest.TestCase):
    def test_after_holiday_close_uses_previous_real_session(self):
        with patch.dict(os.environ, {"TOKYO_MARKET_DATE": ""}):
            self.assertEqual(expected_tokyo_date(dt.datetime(2026, 10, 12, 18, tzinfo=JST)), "2026-10-09")

    def test_next_morning_uses_friday(self):
        with patch.dict(os.environ, {"TOKYO_MARKET_DATE": ""}):
            self.assertEqual(expected_tokyo_date(dt.datetime(2026, 10, 13, 8, tzinfo=JST)), "2026-10-09")

    def test_after_regular_close_uses_today(self):
        with patch.dict(os.environ, {"TOKYO_MARKET_DATE": ""}):
            self.assertEqual(expected_tokyo_date(dt.datetime(2026, 10, 13, 18, tzinfo=JST)), "2026-10-13")

    def test_explicit_holiday_override_is_rejected(self):
        with patch.dict(os.environ, {"TOKYO_MARKET_DATE": "2026-10-12"}):
            with self.assertRaises(RuntimeError):
                expected_tokyo_date(dt.datetime(2026, 10, 13, 18, tzinfo=JST))

if __name__ == "__main__":
    unittest.main()
