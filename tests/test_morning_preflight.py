"""Regression tests for the read-only 08:00 evidence preflight."""
import unittest
import json
from pathlib import Path
from scripts.preflight_morning_infographic import check

class PreflightTests(unittest.TestCase):
    def complete(self):
        report = {"report_id":"2026-10-13_08-00","revision":1,"bodyHash":"sha",
                  "fullText":"Verified original", "snapshot_id":"snap",
                  "snapshot":{"snapshot_id":"snap","report_id":"2026-10-13_08-00","revision":1,"data_cutoff":"2026-10-13T07:55:00+09:00"},
                  "context":{"report_id":"2026-10-13_08-00","revision":1,"data_cutoff":"2026-10-13T07:55:00+09:00"}}
        view = {"report_id":"2026-10-13_08-00","revision":1,"body_hash":"sha",
                "snapshot_id":"snap","facts":[{"id":"f1"}],
                "cards":[{"number":1}],"header":{"subtitle":"x"}}
        return report, view

    def test_complete_is_not_formally_approved(self):
        report, view = self.complete()
        self.assertEqual(check(report, view)["status"], "READY_FOR_CANONICAL_VALIDATION")

    def test_actual_oct12_report_blocks_publication(self):
        source = Path(__file__).resolve().parents[1] / "reports" / "2026-10-12_08-00.json"
        report = json.loads(source.read_text(encoding="utf-8"))
        result = check(report)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("report.original_source_verification", result["missing_or_unverified"])
        self.assertIn("report.snapshot", result["missing_or_unverified"])

    def test_legacy_report_blocked(self):
        self.assertIn("report.snapshot", check({"fullText":"text"})["missing_or_unverified"])

    def test_source_note_blocks(self):
        report, view = self.complete()
        report["source_note"] = "reconstructed"
        self.assertIn("report.original_source_verification", check(report, view)["missing_or_unverified"])

    def test_view_hash_mismatch_blocks(self):
        report, view = self.complete()
        view["body_hash"] = "wrong"
        self.assertIn("identity_mismatch.bodyHash", check(report, view)["missing_or_unverified"])

    def test_context_revision_mismatch_blocks(self):
        report, view = self.complete()
        report["context"]["revision"] = 2
        self.assertIn("identity_mismatch.context_revision", check(report, view)["missing_or_unverified"])

    def test_data_cutoff_mismatch_blocks(self):
        report, view = self.complete()
        report["snapshot"]["data_cutoff"] = "2026-10-13T07:50:00+09:00"
        self.assertIn("identity_mismatch.data_cutoff", check(report, view)["missing_or_unverified"])

    def test_snapshot_mismatch_blocks(self):
        report, view = self.complete()
        report["snapshot"]["snapshot_id"] = "other"
        self.assertIn("identity_mismatch.snapshot", check(report, view)["missing_or_unverified"])

if __name__ == "__main__":
    unittest.main()
