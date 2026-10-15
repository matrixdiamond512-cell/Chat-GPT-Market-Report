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
import sync_latest_report_publication


class ReportContractTests(unittest.TestCase):
    def test_schedule_has_one_authoritative_saturday_slot(self):
        # Saturdays have no new publication slots; saved 07:00/08:00/09:00
        # reports remain valid as legacy history.
        self.assertEqual(validate_market_reports.publication_slots("2026-09-19"), set())
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

    def test_publication_consistency_requires_complete_dashboard_copy(self):
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
                    "currentReportKey": "2020-01-01_08-00",
                    "latestReport": report,
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
                dashboard = json.loads((root / "data/dashboard.json").read_text(encoding="utf-8"))
                dashboard["latestReport"] = {"date": report["date"], "time": report["time"], "title": report["title"]}
                with self.assertRaisesRegex(SystemExit, "complete latest report"):
                    verify_publication_consistency.verify_dashboard_copy(report, dashboard)
            finally:
                sys.argv = old_argv


    def test_current_21_aliases_are_recognized_without_weakening_contract(self):
        source = """主要6市場
金：4,119ドル
WTI原油：89.90ドル
日経225先物（大阪取引所）：71,190円
USD/JPY：158.37円
EUR/USD：1.119
BTCUSD：84,000ドル
今後のイベント
6市場の短期見通し
メインシナリオが崩れる条件
"""
        self.assertRegex(source, validate_market_reports.REQUIRED_21_SECTIONS["主要市場データ"])
        self.assertRegex(source, validate_market_reports.REQUIRED_21_SECTIONS["重要イベント"])
        self.assertRegex(source, validate_market_reports.REQUIRED_21_SECTIONS["6市場の見通し"])
        self.assertRegex(source, validate_market_reports.REQUIRED_21_SECTIONS["シナリオが崩れる条件"])

        report = {
            "date": "2026-10-07",
            "time": "21:00",
            "title": "マーケットレポート｜2026/10/07（水）21:00",
            "theme": "test",
            "leadingMarket": "test",
            "mainScenario": "test",
            "alternativeScenario": "test",
            "breakConditions": "test",
            "riskManagement": ["test"],
            "changes": ["test"],
            "consistency": ["test"],
            "news": ["test"],
            "crossAssetFlow": ["test"],
            "positioning": ["test"],
            "events": ["test"],
            "handover": ["test"],
            "fullText": source,
            "markets": [
                {"name": "金", "direction": "中立"},
                {"name": "WTI原油", "direction": "中立"},
                {"name": "日経225先物（大阪取引所）", "direction": "中立"},
                {"name": "USD/JPY", "direction": "中立"},
                {"name": "EUR/USD", "direction": "中立"},
                {"name": "BTCUSD", "direction": "中立"},
            ],
        }
        errors, warnings = [], []
        validate_market_reports.validate_report_content(report, "report", True, errors, warnings)
        self.assertFalse(any("必須市場不足" in error for error in errors))


    def test_slot_transition_heading_requires_substantive_body(self):
        section_body = (
            "観測した市場の値、基準時刻、材料との因果関係、反対シナリオを照合し、"
            "判断根拠と崩れる条件を明記します。"
        )
        titles = [
            "今日の相場テーマ",
            "主要市場データ",
            "材料と値動きの整合性",
            "今日の主導市場",
            "重要ニュース",
            "クロスアセット資金フロー",
            "需給・ポジション",
            "個別市場見通し",
            "メインシナリオ",
            "代替シナリオ",
            "シナリオが崩れる条件",
            "結論",
        ]
        full_text = "\n\n".join(
            f"{title}\n{section_body * 3}" for title in titles
        )
        transition_title = "NY時間への引き継ぎ"
        transition_body = "次の時間帯では米金利・為替・株価を照合し、前提が変わる条件を確認します。"
        full_text += f"\n\n{transition_title}\n{transition_body}"
        report = {
            "date": "2026-10-16",
            "time": "21:00",
            "title": "マーケットレポート｜2026/10/16（金）21:00",
            "fullText": full_text,
        }

        sync_latest_report_publication.validate_sop_body(report)
        empty_section = {
            **report,
            "fullText": full_text.replace(
                f"{transition_title}\n{transition_body}",
                transition_title,
            ),
        }
        with self.assertRaisesRegex(
            SystemExit, "transition section is empty or substantively insufficient"
        ):
            sync_latest_report_publication.validate_sop_body(empty_section)

    def test_oct15_21_archive_does_not_satisfy_handover_from_incidental_prose(self):
        report = json.loads(
            (ROOT / "reports" / "2026-10-15_21-00.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report.get("report_status"), "SOURCE_ARCHIVED")
        headings = sync_latest_report_publication.sop_headings(report["fullText"])
        self.assertFalse(any("引き継ぎ" in title for title in headings))
        with self.assertRaisesRegex(
            SystemExit, "missing time-slot transition/change section"
        ):
            sync_latest_report_publication.validate_sop_body(report)

if __name__ == "__main__":
    unittest.main()
