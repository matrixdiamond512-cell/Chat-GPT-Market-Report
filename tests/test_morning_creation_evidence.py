"""G2 issuance evidence tests: do not infer success from a synthetic layout fixture."""
import hashlib
import unittest
from morning_fixture import fixture
from scripts.capture_morning_creation_evidence import capture, snapshot_from_same_run_acquisition
from reporting.report import market_row, table_line, REGISTRY
from reporting.snapshot import Market, MarketDataSnapshot
from reporting.context import ReportContext
from scripts.preflight_morning_infographic import check as preflight_check

class MorningCaptureTests(unittest.TestCase):
    def setUp(self):
        self.report, self.view = fixture()
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
        # Handoff is only preflight-ready; original fact offsets and final spec are still needed.
        view = dict(self.view)
        view["body_hash"] = envelope["bodyHash"]
        result = preflight_check(envelope, view)
        self.assertEqual(result["status"], "READY_FOR_CANONICAL_VALIDATION")

    def test_same_run_acquisition_to_snapshot(self):
        markets = {}
        for item in self.snapshot["markets"]:
            source = item["source"][0]
            markets[item["instrument"]] = {
                "id": item["instrument"], "marketType": item["marketType"],
                "venue": item["venue"], "contractMonth": item["contractMonth"],
                "value": item["priceValue"], "unit": item["priceUnit"],
                "change": item["changeValue"], "changePercent": item["changePct"],
                "comparisonBasis": item["comparisonBasis"],
                "asOf": item["asOf"], "sourceId": source["id"], "sourceUrl": source["url"],
                "displayValue": item["displayText"], "verificationStatus": "verified",
                "freshnessStatus": "fresh",
            }
        acquisition = {"generatedAt": self.snapshot["captured_at"],
                       "reportSlot": "08:00", "reportDate": self.context["report_date"],
                       "markets": markets}
        snapshot = MarketDataSnapshot.from_acquisition(ReportContext(**self.context), acquisition)
        self.assertEqual(snapshot.report_id, self.context["report_id"])
        self.assertEqual(len(snapshot.markets), len(self.snapshot["markets"]))
        self.assertTrue(snapshot.snapshot_id.startswith("snapshot-"))
        self.assertEqual(MarketDataSnapshot.restore(snapshot.to_dict()).snapshot_id, snapshot.snapshot_id)

    def test_same_run_acquisition_validation_blocks_missing_and_stale(self):
        rows = {}
        for item in self.snapshot["markets"]:
            source = item["source"][0]
            rows[item["instrument"]] = {
                "id": item["instrument"], "marketType": item["marketType"],
                "value": item["priceValue"], "unit": item["priceUnit"],
                "asOf": item["asOf"], "sourceId": source["id"],
                "sourceUrl": source["url"], "displayValue": item["displayText"],
                "verificationStatus": "verified", "freshnessStatus": "fresh"}
        acquisition = {"generatedAt": self.snapshot["captured_at"], "reportDate": self.context["report_date"],
                       "reportSlot": "08:00", "markets": rows}
        frozen = snapshot_from_same_run_acquisition(self.context, acquisition)
        self.assertEqual(frozen.report_id, self.context["report_id"])
        required_key = next(iter(rows))
        for key, value in [("verificationStatus", "unverified"), ("freshnessStatus", "stale"),
                           ("sourceId", None), ("asOf", None)]:
            with self.subTest(field=key):
                original = rows[required_key][key]
                rows[required_key][key] = value
                with self.assertRaisesRegex(ValueError, "ACQUISITION_"):
                    snapshot_from_same_run_acquisition(self.context, acquisition)
                rows[required_key][key] = original
        missing_row = rows.pop(required_key)
        with self.assertRaisesRegex(ValueError, "ACQUISITION_REQUIRED_MARKETS_MISSING"):
            snapshot_from_same_run_acquisition(self.context, acquisition)
        rows[required_key] = missing_row

    def test_reject_other_slot_acquisition(self):
        with self.assertRaises(ValueError):
            MarketDataSnapshot.from_acquisition(ReportContext(**self.context),
                {"generatedAt": self.snapshot["captured_at"], "reportSlot": "12:00",
                 "markets": {}})

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
