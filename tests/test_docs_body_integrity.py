import tempfile
from pathlib import Path
from sync_reports_from_drive import save_json
import json
import unittest
from report_source_contract import docs_body_text, archive_body_candidate, body_hash

class DocsBodyIntegrityTests(unittest.TestCase):
    TEXT = "\ufeff## 日本語の見出し\n段落一。\n\n## 次の見出し\n段落二。\n"

    def test_text_runs_keep_blank_lines_headings_bom_and_japanese(self):
        doc = {"body":{"content":[{"paragraph":{"elements":[{"textRun":{"content":line}}]}}
                                  for line in self.TEXT.splitlines(keepends=True)]}}
        self.assertEqual(docs_body_text(doc), self.TEXT)
        self.assertEqual(body_hash(docs_body_text(doc)), body_hash(self.TEXT))

    def test_table_and_single_tab_keep_text_runs(self):
        cell = {"content":[{"paragraph":{"elements":[{"textRun":{"content":self.TEXT}}]}}]}
        doc = {"tabs":[{"documentTab":{"body":{"content":[{"table":{"tableRows":[{"tableCells":[cell]}]}}]}}}]}
        self.assertEqual(docs_body_text(doc), self.TEXT)

    def archive(self):
        return {"reports":[{"date":"2026-11-13","time":"16:00","fullText":self.TEXT.replace("\n", ""),
                             "verifiedAtSlot":False,"driveRevisionId":"unchanged-revision",
                             "sourceDocument":{"id":"doc"},"originalReportStatus":"UNVERIFIED"}]}

    def candidate(self, **changes):
        args = dict(date="2026-11-13",slot="16:00",document_id="doc",original_text=self.TEXT,
                    original_hash=body_hash(self.TEXT),previous_hash=body_hash(self.TEXT.replace("\n", "")))
        args.update(changes)
        return archive_body_candidate(self.archive(), **args)

    def test_serialized_candidate_preserves_full_sha_and_source_metadata(self):
        source = self.archive()
        candidate = self.candidate()
        saved = json.dumps(candidate,ensure_ascii=False).encode("utf-8")
        result = json.loads(saved)["reports"][0]
        self.assertEqual(result["fullText"], self.TEXT)
        self.assertEqual(body_hash(result["fullText"]),body_hash(self.TEXT))
        self.assertEqual(result["driveRevisionId"],"unchanged-revision")
        self.assertFalse(result["verifiedAtSlot"])
        self.assertEqual(source,self.archive())

    def test_lost_newlines_cannot_match_original_hash(self):
        with self.assertRaisesRegex(ValueError,"Original body hash"):
            self.candidate(original_text=self.TEXT.replace("\n", ""))

    def test_concurrent_archive_change_rejected(self):
        with self.assertRaisesRegex(ValueError,"changed since"):
            self.candidate(previous_hash="0"*64)

    def test_wrong_document_rejected(self):
        with self.assertRaisesRegex(ValueError,"document mismatch"):
            self.candidate(document_id="other")

    def test_multiple_tabs_not_silently_concatenated(self):
        with self.assertRaisesRegex(ValueError,"single source tab"):
            docs_body_text({"tabs":[{},{}]})

    def test_existing_writer_disk_readback_preserves_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            save_json(path, {"fullText":self.TEXT,"bodyHash":body_hash(self.TEXT)})
            actual = json.loads(path.read_bytes())["fullText"]
            self.assertEqual(actual,self.TEXT)
            self.assertEqual(body_hash(actual),body_hash(self.TEXT))

    def test_existing_writer_rejects_changed_body_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with self.assertRaisesRegex(ValueError,"before save"):
                save_json(path,{"fullText":self.TEXT.replace("\n",""),"bodyHash":body_hash(self.TEXT)})
            self.assertFalse(path.exists())
