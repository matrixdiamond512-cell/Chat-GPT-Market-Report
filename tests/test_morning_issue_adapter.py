"""Issuance adapter does not fetch, infer or publish data."""
import unittest
from morning_fixture import fixture
from scripts.prepare_morning_report_issue import prepare

class MorningIssueAdapterTests(unittest.TestCase):
    def setUp(self):
        self.report, _ = fixture()
        self.context = self.report["context"]
        self.snapshot = self.report["snapshot"]

    def test_requires_exactly_one_source(self):
        with self.assertRaisesRegex(ValueError, "EXACTLY_ONE_EVIDENCE"):
            prepare(self.context, title=self.report["title"], body=self.report["fullText"])
        with self.assertRaisesRegex(ValueError, "EXACTLY_ONE_EVIDENCE"):
            prepare(self.context, acquisition={}, snapshot=self.snapshot,
                    title=self.report["title"], body=self.report["fullText"])

    def test_rejects_fake_market_snapshot(self):
        forged = dict(self.snapshot)
        forged["snapshot_id"] = "forged"
        with self.assertRaises(ValueError):
            prepare(self.context, snapshot=forged, title=self.report["title"],
                    body=self.report["fullText"])

    def test_rejects_legacy_layout_fixture_at_G2(self):
        with self.assertRaises(ValueError):
            prepare(self.context, snapshot=self.snapshot, title=self.report["title"],
                    body=self.report["fullText"])

    def test_rejects_bad_acquisition(self):
        with self.assertRaisesRegex(ValueError, "ACQUISITION_REQUIRED_MARKETS_MISSING"):
            prepare(self.context, acquisition={"markets":{}}, title=self.report["title"],
                    body=self.report["fullText"])

if __name__ == "__main__":
    unittest.main()
