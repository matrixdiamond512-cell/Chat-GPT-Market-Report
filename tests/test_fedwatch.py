import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_rates_bonds_json as builder


class FedWatchTests(unittest.TestCase):
    def sample(self):
        return {"asOf": "2026-08-15T20:00:00Z", "currentTargetRange": "3.50-3.75%",
        "summary": {"nextMeetingDate": "2026-09-16", "dominantAction": "25bp利下げ",
        "dominantTargetRange": "3.25-3.50%", "probabilityPct": 72.4, "oneDayAgoPct": 58.1,
        "oneWeekAgoPct": 61.2, "oneMonthAgoPct": 46.8},
        "meetings": [{"meetingDate": "2026-09-16", "outcomes": [
            {"currentProbabilityPct": 27.6, "oneDayAgoPct": 41.9, "oneWeekAgoPct": 38.8, "oneMonthAgoPct": 53.2},
            {"currentProbabilityPct": 72.4, "oneDayAgoPct": 58.1, "oneWeekAgoPct": 61.2, "oneMonthAgoPct": 46.8},
        ]}]}

    def test_probability_validation(self):
        self.assertEqual(builder.validate_fedwatch(self.sample()), (True, None))
        bad = self.sample()
        bad["meetings"][0]["outcomes"][1]["currentProbabilityPct"] = 71
        self.assertFalse(builder.validate_fedwatch(bad)[0])

    def test_stance_thresholds(self):
        self.assertIn("大きく強まる", builder.stance_shift(10))
        self.assertIn("横ばい", builder.stance_shift(-2.9))
        self.assertIn("大きく弱まる", builder.stance_shift(-10))

    def test_missing_credentials_never_estimates(self):
        old_url, old_key = os.environ.pop("CME_FEDWATCH_API_URL", None), os.environ.pop("CME_FEDWATCH_API_KEY", None)
        try:
            result = builder.fetch_fedwatch({"changeBp": -8})
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["meetings"], [])
        finally:
            if old_url is not None: os.environ["CME_FEDWATCH_API_URL"] = old_url
            if old_key is not None: os.environ["CME_FEDWATCH_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
