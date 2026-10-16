import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'scripts' / 'build_morning_unverified_review.py'
SOURCE = ROOT / 'reports' / '2026-10-12_08-00.json'


class MorningUnverifiedReviewTests(unittest.TestCase):
    def run_builder(self, report_path, output_path):
        return subprocess.run(
            [sys.executable, str(BUILDER), '--report', str(report_path), '--output', str(output_path)],
            cwd=ROOT, capture_output=True, text=True, check=False)

    def test_saved_report_creates_review_only_html_without_manifest(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test-tmp-0800') as directory:
            output = Path(directory) / 'preview'
            result = self.run_builder(SOURCE, output)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('REVIEW_PREVIEW_ONLY', result.stdout)
            self.assertTrue((output / 'report.html').is_file())
            self.assertFalse((output / 'DRAFT-manifest.json').exists())
            contract = json.loads((output / 'render-contract.json').read_text(encoding='utf-8'))
            self.assertEqual(contract['validation']['artifact_type'], 'UNVERIFIED_CONTENT_REVIEW')
            self.assertEqual(len(contract['expected_text']), 43)
            self.assertIn('未検証・公開不可', (output / 'report.html').read_text(encoding='utf-8'))

    def test_builder_rejects_a_report_outside_explicit_unverified_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test-tmp-0800') as directory:
            root = Path(directory)
            report = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
            report['report_status'] = 'PUBLISHED'
            report_path = root / 'report.json'
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
            output = root / 'preview'
            result = self.run_builder(report_path, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('only the explicitly unverified', result.stderr)
            self.assertFalse(output.exists())

    def test_builder_refuses_snapshot_identity_for_review_path(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test-tmp-0800') as directory:
            root = Path(directory)
            report = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
            report['snapshot_id'] = 'must-not-be-accepted'
            report_path = root / 'report.json'
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
            output = root / 'preview'
            result = self.run_builder(report_path, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('refuses report data that carries a snapshot identity', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
