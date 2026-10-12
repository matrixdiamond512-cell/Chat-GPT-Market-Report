import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_drive_publication_receipt.py"

class ReceiptValidationTests(unittest.TestCase):
    def validate(self, receipt):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "publication-receipts").mkdir()
            report = {"date": "2026-10-12", "time": "21:00", "title": "マーケットレポート｜2026/10/12（月）21:00"}
            (root / "data/latest-report.json").write_text(json.dumps({"latestReport": report}), encoding="utf-8")
            (root / "publication-receipts/2026-10-12_21-00.json").write_text(json.dumps(receipt), encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), "--enforce-from", "2026-08-19T21:00:00+09:00"], cwd=root, capture_output=True, text=True)

    def test_legacy_receipt_rejected_with_explicit_reason(self):
        receipt = {"date":"2026-10-12","time":"21:00","docStatus":"READBACK_PASS","docId":"1P6PuJmPwv1bj2ty5cTyXlPkIMNxeYYhfN8ux3gj8Aaw"}
        res = self.validate(receipt)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("LEGACY_RECEIPT_REQUIRES_MIGRATION", res.stderr + res.stdout)

    def test_wrong_slot_legacy_rejected(self):
        receipt = {"date":"2026-10-11","time":"21:00","docStatus":"READBACK_PASS","docId":"abc"}
        res = self.validate(receipt)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("legacy receipt report slot mismatch", res.stderr + res.stdout)

    def test_strict_saved_passes(self):
        docid = "1P6PuJmPwv1bj2ty5cTyXlPkIMNxeYYhfN8ux3gj8Aaw"
        receipt = {"date":"2026-10-12","time":"21:00","title":"マーケットレポート｜2026/10/12（月）21:00","status":"saved","publisher":"chatgpt","driveFileId":docid,"driveUrl":f"https://docs.google.com/document/d/{docid}/edit","savedAt":"2026-10-12T21:11:33+09:00"}
        self.assertEqual(self.validate(receipt).returncode, 0)

    def test_strict_missing_publisher_rejected(self):
        docid = "1P6PuJmPwv1bj2ty5cTyXlPkIMNxeYYhfN8ux3gj8Aaw"
        receipt = {"date":"2026-10-12","time":"21:00","title":"マーケットレポート｜2026/10/12（月）21:00","status":"saved","driveFileId":docid,"driveUrl":f"https://docs.google.com/document/d/{docid}/edit","savedAt":"2026-10-12T21:11:33+09:00"}
        self.assertNotEqual(self.validate(receipt).returncode, 0)

if __name__ == "__main__":
    unittest.main()
