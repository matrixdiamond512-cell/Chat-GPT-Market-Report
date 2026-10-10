import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_market_data_window import completed_times, snapshot_is_current


class SnapshotCurrentTests(unittest.TestCase):
    def test_accepts_usable_snapshot_for_requested_slot_and_day(self):
        payload = {
            "generatedAt": "2026-08-10T19:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "verified",
        }
        now = dt.datetime(2026, 8, 10, 19, 50, tzinfo=dt.timezone(dt.timedelta(hours=9)))
        self.assertTrue(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10), now=now))

    def test_rejects_stale_or_wrong_slot_snapshot(self):
        payload = {
            "generatedAt": "2026-08-08T08:18:37+09:00",
            "reportSlot": "08:00",
            "overallStatus": "verified",
        }
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10)))

    def test_rejects_snapshot_older_than_freshness_limit(self):
        payload = {"generatedAt": "2026-08-10T19:30:00+09:00", "reportSlot": "16:00", "overallStatus": "verified"}
        now = dt.datetime(2026, 8, 10, 19, 49, tzinfo=dt.timezone(dt.timedelta(hours=9)))
        self.assertFalse(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10), now=now))

    def test_accepts_fresh_snapshot_with_explicit_clock(self):
        payload = {"generatedAt": "2026-08-10T19:40:00+09:00", "reportSlot": "16:00", "overallStatus": "verified"}
        now = dt.datetime(2026, 8, 10, 19, 49, tzinfo=dt.timezone(dt.timedelta(hours=9)))
        self.assertTrue(snapshot_is_current(payload, "16:00", dt.date(2026, 8, 10), now=now))

    def test_rejects_blocked_snapshot(self):
        payload = {
            "generatedAt": "2026-08-10T19:49:30+09:00",
            "reportSlot": "16:00",
            "overallStatus": "blocked",
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
