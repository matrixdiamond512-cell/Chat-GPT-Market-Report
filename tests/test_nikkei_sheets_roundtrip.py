from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import fetch_market_data as market_data
from scripts import test_nikkei_sheets_roundtrip as target


def fixture_config():
    symbols = {}
    for symbol_id, source_id in target.TARGETS.items():
        symbols[symbol_id] = {
            "displayName": symbol_id,
            "sources": [{"id": source_id, "name": source_id, "kind": "fixture"}],
        }
    return {"symbols": symbols}


class NikkeiAcquisitionTests(unittest.TestCase):
    def run_acquisition(self, dates=None, bad_source=None, missing_value=None):
        dates = dates or {}
        values = {}
        for symbol_id, source_id in target.TARGETS.items():
            values[symbol_id] = {
                "value": None if symbol_id == missing_value else 100.25,
                "asOf": dates.get(symbol_id, "2026-10-09T15:30:00+09:00"),
                "sourceId": "wrong_source" if symbol_id == bad_source else source_id,
            }

        def load_json(path, default):
            if path.name == "market_data_sources.json":
                return fixture_config()
            return {"defaults": {}, "symbols": {}}

        fake_fetchers = {
            "fixture": lambda source: values[next(k for k, v in target.TARGETS.items() if v == source["id"])]
        }
        fixed_now = market_data.dt.datetime(2026, 10, 12, 10, tzinfo=market_data.JST)
        with patch.object(market_data, "load_json", side_effect=load_json), patch.dict(
            market_data.FETCHERS, fake_fetchers
        ), patch.object(market_data, "validate_candidate", return_value=(True, "OK", "")), patch.object(
            market_data, "now_jst", return_value=fixed_now
        ):
            return target.acquire_official_nikkei()

    def test_accepts_four_official_routes_on_same_market_date(self):
        acquired, metadata = self.run_acquisition()
        self.assertEqual(set(acquired), set(target.TARGETS))
        self.assertEqual(metadata["marketDate"], "2026-10-09")
        self.assertEqual(metadata["sourceIds"], target.TARGETS)

    def test_rejects_mixed_market_dates(self):
        with self.assertRaisesRegex(target.SheetsSyncError, "NIKKEI_MARKET_DATE_MISMATCH"):
            self.run_acquisition(dates={"nikkei_vi": "2026-10-08T15:30:00+09:00"})

    def test_rejects_wrong_source_identity(self):
        with self.assertRaisesRegex(target.SheetsSyncError, "NIKKEI_VALIDATION_DATE_VALUE_OR_SOURCE"):
            self.run_acquisition(bad_source="nikkei225_cash")

    def test_rejects_missing_numeric_value(self):
        with self.assertRaisesRegex(target.SheetsSyncError, "NIKKEI_VALIDATION_DATE_VALUE_OR_SOURCE"):
            self.run_acquisition(missing_value="nikkei225_dev200")


if __name__ == "__main__":
    unittest.main()
