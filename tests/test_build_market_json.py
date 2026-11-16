"""Independent live acquisition must not mutate frozen report projections."""
from copy import deepcopy
import unittest

from scripts.build_market_json import attach_market_data
from scripts.verify_publication_consistency import verify_dashboard_copy


class MarketDataProjectionTests(unittest.TestCase):
    def setUp(self):
        self.canonical = {"date": "2026-10-13", "time": "16:00", "title": "Saved report",
                          "fullText": "Frozen body", "revision": 1, "bodyHash": "saved-hash"}
        self.dashboard = {"latestReport": deepcopy(self.canonical),
                          "reports": [deepcopy(self.canonical)],
                          "currentReportKey": "2026-10-13_16-00", "other": {"keep": True}}
        self.live = {"generatedAt": "2026-11-11T03:50:31+09:00", "overallStatus": "verified",
                     "markets": {"gold": {"value": 4037.7}}, "missingRequired": []}

    def test_live_update_preserves_exact_canonical_latest_and_index(self):
        before = deepcopy(self.dashboard)
        result = attach_market_data(self.dashboard, self.live)
        verify_dashboard_copy(self.canonical, result)
        self.assertEqual(result["latestReport"], self.canonical)
        self.assertEqual(result["reports"], before["reports"])
        self.assertEqual(result["marketData"], self.live)
        self.assertEqual(result["marketDataUpdatedAt"], self.live["generatedAt"])
        self.assertEqual(result["currentReportKey"], before["currentReportKey"])
        self.assertEqual(self.dashboard, before)

    def test_report_frozen_market_data_is_preserved_in_both_projections(self):
        frozen = {"generatedAt": "2026-10-13T15:55:00+09:00", "markets": {"gold": {"value": 1}}}
        self.canonical["marketData"] = frozen
        self.dashboard["latestReport"] = deepcopy(self.canonical)
        self.dashboard["reports"] = [deepcopy(self.canonical)]
        result = attach_market_data(self.dashboard, self.live)
        verify_dashboard_copy(self.canonical, result)
        self.assertEqual(result["reports"], [self.canonical])
        self.assertEqual(result["latestReport"]["marketData"], frozen)
        self.assertEqual(result["marketData"], self.live)

    def test_repeated_degraded_updates_keep_report_and_deduplicate_source(self):
        self.live["overallStatus"] = "degraded"
        self.live["missingRequired"] = ["gold"]
        first = attach_market_data(self.dashboard, self.live)
        second = attach_market_data(first, self.live)
        verify_dashboard_copy(self.canonical, second)
        self.assertEqual(first, second)
        self.assertEqual(len(second["sources"]), 1)
        self.assertEqual(second["sources"][0]["id"], "INDEPENDENT_MARKET_DATA")
        self.assertEqual(len(second["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
