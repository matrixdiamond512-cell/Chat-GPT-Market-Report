import hashlib
import unittest

from scripts.reporting.gcs_wif_create_only import (
    BUCKET_NAME,
    EXPECTED_REF,
    EXPECTED_REPOSITORY,
    OBJECT_PREFIX,
    SERVICE_ACCOUNT_EMAIL,
    create_and_readback_probe,
)

COMMIT = "a" * 40
RUN_ID = "42000000001"


class PreconditionFailed(Exception):
    code = 412


class FakeStore:
    def __init__(self):
        self.objects = {}
        self.next_generation = 777001
        self.upload_calls = 0
        self.delete_calls = 0


class FakeBlob:
    def __init__(self, store, name):
        self.store = store
        self.name = name
        self.generation = None
        self.upload_precondition = None
        self.read_precondition = None
        self.corrupt_readback = False

    def upload_from_string(self, payload, *, content_type, if_generation_match):
        self.store.upload_calls += 1
        self.upload_precondition = if_generation_match
        if if_generation_match != 0:
            raise AssertionError("create-only precondition is required")
        if self.name in self.store.objects:
            raise PreconditionFailed()
        self.store.objects[self.name] = (payload, self.store.next_generation)
        self.generation = self.store.next_generation
        self.store.next_generation += 1

    def reload(self):
        payload, generation = self.store.objects[self.name]
        self.generation = generation
        return payload

    def download_as_bytes(self, *, if_generation_match):
        self.read_precondition = if_generation_match
        payload, generation = self.store.objects[self.name]
        if if_generation_match != generation:
            raise AssertionError("readback must pin the observed generation")
        if self.corrupt_readback:
            return payload + b"tampered"
        return payload


class FakeBucket:
    def __init__(self, store):
        self.store = store
        self.blobs = {}

    def blob(self, name):
        self.blobs.setdefault(name, FakeBlob(self.store, name))
        return self.blobs[name]


class FakeClient:
    def __init__(self):
        self.store = FakeStore()
        self.bucket_name = None
        self.bucket_value = FakeBucket(self.store)

    def bucket(self, name):
        self.bucket_name = name
        return self.bucket_value


def run_probe(client, **overrides):
    values = {
        "run_id": RUN_ID,
        "repository": EXPECTED_REPOSITORY,
        "ref": EXPECTED_REF,
        "commit_sha": COMMIT,
    }
    values.update(overrides)
    return create_and_readback_probe(client, SERVICE_ACCOUNT_EMAIL, **values)


class GcsWifCreateOnlyTests(unittest.TestCase):
    def test_creates_once_with_generation_zero_and_reads_exact_generation(self):
        client = FakeClient()
        result = run_probe(client)
        blob = client.bucket_value.blobs[f"{OBJECT_PREFIX}{RUN_ID}.json"]
        self.assertEqual(client.bucket_name, BUCKET_NAME)
        self.assertEqual(blob.upload_precondition, 0)
        self.assertEqual(blob.read_precondition, result["generation"])
        self.assertTrue(result["created"])
        self.assertEqual(
            result["sha256"],
            hashlib.sha256(client.store.objects[blob.name][0]).hexdigest(),
        )
        self.assertEqual(client.store.upload_calls, 1)
        self.assertEqual(client.store.delete_calls, 0)

    def test_identical_retry_reads_existing_object_without_overwrite(self):
        client = FakeClient()
        first = run_probe(client)
        second = run_probe(client)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(client.store.upload_calls, 2)
        self.assertEqual(client.store.delete_calls, 0)

    def test_existing_different_bytes_are_rejected_without_overwrite(self):
        client = FakeClient()
        first = run_probe(client)
        blob = client.bucket_value.blobs[first["object"]]
        client.store.objects[first["object"]] = (b"different bytes", first["generation"])
        with self.assertRaisesRegex(ValueError, "WIF_TEST_EXISTING_OBJECT_CONFLICT"):
            run_probe(client)
        self.assertEqual(client.store.upload_calls, 2)
        self.assertEqual(client.store.objects[first["object"]][0], b"different bytes")
        self.assertEqual(client.store.delete_calls, 0)

    def test_wrong_principal_is_rejected_before_gcs_access(self):
        client = FakeClient()
        with self.assertRaisesRegex(PermissionError, "WIF_TEST_PRINCIPAL_MISMATCH"):
            create_and_readback_probe(
                client,
                "wrong@example.test",
                run_id=RUN_ID,
                repository=EXPECTED_REPOSITORY,
                ref=EXPECTED_REF,
                commit_sha=COMMIT,
            )
        self.assertIsNone(client.bucket_name)

    def test_wrong_repository_ref_or_commit_is_rejected_before_gcs_access(self):
        for kwargs, message in (
            ({"repository": "other/repo"}, "WIF_TEST_REPOSITORY_OR_REF_MISMATCH"),
            ({"ref": "refs/heads/main"}, "WIF_TEST_REPOSITORY_OR_REF_MISMATCH"),
            ({"commit_sha": "bad"}, "WIF_TEST_COMMIT_SHA_INVALID"),
        ):
            with self.subTest(kwargs=kwargs):
                client = FakeClient()
                with self.assertRaises((PermissionError, ValueError), msg=message):
                    run_probe(client, **kwargs)
                self.assertIsNone(client.bucket_name)

    def test_invalid_run_id_is_rejected_before_gcs_access(self):
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "WIF_TEST_RUN_ID_INVALID"):
            run_probe(client, run_id="../main")
        self.assertIsNone(client.bucket_name)

    def test_readback_mismatch_is_detected(self):
        client = FakeClient()
        blob = client.bucket(BUCKET_NAME).blob(f"{OBJECT_PREFIX}{RUN_ID}.json")
        blob.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, "WIF_TEST_READBACK_MISMATCH"):
            run_probe(client)


class CreateOnlyWorkflowIsolationTests(unittest.TestCase):
    def test_write_probe_is_independently_gated_and_does_not_enable_freeze(self):
        from pathlib import Path

        workflow = Path(".github/workflows/freeze-report-slot-evidence.yml").read_text(encoding="utf-8")
        self.assertIn('"test_wif_create_only"', workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.operation == 'test_wif_create_only' && github.ref == 'refs/heads/codex/0800-main-issuance-e2e-20261029'", workflow)
        self.assertIn("if: github.event_name == 'schedule' || inputs.operation == 'freeze_evidence'", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("test-wif-create-only-${{ github.run_id }}", workflow)
        self.assertIn("python -m scripts.reporting.gcs_wif_create_only", workflow)
        self.assertEqual(workflow.count('cron: "47,53,57 22 * * 0-4"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 2 * * 1-5"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 6 * * 1-5"'), 1)
        self.assertEqual(workflow.count('cron: "47,53,57 11 * * 1-5"'), 1)

    def test_readonly_probe_remains_nonwriting(self):
        from pathlib import Path

        workflow = Path(".github/workflows/freeze-report-slot-evidence.yml").read_text(encoding="utf-8")
        read_only = workflow[workflow.index("  test-wif-readonly:"):workflow.index("  test-wif-create-only:")]
        self.assertIn("contents: read", read_only)
        self.assertNotIn("scripts.reporting.gcs_wif_create_only", read_only)
        self.assertNotIn("upload_from_string", read_only)


if __name__ == "__main__":
    unittest.main()
