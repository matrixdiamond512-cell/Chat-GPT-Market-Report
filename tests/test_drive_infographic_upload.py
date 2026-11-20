"""Regression tests for the real Drive PNG verifier (no API calls)."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_drive_infographic_upload import (
    expected_identity, choose_slot, require_unique, validate_png_bytes, PNG_SIGNATURE,
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
