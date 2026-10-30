import datetime as dt
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from resolve_tokyo_close_target import is_tokyo_session,resolve

JST=dt.timezone(dt.timedelta(hours=9))
class TokyoCloseCalendarTests(unittest.TestCase):
    def test_sports_day_holiday_does_not_require_nonexistent_close(self):
        date,skip=resolve(dt.datetime(2026,10,12,18,10,tzinfo=JST))
        self.assertEqual(date,"2026-10-12")
        self.assertTrue(skip)
        self.assertFalse(is_tokyo_session(dt.date(2026,10,12)))
    def test_next_morning_uses_previous_trading_day(self):
        date,skip=resolve(dt.datetime(2026,10,13,8,tzinfo=JST))
        self.assertEqual((date,skip),("2026-10-09",False))
    def test_normal_session(self):
        date,skip=resolve(dt.datetime(2026,10,13,18,tzinfo=JST))
        self.assertEqual((date,skip),("2026-10-13",False))
    def test_saturday_retries_friday(self):
        self.assertEqual(resolve(dt.datetime(2026,10,10,9,tzinfo=JST)),("2026-10-09",False))
    def test_manual_holiday_is_not_silently_mislabeled(self):
        with self.assertRaises(ValueError):
            resolve(dt.datetime(2026,10,13,18,tzinfo=JST),"2026-10-12")
    def test_year_end_closure(self):
        self.assertFalse(is_tokyo_session(dt.date(2026,12,31)))
        self.assertFalse(is_tokyo_session(dt.date(2027,1,2)))

if __name__=="__main__":
    unittest.main()
