from datetime import datetime, timezone
import inspect
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from google.cloud.storage import Blob, Bucket
from scripts.report_continuity_gcs import GcsShadowStorage
from scripts.report_continuity_shadow import EvidenceWriter
from scripts.resolve_market_report_slot import resolve_report_identity

KEY = 'shadow/2026-10-16_21-00/evidence'
NOW = datetime(2026, 10, 16, 11, 50, tzinfo=timezone.utc)


class GcsSdkCompatibilityTests(unittest.TestCase):
    def test_installed_sdk_exposes_adapter_parameters(self):
        requirements = {
            Bucket.blob: {'generation'},
            Bucket.get_blob: {'timeout', 'retry'},
            Blob.upload_from_string: {
                'content_type', 'if_generation_match', 'timeout', 'retry', 'checksum',
            },
            Blob.download_as_bytes: {
                'if_generation_match', 'timeout', 'retry',
            },
        }
        for method, expected in requirements.items():
            with self.subTest(method=method.__qualname__):
                self.assertTrue(expected.issubset(inspect.signature(method).parameters))


class GcsShadowStorageTests(unittest.TestCase):
    def setUp(self):
        self.bucket = Mock()
        self.upload = Mock(generation='17', time_created=NOW)
        self.pinned = Mock()
        self.pinned.download_as_bytes.return_value = b'fixture'
        self.bucket.blob.side_effect = lambda name, **kw: self.pinned if kw else self.upload
        self.bucket.get_blob.return_value = SimpleNamespace(generation='17', time_created=NOW)
        self.store = GcsShadowStorage(self.bucket, enabled=True)

    def test_disabled_by_default_has_no_io(self):
        for method in ('create', 'read'):
            store = GcsShadowStorage(self.bucket)
            with self.assertRaisesRegex(RuntimeError, 'DISABLED'):
                getattr(store, method)(KEY, b'a') if method == 'create' else store.read(KEY)
        self.assertEqual(self.bucket.mock_calls, [])

    def test_only_shadow_keys(self):
        for key in ('data/report-evidence/x', '../reports/x', KEY+'/../x', '/'+KEY):
            with self.assertRaises(ValueError):
                self.store.read(key)
        self.assertEqual(self.bucket.mock_calls, [])

    def test_create_is_create_only_without_sdk_retry(self):
        result = self.store.create(KEY, b'fixture')
        self.upload.upload_from_string.assert_called_once_with(
            b'fixture', content_type='application/octet-stream',
            if_generation_match=0, timeout=10, retry=None, checksum=None)
        self.assertEqual(result.generation, 17)
        self.assertEqual(result.committed_at, NOW)

    def test_read_pins_generation(self):
        self.assertEqual(self.store.read(KEY).data, b'fixture')
        self.bucket.blob.assert_called_with(KEY, generation=17)
        self.pinned.download_as_bytes.assert_called_once_with(
            if_generation_match=17, timeout=10, retry=None)

    def test_412_is_conflict_but_other_errors_propagate(self):
        class HttpError(Exception):
            def __init__(self, code):
                self.code = code
        for code in (412, 403, 500):
            self.upload.upload_from_string.side_effect = HttpError(code)
            with self.assertRaises(FileExistsError if code == 412 else HttpError):
                self.store.create(KEY, b'fixture')

    def test_missing_object(self):
        self.bucket.get_blob.return_value = None
        with self.assertRaises(FileNotFoundError):
            self.store.read(KEY)

    def test_reject_invalid_metadata(self):
        for generation, timestamp in [
            ('0', NOW), ('17', None), ('17', NOW.replace(tzinfo=None)),
        ]:
            self.bucket.get_blob.return_value = SimpleNamespace(
                generation=generation, time_created=timestamp)
            with self.assertRaises(ValueError):
                self.store.read(KEY)

    def test_writer_reads_back_sdk_bytes(self):
        identity = resolve_report_identity(
            schedule_time_utc='2026-10-16T11:47:00Z', attempt_minutes=13, now=NOW)
        writer = EvidenceWriter(self.store, lambda: NOW)
        self.assertEqual(writer.write(identity, b'fixture')['status'], 'CREATED')
        self.pinned.download_as_bytes.return_value = b'corrupt'
        self.assertEqual(writer.write(identity, b'fixture')['status'], 'CONFLICT')

    def test_uncertain_upload_then_retry_reconciles(self):
        class Precondition(Exception):
            code = 412
        identity = resolve_report_identity(
            schedule_time_utc='2026-10-16T11:47:00Z', attempt_minutes=13, now=NOW)
        writer = EvidenceWriter(self.store, lambda: NOW)
        self.upload.upload_from_string.side_effect = TimeoutError('response lost')
        with self.assertRaises(TimeoutError):
            writer.write(identity, b'fixture')
        self.upload.upload_from_string.side_effect = Precondition()
        self.assertEqual(writer.write(identity, b'fixture')['status'], 'NO_OP')


if __name__ == '__main__':
    unittest.main()
