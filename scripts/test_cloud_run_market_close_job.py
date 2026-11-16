from __future__ import annotations

import os
import json
import sys
import subprocess
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

    def test_market_failure_is_distinct_from_successful_persistence(self):
        result = job.classify_sync_result(1, {
            "status": "FAILED",
            "stages": {stage: "SUCCESS" for stage in job.PERSISTENCE_STAGES},
        })
        self.assertEqual(result["marketDataStatus"], "FAILED")
        self.assertEqual(result["sheetsPersistenceStatus"], "SUCCESS")

    def test_late_manual_snapshot_has_actual_generation_time_and_cutoff_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "latest.json"
            path.write_text(json.dumps({"reportDate": "2026-11-16", "reportSlot": "08:00", "markets": {}}), encoding="utf-8")
            generated = job.dt.datetime(2026, 11, 16, 12, 38, tzinfo=job.JST)
            result = job.finalize_market_snapshot(path, generated, late_manual=True)
            self.assertEqual(result["generatedAt"], "2026-11-16T12:38:00+09:00")
            self.assertEqual(result["cutoffStatus"], "MISSED_MANUAL_TEST_ONLY")
            self.assertEqual(result["acquisitionMode"], "TEST_ONLY-MANUAL-LATE")

    def test_late_manual_run_finalizes_snapshot_before_mixed_session_sync(self):
        base_datetime = job.dt.datetime
        fixed_now = base_datetime(2026, 11, 16, 12, 38, tzinfo=job.JST)

        class FrozenDateTime(base_datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now if tz else fixed_now.replace(tzinfo=None)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "work"
            work.mkdir()
            input_path = root / "input.json"
            report = {
                "date": "2026-11-16",
                "time": "08:00",
                "marketDataTable": {
                    "dataDate": "2026-11-13",
                    "rows": [{"label": f"row-{index}"} for index in range(28)],
                },
            }
            input_path.write_text(json.dumps({"latestReport": report}), encoding="utf-8")
            observed = {}

            def fake_run(script, *args, env=None, check=True):
                if script == "repair_morning_daily_references.py":
                    market_latest = root / "data" / "market" / "latest.json"
                    market_latest.parent.mkdir(parents=True, exist_ok=True)
                    markets = {
                        "vix": {
                            "verificationStatus": "verified",
                            "value": 20.0,
                            "asOf": "2026-11-13T16:15:00-05:00",
                            "sessionDate": "2026-11-13",
                            "expectedSessionDate": "2026-11-13",
                        },
                        "nikkei_vi": {
                            "verificationStatus": "verified",
                            "value": 25.0,
                            "asOf": "2026-11-13T15:50:00+09:00",
                            "sessionDate": "2026-11-13",
                            "expectedSessionDate": "2026-11-13",
                        },
                        "btcusd": {
                            "verificationStatus": "verified",
                            "value": 65312.48,
                            "asOf": "2026-11-15T00:00:00Z",
                            "sessionDate": "2026-11-14",
                            "expectedSessionDate": "2026-11-14",
                        },
                    }
                    market_latest.write_text(json.dumps({
                        "reportDate": "2026-11-16",
                        "reportSlot": "08:00",
                        "markets": markets,
                    }), encoding="utf-8")
                    report_path = root / "data" / "latest-report.json"
                    payload = json.loads(report_path.read_text(encoding="utf-8"))
                    latest_report = payload["latestReport"]
                    latest_report["dataProvenance"] = {
                        "dailyCloseRepair": {
                            "items": {
                                f"row-{index}": {"status": "verified", "dataDate": "2026-11-13"}
                                for index in range(28)
                            },
                            "unavailable": {},
                        },
                        "morningCoverage": {"items": {}},
                    }
                    report_path.write_text(json.dumps(payload), encoding="utf-8")
                if script == "fetch_morning_reference.py":
                    output_path = Path(args[args.index("--output-path") + 1])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(json.dumps({"items": {}}), encoding="utf-8")
                if script == "sync_market_close_sheet.py":
                    latest_path = Path(args[args.index("--latest") + 1])
                    snapshot = json.loads(latest_path.read_text(encoding="utf-8"))
                    observed.update(snapshot)
                    self.assertEqual(snapshot["generatedAt"], "2026-11-16T12:38:00+09:00")
                    self.assertEqual(snapshot["cutoffStatus"], "MISSED_MANUAL_TEST_ONLY")
                    self.assertEqual(snapshot["acquisitionMode"], "TEST_ONLY-MANUAL-LATE")
                    self.assertEqual(snapshot["reportDate"], "2026-11-16")
                    self.assertEqual(snapshot["markets"]["btcusd"]["expectedSessionDate"], "2026-11-14")
                    self.assertEqual(
                        close_sync.resolve_target_date(snapshot, fixed_now).isoformat(),
                        "2026-11-13",
                    )
                    status_path = Path(args[args.index("--status-output") + 1])
                    status_path.write_text(json.dumps({
                        "status": "SUCCESS",
                        "stages": {stage: "SUCCESS" for stage in job.PERSISTENCE_STAGES},
                    }), encoding="utf-8")
                stdout = ""
                if script == "write_test_only_close_evidence.py":
                    stdout = "generation=42 sha256=" + ("a" * 64)
                return subprocess.CompletedProcess([script], 0, stdout, "")

            with patch.dict(os.environ, {
                "GOOGLE_CLOUD_PROJECT": job.ALLOWED_PROJECT,
                job.EVIDENCE_BUCKET: "market-report-test-only-close-evidence",
                "MARKET_CLOSE_ENVIRONMENT": "TEST_ONLY",
                "MARKET_CLOSE_REPORT_DATE": "2026-11-16",
                "MARKET_CLOSE_TEST_ONLY_INPUT_JSON": str(input_path),
                "MARKET_CLOSE_TEST_ONLY_LATE_RUN": "1",
                "CLOUD_RUN_EXECUTION": "late-manual-regression",
            }, clear=True), patch.object(job, "ROOT", root), patch.object(job, "WORK", work), \
                 patch.object(job, "_run", side_effect=fake_run), patch.object(job.dt, "datetime", FrozenDateTime):
                result = job.run()

            self.assertEqual(result["cutoffStatus"], "MISSED_MANUAL_TEST_ONLY")
            self.assertEqual(result["reportTableDataDate"], "2026-11-13")
            self.assertEqual(result["sheetCloseTargetDate"], "2026-11-13")
            self.assertEqual(result["sheetsPersistenceStatus"], "SUCCESS")
            self.assertEqual(observed["markets"]["btcusd"]["expectedSessionDate"], "2026-11-14")

    def test_close_snapshot_merge_keeps_expected_market_session_date(self):
        import build_chatgpt_report_input as contract
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            market_dir = root / "data" / "market"
            market_dir.mkdir(parents=True)
            (market_dir / "latest.json").write_text(json.dumps({"markets": {}}), encoding="utf-8")
            items = {}
            for _, symbol, _, market_type, session in contract.ITEMS:
                items[symbol] = {
                    "verificationStatus": "verified", "expectedSessionDate": "2026-11-12",
                    "asOf": "2026-11-12", "value": 100, "sourceName": "source",
                    "sourceUrl": "https://example.test", "marketType": market_type, "session": session,
                }
            (market_dir / "chatgpt-input.json").write_text(json.dumps({"reportDate": "2026-11-16", "markets": items}), encoding="utf-8")
            with patch.object(job, "ROOT", root):
                result = job.merge_verified_28_rows_into_close_snapshot()
            self.assertEqual(result["markets"]["dow"]["expectedSessionDate"], "2026-11-12")

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
