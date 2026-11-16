from __future__ import annotations

import datetime as dt
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_japan_close_reference as apply


class JapanReferenceValidationTests(unittest.TestCase):
    def test_exact_date_numeric_value_and_source_are_required(self):
        expected = dt.date(2026, 11, 13)
        item = {"date": "2026-11-13", "value": "52,000円", "sourceName": "JPX", "sourceUrl": "https://example.test"}
        self.assertTrue(apply.reference_item_is_exact(item, "日経225先物（大阪取引所）", expected))

    def test_stale_date_is_rejected(self):
        expected = dt.date(2026, 11, 13)
        item = {"date": "2026-11-12", "value": "52,000円", "sourceName": "JPX", "sourceUrl": "https://example.test"}
        self.assertFalse(apply.reference_item_is_exact(item, "日経225先物（大阪取引所）", expected))

    def test_untyped_or_unsourced_reference_is_rejected(self):
        expected = dt.date(2026, 11, 13)
        for item in (
            {"date": "2026-11-13", "value": "取得不能", "sourceName": "JPX", "sourceUrl": "https://example.test"},
            {"date": "2026-11-13", "value": "52,000円", "sourceName": "", "sourceUrl": ""},
        ):
            self.assertFalse(apply.reference_item_is_exact(item, "日経225先物（大阪取引所）", expected))

    def test_monday_after_japan_holiday_uses_preceding_friday(self):
        fake = type("FakeJapanHoliday", (), {"is_holiday": staticmethod(lambda day: day == dt.date(2026, 11, 23))})
        with patch.dict(sys.modules, {"jpholiday": fake}):
            self.assertEqual(apply.expected_prior(dt.date(2026, 11, 24)), dt.date(2026, 11, 20))

    def test_rates_reference_requires_expected_session_date(self):
        row = {"value": "取得不能（missing）"}
        # The helper must fail closed if the existing rates JSON is missing the exact date.
        with patch.object(apply, "load", return_value={"rates": [{"name": "日本10年国債利回り", "value": 2.8, "asOf": "2026-11-12", "status": "confirmed"}]}):
            result = apply.apply_rates_reference({"日本10年国債利回り": row}, dt.date(2026, 11, 13))
        self.assertEqual(result["applied"], [])
        self.assertIn("date mismatch", result["reason"])

    def test_rates_reference_requires_attributed_source(self):
        row = {"value": "取得不能（missing）"}
        payload = {"rates": [{"name": "日本10年国債利回り", "value": 2.8, "asOf": "2026-11-13", "status": "confirmed"}]}
        with patch.object(apply, "load", return_value=payload):
            result = apply.apply_rates_reference({"日本10年国債利回り": row}, dt.date(2026, 11, 13))
        self.assertEqual(result["applied"], [])
        self.assertIn("source attribution missing", result["reason"])
        self.assertEqual(row["value"], "取得不能（missing）")


if __name__ == "__main__":
    unittest.main()
