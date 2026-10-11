from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.test_market_data_sheets_roundtrip import run_roundtrip
from scripts.write_market_data_to_sheets import SheetsSyncError


class TestSheetGuardTests(unittest.TestCase):
    def test_missing_test_credentials_fail_before_any_api_request(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SheetsSyncError, "TEST_SHEET_CONFIG_MISSING"):
                run_roundtrip()

    def test_production_sheet_id_is_rejected_as_test_target(self):
        env = {
            "MARKET_DATA_TEST_SPREADSHEET_ID": "same-id",
            "MARKET_DATA_SPREADSHEET_ID": "same-id",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SheetsSyncError, "TEST_SHEET_MUST_BE_SEPARATE_FROM_PRODUCTION"):
                run_roundtrip()

    def test_missing_production_sheet_id_fails_closed(self):
        env = {
            "MARKET_DATA_TEST_SPREADSHEET_ID": "test-id",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SheetsSyncError, "TEST_SHEET_CONFIG_MISSING"):
                run_roundtrip()


if __name__ == "__main__":
    unittest.main()

