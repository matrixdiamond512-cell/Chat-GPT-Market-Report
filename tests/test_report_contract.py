import sys
import unittest
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_reports
import reconcile_report_history
import validate_market_reports
import verify_publication_consistency


class ReportContractTests(unittest.TestCase):
    def test_schedule_has_one_authoritative_saturday_slot(self):
        self.assertEqual(validate_market_reports.publication_slots("2026-09-19"), {"08:00"})
        self.assertEqual(validate_market_reports.publication_slots("2026-09-20"), set())
        self.assertEqual(validate_market_reports.expected_slots("2026-09-19"), {"07:00", "08:00", "09:00"})

    def test_inline_scenario_labels_are_recognized(self):
        source = """【11．シナリオ分析】
メイン：WTIが100ドル未満を維持し、株高が続く。
代替：原油反発で株価が調整する。
崩れる条件：WTI急反発と米金利上昇。
"""
        for name, pattern in validate_market_reports.REQUIRED_21_SECTIONS.items():
            if name == "メインシナリオ":
                self.assertRegex(source, pattern)
            elif name == "代替シナリオ":
                self.assertRegex(source, pattern)
            elif name == "シナリオが崩れる条件":
                self.assertRegex(source, pattern)

    def test_full_text_original_is_valid_without_invented_market_objects(self):
        report = {
            "date": "2026-09-25",
            "time": "16:00",
            "title": "マーケットレポート｜2026/09/25（金）16:00",
            "fullText": "既存レポート本文。" * 150,
        }
        errors, warnings = [], []
        validate_market_reports.validate_report_content(report, "report", True, errors, warnings)
        self.assertEqual(errors, [])
        self.assertTrue(any("原文全文形式" in warning for warning in warnings))

        report["time"] = "21:00"
        errors, warnings = [], []
        validate_market_reports.validate_report_content(report, "report", True, errors, warnings)
        self.assertTrue(any("markets は配列" in error for error in errors))

    def test_stale_latest_cannot_overwrite_canonical(self):
        current = {"date": "2026-09-22", "time": "21:00", "title": "t", "revision": 3}
        incoming = {"date": "2026-09-22", "time": "21:00", "title": "old", "revision": 2}
        with self.assertRaises(SystemExit):
            build_reports._choose_canonical_update(current, incoming, "reports/2026-09-22_21-00.json")

    def test_older_slot_correction_uses_its_own_revision(self):
        current = {"date": "2026-09-22", "time": "08:00", "title": "old", "revision": 1}
        incoming = {"date": "2026-09-22", "time": "08:00", "title": "corrected", "revision": 2}
        self.assertTrue(
            reconcile_report_history._should_replace(current, incoming, ("2026-09-22", "08:00"))
        )

    def test_ambiguous_correction_is_rejected(self):
        current = {"date": "2026-09-22", "time": "08:00", "title": "old"}
        incoming = {"date": "2026-09-22", "time": "08:00", "title": "different"}
        with self.assertRaises(ValueError):
            reconcile_report_history._should_replace(current, incoming, ("2026-09-22", "08:00"))

    def test_publication_consistency_accepts_one_projection(self):
        report = {
            "date": "2020-01-01",
            "time": "08:00",
            "title": "マーケットレポート｜2020/01/01（水）08:00",
            "theme": "test",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "data").mkdir()
            (root / "data/latest-report.json").write_text(json.dumps({"latestReport": report}), encoding="utf-8")
            (root / "reports/2020-01-01_08-00.json").write_text(json.dumps(report), encoding="utf-8")
            (root / "reports.json").write_text(json.dumps([report]), encoding="utf-8")
            (root / "data/dashboard.json").write_text(
                json.dumps({
                    "currentReportKey": "2020-01-01 08:00",
                    "latestReport": {"date": report["date"], "time": report["time"], "title": report["title"], "summary": "projection"},
                }),
                encoding="utf-8",
            )
            old_argv = sys.argv
            try:
                sys.argv = [
                    "verify_publication_consistency.py",
                    "--latest", str(root / "data/latest-report.json"),
                    "--reports", str(root / "reports"),
                    "--index", str(root / "reports.json"),
                    "--dashboard", str(root / "data/dashboard.json"),
                ]
                self.assertEqual(verify_publication_consistency.main(), 0)
            finally:
                sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
