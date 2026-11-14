import hashlib
import unittest

from scripts.reporting.gcs_wif_readonly import (
    BUCKET_NAME,
    EXPECTED_SHA256,
    GENERATION,
    OBJECT_NAME,
    SERVICE_ACCOUNT_EMAIL,
    read_pinned_test_object,
)


class FakeBlob:
    def __init__(self, payload, generation):
        self.payload = payload
        self.generation = generation
        self.requested_generation = None
        self.reload_calls = 0
        self.download_calls = 0
        self.upload_calls = 0

    def reload(self):
        self.reload_calls += 1

    def download_as_bytes(self, *, if_generation_match):
        self.download_calls += 1
        self.requested_generation = if_generation_match
        if if_generation_match != self.generation:
            raise AssertionError("generation precondition required")
        return self.payload

    def upload_from_string(self, *args, **kwargs):
        self.upload_calls += 1
        raise AssertionError("read-only probe must never upload")


class FakeBucket:
    def __init__(self, blob):
        self.value = blob
        self.request = None

    def blob(self, name, *, generation):
        self.request = (name, generation)
        return self.value


class FakeClient:
    def __init__(self, payload, generation=GENERATION):
        self.blob_value = FakeBlob(payload, generation)
        self.bucket_request = None
        self.bucket_value = FakeBucket(self.blob_value)

    def bucket(self, name):
        self.bucket_request = name
        return self.bucket_value


class GcsWifReadonlyTests(unittest.TestCase):
    def test_reads_one_fixed_generation_and_checks_hash_without_writes(self):
        payload = b"fixture bytes are not the live object"
        expected = hashlib.sha256(payload).hexdigest()
        client = FakeClient(payload)
        result = read_pinned_test_object(
            client, SERVICE_ACCOUNT_EMAIL, expected_sha256=expected
        )
        self.assertEqual(client.bucket_request, BUCKET_NAME)
        self.assertEqual(client.bucket_value.request, (OBJECT_NAME, GENERATION))
        self.assertEqual(client.blob_value.requested_generation, GENERATION)
        self.assertEqual(result["generation"], GENERATION)
        self.assertEqual(result["sha256"], expected)
        self.assertEqual(client.blob_value.upload_calls, 0)

    def test_rejects_wrong_service_account_before_gcs_access(self):
        client = FakeClient(b"ignored")
        with self.assertRaisesRegex(PermissionError, "WIF_TEST_PRINCIPAL_MISMATCH"):
            read_pinned_test_object(client, "untrusted@example.test")
        self.assertIsNone(client.bucket_request)

    def test_rejects_wrong_generation(self):
        client = FakeClient(b"ignored", generation=GENERATION + 1)
        with self.assertRaisesRegex(ValueError, "WIF_TEST_GENERATION_MISMATCH"):
            read_pinned_test_object(client, SERVICE_ACCOUNT_EMAIL)
        self.assertEqual(client.blob_value.download_calls, 0)
        self.assertEqual(client.blob_value.upload_calls, 0)

    def test_rejects_hash_mismatch_without_write(self):
        client = FakeClient(b"different object bytes")
        with self.assertRaisesRegex(ValueError, "WIF_TEST_SHA256_MISMATCH"):
            read_pinned_test_object(client, SERVICE_ACCOUNT_EMAIL)
        self.assertEqual(client.blob_value.upload_calls, 0)

    def test_workflow_keeps_wif_probe_separate_and_read_only(self):
        from pathlib import Path

        workflow = Path(".github/workflows/freeze-report-slot-evidence.yml").read_text(encoding="utf-8")
        normal_job = workflow[workflow.index("  freeze:"):workflow.index("  test-wif-readonly:")]
        readonly_job = workflow[workflow.index("  test-wif-readonly:"):]
        self.assertIn("if: github.event_name == 'schedule' || inputs.operation == 'freeze_evidence'", normal_job)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.operation == 'test_wif_readonly'", readonly_job)
        self.assertIn("contents: read", readonly_job)
        self.assertIn("id-token: write", readonly_job)
        self.assertIn("google-github-actions/auth@v3", readonly_job)
        self.assertIn("python -m scripts.reporting.gcs_wif_readonly", readonly_job)
        self.assertNotIn("--persist-gcs", readonly_job)
        self.assertNotIn("upload_from_string", readonly_job)
        self.assertEqual(workflow.count('cron: "47,53,57 22 * * 0-4"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 2 * * 1-5"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 6 * * 1-5"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 11 * * 1-5"'), 1)

if __name__ == "__main__":
    unittest.main()
