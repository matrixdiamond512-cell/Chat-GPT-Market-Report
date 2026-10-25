import io
import json
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from scripts.report_continuity_ingress import (
    SCHEDULER_TRIGGER_BODY, SchedulerBinding, create_app, single_binding_map,
)
from scripts.report_continuity_shadow import (
    EvidenceWriter, FakeStorage, JobCoordinator,
)
from scripts.resolve_market_report_slot import ReportIdentity
from scripts.run_report_continuity_service import build_app

AUDIENCE = "https://p1-shadow-test.run.app"
JOB = "projects/test-project/locations/asia-northeast1/jobs/slot-0800-t13"
CALLER = "p1-scheduler-0800-t13@test-project.iam.gserviceaccount.com"
NOW = datetime(2026, 10, 26, 22, 48, tzinfo=timezone.utc)  # Tuesday 07:48 JST
SCHEDULE = "2026-10-26T22:47:00Z"  # T-13 for Tuesday 08:00 JST


def run_request(app, *, token="valid", job=JOB, schedule=SCHEDULE, body=None,
                method="POST", content_type="application/json", extra_headers=None):
    raw = SCHEDULER_TRIGGER_BODY if body is None else json.dumps(body, separators=(",", ":")).encode()
    environ = {}
    from wsgiref.util import setup_testing_defaults
    setup_testing_defaults(environ)
    environ.update({
        "REQUEST_METHOD": method,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
        "HTTP_X_CLOUDSCHEDULER_JOBNAME": job,
        "HTTP_X_CLOUDSCHEDULER_SCHEDULETIME": schedule,
    })
    environ.update(extra_headers or {})
    captured = {}
    def start_response(status, headers):
        captured.update(status=status, headers=dict(headers))
    result = b"".join(app(environ, start_response))
    return captured["status"], json.loads(result)


