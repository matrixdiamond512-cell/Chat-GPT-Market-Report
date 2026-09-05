import unittest

from fetch_us_premarket import breadth, coverage_status
from stock_freshness import current_block, envelope, is_current, last_good_from
from validate_stock_data_freshness import check_component


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

    def test_unavailable_payload_is_not_retained_as_last_good(self):
        unavailable = {"status": "unavailable", "freshness": "unavailable", "dataDate": None}
        self.assertIsNone(last_good_from(unavailable))

    def test_current_requires_explicit_freshness_and_exact_date(self):
        current = current_block(
            status="ok",
            data_date="2026-08-18",
            as_of="2026-08-18T08:50:00+09:00",
            updated_at="2026-08-18T08:50:00+09:00",
        )
        self.assertTrue(is_current(current, "2026-08-18"))
        current["freshness"] = None
        self.assertFalse(is_current(current, "2026-08-18"))

    def test_validator_uses_market_reference_date_not_runner_date(self):
        current = current_block(
            status="ok",
            data_date="2026-08-18",
            as_of="2026-08-18T08:50:00+09:00",
            updated_at="2026-08-18T08:50:00+09:00",
        )
        errors = []
        check_component(
            "tokyo-preopen",
            current,
            "2026-08-18",
            errors,
            reference_date="2026-08-18",
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

