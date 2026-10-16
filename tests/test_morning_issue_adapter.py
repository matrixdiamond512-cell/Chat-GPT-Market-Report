"""Issuance adapter does not fetch, infer or publish data."""
import hashlib
import unittest
from morning_fixture import fixture
from scripts.prepare_morning_report_issue import prepare
from reporting.report import REGISTRY, market_row, table_line
from reporting.snapshot import Market

class MorningIssueAdapterTests(unittest.TestCase):
    def setUp(self):
        self.report, _ = fixture()
        self.context = self.report["context"]
        self.snapshot = self.report["snapshot"]

    def test_verified_g2_snapshot_issuance_success(self):
        sections = []
        for heading in REGISTRY["required"]:
            lines = ([table_line(market_row(Market(**m))) for m in self.snapshot["markets"]]
                     if heading == "主要市場データ" else ["合成検証用の文章"])
            sections.extend([heading, *lines])
        body = self.report["title"] + "\n" + "\n".join(sections) + "\n"
        created = prepare(self.context, snapshot=self.snapshot,
                          title=self.report["title"], body=body)
        self.assertEqual(created["validated_gates"], ["G0", "G1", "G2"])
        self.assertEqual(created["bodyHash"], hashlib.sha256(body.encode("utf-8")).hexdigest())
        self.assertEqual(created["snapshot_id"], self.snapshot["snapshot_id"])
        self.assertEqual(created["evidence_stage"], "G2_DRAFT_NOT_SAVED")

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
