import hashlib
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.reporting import cloud_run_testonly as runtime
from scripts.reporting.scheduler_reliability import JST
from scripts.reporting.test_only_evidence_store import (
    TEST_ONLY_BUCKET,
    TEST_ONLY_PREFIX,
    TestOnlyEvidenceStore,
    TestOnlyStorageError,
    TestOnlyConflict,
)


PRINCIPAL = "scheduler-caller@test-only.iam.gserviceaccount.com"
AUDIENCE = "https://market-report-test-only.invalid/evidence/16-00"
JOB_RESOURCE = "projects/test-project/locations/asia-northeast1/jobs/evidence-1600"


class FakeRequest:
    method = "POST"

    def __init__(self, headers=None, body=b""):
        self.headers = headers or {}
        self._body = body

    def get_data(self, *, cache=True, as_text=False):
        if as_text:
            return self._body.decode("utf-8")
        return self._body


class FakeStore:
    def __init__(self, evidence_state="ABSENT"):
        self.input_calls = []
        self.create_calls = []
        self.evidence_state = evidence_state

    def read_input(self, report_id):
        self.input_calls.append(report_id)
        raw = b'{"fixture":"input"}'
        return {
            "object": f"{TEST_ONLY_PREFIX}/inputs/{report_id}.json",
            "generation": 1001,
            "sha256": "a" * 64,
            "bytes": raw,
            "payload": {"fixture": "input"},
        }

    def create_evidence(self, report_date, report_slot, evidence):
        self.create_calls.append((report_date, report_slot, evidence))
        return {
            "object": f"{TEST_ONLY_PREFIX}/evidence/{report_date}_{report_slot.replace(':', '-')}-r1.json",
            "generation": 2002,
            "sha256": "b" * 64,
            "bytes": 20,
            "stored_at": "2026-11-11T06:00:00+00:00",
            "created": True,
            "report_id": f"{report_date}_{report_slot.replace(':', '-')}",
            "revision": 1,
            "evidence_id": "c" * 64,
        }

    def read_evidence(self, report_date, report_slot):
        return {"state": self.evidence_state, "object": "test-only/evidence/sample.json"}


class FakeLogging:
    def __init__(self, payload=None, fail=False):
        self.payload = payload
        self.fail = fail
        self.filters = []

    def list_entries(self, **kwargs):
        self.filters.append(kwargs)
        if self.fail:
            raise PermissionError("logging read denied")
        if self.payload is None:
            return iter(())
        class Entry:
            pass
        entry = Entry()
        entry.payload = self.payload
        return iter((entry,))


def request_for(*, job=None, schedule="2026-11-11T15:47:00+09:00", audience=AUDIENCE):
    return FakeRequest({
        "Authorization": "Bearer test-token",
        "X-CloudScheduler-JobName": job or JOB_RESOURCE.rsplit("/", 1)[-1],
        "X-CloudScheduler-ScheduleTime": schedule,
    }, body=b'{"reportId":"forged-ignored","principal":"attacker"}')


def verifier(token, audience):
    if token != "test-token":
        raise AssertionError("unexpected token")
    return {"email": PRINCIPAL, "email_verified": True, "aud": audience}


def producer_config():
    return {
        "test_only_environment": "TEST_ONLY",
        "service_mode": "producer",
        "oidc_audience": AUDIENCE,
        "expected_principal": PRINCIPAL,
        "expected_job_resource": JOB_RESOURCE,
        "expected_report_slot": "16:00",
        "test_only_bucket": TEST_ONLY_BUCKET,
        "test_only_prefix": TEST_ONLY_PREFIX,
        "producer_job_resource": JOB_RESOURCE,
        "producer_service_name": "evidence-1600",
    }


def watchdog_config():
    cfg = producer_config()
    cfg.update({
        "service_mode": "watchdog",
        "expected_job_resource": "projects/test-project/locations/asia-northeast1/jobs/watchdog-1600",
    })
    return cfg


