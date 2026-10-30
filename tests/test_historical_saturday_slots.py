import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("validate_market_reports",ROOT/"scripts"/"validate_market_reports.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class HistoricalSaturdaySlots(unittest.TestCase):
    def test_historical_saturday_0800_is_valid_stored_slot(self):
        self.assertIn("08:00",module.expected_slots("2026-09-19"))
    def test_saturday_0800_is_not_current_publication(self):
        self.assertNotIn("08:00",module.publication_slots("2026-10-17"))
    def test_sunday_is_not_published(self):
        self.assertEqual(module.publication_slots("2026-10-18"),set())
    def test_weekday_slots_unchanged(self):
        self.assertEqual(module.publication_slots("2026-10-13"),{"08:00","12:00","16:00","21:00"})

if __name__=="__main__": unittest.main()
