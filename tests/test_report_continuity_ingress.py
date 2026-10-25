import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from scripts.report_continuity_ingress import (
    SchedulerBinding, create_app, single_binding_map,
)
from scripts.run_report_continuity_service import build_app

AUDIENCE = "https://p1-shadow-test.run.app"
JOB = "projects/test-project/locations/asia-northeast1/jobs/slot-0800-t13"
CALLER = "p1-scheduler-0800-t13@test-project.iam.gserviceaccount.com"
NOW = datetime(2026, 10, 26, 22, 48, tzinfo=timezone.utc)  # Tuesday 07:48 JST
SCHEDULE = "2026-10-26T22:47:00Z"  # T-13 for Tuesday 08:00 JST


def run_request(app, *, token="valid", job=JOB, schedule=SCHEDULE, body=None,
                method="POST", content_type="application/json", extra_headers=None):
    raw = json.dumps(body if body is not None else {"reportId": "2026-10-27_08-00"}).encode()
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
        self.app = create_app(
            bindings={JOB: SchedulerBinding(JOB, CALLER, 13, "08:00")},
            audience=AUDIENCE, processor=self.processor, verifier=self.verifier,
            clock=lambda: NOW,
        )

    def test_valid_oidc_scheduler_request_reaches_shadow_processor(self):
        status, result = run_request(self.app)
        self.assertEqual(status, "200 OK")
        self.assertEqual(result["status"], "CREATED")
        self.assertEqual(self.processor.call_args.args[0].report_id, "2026-10-27_08-00")
        self.verifier.assert_called_once_with("valid", AUDIENCE)

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
            claims = dict(valid_claims)
            claims[key] = value
            self.verifier.return_value = claims
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
            "2026-10-26T22:53:00Z",  # maps to 08:06, invalid target slot
            "2026-10-23T22:47:00Z",  # Saturday 08:00 is outside this weekday binding
            "2026-10-27T22:47:00Z",  # future scheduled event
            "2026-10-26T02:47:00Z",  # valid 12:00 schedule for the wrong job name
            "2026-10-26T22:47:01Z",  # seconds are not allowed
        )
        for schedule in cases:
            with self.subTest(schedule=schedule):
                status, _ = run_request(self.app, schedule=schedule)
                self.assertEqual(status, "400 Bad Request")
        self.processor.assert_not_called()

    def test_expired_slot_does_not_write(self):
        app = create_app(
            bindings={JOB: SchedulerBinding(JOB, CALLER, 13, "08:00")},
            audience=AUDIENCE, processor=self.processor, verifier=self.verifier,
            clock=lambda: datetime(2026, 10, 27, 23, 00, tzinfo=timezone.utc),
        )
        status, _ = run_request(app)
        self.assertEqual(status, "409 Conflict")
        self.processor.assert_not_called()

    def test_report_identity_must_match_body(self):
        status, _ = run_request(self.app, body={"reportId": "2026-10-27_12-00"})
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
        status, result = run_request(app, body={"reportId": "2026-10-27_08-00"})
        self.assertEqual(status, "200 OK")
        self.assertEqual(result["status"], "DISABLED")
        factory.assert_not_called()

    def test_enabled_service_requires_bucket_name(self):
        env = {
            "P1_OIDC_AUDIENCE": AUDIENCE,
            "P1_SCHEDULER_BINDINGS_JSON": json.dumps([{
                "job_name": JOB, "service_account_email": CALLER,
                "attempt_minutes": 13, "target_slot": "08:00",
            }]),
            "SHADOW_STORAGE_ENABLED": "true",
        }
        with self.assertRaisesRegex(RuntimeError, "P1_GCS_BUCKET"):
            build_app(env, storage_client_factory=Mock())

    def test_binding_config_requires_unique_callers_and_known_attempts(self):
        entries = [
            {"job_name": JOB, "service_account_email": CALLER, "attempt_minutes": 13, "target_slot": "08:00"},
            {"job_name": JOB + "-2",
             "service_account_email": "p1-scheduler-2@test-project.iam.gserviceaccount.com",
             "attempt_minutes": 7, "target_slot": "08:00"},
        ]
        self.assertEqual(len(single_binding_map(entries)), 2)
        entries[1]["service_account_email"] = CALLER
        with self.assertRaisesRegex(ValueError, "UNIQUE"):
            single_binding_map(entries)
        entries[1]["attempt_minutes"] = True
        with self.assertRaises(ValueError):
            single_binding_map(entries)


if __name__ == "__main__":
    unittest.main()
