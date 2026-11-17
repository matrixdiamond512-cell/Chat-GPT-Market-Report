"""Monthly-folder access must fail closed before imports or publication."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import json
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_reports_from_drive as sync


class DriveSourceFolderTests(unittest.TestCase):
    now = datetime(2026, 11, 17, 14, tzinfo=timezone(timedelta(hours=9)))

    def test_missing_folder_stops_apply_without_global_scan_or_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/latest-report.json").write_text(
                json.dumps({"latestReport": {"date": "2026-11-13"}}), encoding="utf-8")
            session = Mock()
            with patch.object(sync, "open_session", return_value=session), \
                 patch.object(sync, "get_json", return_value={"files": []}), \
                 patch.object(sync, "eligible_sources") as scan, \
                 patch.object(sync, "save_json") as write, \
                 patch.object(sync.subprocess, "run") as downstream:
                with self.assertRaisesRegex(RuntimeError, "BLOCKED_MONTHLY_FOLDER_ACCESS"):
                    sync.poll(root, apply=True, enforce_slot=True)
                scan.assert_not_called()
                write.assert_not_called()
                downstream.assert_not_called()
            session.close.assert_called_once()

    def test_duplicate_folder_on_later_page_is_rejected(self):
        with patch.object(sync, "get_json", side_effect=[
            {"files": [{"id": "one"}], "nextPageToken": "page-two"},
            {"files": [{"id": "two"}]},
        ]) as get:
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_MONTHLY_FOLDER_AMBIGUOUS"):
                sync.monthly_source_folder(Mock(), self.now)
            self.assertEqual(get.call_args.args[2]["pageToken"], "page-two")

    def test_unique_folder_and_scoped_query(self):
        with patch.object(sync, "get_json", side_effect=[
            {"files": [{"id": "monthly"}]}, {"files": [{
                "id": "doc", "name": "マーケットレポート_2026-11-17_12-00",
                "parents": ["monthly"],
            }]},
        ]) as get:
            folder = sync.monthly_source_folder(Mock(), self.now)
            found, count = sync.eligible_sources(Mock(), self.now, folder)
            self.assertEqual(count, 1)
            self.assertEqual(found[("2026-11-17", "12:00")][0]["id"], "doc")
            self.assertIn("'monthly' in parents", get.call_args.args[2]["q"])

    def test_no_folder_cannot_scan(self):
        with patch.object(sync, "get_json") as get:
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_MONTHLY_FOLDER_ACCESS"):
                sync.eligible_sources(Mock(), self.now, None)
            get.assert_not_called()

    def test_doc_moved_during_readback_is_rejected_before_body_validation(self):
        item = {"id": "doc", "name": "source", "parents": ["monthly"]}
        with patch.object(sync, "get_json", side_effect=[
            {"documentId": "doc", "title": "source"},
            {"id": "doc", "name": "source", "parents": ["other"],
             "mimeType": "application/vnd.google-apps.document"},
        ]):
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_SOURCE_PARENT_OR_TYPE_CHANGED"):
                sync.build_report(Mock(), "2026-11-17", "12:00", item, folder_id="monthly")

    def test_orphan_is_rejected_before_docs_read(self):
        with patch.object(sync, "get_json") as get:
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_SOURCE_PARENT_MISMATCH"):
                sync.build_report(Mock(), "2026-11-17", "12:00", {"id": "doc"}, folder_id="monthly")
            get.assert_not_called()

    def test_same_doc_in_monthly_folder_retains_exact_text_and_revision(self):
        item = {"id": "doc", "name": "source", "parents": ["monthly"]}
        doc = {"documentId": "doc", "title": "source", "revisionId": "revision-1",
               "body": {"content": [{"paragraph": {"elements": [
                   {"textRun": {"content": "本文。\n"}}]}}]}}
        metadata = dict(item, mimeType="application/vnd.google-apps.document")
        with patch.object(sync, "get_json", side_effect=[doc, metadata]), \
             patch("report_source_contract.validate_saved_body"), \
             patch("sync_latest_report_publication.validate_sop_body"):
            report = sync.build_report(Mock(), "2026-11-17", "12:00", item, folder_id="monthly")
        self.assertEqual(report["fullText"], "本文。\n")
        self.assertEqual(report["sourceRevisionId"], "revision-1")
        self.assertEqual(report["sourceDocument"]["id"], "doc")
        self.assertEqual(report["report_status"], "SOURCE_ARCHIVED")


if __name__ == "__main__":
    unittest.main()
