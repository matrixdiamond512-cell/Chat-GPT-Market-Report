"""Source cutoff tests: no HTTP, no GitHub writes and no data mutations."""
import unittest
from scripts.run_market_data_acquisition import within_report_cutoff

def payload(attempt_at="2026-10-15T15:58:00+09:00",
            observed_at="2026-10-15T15:56:00+09:00",status="verified"):
    return {
        "reportSlot":"16:00",
        "generatedAt":attempt_at,
        "markets":{"gold":{
            "verificationStatus":status,"asOf":observed_at,
            "value":4050
        }}
    }


class CutoffRegressions(unittest.TestCase):
    def test_on_time_acquisition_is_eligible(self):
        self.assertTrue(within_report_cutoff(payload()))

    def test_generated_after_slot_is_blocked(self):
        self.assertFalse(within_report_cutoff(
            payload(attempt_at="2026-10-15T21:13:28+09:00")))

    def test_observation_after_slot_is_blocked(self):
        self.assertFalse(within_report_cutoff(
            payload(observed_at="2026-10-15T16:01:00+09:00")))

    def test_overnight_old_reference_is_allowed_before_cutoff(self):
        self.assertTrue(within_report_cutoff(
            payload(observed_at="2026-10-14T15:00:00+09:00")))

    def test_verified_market_must_have_observation_time(self):
        self.assertFalse(within_report_cutoff(payload(observed_at=None)))

    def test_invalid_slot_is_blocked(self):
        value=payload()
        value["reportSlot"]="18:00"
        self.assertFalse(within_report_cutoff(value))

if __name__=="__main__":
    unittest.main()
