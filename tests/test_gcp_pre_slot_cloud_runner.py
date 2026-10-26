import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.reporting.slot_recovery_contract import ContractError
from scripts.gcp.pre_slot_cloud_runner import (
    GCSAttemptLedger, GCSPrivateEvidenceStore, build_internal_trigger,
    parse_schedule_time, process_test_only_request,
)

JST = ZoneInfo("Asia/Tokyo")


class FakeStore:
    def __init__(self, attempt_id):
        self.attempt_id = attempt_id
        self.data = {}
        self.generations = {}
    def put_if_absent(self, key, value):
        if key in self.data:
            raise ContractError("EVIDENCE_IMMUTABLE_CONFLICT")
        self.data[key] = value
        self.generations[key] = 1
    def read(self, key):
        return self.data[key]
    def delete_if_same_generation(self, key):
        self.data.pop(key, None)
        return True


class PreconditionFailed(Exception):
    code = 412


class FakeBlob:
    def __init__(self, bucket, name, generation=None):
        self.bucket, self.name, self.requested_generation = bucket, name, generation
        self.generation = None
    def upload_from_string(self, value, content_type=None, if_generation_match=None):
        if self.name in self.bucket.objects:
            raise PreconditionFailed()
        self.bucket.objects[self.name] = (1, bytes(value))
        self.generation = 1
    def reload(self):
        self.generation = self.bucket.objects[self.name][0]
    def download_as_bytes(self, if_generation_match=None):
        generation, value = self.bucket.objects[self.name]
        if generation != self.requested_generation or generation != if_generation_match:
            raise AssertionError("readback not pinned to exact generation")
        return value
    def delete(self, if_generation_match=None):
        if self.bucket.objects[self.name][0] != if_generation_match:
            raise AssertionError("delete generation mismatch")
        del self.bucket.objects[self.name]


class FakeBucket:
    def __init__(self):
        self.objects = {}
    def blob(self, name, generation=None):
        return FakeBlob(self, name, generation)


