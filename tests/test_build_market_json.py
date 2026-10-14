"""Independent market data must not mutate the canonical report projection."""

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_market_json


class AttachMarketDataTests(unittest.TestCase):
    def test_market_data_stays_in_dashboard_envelope(self):
        report = {
            "date": "2026-10-13",
            "time": "16:00",
            "title": "canonical report",
            "bodyHash": "a" * 64,
            "markets": [{"name": "金", "price": "4,167.20ドル"}],
        }
        dashboard = {
            "currentReportKey": "2026-10-13_16-00",
            "latestReport": deepcopy(report),
            "reports": [deepcopy(report)],
        }
        original = deepcopy(dashboard)
        market_data = {
            "reportSlot": "16:00",
            "generatedAt": "2026-10-13T16:10:00+09:00",
            "overallStatus": "verified",
            "markets": {"gold": {"value": 4167.2}},
        }

        result = build_market_json.attach_market_data(dashboard, market_data)

        self.assertEqual(dashboard, original)
        self.assertEqual(result["latestReport"], report)
        self.assertEqual(result["reports"], [report])
        self.assertEqual(result["marketData"], market_data)
        self.assertNotIn("marketData", result["latestReport"])
        self.assertNotIn("marketData", result["reports"][0])
        self.assertEqual(result["marketDataUpdatedAt"], market_data["generatedAt"])


if __name__ == "__main__":
    unittest.main()
