from __future__ import annotations

import json
import unittest

from scripts.summarize_market_data_diagnostics import summarize


class DiagnosticSummaryTests(unittest.TestCase):
    def test_failure_and_fallback_are_identifiable_without_quote_values(self):
        payload = {
            "overallStatus": "blocked",
            "generatedAt": "2026-10-11T10:59:00+09:00",
            "reportSlot": "08:00",
            "markets": {
                "dow": {
                    "value": 12345.67,
                    "verificationStatus": "fallback",
                    "freshnessStatus": "last_verified",
                    "asOf": "2026-10-09T16:00:00-04:00",
                    "sourceId": "cached_source",
                    "fallbackUsed": True,
                    "error": "must not be printed",
                },
                "nasdaq": {
                    "value": None,
                    "verificationStatus": "unavailable",
                    "freshnessStatus": "missing",
                    "fallbackUsed": False,
                    "error": "raw provider response must not be printed",
                },
            },
            "errors": [
                {"symbol": "dow", "sourceId": "provider_a", "code": "TIMEOUT", "message": "secret-like raw detail", "attempt": 2},
                {"symbol": "dow", "sourceId": "provider_b", "code": "SOURCE_DIVERGENCE", "message": "12345.67 vs 12344.00"},
                {"symbol": "nasdaq", "sourceId": "provider_c", "code": "DNS_ERROR", "message": "provider detail"},
            ],
        }
        config = {
            "symbols": {
                "dow": {"required": True, "sources": [{"id": "provider_a"}]},
                "nasdaq": {"required": True, "sources": [{"id": "provider_c"}]},
                "optional": {"required": False, "sources": []},
            }
        }

        result = summarize(payload, config)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["connectedCount"], 2)
        self.assertEqual(result["requiredCount"], 2)
        self.assertEqual(result["items"][0]["diagnosis"], "FALLBACK_AFTER_SOURCE_DIVERGENCE")
        self.assertEqual(result["items"][0]["sourceErrors"][0], {"sourceId": "provider_a", "code": "TIMEOUT", "attempt": 2})
        self.assertEqual(result["items"][1]["diagnosis"], "NO_CURRENT_SOURCE_PASSED_VALIDATION")
        for forbidden in ("12345.67", "12344.00", "secret-like raw detail", "must not be printed", "raw provider response"):
            self.assertNotIn(forbidden, encoded)

    def test_divergence_is_identified_as_fallback_cause(self):
        result = summarize(
            {"markets": {"gold": {"verificationStatus": "fallback", "value": 2000, "fallbackUsed": True}},
             "errors": [{"symbol": "gold", "sourceId": "a|b", "code": "SOURCE_DIVERGENCE"}]},
            {"symbols": {"gold": {"sources": [{"id": "a"}, {"id": "b"}]}}},
        )
        self.assertEqual(result["items"][0]["diagnosis"], "FALLBACK_AFTER_SOURCE_DIVERGENCE")
        self.assertEqual(result["items"][0]["acquisitionResult"], "FAILED")
        self.assertEqual(result["items"][0]["validationResult"], "NOT_CURRENTLY_VERIFIED")
        self.assertEqual(result["items"][0]["persistenceResult"], "NOT_ATTEMPTED_BY_COLLECTOR")
        self.assertNotIn("2000", json.dumps(result))


if __name__ == "__main__":
    unittest.main()

