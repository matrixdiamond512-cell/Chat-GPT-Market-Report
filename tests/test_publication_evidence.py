import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.persist_report_slot_evidence import persist_slot_evidence
from scripts.reporting.publication_evidence import is_canonical_document, validate_receipt, verify_slot_evidence
from scripts.verify_publication_consistency import requires_strict_receipt


class PublicationEvidenceTests(unittest.TestCase):
    def test_archived_report_promotion_uses_unique_canonical_doc_identity(self):
        canonical = [{"id": "original-doc"}]
        self.assertTrue(is_canonical_document(canonical, "original-doc"))
        self.assertFalse(is_canonical_document(canonical, "duplicate-doc"))
        self.assertFalse(is_canonical_document(canonical + [{"id": "original-doc"}], "original-doc"))
        self.assertFalse(is_canonical_document(canonical, None))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.market_path = self.root / "market.json"
        self.payload = {
            "generatedAt": "2026-10-16T07:50:00+09:00", "reportDate": "2026-10-16",
            "reportSlot": "08:00", "overallStatus": "verified",
            "markets": {"USDJPY": {"id": "USDJPY", "marketType": "FX", "unit": "JPY",
                "value": 157.8, "change": 0.0, "changePercent": 0.0,
                "comparisonBasis": "previous_close", "asOf": "2026-10-16T07:49:00+09:00",
                "sourceId": "source-usdjpy", "sourceUrl": "https://example.test/usdjpy",
                "verificationStatus": "verified", "freshnessStatus": "fresh", "displayValue": "157.8"}},
        }
        self.market_path.write_text(json.dumps(self.payload), encoding="utf-8")
        self.evidence_path, _ = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.root / "data/report-evidence")
        self.body = "マーケットレポート本文" * 500
        self.body_hash = hashlib.sha256(self.body.encode()).hexdigest()
        self.report = {"date": "2026-10-16", "time": "08:00", "title": "マーケットレポート｜2026/10/16（金）08:00",
                       "revision": 1, "fullText": self.body, "bodyHash": self.body_hash,
                       "sourceDocument": {"id": "doc-id", "url": "https://docs.google.com/document/d/doc-id/edit"}}
        self.drive_file = {"id": "doc-id", "createdTime": "2026-10-16T08:02:00+09:00",
                           "modifiedTime": "2026-10-16T08:03:00+09:00"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_doc_readback_is_bound_to_frozen_context_and_snapshot(self):
        receipt = verify_slot_evidence(self.report, self.evidence_path, self.drive_file, "drive-revision-1")
        self.report["report_status"] = "DOC_READBACK_PASS"
        self.report["publicationEvidence"] = {key: receipt[key] for key in (
            "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId")}
        validate_receipt(receipt, self.report)

    def test_missing_or_tampered_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_SNAPSHOT_MISSING"):
            verify_slot_evidence(self.report, self.root / "missing.json", self.drive_file, "rev")
        data = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        data["snapshot"]["markets"][0]["priceValue"] = 1
        self.evidence_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "BLOCKED_SNAPSHOT_HASH_MISMATCH"):
            verify_slot_evidence(self.report, self.evidence_path, self.drive_file, "rev")

    def test_post_slot_document_edit_fails_closed(self):
        late = dict(self.drive_file, modifiedTime="2026-10-17T08:03:00+09:00")
        with self.assertRaisesRegex(ValueError, "outside the slot readback window"):
            verify_slot_evidence(self.report, self.evidence_path, late, "drive-revision-1")

    def test_receipt_body_or_evidence_mismatch_is_rejected(self):
        receipt = verify_slot_evidence(self.report, self.evidence_path, self.drive_file, "drive-revision-1")
        self.report["publicationEvidence"] = {key: receipt[key] for key in (
            "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId")}
        receipt["bodyHash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "body hash mismatch"):
            validate_receipt(receipt, self.report)

    def test_strict_receipt_epoch_preserves_legacy_history_and_requires_new_proof(self):
        legacy = {"date": "2026-10-15", "time": "21:00", "report_status": "DOC_READBACK_PASS"}
        current = {"date": "2026-10-16", "time": "08:00", "report_status": "DOC_READBACK_PASS"}
        self.assertFalse(requires_strict_receipt(legacy))
        self.assertTrue(requires_strict_receipt(current))


if __name__ == "__main__":
    unittest.main()
