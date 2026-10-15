"""Regression coverage for immutable report revisions and shared slot IDs."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_reports
import reconcile_latest_report_market_data as market_reconcile
import report_identity
import sync_latest_report_publication
from reporting.timeline import TIMELINE_COLUMNS, TIMELINE_PERIODS


SOURCE_TEXT = (ROOT / "tests/fixtures/market_report_20261013_1600_original.txt").read_text(encoding="utf-8")
SOURCE_HASH = hashlib.sha256(SOURCE_TEXT.encode("utf-8")).hexdigest()


def source_report(revision: int = 7) -> dict:
    return {
        "date": "2026-10-13",
        "time": "16:00",
        "title": SOURCE_TEXT.splitlines()[0],
        "revision": revision,
        "sourceDocument": {"id": "original-doc-id"},
        "bodyHash": SOURCE_HASH,
        "fullText": SOURCE_TEXT,
        "theme": "original theme",
        "markets": [{"name": "金", "price": "取得不能"}],
        "marketDataTable": {"rows": [{"label": "金", "value": "取得不能"}]},
    }


class ReportIdentityTests(unittest.TestCase):
    def test_internal_key_display_time_and_canonical_filename_are_distinct(self):
        report = {"date": "2026-10-13", "time": "16:00"}
        self.assertEqual(report_identity.internal_report_key(report), "2026-10-13_16-00")
        self.assertEqual(report_identity.display_report_datetime(report), "2026-10-13 16:00")
        self.assertEqual(report_identity.canonical_filename(report), "2026-10-13_16-00.json")
        for malformed in ({"date": "2026/10/13", "time": "16:00"},
                          {"date": "2026-10-13", "time": "25:00"}):
            with self.assertRaises(ValueError):
                report_identity.internal_report_key(malformed)


class CanonicalRevisionTests(unittest.TestCase):
    def test_same_revision_same_source_body_and_derivation_is_no_op(self):
        report = source_report()
        incoming = json.loads(json.dumps(report))
        self.assertEqual(build_reports._choose_canonical_update(report, incoming, "canonical"), "keep")

    def test_same_revision_derived_market_data_does_not_rewrite_canonical(self):
        report = source_report()
        incoming = json.loads(json.dumps(report))
        incoming["markets"][0]["price"] = "4,400.00ドル/oz"
        incoming["marketDataTable"]["rows"][0]["value"] = "4,400.00ドル/oz"
        incoming["dataProvenance"] = {"marketDataReconciliation": {"updatedSymbols": ["gold"]}}
        self.assertEqual(build_reports._choose_canonical_update(report, incoming, "canonical"), "keep")

    def test_same_revision_changed_body_or_body_hash_is_blocked(self):
        report = source_report()
        changed_body = source_report()
        changed_body["fullText"] += "追加された本文"
        with self.assertRaisesRegex(SystemExit, "same-revision canonical conflict"):
            build_reports._choose_canonical_update(report, changed_body, "canonical")

        mismatched_hash = source_report()
        mismatched_hash["bodyHash"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "same-revision canonical conflict"):
            build_reports._choose_canonical_update(report, mismatched_hash, "canonical")

    def test_older_revision_is_blocked(self):
        current = source_report(8)
        incoming = source_report(7)
        with self.assertRaisesRegex(SystemExit, "not newer"):
            build_reports._choose_canonical_update(current, incoming, "canonical")

    def test_newer_revision_requires_verified_original_and_is_writable(self):
        current = source_report(7)
        incoming = source_report(8)
        incoming["theme"] = "verified correction"
        self.assertEqual(build_reports._choose_canonical_update(current, incoming, "canonical"), "write")

        incoming["bodyHash"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "body hash"):
            build_reports._choose_canonical_update(current, incoming, "canonical")


class ReconcileIsolationTests(unittest.TestCase):
    def test_verified_snapshot_does_not_mutate_saved_latest_report(self):
        report = {
            "date": "2026-08-19", "time": "12:00",
            "marketDataTable": {"rows": [{"label": "金", "value": "取得不能"}]},
        }
        snapshot = {
            "generatedAt": "2026-08-19T12:15:54+09:00", "reportSlot": "12:00",
            "overallStatus": "verified",
            "markets": {"gold": {"value": 4408.4, "displayValue": "4,408.40",
                                     "changeText": "+42.40", "changePercent": 0.97,
                                     "verificationStatus": "verified",
                                     "asOf": "2026-08-19T12:05:17+09:00"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            latest_path = Path(directory) / "latest-report.json"
            latest_path.write_text(json.dumps({"latestReport": report}), encoding="utf-8")
            before = latest_path.read_bytes()
            with patch.object(market_reconcile, "LATEST_REPORT", latest_path):
                changed = market_reconcile.update_latest_report(snapshot)
            self.assertEqual(changed, ["gold"])
            self.assertEqual(latest_path.read_bytes(), before)


class SavedDocHeadingCompatibilityTests(unittest.TestCase):
    def test_morning_previous_report_version_heading_is_valid(self):
        headings = [
            "1．総合判断・今日の相場テーマ",
            "2．前営業日終値・主要市場データ",
            "3．昨夜NY市場の時系列",
            "4．前回21:00版からの変化・材料と値動きの整合性",
            "5．主導市場・クロスアセット資金フロー",
            "6．重要ニュースと影響市場",
            "7．需給・ポジション",
            "8．主要6市場の短期見通し",
            "9．本日のメインシナリオと代替シナリオ",
            "10．シナリオが崩れる条件・リスク管理",
            "11．本日イベント・次の時間帯への引き継ぎ",
            "12．結論",
        ]
        lines = ["マーケットレポート｜2026/10/15（木）08:00"]
        for index, heading in enumerate(headings):
            lines.extend([heading, "根拠・市場反応・比較基準を整理し監視条件を確認する。"*5])
            if index == 2:
                lines.extend(["|"+"|".join(TIMELINE_COLUMNS)+"|", "|---|---|---|---|---|---|---|"])
                for period_index,(period,_aliases) in enumerate(TIMELINE_PERIODS["08:00"]):
                    lines.append(
                        f"|{period}|05:00-06:00|市場の状態を確認し、売買材料の変化を観測しました。"
                        "|米株先物が下落し、為替は円高方向へ動きました。"
                        "|金利との連動を示し、東京市場への影響を確認します。"
                        f"|市場観測時刻 05:30、合成根拠 SYN-{period_index+1}。|次の時間帯は東京株と為替の反応を確認します。|"
                    )
        text = "\n".join(lines)
        sync_latest_report_publication.validate_sop_body({
            "date": "2026-10-15", "time": "08:00", "fullText": text
        })


class HistoricalFixtureTests(unittest.TestCase):
    def test_existing_incomplete_history_is_kept_but_new_incomplete_report_is_blocked(self):
        legacy = {"date": "2026-08-21", "time": "08:00", "title": "legacy historical row"}
        complete = {"date": "2026-10-13", "time": "16:00", "title": "verified report", "fullText": "verified report body"}
        with tempfile.TemporaryDirectory() as directory:
            reports_dir = Path(directory) / "reports"
            reports_dir.mkdir()
            (reports_dir / "2026-08-21_08-00.json").write_text(json.dumps(legacy), encoding="utf-8")
            (reports_dir / "2026-10-13_16-00.json").write_text(json.dumps(complete), encoding="utf-8")
            with patch.object(build_reports, "REPORTS_DIR", reports_dir):
                loaded = build_reports.load_canonical_reports({("2026-08-21", "08:00"): legacy})
                self.assertEqual({build_reports.slot_key(r) for r in loaded},
                                 {("2026-08-21", "08:00"), ("2026-10-13", "16:00")})
                with self.assertRaisesRegex(ValueError, "missing required fullText"):
                    build_reports.load_canonical_reports()

    def test_display_sample_is_preserved_only_as_fixture(self):
        fixture = ROOT / "tests/fixtures/2026-07-27_21-00_display-sample.json"
        self.assertTrue(fixture.is_file())
        self.assertFalse((ROOT / "reports/2026-07-27_21-00.json").exists())
        row = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertFalse(row.get("fullText"))
        self.assertIn("表示確認用サンプル", json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
