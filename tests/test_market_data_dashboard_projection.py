import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_market_json
import verify_publication_consistency


class IndependentMarketProjectionTests(unittest.TestCase):
    def test_market_refresh_preserves_canonical_report_and_dashboard_identity(self):
        canonical = {
            "date": "2026-10-15",
            "time": "16:00",
            "title": "canonical report",
            "bodyHash": "body-hash",
            "fullText": "immutable source report",
            "revision": 46,
        }
        old_snapshot = {"generatedAt": "2026-10-15T15:00:00+09:00", "overallStatus": "partial"}
        new_snapshot = {
            "generatedAt": "2026-10-15T15:59:00+09:00",
            "overallStatus": "verified",
            "markets": {"gold": {"value": 100, "verificationStatus": "verified"}},
        }
        dashboard = {
            "currentReportKey": "2026-10-15_16-00",
            "latestReport": {**canonical, "marketData": old_snapshot},
            "reports": [{**canonical, "marketData": old_snapshot}],
            "marketData": old_snapshot,
            "sources": [],
            "errors": [],
        }
        before = copy.deepcopy(dashboard)

        projection = build_market_json.attach_market_data(dashboard, new_snapshot)

        self.assertEqual(dashboard, before)
        self.assertEqual(projection["latestReport"], canonical)
        self.assertEqual(projection["reports"][0], canonical)
        self.assertEqual(projection["marketData"], new_snapshot)
        self.assertEqual(projection["marketDataUpdatedAt"], new_snapshot["generatedAt"])
        self.assertEqual(build_market_json.attach_market_data(projection, new_snapshot), projection)
        verify_publication_consistency.verify_dashboard_copy(canonical, projection)


if __name__ == "__main__":
    unittest.main()
