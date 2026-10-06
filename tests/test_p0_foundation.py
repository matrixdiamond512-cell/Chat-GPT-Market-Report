import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import complete_report_schema
import build_reports
import reconcile_report_history
import persist_report_index_to_canonical as unsafe_writer
import validate_drive_publication_receipt as receipt_guard


class P0FoundationTests(unittest.TestCase):
    def test_every_schema_input_processed(self):
        reports = [{'markets': [{'name': '金'}]}, {'markets': [{'name': 'BTCUSD'}]}, {'markets': [{'name': '原油'}]}]
        self.assertTrue(complete_report_schema.complete_reports(reports))
        self.assertTrue(all(r.get('schemaCompletion') and r['markets'][0].get('price') for r in reports))
        self.assertFalse(complete_report_schema.complete_reports(reports))

    def test_naive_aware_comparison_is_explicit_value_error(self):
        current = {'date': '2026-10-01', 'time': '21:00', 'title': 'old', 'updatedAt': '2026-10-01T21:00:00'}
        incoming = dict(current, title='new', updatedAt='2026-10-01T21:05:00+09:00')
        with self.assertRaisesRegex(ValueError, 'timezone'):
            build_reports._choose_canonical_update(current, incoming, 'fixture')
        with self.assertRaisesRegex(ValueError, 'timezone'):
            reconcile_report_history._should_replace(current, incoming, ('2026-10-01', '21:00'))

    def test_date_only_receipt_cli_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            latest = Path(directory)/'latest.json'
            latest.write_text(json.dumps({'date': '2026-09-30', 'time': '21:00', 'title': 'fixture'}), encoding='utf-8')
            with patch.object(sys, 'argv', ['receipt', '--latest', str(latest), '--enforce-from', '2026-10-01']):
                receipt_guard.main()  # legacy skip, no file/production writes

    def test_unsafe_writer_demonstrates_revision_overwrite_in_temp_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); reports = root/'reports'; reports.mkdir()
            path = reports/'2026-10-02_21-00.json'
            protected = {'date': '2026-10-02', 'time': '21:00', 'title': 'corrected', 'revision': 3, 'fullText': '保全'}
            stale = dict(protected, title='stale', revision=1, fullText='古い')
            path.write_text(json.dumps(protected), encoding='utf-8')
            index = root/'reports.json'; index.write_text(json.dumps([stale]), encoding='utf-8')
            with patch.object(unsafe_writer, 'REPORTS_DIR', reports), patch.object(unsafe_writer, 'INDEX_FILE', index):
                unsafe_writer.main()
            overwritten = json.loads(path.read_text(encoding='utf-8'))
            # PASS means risk reproduced, not repaired. Production writer unchanged.
            self.assertEqual(overwritten['revision'], 1)
            self.assertNotEqual(overwritten, protected)