class CloudRunSchedulerAdapterTests(unittest.TestCase):
    def test_oidc_requires_signed_expected_principal_and_audience(self):
        self.assertEqual(
            runtime.verify_scheduler_oidc(
                request_for().headers,
                audience=AUDIENCE,
                expected_principal=PRINCIPAL,
                verifier=verifier,
            ),
            PRINCIPAL,
        )
        with self.assertRaisesRegex(PermissionError, "TOKEN_MISSING"):
            runtime.verify_scheduler_oidc(
                {}, audience=AUDIENCE, expected_principal=PRINCIPAL, verifier=verifier
            )
        def wrong_principal(token, audience):
            return {"email": "other@example.com", "email_verified": True, "aud": audience}
        with self.assertRaisesRegex(PermissionError, "PRINCIPAL_MISMATCH"):
            runtime.verify_scheduler_oidc(
                request_for().headers, audience=AUDIENCE,
                expected_principal=PRINCIPAL, verifier=wrong_principal,
            )
        def wrong_audience(token, audience):
            return {"email": PRINCIPAL, "email_verified": True, "aud": "wrong"}
        with self.assertRaisesRegex(PermissionError, "AUDIENCE_MISMATCH"):
            runtime.verify_scheduler_oidc(
                request_for().headers, audience=AUDIENCE,
                expected_principal=PRINCIPAL, verifier=wrong_audience,
            )

    def test_producer_uses_schedule_headers_and_ignores_body_identity(self):
        store = FakeStore()
        fixed_start = datetime(2026, 11, 11, 15, 52, tzinfo=JST)
        with patch.object(runtime, "build_slot_evidence", return_value={"revision": 1, "reportId": "2026-11-11_16-00"}) as build, \
             patch("scripts.persist_report_slot_evidence.require_evidence_slot_guard"):
            result = runtime.dispatch_request(
                request_for(), producer_config(), verifier=verifier, store=store,
                clock=lambda: fixed_start,
            )
        body, status, headers = result
        decoded = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(decoded["reportId"], "2026-11-11_16-00")
        self.assertEqual(store.input_calls, ["2026-11-11_16-00"])
        self.assertEqual(len(store.create_calls), 1)
        self.assertEqual(build.call_args.kwargs["acquisition_path"],
                         f"gs://{TEST_ONLY_BUCKET}/{TEST_ONLY_PREFIX}/inputs/2026-11-11_16-00.json#1001")

    def test_full_resource_header_wrong_slot_and_late_run_fail_closed(self):
        for request, slot, expected in (
            (request_for(job=JOB_RESOURCE), "16:00", "job_name_mismatch"),
            (request_for(schedule="2026-11-11T15:30:00+09:00"), "16:00", "scheduled_at_not_allowed"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(runtime.ScheduleRequestError, expected):
                    runtime._producer(
                        request, {**producer_config(), "expected_report_slot": slot},
                        verifier=verifier, store=FakeStore(),
                        started_at=datetime(2026, 11, 11, 15, 52, tzinfo=JST),
                    )
        with self.assertRaisesRegex(runtime.ScheduleRequestError, "SCHEDULE_LATE"):
            runtime._producer(
                request_for(), producer_config(), verifier=verifier, store=FakeStore(),
                started_at=datetime(2026, 11, 11, 16, 0, tzinfo=JST),
            )

    def test_watchdog_independently_reads_absence_and_emits_no_notification(self):
        store = FakeStore("ABSENT")
        logs = FakeLogging()
        response = runtime._watchdog(
            request_for(
                job="watchdog-1600",
                schedule="2026-11-11T15:57:00+09:00",
            ),
            watchdog_config(),
            verifier=verifier,
            store=store,
            logging_client=logs,
            now=datetime(2026, 11, 11, 15, 58, tzinfo=JST),
        )
        self.assertEqual(response["state"], "WARNING_EVIDENCE_MISSING")
        self.assertEqual(response["notification"], "NOT_SENT")
        self.assertEqual(response["auditReadStatus"], "NO_ATTEMPT_FOUND")
        self.assertTrue(logs.filters)

    def test_watchdog_marks_audit_api_failure_unknown(self):
        logs = FakeLogging(fail=True)
        response = runtime._watchdog(
            request_for(job="watchdog-1600", schedule="2026-11-11T15:57:00+09:00"),
            watchdog_config(),
            verifier=verifier,
            store=FakeStore("VALID"),
            logging_client=logs,
            now=datetime(2026, 11, 11, 15, 58, tzinfo=JST),
        )
        self.assertEqual(response["state"], "EVIDENCE_STATE_UNKNOWN")
        self.assertEqual(response["notification"], "NOT_SENT")

    def test_watchdog_short_job_id_and_schedule_time_are_strict(self):
        for request, pattern in (
            (request_for(job="projects/test/jobs/watchdog-1600",
                         schedule="2026-11-11T15:57:00+09:00"), "job_name_mismatch"),
            (request_for(job="watchdog-1600",
                         schedule="2026-11-11T15:58:00+09:00"), "SCHEDULE_TIME_MISMATCH"),
        ):
            with self.subTest(pattern=pattern), self.assertRaisesRegex(runtime.ScheduleRequestError, pattern):
                runtime.validate_watchdog_invocation(
                    verified_principal=PRINCIPAL,
                    expected_principal=PRINCIPAL,
                    job_name=request.headers["X-CloudScheduler-JobName"],
                    expected_job_resource=watchdog_config()["expected_job_resource"],
                    report_slot="16:00",
                    schedule_time=request.headers["X-CloudScheduler-ScheduleTime"],
                    started_at=datetime(2026, 11, 11, 15, 58, tzinfo=JST),
                )

    def test_post_and_body_size_guards(self):
        class GetRequest(FakeRequest):
            method = "GET"
        self.assertIsNone(runtime._validate_http_request(FakeRequest()))
        self.assertEqual(runtime._validate_http_request(GetRequest())[1], 405)
        self.assertEqual(runtime._validate_http_request(FakeRequest(body=b"x" * (1024 * 1024 + 1)))[1], 413)


class FakeGcsState:
    def __init__(self):
        self.objects = {}
        self.next_generation = 7000
        self.created_at = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)


class PreconditionFailed(Exception):
    code = 412


class NotFound(Exception):
    code = 404


class FakeBlob:
    def __init__(self, state, name, generation=None):
        self.state = state
        self.name = name
        self.generation = generation
        self.time_created = None
        self.metadata = None
        self.upload_condition = None
        self.read_condition = None

    def upload_from_string(self, payload, *, content_type, if_generation_match):
        self.upload_condition = if_generation_match
        if if_generation_match != 0:
            raise AssertionError("GCS writes must be create-only")
        if self.name in self.state.objects:
            raise PreconditionFailed()
        generation = self.state.next_generation
        self.state.next_generation += 1
        self.state.objects[self.name] = (payload, generation, self.metadata)
        self.generation = generation

    def reload(self):
        if self.name not in self.state.objects:
            raise NotFound()
        payload, generation, _ = self.state.objects[self.name]
        self.generation = generation
        self.time_created = self.state.created_at
        return payload

    def download_as_bytes(self, *, if_generation_match):
        self.read_condition = if_generation_match
        payload, generation, _ = self.state.objects[self.name]
        if if_generation_match != generation:
            raise AssertionError("readback must pin exact generation")
        return payload


class FakeBucket:
    def __init__(self, state):
        self.state = state

    def blob(self, name, generation=None):
        return FakeBlob(self.state, name, generation)


class FakeClient:
    def __init__(self):
        self.state = FakeGcsState()

    def list_blobs(self, bucket_name, *, prefix, max_results):
        self.bucket_name = bucket_name
        if max_results <= 0:
            raise AssertionError("bounded listing required")
        return [
            type("ListedBlob", (), {"name": name, "generation": record[1]})()
            for name, record in sorted(self.state.objects.items())
            if name.startswith(prefix)
        ][:max_results]

    def bucket(self, name):
        self.bucket_name = name
        return FakeBucket(self.state)


class TestOnlyGcsStoreTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.store = TestOnlyEvidenceStore(
            self.client, bucket_name=TEST_ONLY_BUCKET, prefix=TEST_ONLY_PREFIX,
            clock=lambda: datetime(2026, 11, 11, 6, 45, tzinfo=timezone.utc),
        )

    @patch("scripts.reporting.test_only_evidence_store.validate_stored_slot_evidence")
    def test_create_only_generation_sha_and_readback(self, validator):
        validator.return_value = {"reportId": "2026-11-11_16-00", "revision": 1, "evidenceId": "c"}
        evidence = {"reportId": "2026-11-11_16-00", "revision": 1, "evidenceId": "c"}
        saved = self.store.create_evidence("2026-11-11", "16:00", evidence)
        self.assertEqual(saved["generation"], 7000)
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(len(saved["sha256"]), 64)
        self.assertEqual(saved["created"], True)
        object_state = next(iter(self.client.state.objects.values()))
        self.assertEqual(object_state[2]["report_id"], "2026-11-11_16-00")

    @patch("scripts.reporting.test_only_evidence_store.validate_stored_slot_evidence")
    def test_identical_retry_is_idempotent_and_conflicting_bytes_block(self, validator):
        validator.return_value = {"reportId": "2026-11-11_16-00", "revision": 1, "evidenceId": "c"}
        evidence = {"reportId": "2026-11-11_16-00", "revision": 1, "evidenceId": "c"}
        first = self.store.create_evidence("2026-11-11", "16:00", evidence)
        retry = self.store.create_evidence("2026-11-11", "16:00", evidence)
        self.assertTrue(first["created"])
        self.assertFalse(retry["created"])
        with self.assertRaises(TestOnlyConflict):
            self.store.create_evidence("2026-11-11", "16:00", {**evidence, "evidenceId": "d"})

    def test_create_stops_before_upload_after_cutoff(self):
        late = TestOnlyEvidenceStore(
            self.client, bucket_name=TEST_ONLY_BUCKET, prefix=TEST_ONLY_PREFIX,
            clock=lambda: datetime(2026, 11, 11, 7, 1, tzinfo=timezone.utc),
        )
        with self.assertRaisesRegex(TestOnlyStorageError, "SAVE_AFTER_CUTOFF"):
            late.create_evidence(
                "2026-11-11", "16:00",
                {"reportId": "2026-11-11_16-00", "revision": 1, "evidenceId": "c"},
            )
        self.assertEqual(self.client.state.objects, {})

    def test_wrong_bucket_and_prefix_are_rejected(self):
        with self.assertRaisesRegex(TestOnlyStorageError, "BUCKET_REQUIRED"):
            TestOnlyEvidenceStore(self.client, bucket_name="production")
        with self.assertRaisesRegex(TestOnlyStorageError, "PREFIX_REQUIRED"):
            TestOnlyEvidenceStore(self.client, bucket_name=TEST_ONLY_BUCKET, prefix="reports")

    @patch("scripts.reporting.test_only_evidence_store.validate_stored_slot_evidence")
    def test_watchdog_reports_absent_and_unknown_separately(self, validator):
        self.assertEqual(self.store.read_evidence("2026-11-11", "16:00")["state"], "ABSENT")
        class ForbiddenClient:
            def bucket(self, name):
                class Bucket:
                    def blob(self, name, generation=None):
                        class Blob:
                            def reload(self):
                                error = RuntimeError("denied")
                                error.code = 403
                                raise error
                        return Blob()
                return Bucket()
        forbidden = TestOnlyEvidenceStore(
            ForbiddenClient(), bucket_name=TEST_ONLY_BUCKET, prefix=TEST_ONLY_PREFIX
        )
        self.assertEqual(forbidden.read_evidence("2026-11-11", "16:00")["state"], "UNKNOWN")


    def test_attempt_is_logged_before_input_read_failure(self):
        class MissingInputStore(FakeStore):
            def read_input(self, report_id):
                raise runtime.TestOnlyStorageError("INPUT_MISSING")

        events = []
        fixed_start = datetime(2026, 11, 11, 15, 52, tzinfo=JST)
        with patch.object(runtime, "_emit", side_effect=lambda event, **fields: events.append((event, fields))):
            result = runtime.dispatch_request(
                request_for(), producer_config(), verifier=verifier,
                store=MissingInputStore(), clock=lambda: fixed_start,
            )
        self.assertEqual(result[1], 422)
        attempt_events = [fields for event, fields in events if event == "evidence_attempt"]
        self.assertEqual(len(attempt_events), 1)
        self.assertEqual(attempt_events[0]["outcome"], "STARTED")
        self.assertEqual(attempt_events[0]["report_id"], "2026-11-11_16-00")
        self.assertEqual(attempt_events[0]["attempt_id"], f"{JOB_RESOURCE}@2026-11-11T06:47:00+00:00")


    @patch("scripts.reporting.test_only_evidence_store.validate_stored_slot_evidence")
    def test_live_watchdog_reads_only_ledger_linked_pinned_evidence(self, validator):
        validator.return_value = {
            "reportId": "2026-11-11_08-00", "revision": 1,
            "evidenceId": "evidence-id", "evidenceStatus": "READY_FOR_DRAFT",
            "acquisitionSource": {"overallStatus": "verified"},
        }
        attempt = "sched-" + "a" * 32
        ledger_name = (
            f"test-only/08-00/ledger/2026-11-11_08-00/{attempt}.json"
        )
        ledger = json.dumps({
            "schemaVersion": "market-report-pre-slot-trigger/v1",
            "executionMode": "TEST_ONLY", "reportDate": "2026-11-11",
            "reportSlot": "08:00", "attemptId": attempt,
            "scheduledAt": "2026-11-11T07:47:00+09:00",
            "triggeredAt": "2026-11-11T07:47:03+09:00",
        }).encode()
        payload = b"pinned Evidence bytes"
        evidence_name = (
            f"test-only/08-00/evidence/{attempt}/"
            f"{hashlib.sha256(payload).hexdigest()}.json"
        )
        self.client.state.objects[ledger_name] = (ledger, 7001, None)
        self.client.state.objects[evidence_name] = (payload, 7002, None)
        self.client.state.created_at = datetime(2026, 11, 10, 22, 48, tzinfo=timezone.utc)

        result = self.store.read_pre_slot_evidence("2026-11-11", "08:00")

        self.assertEqual(result["state"], "VALID")
        self.assertEqual(result["generation"], 7002)
        self.assertEqual(result["attempt_id"], attempt)
        self.assertEqual(result["sha256"], __import__("hashlib").sha256(payload).hexdigest())
        self.assertEqual(validator.call_args.args[0], payload)
        self.assertEqual(self.client.state.objects[evidence_name][1], 7002)

    @patch("scripts.reporting.test_only_evidence_store.validate_stored_slot_evidence")
    def test_live_watchdog_fails_closed_on_sha_mismatch_and_non_08_slot(self, validator):
        attempt = "sched-" + "b" * 32
        ledger_name = f"test-only/08-00/ledger/2026-11-11_08-00/{attempt}.json"
        ledger = json.dumps({
            "schemaVersion": "market-report-pre-slot-trigger/v1",
            "executionMode": "TEST_ONLY", "reportDate": "2026-11-11",
            "reportSlot": "08:00", "attemptId": attempt,
            "scheduledAt": "2026-11-11T07:47:00+09:00",
            "triggeredAt": "2026-11-11T07:47:03+09:00",
        }).encode()
        self.client.state.objects[ledger_name] = (ledger, 7003, None)
        self.client.state.created_at = datetime(2026, 11, 10, 22, 48, tzinfo=timezone.utc)
        evidence_name = f"test-only/08-00/evidence/{attempt}/{'0' * 64}.json"
        self.client.state.objects[evidence_name] = (b"tampered", 7004, None)

        mismatch = self.store.read_pre_slot_evidence("2026-11-11", "08:00")
        unsupported = self.store.read_pre_slot_evidence("2026-11-11", "12:00")

        self.assertEqual(mismatch["state"], "INVALID")
        self.assertEqual(unsupported["state"], "UNKNOWN")

if __name__ == "__main__":
    unittest.main()
