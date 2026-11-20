"""Regression tests for the real Drive PNG verifier (no API calls)."""
import struct
from datetime import datetime, timezone
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_drive_infographic_upload import (
    expected_identity, choose_slot, require_unique, validate_png_bytes, PNG_SIGNATURE, scheduled_date,
)


class TestDriveInfographicUpload(unittest.TestCase):
    def test_date_and_slot_identity(self):
        self.assertEqual(
            expected_identity("2026-11-20", "21:00"),
            ("マーケットレポート図解2026年11月", "マーケットレポート_2026-11-20_21-00.png"),
        )
        self.assertEqual(expected_identity("2027-02-03", "08:00")[0], "マーケットレポート図解2027年2月")

    def test_schedule_resolution(self):
        self.assertEqual(choose_slot("", "45 12 * * 1-5"), "21:00")
        self.assertEqual(choose_slot("12:00", ""), "12:00")
        with self.assertRaises(ValueError):
            choose_slot("", "not a valid cron")
        with self.assertRaises(ValueError):
            choose_slot("23:00", "")

    def test_delayed_1645_schedule_checks_previous_jst_day(self):
        # Actual Actions failure: scheduled Fri 16:45 JST, executed Sat 01:23 JST.
        late_run = datetime(2026, 11, 20, 16, 23, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("45 7 * * 1-5", late_run), "2026-11-20")

    def test_delayed_2145_schedule_does_not_shift_to_saturday(self):
        late_run = datetime(2026, 11, 21, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("45 12 * * 1-5", late_run), "2026-11-20")

    def test_0845_utc_sunday_is_jst_monday(self):
        next_run = datetime(2026, 11, 23, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("45 23 * * 0-4", next_run), "2026-11-23")

    def test_very_late_or_naive_schedule_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "SCHEDULE_DELAY_AMBIGUOUS"):
            scheduled_date("45 7 * * 1-5", datetime(2026, 11, 21, 16, 23, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            scheduled_date("45 7 * * 1-5", datetime(2026, 11, 20, 16, 23))
        with self.assertRaisesRegex(ValueError, "Unknown scheduled cron"):
            scheduled_date("invalid", datetime(2026, 11, 20, 16, 23, tzinfo=timezone.utc))

    def test_late_2105_watchdog_never_checks_saturday(self):
        late = datetime(2026, 11, 21, 1, 20, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("5,15,30 12 * * 1-5", late), "2026-11-20")

    def test_late_0805_watchdog_uses_monday_jst(self):
        late = datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("5,15,30 23 * * 0-4", late), "2026-11-23")

    def test_early_watchdog_late_run_across_utc_boundary(self):
        late = datetime(2026, 11, 20, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(scheduled_date("5,15,30,50 7 * * 1-5", late), "2026-11-20")

    def test_missing_or_duplicate_file_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "found 0"):
            require_unique([], "DRIVE_INFOGRAPHIC_MISSING_OR_DUPLICATED")
        with self.assertRaisesRegex(ValueError, "found 2"):
            require_unique([{"id": "a"}, {"id": "b"}], "duplicate")
        self.assertEqual(require_unique([{"id": "a"}], "ok")["id"], "a")

    def test_png_file_readback_contract(self):
        payload = PNG_SIGNATURE + b"\x00" * 8 + struct.pack(">II", 1536, 1024) + b"\x00" * 1024
        verified = validate_png_bytes(payload, str(len(payload)))
        self.assertEqual(verified["width"], 1536)
        self.assertEqual(verified["height"], 1024)
        self.assertEqual(len(verified["sha256"]), 64)
        with self.assertRaisesRegex(ValueError, "size differs"):
            validate_png_bytes(payload, "12")
        with self.assertRaisesRegex(ValueError, "not PNG"):
            validate_png_bytes(b"not a png" * 100, "900")
        with self.assertRaisesRegex(ValueError, "invalid dimensions"):
            validate_png_bytes(PNG_SIGNATURE + b"\x00"*8 + struct.pack(">II", 0, 100) + b"\x00"*600, "624")


if __name__ == "__main__":
    unittest.main()
