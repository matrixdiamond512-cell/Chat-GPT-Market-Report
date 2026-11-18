import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys

p = Path(__file__).resolve().parents[1] / "scripts" / "verify_scheduled_report_delivery.py"
sys.path.insert(0, str(p.parent))
spec = importlib.util.spec_from_file_location("delivery", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "reports").mkdir()
        (self.root / "data").mkdir()
        self.report = {"date": "2026-10-13", "time": "08:00", "fullText": "Original document text"}
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        self.write("data/latest-report.json", {"latestReport": self.report})
        self.write("data/dashboard.json", {"latestReport": self.report,
                                            "currentReportKey": "2026-10-13_08-00"})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, obj):
        (self.root / path).write_text(json.dumps(obj), encoding="utf-8")

    def test_complete_slot(self):
        self.assertEqual(module.verify(self.root, "2026-10-13", "08:00")["status"], "PASS")

    def test_missing_canonical_detected(self):
        with self.assertRaisesRegex(ValueError, "Missing published canonical"):
            module.verify(self.root, "2026-10-13", "12:00")

    def test_latest_stale_detected(self):
        self.report["date"] = "2026-10-12"
        self.report["time"] = "21:00"
        self.write("data/latest-report.json", {"latestReport": self.report})
        with self.assertRaisesRegex(ValueError, "behind required slot"):
            module.verify(self.root, "2026-10-13", "08:00")

    def test_index_missing_detected(self):
        self.write("reports.json", [])
        with self.assertRaisesRegex(ValueError, "history index"):
            module.verify(self.root, "2026-10-13", "08:00")


    def test_strict_epoch_rejects_unverified_status(self):
        current = dict(self.report, date="2026-11-18", report_status="SOURCE_ARCHIVED")
        self.write("reports/2026-11-18_08-00.json", current)
        with self.assertRaisesRegex(ValueError, "not publication-eligible"):
            module.verify(self.root, "2026-11-18", "08:00")

    def test_strict_epoch_rejects_legacy_status_and_missing_receipt(self):
        current = dict(self.report, date="2026-11-18")
        self.write("reports/2026-11-18_08-00.json", current)
        with self.assertRaisesRegex(ValueError, "verified publication status"):
            module.verify(self.root, "2026-11-18", "08:00")
        current["report_status"] = "DOC_READBACK_PASS"
        self.write("reports/2026-11-18_08-00.json", current)
        with self.assertRaisesRegex(ValueError, "Missing publication receipt"):
            module.verify(self.root, "2026-11-18", "08:00")

    def test_strict_epoch_checks_receipt_before_claiming_delivery(self):
        from unittest.mock import patch
        current = dict(self.report, date="2026-11-18", report_status="DOC_READBACK_PASS")
        self.write("reports/2026-11-18_08-00.json", current)
        self.write("reports.json", [current])
        self.write("data/latest-report.json", {"latestReport": current})
        self.write("data/dashboard.json", {"latestReport": current,
                                           "currentReportKey": "2026-11-18_08-00"})
        (self.root / "publication-receipts").mkdir()
        self.write("publication-receipts/2026-11-18_08-00.json", {"status": "fake"})
        with patch.object(module, "validate_receipt", side_effect=ValueError("invalid")):
            with self.assertRaisesRegex(ValueError, "receipt failed"):
                module.verify(self.root, "2026-11-18", "08:00")
        with patch.object(module, "validate_receipt") as check:
            self.assertEqual(module.verify(self.root, "2026-11-18", "08:00")["status"], "PASS")
            check.assert_called_once()

    def test_infographic_lane_fails_when_missing_or_unverified(self):
        self.report["infographic_status"] = "NOT_READY"
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        with self.assertRaisesRegex(ValueError, "Infographic missing or unverified"):
            module.verify(self.root, "2026-10-13", "08:00", require_infographic=True)

    def test_infographic_ready_requires_real_identity_metadata(self):
        import hashlib
        self.report.update({"revision": 1, "infographic_status": "READY"})
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        with self.assertRaisesRegex(ValueError, "without a bound manifest"):
            module.verify(self.root, "2026-10-13", "08:00", require_infographic=True)

        body_hash = hashlib.sha256(self.report["fullText"].encode("utf-8")).hexdigest()
        self.report["infographic"] = {
            "artifact_type": "FORMAL_INFOGRAPHIC",
            "manifest_id": "manifest-v1",
            "manifest_hash": "a" * 64,
            "report_id": "2026-10-13_08-00",
            "revision": 1,
            "snapshot_id": "snapshot-01",
            "body_hash": body_hash,
            "drive_file_id": "image-file",
            "sha256": "b" * 64,
            "numeric_validation": "PASS",
            "renderer_status": "PASS",
        }
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        result = module.verify(self.root, "2026-10-13", "08:00", require_infographic=True)
        self.assertEqual(result["infographic"]["status"], "MANIFEST_IDENTITY_PASS")
        self.report["infographic"]["body_hash"] = "0" * 64
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        with self.assertRaisesRegex(ValueError, "body hash mismatch"):
            module.verify(self.root, "2026-10-13", "08:00", require_infographic=True)

    def test_infographic_snapshot_binding_detects_mismatch(self):
        import hashlib
        self.report.update({
            "revision": 1, "infographic_status": "READY",
            "publicationEvidence": {"snapshotId": "correct-snapshot"},
            "infographic": {
                "artifact_type": "FORMAL_INFOGRAPHIC", "manifest_id": "m",
                "manifest_hash": "a" * 64,
                "report_id": "2026-10-13_08-00", "revision": 1,
                "snapshot_id": "wrong-snapshot",
                "body_hash": hashlib.sha256(self.report["fullText"].encode()).hexdigest(),
                "drive_file_id": "im", "sha256": "b" * 64,
                "numeric_validation": "PASS", "renderer_status": "PASS",
            },
        })
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
            module.verify(self.root, "2026-10-13", "08:00", require_infographic=True)


if __name__ == "__main__":
    unittest.main()
