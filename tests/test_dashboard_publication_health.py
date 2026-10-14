"""Regression: reconstructed original cannot be displayed as a healthy report."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sync_latest_report_publication as sync

class DashboardHealthTests(unittest.TestCase):
    def test_reconstructed_source_is_degraded(self):
        self.assertEqual(sync.report_publication_health({"report_status":"RECONSTRUCTED_UNVERIFIED"}),
                         ("degraded", True, "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED"))

    def test_readback_source_retains_original_status(self):
        self.assertEqual(sync.report_publication_health({"report_status":"DOC_READBACK_PASS"}), ("ok", False, ""))

    def test_sync_repairs_old_false_ok_without_changing_report(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "dashboard.json"
            report = {"date":"2026-10-12","time":"08:00","report_status":"RECONSTRUCTED_UNVERIFIED"}
            initial = {"latestReport":report,"currentReportKey":"2026-10-12_08-00",
                       "status":"ok","isStale":False,"staleReason":""}
            sync.dump_json(path, initial)
            with patch.object(sync,"DASHBOARD",path):
                sync.sync_dashboard(report)
                changed = sync.load_json(path,{})
                self.assertEqual(changed["latestReport"],report)
                self.assertEqual(changed["currentReportKey"],"2026-10-12_08-00")
                self.assertEqual(changed["status"],"degraded")
                self.assertIs(changed["isStale"], True)
                self.assertEqual(changed["staleReason"],"REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED")
                before = path.read_bytes()
                sync.sync_dashboard(report)
                self.assertEqual(path.read_bytes(),before)

    def test_healthy_report_does_not_promote_independent_partial_dashboard(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "dashboard.json"
            report = {"date":"2026-10-13","time":"16:00","title":"verified"}
            initial = {"latestReport":{},"currentReportKey":"","status":"partial",
                       "isStale":False,"staleReason":"MARKET_DATA_PARTIAL"}
            sync.dump_json(path, initial)
            with patch.object(sync,"DASHBOARD",path):
                sync.sync_dashboard(report)
                changed = sync.load_json(path,{})
                self.assertEqual(changed["status"],"partial")
                self.assertEqual(changed["staleReason"],"MARKET_DATA_PARTIAL")

if __name__ == "__main__":
    unittest.main()
