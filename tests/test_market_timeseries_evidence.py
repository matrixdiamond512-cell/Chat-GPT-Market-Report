import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_market_data_acquisition import record_market_timeseries


def local_temporary_directory():
    root = Path(__file__).resolve().parents[1] / ".test-tmp"
    root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


def sample(generated_at="2026-10-15T15:30:00+09:00", as_of="2026-10-15T15:29:00+09:00"):
    return {
        "generatedAt": generated_at,
        "reportSlot": "16:00",
        "overallStatus": "verified",
        "fallbackCount": 0,
        "missingRequired": [],
        "markets": {
            "usdjpy": {
                "value": 157.1,
                "unit": "JPY",
                "asOf": as_of,
                "fetchedAt": generated_at,
                "sourceId": "source-a",
                "sourceUrl": "https://example.test/quote",
                "verificationStatus": "verified",
            }
        },
    }


class MarketTimeseriesEvidenceTests(unittest.TestCase):
    def test_cutoff_valid_sample_is_saved_with_source_timestamps(self):
        with local_temporary_directory() as directory:
            path = Path(directory) / "timeseries.json"
            self.assertTrue(record_market_timeseries(sample(), path))
            archive = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("2026-10-15", archive["reportDate"])
            self.assertEqual("16:00", archive["reportSlot"])
            self.assertEqual("2026-10-15T15:30:00+09:00", archive["snapshots"][0]["generatedAt"])
            self.assertEqual("source-a", archive["snapshots"][0]["markets"]["usdjpy"]["sourceId"])

    def test_late_generated_or_observed_value_is_not_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeseries.json"
            self.assertFalse(record_market_timeseries(
                sample(generated_at="2026-10-15T16:01:00+09:00"), path))
            self.assertFalse(record_market_timeseries(
                sample(as_of="2026-10-15T16:00:01+09:00"), path))
            self.assertFalse(path.exists())

    def test_archives_are_sorted_and_idempotent_for_same_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeseries.json"
            first = sample(generated_at="2026-10-15T15:30:00+09:00")
            second = sample(generated_at="2026-10-15T15:39:00+09:00", as_of="2026-10-15T15:38:00+09:00")
            self.assertTrue(record_market_timeseries(second, path))
            self.assertTrue(record_market_timeseries(first, path))
            self.assertTrue(record_market_timeseries(first, path))
            archive = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                ["2026-10-15T15:30:00+09:00", "2026-10-15T15:39:00+09:00"],
                [item["generatedAt"] for item in archive["snapshots"]],
            )

    def test_conflicting_sample_at_same_timestamp_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeseries.json"
            record_market_timeseries(sample(), path)
            conflicting = sample()
            conflicting["markets"]["usdjpy"]["value"] = 158.0
            with self.assertRaises(ValueError):
                record_market_timeseries(conflicting, path)

    def test_archive_rejects_cross_slot_or_naive_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeseries.json"
            cross_slot = sample()
            cross_slot["reportSlot"] = "12:00"
            self.assertFalse(record_market_timeseries(cross_slot, path))
            self.assertFalse(record_market_timeseries(
                sample(generated_at="2026-10-15T15:30:00"), path))


if __name__ == "__main__":
    unittest.main()