class CloudRunIngressTests(unittest.TestCase):
    def setUp(self):
        self.processor = Mock(return_value={"status": "CREATED", "publicationEligible": False})
        self.verifier = Mock(return_value={
            "iss": "https://accounts.google.com", "aud": AUDIENCE,
            "email": CALLER, "email_verified": True,
        })
        self.binding = SchedulerBinding(JOB, CALLER, 13, "08:00")
        self.app = create_app(
            bindings={JOB: self.binding}, audience=AUDIENCE,
            processor=self.processor, verifier=self.verifier, clock=lambda: NOW,
        )

    def test_fixed_scheduler_body_derives_identity_for_two_business_days(self):
        cases = (
            ("2026-10-26T22:47:00Z", datetime(2026, 10, 26, 22, 48, tzinfo=timezone.utc),
             "2026-10-27_08-00"),
            ("2026-10-27T22:47:00Z", datetime(2026, 10, 27, 22, 48, tzinfo=timezone.utc),
             "2026-10-28_08-00"),
        )
        for schedule, current, expected_id in cases:
            app = create_app(
                bindings={JOB: self.binding}, audience=AUDIENCE,
                processor=self.processor, verifier=self.verifier, clock=lambda current=current: current,
            )
            status, result = run_request(app, schedule=schedule)
            self.assertEqual(status, "200 OK")
            self.assertEqual(result["status"], "CREATED")
            identity, body, binding = self.processor.call_args.args
            self.assertEqual(identity.report_id, expected_id)
            self.assertEqual(body, SCHEDULER_TRIGGER_BODY)
            self.assertEqual(binding.attempt_minutes, 13)
        self.assertEqual(self.processor.call_count, 2)

    def test_valid_oidc_request_binds_job_slot_time_and_attempt(self):
        status, result = run_request(self.app)
        self.assertEqual(status, "200 OK")
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(self.processor.call_args.args[0].report_id, "2026-10-27_08-00")
        self.assertEqual(self.processor.call_args.args[2], self.binding)
        self.verifier.assert_called_once_with("valid", AUDIENCE)

    def test_diagnostic_log_distinguishes_app_403_without_leaking_secrets(self):
        captured = io.StringIO()
        secret_token = "private.jwt.test-value"
        with redirect_stderr(captured):
            status, result = run_request(
                self.app, token=secret_token, job=JOB + "-unknown"
            )
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(result["error"], "JOB_NOT_ALLOWLISTED")
        logs = [json.loads(line) for line in captured.getvalue().splitlines()]
        self.assertEqual(logs[0]["event"], "P1_JOB_HEADER_DIAGNOSTIC")
        self.assertEqual(logs[0]["jobHeaderForm"], "OTHER_FULL_RESOURCE")
        self.assertEqual(logs[1], {
            "event": "P1_INGRESS_RESULT",
            "severity": "WARNING",
            "httpStatus": 403,
            "reason": "JOB_NOT_ALLOWLISTED",
        })
        self.assertNotIn(secret_token, captured.getvalue())
        self.assertNotIn(CALLER, captured.getvalue())
        self.assertNotIn(JOB, captured.getvalue())

    def test_job_header_diagnostic_is_classified_without_leaking_values(self):
        cases = [
            ("", "MISSING"),
            (JOB.rsplit("/", 1)[-1], "SHORT_EXPECTED_ID"),
            (JOB + "-unexpected", "OTHER_FULL_RESOURCE"),
            ("other-job", "OTHER_SHORT"),
            ("/not/a/job", "OTHER_FORMAT"),
        ]
        for supplied, expected in cases:
            with self.subTest(expected=expected):
                secret_token = "sensitive.jwt.payload"
                captured = io.StringIO()
                with redirect_stderr(captured):
                    status, response = run_request(
                        self.app, token=secret_token, job=supplied,
                        extra_headers={"HTTP_X_CLOUDSCHEDULER": "true"}
                    )
                self.assertEqual(status, "403 Forbidden")
                self.assertEqual(response, {"error": "JOB_NOT_ALLOWLISTED"})
                logs = [json.loads(line) for line in captured.getvalue().splitlines()]
                self.assertEqual(len(logs), 2)
                self.assertEqual(logs[0]["event"], "P1_JOB_HEADER_DIAGNOSTIC")
                self.assertEqual(logs[0]["jobHeaderForm"], expected)
                self.assertTrue(logs[0]["schedulerMarkerPresent"])
                self.assertTrue(logs[0]["scheduleHeaderPresent"])
                self.assertFalse(logs[0]["alternateJobHeaderPresent"])
                self.assertEqual(logs[1]["reason"], "JOB_NOT_ALLOWLISTED")
                self.assertNotIn(secret_token, captured.getvalue())
                self.assertNotIn(CALLER, captured.getvalue())
                self.assertNotIn(JOB, captured.getvalue())
                self.assertNotIn(supplied, captured.getvalue())

    def test_diagnostic_log_discriminates_caller_and_expired_slot(self):
        self.verifier.return_value = {
            **self.verifier.return_value,
            "email": "different@test-project.iam.gserviceaccount.com",
        }
        captured = io.StringIO()
        with redirect_stderr(captured):
            status, _ = run_request(self.app)
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(json.loads(captured.getvalue())["reason"], "CALLER_NOT_AUTHORIZED")

        self.verifier.return_value = {
            **self.verifier.return_value, "email": CALLER,
        }
        expired = create_app(
            bindings={JOB: self.binding}, audience=AUDIENCE,
            processor=self.processor, verifier=self.verifier,
            clock=lambda: datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc),
        )
        captured = io.StringIO()
        with redirect_stderr(captured):
            status, _ = run_request(expired)
        self.assertEqual(status, "409 Conflict")
        entry = json.loads(captured.getvalue())
        self.assertEqual((entry["httpStatus"], entry["reason"]),
                         (409, "SCHEDULE_EXPIRED"))
        self.processor.assert_not_called()

    def test_diagnostic_log_marks_success_without_echoing_processor_payload(self):
        secret = "do-not-emit-acquisition-payload"
        self.processor.return_value = {"status": "CREATED", "secret": secret}
        captured = io.StringIO()
        with redirect_stderr(captured):
            status, _ = run_request(self.app)
        self.assertEqual(status, "200 OK")
        entry = json.loads(captured.getvalue())
        self.assertEqual((entry["httpStatus"], entry["reason"]), (200, "ACCEPTED"))
        self.assertNotIn(secret, captured.getvalue())

    def test_missing_or_malformed_bearer_is_rejected(self):
        for token in ("", "bad token"):
            with self.subTest(token=token):
                status, _ = run_request(self.app, token=token)
                self.assertEqual(status, "401 Unauthorized")
        self.processor.assert_not_called()

    def test_bad_signature_or_token_verification_failure_is_rejected(self):
        self.verifier.side_effect = ValueError("bad signature")
        status, _ = run_request(self.app)
        self.assertEqual(status, "401 Unauthorized")
        self.processor.assert_not_called()

    def test_wrong_issuer_audience_or_email_claim_is_rejected(self):
        valid_claims = dict(self.verifier.return_value)
        for key, value in (
            ("iss", "https://attacker.example"),
            ("aud", "https://other.run.app"),
            ("email", "other@test-project.iam.gserviceaccount.com"),
            ("email_verified", False),
        ):
            self.verifier.return_value = {**valid_claims, key: value}
            with self.subTest(claim=key):
                status, _ = run_request(self.app)
                self.assertEqual(status, "403 Forbidden")
        self.processor.assert_not_called()

    def test_job_name_is_exactly_allowlisted(self):
        status, _ = run_request(self.app, job=JOB + "-spoof")
        self.assertEqual(status, "403 Forbidden")
        self.processor.assert_not_called()

    def test_wrong_offset_slot_weekend_and_future_schedule_are_rejected(self):
        cases = (
            "2026-10-26T22:53:00Z",  # offset maps away from 08:00
            "2026-10-23T22:47:00Z",  # Saturday 08:00 is outside this weekday binding
            "2026-10-27T22:47:00Z",  # future scheduled event
            "2026-10-26T02:47:00Z",  # valid 12:00 time sent with the 08:00 job name
            "2026-10-26T22:47:01Z",  # seconds are not allowed
        )
        for schedule in cases:
            with self.subTest(schedule=schedule):
                status, _ = run_request(self.app, schedule=schedule)
                self.assertEqual(status, "400 Bad Request")
        self.processor.assert_not_called()

    def test_expired_slot_does_not_write(self):
        app = create_app(
            bindings={JOB: self.binding}, audience=AUDIENCE,
            processor=self.processor, verifier=self.verifier,
            clock=lambda: datetime(2026, 10, 27, 23, 00, tzinfo=timezone.utc),
        )
        status, _ = run_request(app)
        self.assertEqual(status, "409 Conflict")
        self.processor.assert_not_called()

    def test_scheduler_body_is_fixed_and_cannot_supply_report_identity_or_data(self):
        for body in (
            {"schemaVersion": 1, "trigger": "P1_SHADOW", "reportId": "2026-10-27_08-00"},
            {"schemaVersion": 1, "trigger": "P1_SHADOW", "payload": {"close": 999}},
        ):
            with self.subTest(body=body):
                status, _ = run_request(self.app, body=body)
                self.assertEqual(status, "400 Bad Request")
        self.processor.assert_not_called()

    def test_content_type_length_and_method_are_checked(self):
        for kwargs, expected in (
            ({"method": "GET"}, "405 Method Not Allowed"),
            ({"content_type": "text/plain"}, "400 Bad Request"),
            ({"extra_headers": {"CONTENT_LENGTH": "999999999"}}, "413 Payload Too Large"),
            ({"extra_headers": {"CONTENT_LENGTH": "abc"}}, "400 Bad Request"),
        ):
            with self.subTest(kwargs=kwargs):
                status, _ = run_request(self.app, **kwargs)
                self.assertEqual(status, expected)
        self.processor.assert_not_called()

    def test_processor_failure_is_generic_and_does_not_leak_exception(self):
        self.processor.side_effect = RuntimeError("secret details")
        status, result = run_request(self.app)
        self.assertEqual(status, "500 Internal Server Error")
        self.assertEqual(result, {"error": "PROCESSING_FAILED"})

    def test_service_factory_defaults_storage_off_and_never_constructs_client(self):
        env = {
            "P1_OIDC_AUDIENCE": AUDIENCE,
            "P1_SCHEDULER_BINDINGS_JSON": json.dumps([{
                "job_name": JOB, "service_account_email": CALLER,
                "attempt_minutes": 13, "target_slot": "08:00",
            }]),
        }
        factory = Mock(side_effect=AssertionError("storage client must remain lazy and OFF"))
        app = build_app(env, storage_client_factory=factory, clock=lambda: NOW, verifier=self.verifier)
        status, result = run_request(app)
        self.assertEqual(status, "200 OK")
        self.assertEqual(result["status"], "DISABLED")
        factory.assert_not_called()

    def test_enabled_service_requires_bucket_and_acquisition_provider(self):
        base = {
            "P1_OIDC_AUDIENCE": AUDIENCE,
            "P1_SCHEDULER_BINDINGS_JSON": json.dumps([{
                "job_name": JOB, "service_account_email": CALLER,
                "attempt_minutes": 13, "target_slot": "08:00",
            }]),
            "SHADOW_STORAGE_ENABLED": "true",
        }
        with self.assertRaisesRegex(RuntimeError, "P1_GCS_BUCKET"):
            build_app(base, storage_client_factory=Mock())
        with self.assertRaisesRegex(RuntimeError, "P1_ACQUISITION_PROVIDER"):
            build_app({**base, "P1_GCS_BUCKET": "p1-test-bucket"},
                      storage_client_factory=Mock(), acquisition_provider=None)

    def test_binding_config_requires_unique_callers_and_only_three_attempts(self):
        entries = [
            {"job_name": JOB, "service_account_email": CALLER,
             "attempt_minutes": 13, "target_slot": "08:00"},
            {"job_name": JOB + "-2",
             "service_account_email": "p1-scheduler-2@test-project.iam.gserviceaccount.com",
             "attempt_minutes": 7, "target_slot": "08:00"},
        ]
        self.assertEqual(len(single_binding_map(entries)), 2)
        entries[1]["service_account_email"] = CALLER
        with self.assertRaisesRegex(ValueError, "UNIQUE"):
            single_binding_map(entries)
        entries[1]["service_account_email"] = "p1-scheduler-2@test-project.iam.gserviceaccount.com"
        entries[1]["attempt_minutes"] = 0
        with self.assertRaises(ValueError):
            single_binding_map(entries)


