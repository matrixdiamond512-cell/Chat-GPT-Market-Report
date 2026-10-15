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
        with tempfile.TemporaryDirectory() as dirname:
            self.assertEqual(sync.report_publication_health(
                {"date":"2026-10-13", "time":"16:00", "report_status":"DOC_READBACK_PASS"},
                Path(dirname)), ("ok", False, ""))

    def test_later_held_canonical_slots_mark_dashboard_stale_without_promotion(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            sync.dump_json(root / "2026-10-15_08-00.json", {
                "date":"2026-10-15", "time":"08:00", "report_status":"SOURCE_ARCHIVED"})
            sync.dump_json(root / "2026-10-15_16-00.json", {
                "date":"2026-10-15", "time":"16:00", "report_status":"BLOCKED_SNAPSHOT_MISSING"})
            report = {"date":"2026-10-13", "time":"16:00", "report_status":"PUBLISHED"}
            self.assertTrue(sync.report_publication_health(report, root)[1])
            path = root / "dashboard.json"
            sync.dump_json(path, {"latestReport":{}, "currentReportKey":"", "status":"ok",
                                  "isStale":False, "staleReason":""})
            with patch.object(sync, "DASHBOARD", path), patch.object(sync, "REPORTS_DIR", root):
                sync.sync_dashboard(report)
            changed = sync.load_json(path, {})
            self.assertEqual(changed["latestReport"], report)
            self.assertEqual(changed["status"], "degraded")
            self.assertIs(changed["isStale"], True)
            self.assertTrue(changed["staleReason"].startswith("LATEST_PUBLICATION_LAGGING_HELD_SOURCES:"))

    def test_newer_eligible_report_is_not_marked_stale_by_older_archives(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            sync.dump_json(root / "2026-10-15_08-00.json", {
                "date":"2026-10-15", "time":"08:00", "report_status":"SOURCE_ARCHIVED"})
            report = {"date":"2026-10-16", "time":"08:00", "report_status":"DOC_READBACK_PASS"}
            self.assertEqual(sync.report_publication_health(report, root), ("ok", False, ""))

    def test_sync_repairs_old_false_ok_without_changing_report(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "dashboard.json"
            report = {"date":"2026-10-12","time":"08:00","report_status":"RECONSTRUCTED_UNVERIFIED"}
            initial = {"latestReport":report,"currentReportKey":"2026-10-12_08-00",
                       "status":"ok","isStale":False,"staleReason":""}
            sync.dump_json(path, initial)
            with patch.object(sync,"DASHBOARD",path), patch.object(sync,"REPORTS_DIR",Path(dirname) / "empty-reports"):
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
            with patch.object(sync,"DASHBOARD",path), patch.object(sync,"REPORTS_DIR",Path(dirname) / "empty-reports"):
                sync.sync_dashboard(report)
                changed = sync.load_json(path,{})
                self.assertEqual(changed["status"],"partial")
                self.assertEqual(changed["staleReason"],"MARKET_DATA_PARTIAL")

if __name__ == "__main__":
    unittest.main()
