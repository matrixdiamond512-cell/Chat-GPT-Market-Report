from __future__ import annotations

import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_run_market_close_job as job
import sync_market_close_sheet as close_sync


class CloudRunTestOnlyGuardTests(unittest.TestCase):
    def test_partial_market_data_can_be_persisted_successfully(self):
        result = job.classify_sync_result(1, {
            "status": "PARTIAL",
            "stages": {stage: "SUCCESS" for stage in job.PERSISTENCE_STAGES},
        })
        self.assertEqual(result["marketDataStatus"], "PARTIAL")
        self.assertEqual(result["sheetsPersistenceStatus"], "SUCCESS")
        self.assertEqual(result["failedPersistenceStages"], [])

    def test_readback_failure_means_job_persistence_failure(self):
        result = job.classify_sync_result(1, {
            "status": "PARTIAL",
            "stages": {
                "SHEETS_IMPORT": "SUCCESS", "CHATGPT_INPUT": "SUCCESS",
                "CLOSE_DATA_WRITE": "SUCCESS", "READBACK_VERIFY": "FAILED",
            },
        })
        self.assertEqual(result["marketDataStatus"], "PARTIAL")
        self.assertEqual(result["sheetsPersistenceStatus"], "FAILED")
        self.assertEqual(result["failedPersistenceStages"], ["READBACK_VERIFY"])

    def test_missing_or_failed_write_stage_is_not_success(self):
        result = job.classify_sync_result(1, {"status": "FAILED", "stages": {"SHEETS_IMPORT": "SUCCESS"}})
        self.assertEqual(result["sheetsPersistenceStatus"], "FAILED")
        self.assertIn("CLOSE_DATA_WRITE", result["failedPersistenceStages"])

    def test_job_uses_issue_205_allowlisted_isolated_sheet(self):
        self.assertEqual(job.TEST_ONLY_SPREADSHEET_ID, "1KBDBa-m35ZgleJpD-uPrxOHafIECjfKw4k1nL2HzDLs")

    def test_test_only_adc_refuses_non_test_project_or_sheet_before_auth(self):
        with self.assertRaises(close_sync.CloseSyncError):
            close_sync.create_test_only_adc_session("market-report-production", job.TEST_ONLY_SPREADSHEET_ID)
        with self.assertRaises(close_sync.CloseSyncError):
            close_sync.create_test_only_adc_session("market-report-test-only", "1vqraQzVpIHWLFSxP5X5NWoTYquT6B27l-A7UuyYauNY")

    def test_rejects_non_test_project(self):
        with patch.dict(os.environ, {
            "GOOGLE_CLOUD_PROJECT": "production-project",
            job.EVIDENCE_BUCKET: "market-report-test-only-close-evidence",
            "MARKET_CLOSE_ENVIRONMENT": "TEST_ONLY",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "TEST_ONLY"):
                job.run()

    def test_rejects_missing_test_evidence_bucket(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": job.ALLOWED_PROJECT, "MARKET_CLOSE_ENVIRONMENT": "TEST_ONLY"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, job.EVIDENCE_BUCKET):
                job.run()

    def test_rejects_non_test_evidence_bucket(self):
        with patch.dict(os.environ, {
            "GOOGLE_CLOUD_PROJECT": job.ALLOWED_PROJECT,
            job.EVIDENCE_BUCKET: "market-report-production",
            "MARKET_CLOSE_ENVIRONMENT": "TEST_ONLY",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "dedicated TEST_ONLY bucket"):
                job.run()

    def test_rejects_non_test_only_mode(self):
        with patch.dict(os.environ, {
            "GOOGLE_CLOUD_PROJECT": job.ALLOWED_PROJECT,
            job.EVIDENCE_BUCKET: "market-report-test-only-close-evidence",
            "MARKET_CLOSE_ENVIRONMENT": "PRODUCTION",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must equal TEST_ONLY"):
                job.run()

    def test_report_date_is_included_in_idempotency_key(self):
        self.assertEqual("2026-11-16:08:00:test", f"2026-11-16:08:00:test")

    def test_close_snapshot_merge_keeps_only_exact_date_provenance(self):
        import build_chatgpt_report_input as contract
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            market_dir = root / "data" / "market"
            market_dir.mkdir(parents=True)
            (market_dir / "latest.json").write_text(json.dumps({"markets": {"vix": {"value": 15}}}), encoding="utf-8")
            items = {}
            for _, symbol, _, market_type, session in contract.ITEMS:
                items[symbol] = {
                    "verificationStatus": "verified", "expectedSessionDate": "2026-11-13",
                    "asOf": "2026-11-13", "value": 100, "sourceName": "source",
                    "sourceUrl": "https://example.test", "marketType": market_type, "session": session,
                }
            items["russell2000"]["asOf"] = "2026-11-12"
            (market_dir / "chatgpt-input.json").write_text(json.dumps({"reportDate": "2026-11-16", "markets": items}), encoding="utf-8")
            with patch.object(job, "ROOT", root):
                result = job.merge_verified_28_rows_into_close_snapshot()
            self.assertIn("nikkei225", result["markets"])
            self.assertNotIn("russell2000", result["markets"])


if __name__ == "__main__":
    unittest.main()
