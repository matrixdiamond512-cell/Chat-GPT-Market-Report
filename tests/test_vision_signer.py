"""Trusted Vision signer regressions; providers and secrets are test-local only."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reporting.infographic import ValidationFailure, validate_image, vision_attestation_payload  # noqa: E402
from reporting.vision_provider import (FIXTURE_PROVIDER_ID, REQUIRED_VISION_CHECKS,
    VisionProviderFailure, VisionReviewResult, FixtureVisionProvider)  # noqa: E402
from reporting.vision_signer import VisionSignerFailure, sign_review, write_review  # noqa: E402
from tests.test_infographic_validation import sample, spec  # noqa: E402
from tests.transaction_fixture import png_bytes  # noqa: E402


class VerdictProvider:
    provider_id = FIXTURE_PROVIDER_ID

    def __init__(self, change=None):
        self.change = change

    def review(self, image_path, report, candidate):
        del image_path, report, candidate
        value = {name: 'PASS' for name in REQUIRED_VISION_CHECKS}
        if self.change:
            value[self.change[0]] = self.change[1]
        return VisionReviewResult.parse(value)


class TrustedVisionSignerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.report = sample()
        self.candidate = spec(self.report)
        self.image = self.directory / 'fixture.png'
        self.image.write_bytes(png_bytes())
        self.secret = secrets.token_urlsafe(48)
        self.environment = patch.dict(os.environ, {
            'MARKET_REPORT_VISION_HMAC_KEY': self.secret,
            'MARKET_REPORT_TRUSTED_VISION_PROVIDER': FIXTURE_PROVIDER_ID,
        }, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)

    def make_review(self, report=None, candidate=None, image=None, provider=None):
        return sign_review(report or self.report, candidate or self.candidate,
            image or self.image, 'doc-fixture-1', 'drive-image-fixture-1',
            provider or FixtureVisionProvider())

    def test_01_fixture_signs_complete_review(self):
        self.assertEqual(self.make_review()['status'], 'VERIFIED')

    def test_02_existing_python_validator_accepts_signed_review(self):
        review = self.make_review()
        self.assertEqual(validate_image(self.report, self.candidate, str(self.image), review)['status'], 'PASS')

    def test_03_dynamic_apps_script_verifies_review_and_payload(self):
        review = self.make_review()
        review_path = self.directory / 'review.json'
        payload_path = self.directory / 'payload.txt'
        review_path.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
        with payload_path.open('w', encoding='utf-8', newline='') as stream:
            stream.write(vision_attestation_payload(review))
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node.js is required for cross-runtime verification')
        result = subprocess.run([node, 'scripts/test_apps_script_signed_review.js', str(review_path), str(payload_path)],
            cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, encoding='utf-8', check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(self.secret, result.stdout + result.stderr)

    def test_04_body_tamper_is_rejected(self):
        review = self.make_review()
        changed = dict(self.report, fullText=self.report['fullText'] + '改変')
        with self.assertRaises(ValidationFailure):
            validate_image(changed, self.candidate, str(self.image), review)

    def test_05_title_tamper_is_rejected(self):
        review = self.make_review()
        changed = dict(self.report, title=self.report['title'] + '改変')
        with self.assertRaises(ValidationFailure):
            validate_image(changed, self.candidate, str(self.image), review)

    def test_06_report_id_tamper_is_rejected(self):
        review = self.make_review()
        review['report_id'] = '2026-10-06_16-00'
        with self.assertRaises(ValidationFailure):
            validate_image(self.report, self.candidate, str(self.image), review)

    def test_07_image_byte_tamper_is_rejected(self):
        review = self.make_review()
        changed = self.directory / 'changed.png'
        changed.write_bytes(png_bytes() + b'\x00')
        with self.assertRaises(ValidationFailure):
            validate_image(self.report, self.candidate, str(changed), review)

    def test_08_apps_script_rejects_drive_id_tamper(self):
        self.test_03_dynamic_apps_script_verifies_review_and_payload()

    def test_09_source_document_id_tamper_is_rejected(self):
        review = self.make_review()
        review['source_document_id'] = 'different-document'
        with self.assertRaises(ValidationFailure):
            validate_image(self.report, self.candidate, str(self.image), review)

    def test_10_provider_mismatch_is_rejected(self):
        review = self.make_review()
        review['provider'] = 'other-provider'
        with self.assertRaises(ValidationFailure):
            validate_image(self.report, self.candidate, str(self.image), review)

    def test_11_signature_tamper_is_rejected(self):
        review = self.make_review()
        review['signature'] = '0' * 64
        with self.assertRaises(ValidationFailure):
            validate_image(self.report, self.candidate, str(self.image), review)

    def test_12_short_key_is_rejected(self):
        with patch.dict(os.environ, {'MARKET_REPORT_VISION_HMAC_KEY': 'short'}):
            with self.assertRaisesRegex(VisionSignerFailure, 'VISION_ATTESTATION_KEY_INVALID'):
                self.make_review()

    def test_13_missing_secret_is_rejected(self):
        with patch.dict(os.environ, {'MARKET_REPORT_VISION_HMAC_KEY': ''}):
            with self.assertRaisesRegex(VisionSignerFailure, 'VISION_PROVIDER_NOT_CONFIGURED'):
                self.make_review()

    def test_14_missing_provider_is_rejected(self):
        with patch.dict(os.environ, {'MARKET_REPORT_TRUSTED_VISION_PROVIDER': ''}):
            with self.assertRaisesRegex(VisionSignerFailure, 'VISION_PROVIDER_NOT_CONFIGURED'):
                self.make_review()

    def test_15_missing_required_provider_check_is_invalid(self):
        value = {name: 'PASS' for name in REQUIRED_VISION_CHECKS}
        value.pop('numbers_match')
        with self.assertRaisesRegex(VisionProviderFailure, 'VISION_OUTPUT_SCHEMA_INVALID'):
            VisionReviewResult.parse(value)

    def test_16_numbers_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('numbers_match', 'FAIL')))

    def test_17_numbers_uncertain_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_UNCERTAIN'):
            self.make_review(provider=VerdictProvider(('numbers_match', 'UNCERTAIN')))

    def test_18_decorative_chart_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('decorative_charts', 'FAIL')))

    def test_19_gauge_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('gauges', 'FAIL')))

    def test_20_people_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('people', 'FAIL')))

    def test_21_text_overflow_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('text_overflow', 'FAIL')))

    def test_22_major_typo_fail_blocks_signature(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'VISION_REVIEW_FAILED'):
            self.make_review(provider=VerdictProvider(('major_typos', 'FAIL')))

    def test_23_fixture_provider_forbidden_for_real_identity(self):
        with patch.dict(os.environ, {'MARKET_REPORT_TRUSTED_VISION_PROVIDER': 'approved-real-provider'}):
            with self.assertRaisesRegex(VisionSignerFailure, 'VISION_FIXTURE_PROVIDER_FORBIDDEN'):
                self.make_review()

    def test_24_payload_contract_has_exact_existing_field_order(self):
        review = self.make_review()
        lines = vision_attestation_payload(review).splitlines()
        self.assertEqual([line.split('=', 1)[0] for line in lines], [
            'schema', 'status', 'provider', 'review_id', 'report_id', 'title', 'source_sha256',
            'image_sha256', 'source_document_id', 'drive_image_file_id', 'reviewed_at', 'checks'])

    def test_25_cli_never_emits_or_serializes_secret(self):
        report_path = self.directory / 'report.json'
        spec_path = self.directory / 'spec.json'
        output = self.directory / 'マーケットレポート_2026-10-06_12-00.vision-review.json'
        report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding='utf-8')
        spec_path.write_text(json.dumps(self.candidate, ensure_ascii=False), encoding='utf-8')
        cli_env = os.environ.copy()
        cli_env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run([sys.executable, 'scripts/sign_market_report_vision_review.py',
            '--report', str(report_path), '--spec', str(spec_path), '--image', str(self.image),
            '--source-document-id', 'doc-fixture-1', '--drive-image-file-id', 'drive-image-fixture-1',
            '--output', str(output), '--provider', 'fixture', '--dry-run'], cwd=ROOT,
            env=cli_env, capture_output=True, text=True, encoding='utf-8', check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        serialized = output.read_text(encoding='utf-8')
        self.assertNotIn(self.secret, serialized + result.stdout + result.stderr)
        self.assertNotIn('signature key', serialized.lower())
        self.assertEqual(json.loads(result.stdout)['production_write'], False)

    def test_26_existing_output_is_never_overwritten(self):
        review = self.make_review()
        output = self.directory / 'review.json'
        output.write_text('existing\n', encoding='utf-8')
        with self.assertRaisesRegex(VisionSignerFailure, 'OUTPUT_ALREADY_EXISTS'):
            write_review(review, output)
        self.assertEqual(output.read_text(encoding='utf-8'), 'existing\n')

    def test_27_protected_report_path_is_rejected(self):
        with self.assertRaisesRegex(VisionSignerFailure, 'PROTECTED_OUTPUT_PATH'):
            write_review({}, ROOT / 'reports.json')


if __name__ == '__main__':
    unittest.main()
