import unittest

from fetch_us_premarket import breadth, coverage_status
from stock_freshness import current_block, envelope, last_good_from


class FreshnessModelTests(unittest.TestCase):
    def test_unavailable_current_never_inherits_old_rows(self):
        previous = {
            "status": "verified",
            "freshness": "fresh",
            "dataDate": "2026-08-14",
            "updatedAt": "2026-08-15T07:00:00+09:00",
            "gainers": [{"symbol": "OLD"}],
        }
        current = current_block(
            status="unavailable",
            data_date=None,
            as_of=None,
            updated_at="2026-08-18T08:50:00+09:00",
            error="source unavailable",
            gainers=[],
        )
        payload = envelope(current, previous)
        self.assertEqual(payload["current"]["status"], "unavailable")
        self.assertEqual(payload["current"]["gainers"], [])
        self.assertEqual(payload["lastGood"]["dataDate"], "2026-08-14")
        self.assertEqual(payload["lastGood"]["freshness"], "stale")

    def test_coverage_thresholds(self):
        self.assertEqual(coverage_status(50, 45), ("ok", 90.0))
        self.assertEqual(coverage_status(50, 35), ("partial", 70.0))
        self.assertEqual(coverage_status(50, 34)[0], "unavailable")

    def test_premarket_flat_threshold_is_explicit(self):
        result = breadth([
            {"changePct": 0.05},
            {"changePct": -0.05},
            {"changePct": 0.051},
            {"changePct": -0.051},
        ])
        self.assertEqual(result["flatThresholdPct"], 0.05)
        self.assertEqual((result["up"], result["down"], result["flat"]), (1, 1, 2))

    def test_legacy_flat_payload_is_retained_only_as_stale_last_good(self):
        legacy = {"status": "verified", "dataDate": "2026-08-14", "gainers": [{"symbol": "OLD"}]}
        retained = last_good_from(legacy)
        self.assertEqual(retained["freshness"], "stale")
        self.assertEqual(retained["dataDate"], "2026-08-14")


if __name__ == "__main__":
    unittest.main()

