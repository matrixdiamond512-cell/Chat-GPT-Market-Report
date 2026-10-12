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

    def test_verified_g2_document_produces_bound_envelope(self):
        sections = []
        for heading in REGISTRY["required"]:
            if heading == "主要市場データ":
                lines = [table_line(market_row(Market(**item)))
                         for item in self.snapshot["markets"]]
            else:
                lines = ["合成テスト用の検証行"]
            sections.extend([heading, *lines])
        text = self.title + "\n" + "\n".join(sections) + "\n"
        envelope = capture(self.context, self.snapshot, title=self.title, full_text=text)
        self.assertEqual(envelope["evidence_stage"], "G2_DRAFT_NOT_SAVED")
        self.assertEqual(envelope["validated_gates"], ["G0", "G1", "G2"])
        self.assertEqual(envelope["bodyHash"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(envelope["fullText"], text)

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
