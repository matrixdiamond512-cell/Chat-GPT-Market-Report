"""G2 issuance evidence tests: do not infer success from a synthetic layout fixture."""
import hashlib
import unittest
from morning_fixture import fixture
from scripts.capture_morning_creation_evidence import capture
from reporting.report import market_row, table_line, REGISTRY
from reporting.snapshot import Market

class MorningCaptureTests(unittest.TestCase):
    def setUp(self):
        self.report, _ = fixture()
        self.context = self.report["context"]
        self.snapshot = self.report["snapshot"]
        self.title = self.report["title"]

    def test_bad_slot_fails(self):
        self.context["report_time"] = "12:00"
        with self.assertRaises(ValueError):
            capture(self.context, self.snapshot, title=self.title, full_text=self.report["fullText"])

    def test_body_mismatch_fails(self):
        with self.assertRaises(ValueError):
            capture(self.context, self.snapshot, title=self.title, full_text="Changed original")

    def test_snapshot_tampering_fails(self):
        self.snapshot["snapshot_id"] = "forged"
        with self.assertRaises(ValueError):
            capture(self.context, self.snapshot, title=self.title, full_text=self.report["fullText"])

    def test_real_g2_gate_cannot_be_skipped(self):
        # Layout fixture is source-bound but not a G2 market-table production report.
        with self.assertRaises(ValueError):
            capture(self.context, self.snapshot, title=self.title, full_text=self.report["fullText"])

if __name__ == "__main__":
    unittest.main()
