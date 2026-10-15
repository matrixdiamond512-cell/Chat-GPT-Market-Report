from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_reports
import prepare_pages_site
import persist_report_index_to_canonical
import validate_report_index
import verify_scheduled_report_delivery
from reporting.publication_eligibility import is_publication_eligible


def report(slot: str, status: str | None = None) -> dict:
    item = {
        "date": "2026-10-14",
        "time": slot,
        "title": f"Market report {slot}",
        "fullText": f"Market report {slot}\nOriginal body.",
    }
    if status is not None:
        item["report_status"] = status
    return item


class PublicationEligibilityTests(unittest.TestCase):
    def test_statusless_legacy_and_passed_reports_remain_public(self):
        for item in (
            report("08:00"),
            report("12:00", "PUBLISHED"),
            report("16:00", "DOC_READBACK_PASS"),
        ):
            with self.subTest(status=item.get("report_status")):
                self.assertTrue(is_publication_eligible(item))

    def test_source_only_blocked_reconstructed_and_unknown_reports_fail_closed(self):
        for status in ("SOURCE_ARCHIVED", "BLOCKED", "RECONSTRUCTED_UNVERIFIED", "PENDING_REVIEW"):
            with self.subTest(status=status):
                self.assertFalse(is_publication_eligible(report("08:00", status)))

    def test_canonical_persistence_allows_only_explicitly_nonpublic_extra_files(self):
        published = report("16:00", "PUBLISHED")
        archived = report("08:00", "SOURCE_ARCHIVED")
        canonical = {
            persist_report_index_to_canonical.slot_key(published): published,
            persist_report_index_to_canonical.slot_key(archived): archived,
        }

        persist_report_index_to_canonical.validate_slot_sets([published], canonical)

        legacy = report("12:00")
        canonical[persist_report_index_to_canonical.slot_key(legacy)] = legacy
        with self.assertRaisesRegex(SystemExit, "eligible_canonical_missing_from_index"):
            persist_report_index_to_canonical.validate_slot_sets([published], canonical)

    def test_canonical_persistence_rejects_index_entries_without_files(self):
        published = report("16:00", "PUBLISHED")
        with self.assertRaisesRegex(SystemExit, "missing_canonical"):
            persist_report_index_to_canonical.validate_slot_sets([published], {})

    def test_persistence_keeps_archived_canonical_source_unchanged(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory)
            reports_dir = root / "reports"
            reports_dir.mkdir()
            published = report("16:00", "PUBLISHED")
            archived = report("08:00", "SOURCE_ARCHIVED")
            published_path = reports_dir / "2026-10-14_16-00.json"
            archived_path = reports_dir / "2026-10-14_08-00.json"
            published_path.write_text(json.dumps(published, ensure_ascii=False), encoding="utf-8")
            archived_path.write_text(json.dumps(archived, ensure_ascii=False, indent=4), encoding="utf-8")
            archived_before = archived_path.read_bytes()
            index_path = root / "reports.json"
            index_path.write_text(json.dumps([published], ensure_ascii=False), encoding="utf-8")

            with patch.object(persist_report_index_to_canonical, "REPORTS_DIR", reports_dir), \
                 patch.object(persist_report_index_to_canonical, "INDEX_FILE", index_path):
                persist_report_index_to_canonical.main()

            self.assertEqual(archived_path.read_bytes(), archived_before)
            self.assertEqual(json.loads(published_path.read_text(encoding="utf-8")), published)

    def test_builder_keeps_quarantined_history_but_excludes_it_from_public_index(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory)
            reports_dir = root / "reports"
            reports_dir.mkdir()
            published = report("16:00", "PUBLISHED")
            archived = report("08:00", "SOURCE_ARCHIVED")
            paths = {
                (published["date"], published["time"]): reports_dir / "2026-10-14_16-00.json",
                (archived["date"], archived["time"]): reports_dir / "2026-10-14_08-00.json",
            }
            for item in (published, archived):
                paths[(item["date"], item["time"])].write_text(
                    json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            archived_bytes = paths[(archived["date"], archived["time"])].read_bytes()
            old_index = [published, archived]
            previous_by_slot = {build_reports.slot_key(item): item for item in old_index}
            old_keys = set(previous_by_slot)
            original_reports_dir, original_output = build_reports.REPORTS_DIR, build_reports.OUTPUT_FILE
            try:
                build_reports.REPORTS_DIR = reports_dir
                build_reports.OUTPUT_FILE = root / "reports.json"
                build_reports.write_index([published, archived])
                build_reports.verify_no_history_loss(old_keys, previous_by_slot)
                saved_index = json.loads(build_reports.OUTPUT_FILE.read_text(encoding="utf-8"))
                self.assertEqual(saved_index, [published])
                self.assertEqual(paths[(archived["date"], archived["time"])].read_bytes(), archived_bytes)
            finally:
                build_reports.REPORTS_DIR = original_reports_dir
                build_reports.OUTPUT_FILE = original_output

    def test_public_index_validator_rejects_source_archive(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            item = report("08:00", "SOURCE_ARCHIVED")
            (root / "reports.json").write_text(json.dumps([item]), encoding="utf-8")
            argv = ["validate_report_index.py", "--root", str(root)]
            with patch.object(sys, "argv", argv), self.assertRaisesRegex(SystemExit, "not publication-eligible"):
                validate_report_index.main()

    def test_scheduled_delivery_rejects_archive_even_if_original_exists(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            archived = report("08:00", "SOURCE_ARCHIVED")
            (root / "reports/2026-10-14_08-00.json").write_text(json.dumps(archived), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not publication-eligible"):
                verify_scheduled_report_delivery.verify(root, "2026-10-14", "08:00")

    def test_pages_staging_hides_ineligible_canonical_files_without_deleting_sources(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory)
            source = root / "repo"
            site = root / "site"
            (source / "reports").mkdir(parents=True)
            published = report("16:00", "PUBLISHED")
            archived = report("08:00", "SOURCE_ARCHIVED")
            for item in (published, archived):
                name = f"2026-10-14_{item['time'].replace(':', '-')}.json"
                (source / "reports" / name).write_text(json.dumps(item), encoding="utf-8")
            (source / "reports.json").write_text(json.dumps([published]), encoding="utf-8")

            excluded = prepare_pages_site.prepare_pages_site(source, site)

            self.assertEqual(excluded, ["2026-10-14_08-00.json"])
            self.assertTrue((site / "reports/2026-10-14_16-00.json").exists())
            self.assertFalse((site / "reports/2026-10-14_08-00.json").exists())
            self.assertTrue((source / "reports/2026-10-14_08-00.json").exists())


if __name__ == "__main__":
    unittest.main()