class SchedulerAttemptEvidenceTests(unittest.TestCase):
    def test_three_attempts_and_duplicate_or_conflicting_redelivery(self):
        target = datetime.fromisoformat("2026-10-27T08:00:00+09:00")
        identity = ReportIdentity("2026-10-27_08-00", target, "ACTIVE")
        current = [target - timedelta(minutes=13)]
        store = FakeStorage(lambda: current[0])
        coordinator = JobCoordinator(EvidenceWriter(store, lambda: current[0]), enabled=True)

        first = coordinator.run(identity, b"snapshot-at-t13", attempt_minutes=13)
        duplicate = coordinator.run(identity, b"snapshot-at-t13", attempt_minutes=13)
        current[0] = target - timedelta(minutes=7)
        second = coordinator.run(identity, b"snapshot-at-t7", attempt_minutes=7)
        current[0] = target - timedelta(minutes=3)
        third = coordinator.run(identity, b"snapshot-at-t3", attempt_minutes=3)
        before_conflict = set(store._objects)
        conflict = coordinator.run(identity, b"changed-t7-redelivery", attempt_minutes=7)

        self.assertEqual([first["status"], duplicate["status"], second["status"], third["status"]],
                         ["CREATED", "NO_OP", "CREATED", "CREATED"])
        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertEqual(store.read("shadow/2026-10-27_08-00/attempts/t-13/evidence").data,
                         b"snapshot-at-t13")
        self.assertEqual(store.read("shadow/2026-10-27_08-00/attempts/t-7/evidence").data,
                         b"snapshot-at-t7")
        self.assertEqual(store.read("shadow/2026-10-27_08-00/attempts/t-3/evidence").data,
                         b"snapshot-at-t3")
        self.assertEqual(set(store._objects), before_conflict)
        self.assertEqual(len(store._objects), 6)

class FixtureProviderTests(unittest.TestCase):
    def test_fixture_provider_is_identity_bound_and_not_scheduler_payload(self):
        from scripts.p1_trial_fixture_provider import acquire
        identity = ReportIdentity(
            "2026-10-27_08-00",
            datetime.fromisoformat("2026-10-27T08:00:00+09:00"),
            "ACTIVE",
        )
        binding = SchedulerBinding(JOB, CALLER, 13, "08:00")
        first = acquire(identity, binding, SCHEDULER_TRIGGER_BODY)
        second = acquire(identity, binding, SCHEDULER_TRIGGER_BODY)
        self.assertEqual(first, second)
        self.assertNotEqual(first, SCHEDULER_TRIGGER_BODY)
        self.assertIn(b'"kind":"P1_TEST_FIXTURE"', first)
        self.assertIn(b'"source":"fixture-not-market-data"', first)
        self.assertIn(identity.report_id.encode(), first)
        self.assertIn(b'"attemptMinutes":13', first)
        with self.assertRaisesRegex(ValueError, "INVALID_SCHEDULER_TRIGGER"):
            acquire(identity, binding, b'{"market":"payload"}')


if __name__ == "__main__":
    unittest.main()