class CloudRunnerContractTests(unittest.TestCase):
    job = "projects/test-project/locations/asia-northeast1/jobs/test-0747"
    when = "2026-10-19T07:47:00+09:00"
    start = datetime.fromisoformat("2026-10-19T07:47:10+09:00")
    allowed = {job: "scheduler-0747@test-project.iam.gserviceaccount.com"}

    def test_scheduler_time_is_not_used_as_actual_start(self):
        payload = build_internal_trigger(self.job, self.when, self.start)
        self.assertEqual(payload["triggeredAt"], self.start.isoformat())
        self.assertEqual(payload["scheduledAt"], self.when)
        self.assertEqual(payload["reportDate"], "2026-10-19")

    def test_success_uses_exact_trigger_auth_and_private_readback(self):
        stored = {}
        def claim(payload):
            stored["ledger"] = dict(payload)
            return "test-only/ledger/claimed.json"
        def acquire(trigger):
            return b'{"fixture":"acquisition"}'
        # Existing capture is isolated behind this seam; normal logic below
        # replaces it in cloud runtime and never receives Docs/main credentials.
        from unittest.mock import patch
        fake_result = {
            "status": "PASS_TEST_ONLY", "attemptId": "sched-fixture",
            "reportId": "2026-10-19_08-00", "revision": 1, "evidenceId": "a" * 64,
            "snapshotHash": "b" * 64, "contextHash": "c" * 64, "sourceHash": "d" * 64,
            "capturedAt": "2026-10-19T07:46:00+09:00", "readbackSha256": "e" * 64,
            "readback": "PASS_EXACT_BYTES", "mainReadback": "NOT_RUN_TEST_ONLY_PRIVATE_STORE",
        }
        import scripts.gcp.pre_slot_cloud_runner as runner
        with patch.object(runner, "execute_test_only_capture", return_value=fake_result):
            result = process_test_only_request(
                {"Authorization": "Bearer test", "X-CloudScheduler-JobName": self.job,
                 "X-CloudScheduler-ScheduleTime": self.when}, b"{}",
                actual_start=self.start, allowed_callers=self.allowed, audience="https://runner",
                secret=b"x" * 32, verify_oidc=lambda token, aud: self.allowed[self.job],
                claim_attempt=claim, acquire=acquire,
                store_factory=lambda attempt: FakeStore(attempt),
                clock=lambda: self.start,
            )
        self.assertEqual(result["status"], "PASS_TEST_ONLY")
        self.assertEqual(result["mainReadback"], "NOT_RUN_TEST_ONLY_NO_MAIN_WRITE")
        self.assertEqual(result["docsWrite"], "NOT_RUN_TEST_ONLY_NO_DOCS_WRITE")
        self.assertIn("ledger", stored)

    def test_bad_oidc_and_allowlist_fail_before_claim(self):
        claimed = []
        def claim(payload):
            claimed.append(payload)
            return "ledger"
        with self.assertRaisesRegex(ContractError, "SCHEDULER_CALLER_NOT_ALLOWLISTED"):
            process_test_only_request(
                {"Authorization": "Bearer test", "X-CloudScheduler-JobName": self.job,
                 "X-CloudScheduler-ScheduleTime": self.when}, b"{}",
                actual_start=self.start, allowed_callers=self.allowed, audience="https://runner",
                secret=b"x" * 32, verify_oidc=lambda token, aud: "wrong@example.com",
                claim_attempt=claim, acquire=lambda trigger: b"{}",
                store_factory=lambda attempt: FakeStore(attempt), clock=lambda: self.start,
            )
        self.assertEqual(claimed, [])

    def test_bad_signature_is_rejected_by_existing_contract(self):
        from scripts.reporting.slot_recovery_contract import verify_pre_slot_trigger
        payload = build_internal_trigger(self.job, self.when, self.start)
        from scripts.reporting.slot_recovery_contract import sign_trigger_request
        signature = sign_trigger_request(payload, b"x" * 32)
        with self.assertRaisesRegex(ContractError, "TRIGGER_SIGNATURE_INVALID"):
            verify_pre_slot_trigger(payload, signature, b"y" * 32, now=self.start)

    def test_delayed_runner_fails_closed_before_claim(self):
        claimed = []
        late = datetime.fromisoformat("2026-10-19T07:48:01+09:00")
        with self.assertRaisesRegex(ContractError, "TRIGGER_START_DELAY_EXCEEDED"):
            process_test_only_request(
                {"Authorization": "Bearer test", "X-CloudScheduler-JobName": self.job,
                 "X-CloudScheduler-ScheduleTime": self.when}, b"{}",
                actual_start=late, allowed_callers=self.allowed, audience="https://runner",
                secret=b"x" * 32, verify_oidc=lambda token, aud: self.allowed[self.job],
                claim_attempt=lambda payload: claimed.append(payload),
                acquire=lambda trigger: b"{}", store_factory=lambda attempt: FakeStore(attempt),
                clock=lambda: late,
            )
        self.assertEqual(claimed, [])

    def test_private_gcs_store_uses_create_only_and_generation_pinned_readback(self):
        bucket = FakeBucket()
        store = GCSPrivateEvidenceStore(bucket, "test-only/08-00", "attempt-123")
        key = "a" * 64
        payload = b"immutable-evidence"
        store.put_if_absent(key, payload)
        self.assertEqual(store.read(key), payload)
        with self.assertRaisesRegex(ContractError, "EVIDENCE_IMMUTABLE_CONFLICT"):
            store.put_if_absent(key, payload)
        self.assertTrue(store.delete_if_same_generation(key))
        self.assertEqual(bucket.objects, {})

    def test_gcs_attempt_ledger_rejects_duplicate_scheduler_delivery(self):
        bucket = FakeBucket()
        ledger = GCSAttemptLedger(bucket, "test-only/08-00")
        payload = build_internal_trigger(self.job, self.when, self.start)
        ledger.claim(payload)
        with self.assertRaisesRegex(ContractError, "TEST_ATTEMPT_ALREADY_CLAIMED"):
            ledger.claim(payload)

    def test_wrong_schedule_and_body_are_rejected(self):
        with self.assertRaisesRegex(ContractError, "SCHEDULER_TIME_OUT_OF_SCOPE"):
            build_internal_trigger(self.job, "2026-10-19T07:46:00+09:00", self.start)
        with self.assertRaisesRegex(ContractError, "REQUEST_BODY_NOT_ALLOWED"):
            process_test_only_request(
                {"Authorization": "Bearer test", "X-CloudScheduler-JobName": self.job,
                 "X-CloudScheduler-ScheduleTime": self.when}, b'{"mode":"LIVE"}',
                actual_start=self.start, allowed_callers=self.allowed, audience="https://runner",
                secret=b"x" * 32, verify_oidc=lambda token, aud: self.allowed[self.job],
                claim_attempt=lambda payload: self.fail("claim must not occur"),
                acquire=lambda trigger: b"{}", store_factory=lambda attempt: FakeStore(attempt),
                clock=lambda: self.start,
            )


if __name__ == "__main__":
    unittest.main()
