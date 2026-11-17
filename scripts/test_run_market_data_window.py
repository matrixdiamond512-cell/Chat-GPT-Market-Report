import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_market_data_window import completed_times, snapshot_is_current, acquisition_window_status


class AcquisitionWindowGuardTests(unittest.TestCase):
    def test_delayed_overnight_job_never_becomes_todays_future_slot(self):
        jst = dt.timezone(dt.timedelta(hours=9))
        actual = dt.datetime(2026, 11, 17, 6, 14, tzinfo=jst)
        self.assertEqual(
            acquisition_window_status(actual, "21:00", ["20:30", "20:35", "20:55"]),
            "BLOCKED_FUTURE_ACQUISITION_WINDOW",
        )

    def test_normal_and_short_early_attempt_allowed(self):
        jst = dt.timezone(dt.timedelta(hours=9))
        self.assertEqual(
            acquisition_window_status(dt.datetime(2026, 11, 17, 20, 28, tzinfo=jst),
                                      "21:00", ["20:30", "20:35"]),
            "OK",
        )
        self.assertEqual(
            acquisition_window_status(dt.datetime(2026, 11, 17, 11, 15, tzinfo=jst),
                                      "12:00", ["11:30", "11:35"]),
            "OK",
        )

    def test_far_after_cutoff_cannot_retag_old_schedule(self):
        jst = dt.timezone(dt.timedelta(hours=9))
        self.assertEqual(
            acquisition_window_status(dt.datetime(2026, 11, 17, 17, 40, tzinfo=jst),
                                      "12:00", ["11:30", "11:55"]),
            "BLOCKED_EXPIRED_ACQUISITION_WINDOW",
        )

class SnapshotCurrentTests(unittest.TestCase):
    def test_accepts_usable_snapshot_for_requested_slot_and_day(self):
        payload = {
            "generatedAt": "2026-08-10T15:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "verified",
        }
        self.assertTrue(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_stale_or_wrong_slot_snapshot(self):
        payload = {
            "generatedAt": "2026-08-08T08:18:37+09:00",
            "reportSlot": "08:00",
            "overallStatus": "verified",
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_blocked_snapshot(self):
        payload = {
            "generatedAt": "2026-08-10T19:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "blocked",
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_late_snapshot_even_if_wrongly_marked_verified(self):
        payload = {
            "generatedAt": "2026-08-10T19:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "verified",
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_price_observed_after_slot(self):
        payload = {
            "generatedAt": "2026-08-10T15:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "verified",
            "markets": {"gold": {"asOf":"2026-08-10T16:03:00+09:00"}},
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_unparseable_asof_without_crashing(self):
        payload = {
            "generatedAt": "2026-08-10T15:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "verified",
            "markets": {"gold": {"asOf":"N/A"}},
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_late_recovery_does_not_claim_an_on_time_attempt(self):
        rows = [
            {"reportSlot": "16:00", "scheduledTime": "15:50", "outcome": "verified"},
            {
                "reportSlot": "16:00",
                "scheduledTime": "15:55",
                "outcome": "verified",
                "recoveryAfterExpiry": True,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(completed_times(path, "16:00"), {"15:50"})


if __name__ == "__main__":
    unittest.main()
